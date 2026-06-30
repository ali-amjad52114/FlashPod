"""Bright Data SERP API client — turns a free-text query into supplier offers.

The vision LLM emits variable line items ({type, count, description}), so pricing is driven by
a search string, not a fixed SKU list. One Google Shopping query (udm=28) returns offers from
many merchants at once, which is exactly the multi-supplier "compare options" view we want.

API (https://docs.brightdata.com/scraping-automation/serp-api):
    POST https://api.brightdata.com/request
    Authorization: Bearer <BRIGHTDATA_API_KEY>
    body: { "zone": <SERP_ZONE>, "url": <google url with udm=28 & brd_json=1>, "format": "raw" }

We do NOT filter offers here — every priced result is returned (sorted cheapest-first for
display). Selection/headline price is the caller's concern.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import requests

API_URL = "https://api.brightdata.com/request"
CACHE_DIR = Path(__file__).parent / ".cache"
REQUEST_TIMEOUT = 60

# Defensive: the parsed Shopping JSON keys vary; check these in order.
_RESULT_KEYS = ("shopping", "shopping_results", "products", "organic", "results")
_PRICE_KEYS = ("price", "extracted_price", "current_price", "offer_price")
_SELLER_KEYS = ("shop", "source", "seller", "merchant", "store")
_LINK_KEYS = ("link", "url", "product_link", "href")
_STOCK_KEYS = ("availability", "in_stock", "stock")


@dataclass(frozen=True)
class Offer:
    """One supplier's listing for a query."""

    supplier: str
    price: float
    url: str = ""
    in_stock: bool = True
    title: str = ""


class BrightDataError(RuntimeError):
    """SERP request failed or credentials are missing."""


def credentials() -> tuple[str, str]:
    token = os.environ.get("BRIGHTDATA_API_KEY")
    zone = os.environ.get("BRIGHTDATA_SERP_ZONE", "serp_api1")
    if not token:
        raise BrightDataError(
            "BRIGHTDATA_API_KEY not set. Add it to .env "
            "(and BRIGHTDATA_SERP_ZONE if your zone isn't 'serp_api1')."
        )
    return token, zone


def _shopping_url(query: str) -> str:
    # udm=28 -> Shopping, brd_json=1 -> parsed JSON, gl/hl pin US English pricing.
    return f"https://www.google.com/search?q={quote_plus(query)}&udm=28&brd_json=1&gl=us&hl=en"


def fetch_shopping(query: str, *, dump_raw: bool = False) -> dict:
    """Run one Google Shopping query through the Bright Data SERP API -> parsed JSON dict."""
    token, zone = credentials()
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
    except ValueError as exc:
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
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if not isinstance(value, str):
        return None
    match = re.search(r"\d[\d,]*\.?\d*", value.replace(",", ""))
    return round(float(match.group()), 2) if match else None


def _in_stock(value) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    return "out" not in str(value).lower()


def parse_offers(data: dict) -> list[Offer]:
    """Every priced merchant offer in the parsed Shopping JSON, sorted cheapest-first.

    No filtering beyond "must have a parseable price" — a listing with no price can't be
    priced. Sorting is presentation only; nothing is dropped.
    """
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
    return sorted(offers, key=lambda o: o.price)


def scrape_query(query: str, *, dump_raw: bool = False) -> list[Offer]:
    """All supplier offers for one query (empty list if the scrape yields nothing)."""
    return parse_offers(fetch_shopping(query, dump_raw=dump_raw))
