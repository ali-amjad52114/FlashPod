"""Overlay live Bright Data prices onto the worker's priced items.

The Runpod worker counts symbols and prices them with a built-in static
``PRICE_MAP``. When the Bright Data pricing service is wired in, the backend
overlays live unit prices on top of that result: it keeps the worker's
quantities + boxes (the traceability data) and only swaps the money.

Each repriced item carries its provenance (``price_source``, ``source_url``,
``vendor``) so the UI/proposal can show *where* a price came from — consistent
with FlashPod's "every number links back" theme.
"""

from datetime import datetime

from .brightdata_client import PriceQuote


def apply_live_prices(
    priced_items: list[dict],
    quotes: dict[str, PriceQuote],
) -> tuple[list[dict], bool]:
    """Return ``(items, repriced)`` with live unit prices applied where available.

    Items without a live quote keep the worker's price and are tagged
    ``price_source="fallback"``. Quantities, labels, and boxes are never touched.
    """
    items: list[dict] = []
    repriced = False

    for item in priced_items:
        new_item = dict(item)
        quote = quotes.get(item.get("type"))
        if quote is not None:
            new_item["unit_price"] = quote.unit_price
            new_item["total"] = round(item.get("quantity", 0) * quote.unit_price, 2)
            new_item["price_source"] = "brightdata"
            if quote.vendor:
                new_item["vendor"] = quote.vendor
            if quote.source_url:
                new_item["source_url"] = quote.source_url
            if quote.matched_title:
                new_item["matched_title"] = quote.matched_title
            repriced = True
        else:
            new_item.setdefault("price_source", "fallback")
        items.append(new_item)

    return items, repriced


def build_proposal_text(project_name: str, priced_items: list[dict]) -> str:
    """Rebuild the formatted proposal text from priced items.

    Mirrors the worker's proposal layout so totals stay consistent after a
    reprice. A ``*`` next to the unit price marks a live Bright Data price.
    """
    lines = [
        f"FlashPod Electrical Proposal — {project_name}",
        f"Date: {datetime.now():%Y-%m-%d}",
        "",
        f"{'Item':<20}{'Qty':>6}{'Unit':>12}{'Total':>14}",
        "-" * 52,
    ]

    subtotal = 0.0
    has_live = False
    for it in priced_items:
        label = str(it.get("label", it.get("type", "?")))
        qty = it.get("quantity", 0)
        unit_price = float(it.get("unit_price", 0.0))
        total = float(it.get("total", 0.0))
        subtotal += total
        live = it.get("price_source") == "brightdata"
        has_live = has_live or live
        unit = f"{unit_price:.2f}{'*' if live else ' '}"
        lines.append(f"{label:<20}{qty:>6}{unit:>12}{total:>14.2f}")

    lines.append("-" * 52)
    lines.append(f"{'SUBTOTAL':<38}{round(subtotal, 2):>14.2f}")
    if has_live:
        lines.append("")
        lines.append("* live market price via Bright Data")

    return "\n".join(lines)
