"""Bright Data SERP API client — pulls multi-supplier prices from Google Shopping.

One Google Shopping query returns offers from many merchants (Home Depot, Lowe's, Grainger,
Walmart, ...), so a single request per SKU gives us the "multiple suppliers" comparison.

API (grounded in https://docs.brightdata.com/scraping-automation/serp-api):
    POST https://api.brightdata.com/request
    Authorization: Bearer <BRIGHTDATA_API_KEY>
    body: { "zone": <SERP_ZONE>, "url": <google url>, "format": "raw" }
    - udm=28     -> Google Shopping results
    - brd_json=1 -> parsed JSON instead of raw HTML

Cost: ~$1.50 / 1,000 requests => a full 6-SKU catalog refresh is < $0.01.

The parsed Shopping JSON schema isn't fully documented, so offer parsing is defensive and
the first raw response is dumped to pricing/.cache/ to lock the real shape. Network + parsing
live here; pure selection/catalog logic lives in catalog.py.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import requests

from .catalog import Offer
from .symbol_sku import SKU_SPECS, SkuSpec

API_URL = "https://api.brightdata.com/request"
CACHE_DIR = Path(__file__).parent / ".cache"
REQUEST_TIMEOUT = 60  # SERP requests can be slow; one warm call per SKU.

# Keys the parsed Shopping JSON might use for the offer list / fields (defensive).
_RESULT_KEYS = ("shopping", "shopping_results", "products", "organic", "results")
_PRICE_KEYS = ("price", "extracted_price", "current_price", "offer_price")
_SELLER_KEYS = ("source", "seller", "merchant", "store", "shop")
_LINK_KEYS = ("link", "url", "product_link", "href")
_STOCK_KEYS = ("availability", "in_stock", "stock")


class BrightDataError(RuntimeError):
    """Raised when the SERP request fails or credentials are missing."""


def _credentials() -> tuple[str, str]:
    token = os.environ.get("BRIGHTDATA_API_KEY")
    zone = os.environ.get("BRIGHTDATA_SERP_ZONE", "serp_api")
    if not token:
        raise BrightDataError(
            "BRIGHTDATA_API_KEY not set. Add it to .env "
            "(and BRIGHTDATA_SERP_ZONE if your zone isn't named 'serp_api')."
        )
    return token, zone


def _shopping_url(query: str) -> str:
    # udm=28 -> Shopping, brd_json=1 -> parsed JSON, gl/hl pin US English pricing.
    return (
        "https://www.google.com/search?"
        f"q={quote_plus(query)}&udm=28&brd_json=1&gl=us&hl=en"
    )


def fetch_shopping(query: str, *, dump_raw: bool = True) -> dict:
    """Run one Google Shopping query through the Bright Data SERP API -> parsed JSON dict."""
    token, zone = _credentials()
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"zone": zone, "url": _shopping_url(query), "format": "raw"},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise BrightDataError(f"SERP request failed (HTTP {resp.status_code}): {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as exc:  # brd_json should yield JSON; surface anything else.
        raise BrightDataError(f"Expected JSON from SERP API, got: {resp.text[:300]}") from exc

    if dump_raw:
        CACHE_DIR.mkdir(exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "_", query.lower())[:50]
        (CACHE_DIR / f"raw_{safe}.json").write_text(json.dumps(data, indent=2))
    return data


def _first(d: dict, keys: tuple[str, ...]):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def _to_price(value) -> float | None:
    """'$4.25', '4.25', 1234 (cents?) -> float dollars. Returns None if unparseable."""
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if not isinstance(value, str):
        return None
    match = re.search(r"\d[\d,]*\.?\d*", value.replace(",", ""))
    return round(float(match.group()), 2) if match else None


def _in_stock(value) -> bool:
    if value is None:
        return True  # assume available unless told otherwise
    if isinstance(value, bool):
        return value
    return "out" not in str(value).lower()


def parse_offers(data: dict) -> list[Offer]:
    """Pull merchant offers out of the parsed Shopping JSON, defensively across key variants."""
    results = _first(data, _RESULT_KEYS) or []
    if not isinstance(results, list):
        return []

    offers: list[Offer] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        price = _to_price(_first(item, _PRICE_KEYS))
        if price is None or price <= 0:
            continue
        supplier = _first(item, _SELLER_KEYS) or item.get("title") or "Unknown"
        offers.append(
            Offer(
                supplier=str(supplier).strip(),
                price=price,
                url=str(_first(item, _LINK_KEYS) or ""),
                in_stock=_in_stock(_first(item, _STOCK_KEYS)),
                title=str(item.get("title") or ""),
            )
        )
    return offers


def scrape_sku(spec: SkuSpec, *, dump_raw: bool = True) -> list[Offer]:
    """Live multi-supplier offers for one SKU. Empty list if the scrape yields nothing."""
    return parse_offers(fetch_shopping(spec.search_query, dump_raw=dump_raw))


def scrape_all(specs: tuple[SkuSpec, ...] = SKU_SPECS) -> dict[str, list[Offer]]:
    """Scrape every SKU. One SKU failing doesn't sink the rest (it returns []) ."""
    out: dict[str, list[Offer]] = {}
    for spec in specs:
        try:
            out[spec.type] = scrape_sku(spec)
        except BrightDataError as exc:
            print(f"  ! {spec.type}: {exc}")
            out[spec.type] = []
    return out
