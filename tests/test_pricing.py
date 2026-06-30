"""Unit tests for the pricing core — offer selection, catalog assembly, pricebook, embedding.

All network-free: the Bright Data scraper's parsing is tested against canned dicts, never a
live request.
"""
import json

import pytest

from pricing import build_catalog
from pricing.catalog import (
    Offer,
    assemble_catalog,
    build_catalog_item,
    build_pricebook,
    load_catalog,
    select_best_offer,
)
from pricing.embed_pricebook import inject, render_literal
from pricing.scraper import _to_price, parse_offers
from pricing.symbol_sku import SKU_BY_TYPE, SKU_SPECS


# --- select_best_offer -------------------------------------------------------
def test_picks_cheapest_in_stock():
    offers = [
        Offer("Grainger", 5.10, in_stock=True),
        Offer("Home Depot", 4.25, in_stock=True),
        Offer("Lowe's", 4.80, in_stock=True),
    ]
    assert select_best_offer(offers).supplier == "Home Depot"


def test_ignores_out_of_stock_even_if_cheaper():
    offers = [
        Offer("CheapButGone", 1.00, in_stock=False),
        Offer("Home Depot", 4.25, in_stock=True),
    ]
    assert select_best_offer(offers).supplier == "Home Depot"


def test_falls_back_to_cheapest_when_none_in_stock():
    offers = [Offer("A", 9.0, in_stock=False), Offer("B", 7.0, in_stock=False)]
    assert select_best_offer(offers).supplier == "B"


def test_tie_breaks_toward_preferred_supplier():
    offers = [Offer("Random Seller", 4.25), Offer("Home Depot", 4.25)]
    assert select_best_offer(offers).supplier == "Home Depot"


def test_empty_offers_returns_none():
    assert select_best_offer([]) is None


def test_floor_price_drops_junk_listings():
    # $0.01 "switch" is junk vs a $2.80 reference -> floor skips it, takes next cheapest.
    offers = [Offer("Junk", 0.01), Offer("Home Depot", 3.52), Offer("Grainger", 3.90)]
    assert select_best_offer(offers, floor_price=0.4 * 2.80).supplier == "Home Depot"


def test_floor_price_falls_back_if_it_removes_everything():
    offers = [Offer("A", 0.50), Offer("B", 0.60)]
    assert select_best_offer(offers, floor_price=100.0).price == 0.50


# --- catalog item / fallback -------------------------------------------------
def test_item_uses_fallback_when_no_offers():
    spec = SKU_BY_TYPE["duplex_outlet"]
    item = build_catalog_item(spec, [])
    assert item["offer_count"] == 0
    assert item["selected"]["price"] == spec.fallback_price
    assert "fallback" in item["selected"]["supplier"]


def test_assemble_catalog_covers_every_spec():
    catalog = assemble_catalog({}, generated_at="t", source="test")
    assert set(catalog["items"]) == {s.type for s in SKU_SPECS}


# --- pricebook ---------------------------------------------------------------
def test_build_pricebook_shape():
    catalog = assemble_catalog(
        {"switch": [Offer("Home Depot", 2.67, "https://hd", True)]},
        generated_at="t",
        source="test",
    )
    pb = build_pricebook(catalog)
    assert pb["switch"]["unit_price"] == 2.67
    assert pb["switch"]["supplier"] == "Home Depot"
    assert pb["switch"]["source_url"] == "https://hd"
    assert pb["switch"]["sku"] == SKU_BY_TYPE["switch"].sku


# --- scraper parsing (defensive, no network) ---------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [("$4.25", 4.25), ("1,234.50", 1234.50), (3, 3.0), ("Out of stock", None), (None, None)],
)
def test_to_price(raw, expected):
    assert _to_price(raw) == expected


def test_parse_offers_handles_key_variants():
    data = {
        "shopping": [
            {"title": "Leviton Outlet", "price": "$4.25", "source": "Home Depot", "link": "https://hd"},
            {"title": "Other", "extracted_price": 3.99, "seller": "Lowe's"},
            {"title": "No price here"},  # dropped
        ]
    }
    offers = parse_offers(data)
    assert len(offers) == 2
    assert {o.supplier for o in offers} == {"Home Depot", "Lowe's"}


def test_parse_offers_empty_on_garbage():
    assert parse_offers({"unexpected": "shape"}) == []


# --- embed round-trip --------------------------------------------------------
def test_render_literal_is_valid_python():
    pb = {"switch": {"label": "Switch", "unit_price": 2.67, "sku": "X",
                     "supplier": "Home Depot", "source_url": "https://hd", "unit": "each"}}
    literal = render_literal(pb, indent="")
    ns: dict = {}
    exec(literal, ns)  # noqa: S102 - generated code under test
    assert ns["EMBEDDED_PRICEBOOK"]["switch"]["unit_price"] == 2.67


def test_inject_is_idempotent(tmp_path):
    f = tmp_path / "w.py"
    f.write_text("a = 1\n    # >>> PRICEBOOK_START\n    old = {}\n    # <<< PRICEBOOK_END\nb = 2\n")
    literal = render_literal({"switch": {"label": "Switch", "unit_price": 2.67, "sku": "X",
                                         "supplier": "HD", "source_url": "", "unit": "each"}})
    inject(f, literal)
    once = f.read_text()
    inject(f, literal)
    assert f.read_text() == once
    assert "a = 1" in once and "b = 2" in once  # surrounding code preserved


# --- cached catalog sanity ---------------------------------------------------
def test_cached_catalog_is_complete_and_priced():
    catalog = load_catalog()
    assert set(catalog["items"]) == {s.type for s in SKU_SPECS}
    for item in catalog["items"].values():
        assert item["selected"]["price"] > 0
        assert item["sku"]


def test_build_catalog_does_not_clobber_when_scrape_returns_no_offers(monkeypatch, tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text('{"existing": true}\n')

    monkeypatch.setattr(build_catalog, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(build_catalog, "_credentials", lambda: ("token", "zone"))
    monkeypatch.setattr(build_catalog, "scrape_all", lambda: {s.type: [] for s in SKU_SPECS})

    with pytest.raises(SystemExit, match="no offers"):
        build_catalog.main()

    assert json.loads(catalog_path.read_text()) == {"existing": True}
