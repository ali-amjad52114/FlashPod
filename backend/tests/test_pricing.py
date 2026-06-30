"""Tests for pricing.py — apply_live_prices() and build_proposal_text()."""

import pytest

from app.services.brightdata_client import PriceQuote
from app.services.pricing import apply_live_prices, build_proposal_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ITEMS = [
    {
        "type": "duplex_outlet",
        "label": "Duplex Outlet",
        "quantity": 10,
        "unit_price": 4.25,
        "total": 42.50,
        "boxes": [[1, 2, 3, 4], [5, 6, 7, 8]],
    },
    {
        "type": "gfci_outlet",
        "label": "GFCI Outlet",
        "quantity": 5,
        "unit_price": 18.50,
        "total": 92.50,
        "boxes": [[9, 10, 11, 12]],
    },
]

FULL_QUOTES = {
    "duplex_outlet": PriceQuote("duplex_outlet", 5.00, vendor="Home Depot", source_url="https://hd.com/1"),
    "gfci_outlet": PriceQuote("gfci_outlet", 20.00, vendor="Grainger"),
}


# ---------------------------------------------------------------------------
# apply_live_prices
# ---------------------------------------------------------------------------

def test_full_coverage_all_items_tagged_brightdata():
    items, repriced = apply_live_prices(ITEMS, FULL_QUOTES)
    assert repriced is True
    for item in items:
        assert item["price_source"] == "brightdata", f"{item['type']} should be 'brightdata'"


def test_full_coverage_prices_updated():
    items, _ = apply_live_prices(ITEMS, FULL_QUOTES)
    outlet = next(i for i in items if i["type"] == "duplex_outlet")
    gfci = next(i for i in items if i["type"] == "gfci_outlet")
    assert outlet["unit_price"] == 5.00
    assert outlet["total"] == 50.00  # 10 * 5.00
    assert gfci["unit_price"] == 20.00
    assert gfci["total"] == 100.00  # 5 * 20.00


def test_full_coverage_vendor_and_source_url_attached():
    items, _ = apply_live_prices(ITEMS, FULL_QUOTES)
    outlet = next(i for i in items if i["type"] == "duplex_outlet")
    assert outlet["vendor"] == "Home Depot"
    assert outlet["source_url"] == "https://hd.com/1"


def test_full_coverage_boxes_and_quantity_preserved():
    """Traceability data (boxes) and counts must never be touched."""
    items, _ = apply_live_prices(ITEMS, FULL_QUOTES)
    outlet = next(i for i in items if i["type"] == "duplex_outlet")
    assert outlet["quantity"] == 10
    assert outlet["boxes"] == [[1, 2, 3, 4], [5, 6, 7, 8]]


def test_partial_coverage_mix_of_sources():
    partial_quotes = {"duplex_outlet": PriceQuote("duplex_outlet", 5.00)}
    items, repriced = apply_live_prices(ITEMS, partial_quotes)

    assert repriced is True
    outlet = next(i for i in items if i["type"] == "duplex_outlet")
    gfci = next(i for i in items if i["type"] == "gfci_outlet")

    assert outlet["price_source"] == "brightdata"
    assert outlet["unit_price"] == 5.00

    assert gfci["price_source"] == "fallback"
    assert gfci["unit_price"] == 18.50  # worker's original price kept


def test_partial_coverage_fallback_total_unchanged():
    partial_quotes = {"duplex_outlet": PriceQuote("duplex_outlet", 5.00)}
    items, _ = apply_live_prices(ITEMS, partial_quotes)
    gfci = next(i for i in items if i["type"] == "gfci_outlet")
    assert gfci["total"] == 92.50


def test_zero_coverage_all_items_tagged_fallback():
    items, repriced = apply_live_prices(ITEMS, {})
    assert repriced is False
    for item in items:
        assert item["price_source"] == "fallback"


def test_zero_coverage_prices_unchanged():
    items, _ = apply_live_prices(ITEMS, {})
    outlet = next(i for i in items if i["type"] == "duplex_outlet")
    assert outlet["unit_price"] == 4.25
    assert outlet["total"] == 42.50


def test_apply_does_not_mutate_original_list():
    """apply_live_prices must return new item dicts and not mutate the input."""
    original_price = ITEMS[0]["unit_price"]
    apply_live_prices(ITEMS, FULL_QUOTES)
    assert ITEMS[0]["unit_price"] == original_price
    assert "price_source" not in ITEMS[0]


def test_quotes_with_no_matching_sym_types():
    """Quotes that don't match any priced item → repriced=False, all fallback."""
    unrelated_quotes = {"panel": PriceQuote("panel", 320.00)}
    items, repriced = apply_live_prices(ITEMS, unrelated_quotes)
    assert repriced is False
    for item in items:
        assert item["price_source"] == "fallback"


def test_empty_priced_items_returns_empty():
    items, repriced = apply_live_prices([], FULL_QUOTES)
    assert items == []
    assert repriced is False


# ---------------------------------------------------------------------------
# build_proposal_text
# ---------------------------------------------------------------------------

def test_proposal_includes_project_name():
    text = build_proposal_text("Office Reno", ITEMS)
    assert "Office Reno" in text


def test_proposal_live_price_has_asterisk():
    live_items = [
        {"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 5,
         "unit_price": 5.00, "total": 25.00, "price_source": "brightdata"},
    ]
    text = build_proposal_text("Test", live_items)
    assert "*" in text
    assert "live market price via Bright Data" in text


def test_proposal_fallback_price_has_no_asterisk():
    fallback_items = [
        {"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 5,
         "unit_price": 4.25, "total": 21.25, "price_source": "fallback"},
    ]
    text = build_proposal_text("Test", fallback_items)
    assert "live market price via Bright Data" not in text


def test_proposal_manual_price_has_no_asterisk():
    manual_items = [
        {"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 5,
         "unit_price": 4.25, "total": 21.25, "price_source": "manual"},
    ]
    text = build_proposal_text("Test", manual_items)
    assert "live market price via Bright Data" not in text


def test_proposal_subtotal_is_correct():
    mixed_items = [
        {"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 5,
         "unit_price": 4.00, "total": 20.00, "price_source": "fallback"},
        {"type": "switch", "label": "Switch", "quantity": 3,
         "unit_price": 3.00, "total": 9.00, "price_source": "fallback"},
    ]
    text = build_proposal_text("Test", mixed_items)
    assert "29.00" in text


def test_proposal_mixed_sources_asterisk_only_on_live():
    mixed_items = [
        {"type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 5,
         "unit_price": 5.00, "total": 25.00, "price_source": "brightdata"},
        {"type": "switch", "label": "Switch", "quantity": 3,
         "unit_price": 3.25, "total": 9.75, "price_source": "fallback"},
    ]
    text = build_proposal_text("Test", mixed_items)
    # asterisk appears (because one item is live)
    assert "*" in text
    assert "live market price via Bright Data" in text
