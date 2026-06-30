# DEPRECATED — pricing has moved into the Runpod worker (analyze_drawing calls
# Bright Data internally). This module is no longer called by the takeoff flow.
# Kept for reference; remove once worker-side integration is confirmed live.

"""Client for the Bright Data-backed material-pricing service.

Bright Data is FlashPod's **live pricing** layer: given a list of electrical
symbol types, the service scrapes/normalizes current supplier prices (Home Depot,
Grainger, etc.) and returns a unit price per type. See the README "Production"
table: ``Price | price_items() | Bright Data + normalization``.

A teammate owns the actual scraping service; this module is the backend adapter
that calls it. The contract is intentionally small and tolerant so it lines up
with whatever shape that service ships:

Request  (POST ``BRIGHTDATA_PRICING_URL``)::

    { "items": [ { "sym_type": "duplex_outlet", "label": "Duplex Outlet", "query": "..." } ] }

Response (either of these is accepted)::

    { "prices": [ { "sym_type": "duplex_outlet", "unit_price": 4.25,
                    "currency": "USD", "vendor": "Home Depot",
                    "source_url": "https://...", "matched_title": "..." } ] }
    # ...or a plain map:
    { "duplex_outlet": 4.25 }

Design rules:
  - **Never fail the takeoff because pricing is down.** Every error path returns an
    empty map; the caller then keeps the worker's fallback prices.
  - If ``BRIGHTDATA_PRICING_URL`` is unset, this is a no-op (returns ``{}``),
    so the backend runs out-of-the-box before the service is wired in.
"""

import logging
import math
import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# The teammate's pricing service endpoint. Unset => Bright Data pricing disabled.
BRIGHTDATA_PRICING_URL: str = os.getenv("BRIGHTDATA_PRICING_URL", "")
BRIGHTDATA_API_KEY: str = os.getenv("BRIGHTDATA_API_KEY", "")
# Pricing is non-critical, so keep the timeout short — we fall back fast.
TIMEOUT: float = float(os.getenv("BRIGHTDATA_TIMEOUT", "20"))


@dataclass
class PriceQuote:
    """A single live unit price for one symbol type."""

    sym_type: str
    unit_price: float
    currency: str = "USD"
    vendor: str | None = None
    source_url: str | None = None
    matched_title: str | None = None


def is_enabled() -> bool:
    """True when a pricing service URL is configured."""
    return bool(BRIGHTDATA_PRICING_URL)


async def fetch_unit_prices(items: list[dict]) -> dict[str, PriceQuote]:
    """Fetch live unit prices for the given symbol types.

    Args:
        items: list of dicts, each with at least ``sym_type`` and ``label``.
            An optional ``query`` overrides the search string the scraper uses.

    Returns:
        Mapping ``sym_type -> PriceQuote``. Empty when pricing is disabled or
        the service is unreachable (caller falls back to worker prices).
    """
    if not is_enabled() or not items:
        return {}

    request_items = [
        {
            "sym_type": it["sym_type"],
            "label": it.get("label") or it["sym_type"],
            "query": it.get("query") or it.get("label") or it["sym_type"],
        }
        for it in items
        if it.get("sym_type")
    ]
    if not request_items:
        return {}

    headers: dict[str, str] = {}
    if BRIGHTDATA_API_KEY:
        headers["Authorization"] = f"Bearer {BRIGHTDATA_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                BRIGHTDATA_PRICING_URL,
                json={"items": request_items},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        # ValueError covers a non-JSON body. Pricing is best-effort: log and fall back.
        logger.warning("Bright Data pricing unavailable, using fallback prices: %s", exc)
        return {}

    return _parse_prices(data)


def _parse_prices(data: object) -> dict[str, PriceQuote]:
    """Normalize the service response into ``sym_type -> PriceQuote``.

    Accepts both the structured ``{"prices": [...]}`` form and a plain
    ``{sym_type: price}`` map so the teammate's service can ship either.
    """
    quotes: dict[str, PriceQuote] = {}

    if isinstance(data, dict) and "prices" in data:
        rows = data.get("prices") or []
    elif isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        # Plain {sym_type: price} map.
        for sym_type, price in data.items():
            quote = _quote_from_scalar(sym_type, price)
            if quote:
                quotes[sym_type] = quote
        return quotes
    else:
        return quotes

    for row in rows:
        if not isinstance(row, dict):
            continue
        sym_type = row.get("sym_type") or row.get("type")
        price = row.get("unit_price", row.get("price"))
        if not sym_type or price is None:
            continue
        try:
            unit_price = float(price)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(unit_price) or unit_price <= 0:
            continue
        quotes[sym_type] = PriceQuote(
            sym_type=sym_type,
            unit_price=round(unit_price, 2),
            currency=row.get("currency", "USD"),
            vendor=row.get("vendor"),
            source_url=row.get("source_url") or row.get("url"),
            matched_title=row.get("matched_title") or row.get("title"),
        )

    return quotes


def _quote_from_scalar(sym_type: str, price: object) -> PriceQuote | None:
    try:
        unit_price = float(price)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(unit_price) or unit_price <= 0:
        return None
    return PriceQuote(sym_type=sym_type, unit_price=round(unit_price, 2))
