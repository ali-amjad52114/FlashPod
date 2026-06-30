"""Dynamic pricing — price the vision LLM's takeoff line items against live Bright Data offers.

Input is whatever the detector emits, per line:  {type, count, description}.  Types vary per
drawing, so there is no fixed catalog: each line's `description` (falling back to `type`) becomes
a Google Shopping query, and we keep EVERY returned offer. The headline `unit_price` defaults to
the cheapest offer purely so the proposal has a number — nothing is filtered out, and the full
`offers` list rides along for the compare UI.

Resilience: a file-backed cache keyed by query makes repeated runs instant and survives a flaky
network during the demo; a tiny keyword fallback covers the case where a scrape returns nothing.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .scraper import BrightDataError, Offer, scrape_query

CACHE_PATH = Path(__file__).parent / "price_cache.json"

# Optional query sharpeners for terse/region-specific detector labels -> better Shopping hits.
# Substring match on the lowercased type; purely to improve results, never required.
QUERY_ALIASES: dict[str, str] = {
    "dgpo": "double power outlet receptacle",
    "gpo": "power outlet receptacle",
    "data outlet": "cat6 rj45 data jack wall outlet",
    "voice": "rj45 voice phone jack wall outlet",
    "tv antenna": "tv antenna coax wall outlet",
}

# Last-resort per-keyword estimate when a scrape yields nothing (clearly flagged in output).
FALLBACK_PRICES: dict[str, float] = {
    "gfci": 16.0, "outlet": 3.0, "receptacle": 3.0, "switch": 3.0,
    "data": 4.0, "cat6": 4.0, "rj45": 4.0, "voice": 4.0,
    "antenna": 12.0, "light": 45.0, "panel": 140.0,
}
DEFAULT_FALLBACK_PRICE = 5.0


def build_query(item: dict) -> str:
    """Search string for a line item: description first, sharpened by an alias if one matches."""
    base = (item.get("description") or item.get("type") or "").strip()
    label = (item.get("type") or "").lower()
    for key, sharper in QUERY_ALIASES.items():
        if key in label or key in base.lower():
            return f"{base} {sharper}".strip()
    return base


def fallback_unit_price(query: str) -> float:
    q = query.lower()
    for keyword, price in FALLBACK_PRICES.items():
        if keyword in q:
            return price
    return DEFAULT_FALLBACK_PRICE


class PriceCache:
    """Query -> offers, persisted to JSON so the demo runs off a warm cache."""

    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        self._data: dict[str, list[dict]] = {}
        if path.exists():
            self._data = json.loads(path.read_text())

    def get(self, query: str) -> list[Offer] | None:
        raw = self._data.get(query)
        return [Offer(**o) for o in raw] if raw is not None else None

    def put(self, query: str, offers: list[Offer]) -> None:
        self._data[query] = [asdict(o) for o in offers]

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2) + "\n")


def price_line_items(
    items: list[dict],
    *,
    cache: PriceCache | None = None,
    use_cache: bool = True,
    dump_raw: bool = False,
) -> list[dict]:
    """Price each {type, count, description} line. Returns priced lines with ALL offers attached."""
    cache = cache if cache is not None else (PriceCache() if use_cache else None)
    priced: list[dict] = []

    for item in items:
        sym_type = item.get("type", "item")
        label = item.get("label") or item.get("type") or "Item"
        count = int(item.get("count", item.get("quantity", 1)))
        query = build_query(item)

        offers = cache.get(query) if cache else None
        source = "cache"
        if offers is None:
            try:
                offers = scrape_query(query, dump_raw=dump_raw)
                source = "serp"
                if cache is not None:
                    cache.put(query, offers)
            except BrightDataError:
                offers = []
                source = "error"

        best = offers[0] if offers else None  # offers are sorted cheapest-first
        if best is not None:
            unit_price, supplier, source_url = best.price, best.supplier, best.url
        else:
            unit_price = fallback_unit_price(query)
            supplier, source_url = "estimate (no live offer)", ""
            source = "fallback"

        priced.append({
            "type": sym_type,
            "label": label,
            "description": item.get("description", ""),
            "count": count,
            "query": query,
            "unit_price": unit_price,
            "supplier": supplier,
            "source_url": source_url,
            "total": round(unit_price * count, 2),
            "source": source,
            "offer_count": len(offers),
            "offers": [asdict(o) for o in offers],  # every offer, nothing filtered
        })

    if cache is not None:
        cache.save()
    return priced
