"""Cached catalog + offer selection — the pure (network-free) pricing core.

Pipeline:  scraped offers --assemble_catalog--> catalog.json (cached) --build_pricebook-->
           pricebook (what the worker uses to price a takeoff).

`select_best_offer` is the policy that turns N supplier offers into the one price we quote
(cheapest in-stock, with a light preference for known electrical suppliers on ties). Keeping
it here and side-effect-free makes it unit-testable without hitting the network.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .symbol_sku import SKU_BY_TYPE, SKU_SPECS, SkuSpec

CATALOG_PATH = Path(__file__).parent / "catalog.json"

# Light preference on price ties / for display ordering. Lowercase substring match.
PREFERRED_SUPPLIERS = ("home depot", "lowe", "grainger", "graybar", "platt", "menards")

# Ignore offers priced below this fraction of the SKU's researched reference price — they're
# almost always a different/lesser product or a junk listing (e.g. a $0.01 "switch"). Anchored
# to the reference price (domain knowledge), not the offer median, which bundles/multi-packs skew.
JUNK_FLOOR_RATIO = 0.4


@dataclass(frozen=True)
class Offer:
    """One supplier's price for a SKU."""

    supplier: str
    price: float
    url: str = ""
    in_stock: bool = True
    title: str = ""


def _supplier_rank(supplier: str) -> int:
    s = supplier.lower()
    for i, name in enumerate(PREFERRED_SUPPLIERS):
        if name in s:
            return i
    return len(PREFERRED_SUPPLIERS)


def select_best_offer(offers: list[Offer], floor_price: float = 0.0) -> Offer | None:
    """Cheapest in-stock offer at/above `floor_price`; ties break toward preferred suppliers.

    `floor_price` rejects junk/mismatch listings below a sane minimum (see JUNK_FLOOR_RATIO);
    pass 0 to disable. Falls back to cheapest overall if nothing is in-stock, and to the
    unfiltered pool if the floor would eliminate everything. None if no offers.
    """
    if not offers:
        return None
    pool = [o for o in offers if o.in_stock] or offers
    if floor_price > 0:
        pool = [o for o in pool if o.price >= floor_price] or pool
    return min(pool, key=lambda o: (o.price, _supplier_rank(o.supplier)))


def build_catalog_item(spec: SkuSpec, offers: list[Offer]) -> dict:
    """Assemble one catalog entry: the spec + every offer + the selected (quoted) offer."""
    ordered = sorted(offers, key=lambda o: (o.price, _supplier_rank(o.supplier)))
    best = select_best_offer(offers, floor_price=JUNK_FLOOR_RATIO * spec.fallback_price)
    selected = asdict(best) if best else {
        # No live offer -> quote the spec's fallback so the pipeline never stalls.
        "supplier": "list price (fallback)",
        "price": spec.fallback_price,
        "url": "",
        "in_stock": True,
        "title": spec.description,
    }
    return {
        "type": spec.type,
        "label": spec.label,
        "sku": spec.sku,
        "description": spec.description,
        "unit": spec.unit,
        "search_query": spec.search_query,
        "selected": selected,
        "offers": [asdict(o) for o in ordered],
        "offer_count": len(ordered),
    }


def assemble_catalog(scraped: dict[str, list[Offer]], *, generated_at: str, source: str) -> dict:
    """Turn {type: [offers]} into the full catalog.json structure."""
    return {
        "generated_at": generated_at,
        "source": source,
        "currency": "USD",
        "items": {
            spec.type: build_catalog_item(spec, scraped.get(spec.type, []))
            for spec in SKU_SPECS
        },
    }


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    """Load the cached catalog.json (raises if missing — run build_catalog.py first)."""
    if not path.exists():
        raise FileNotFoundError(f"No cached catalog at {path}. Run `python -m pricing.build_catalog`.")
    return json.loads(path.read_text())


def build_pricebook(catalog: dict) -> dict[str, dict]:
    """Reduce the catalog to the compact pricebook the takeoff worker prices from.

    type -> { label, unit_price, sku, supplier, source_url, unit, offer_count }
    """
    pricebook: dict[str, dict] = {}
    for sym_type, item in catalog.get("items", {}).items():
        spec = SKU_BY_TYPE.get(sym_type)
        selected = item.get("selected") or {}
        pricebook[sym_type] = {
            "label": item.get("label", sym_type.replace("_", " ").title()),
            "unit_price": float(selected.get("price", spec.fallback_price if spec else 0.0)),
            "sku": item.get("sku", ""),
            "supplier": selected.get("supplier", ""),
            "source_url": selected.get("url", ""),
            "unit": item.get("unit", "each"),
            "offer_count": item.get("offer_count", 0),
        }
    return pricebook
