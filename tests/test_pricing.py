"""Unit tests for the dynamic pricing module — query building, offer parsing (no filtering),
caching, and line pricing. All network-free: scraping is monkeypatched.
"""
import json

import pytest

from pricing import pricing as pricing_mod
from pricing.pricing import PriceCache, build_query, fallback_unit_price, price_line_items
from pricing.scraper import Offer, parse_offers


# --- query building ----------------------------------------------------------
def test_query_prefers_description():
    assert build_query({"type": "X", "description": "General double power outlet"}).startswith(
        "General double power outlet"
    )


def test_query_applies_alias_for_known_type():
    q = build_query({"type": "DGPO Outlet", "description": "double power"})
    assert "receptacle" in q  # alias sharpener appended


def test_query_falls_back_to_type_without_description():
    assert build_query({"type": "TV Antenna"}) == "TV Antenna tv antenna coax wall outlet"


# --- offer parsing: nothing filtered, sorted cheapest-first ------------------
def test_parse_keeps_all_priced_offers_sorted():
    data = {"shopping": [
        {"title": "A", "price": "$9.00", "shop": "HD", "link": "x"},
        {"title": "B", "price": "$2.00", "shop": "Lowe's"},
        {"title": "C", "price": "$0.01", "shop": "Junk"},   # NOT filtered — kept
        {"title": "No price"},                               # only dropped: unpriceable
    ]}
    offers = parse_offers(data)
    assert [o.price for o in offers] == [0.01, 2.00, 9.00]   # all kept, cheapest-first


def test_parse_empty_on_garbage():
    assert parse_offers({"unexpected": "shape"}) == []


# --- fallback ----------------------------------------------------------------
@pytest.mark.parametrize("query,expected", [
    ("a gfci outlet", 16.0), ("single pole switch", 3.0), ("cat6 rj45 jack", 4.0),
    ("mystery thing", 5.0),
])
def test_fallback_unit_price(query, expected):
    assert fallback_unit_price(query) == expected


# --- price_line_items (scrape monkeypatched) ---------------------------------
def _fake_scrape(query, *, dump_raw=False):
    return [Offer("Cheap Co", 2.0, "u1", True, "t1"), Offer("Mid Co", 5.0, "u2", True, "t2")]


def test_prices_line_with_all_offers_and_cheapest_headline(monkeypatch):
    monkeypatch.setattr(pricing_mod, "scrape_query", _fake_scrape)
    priced = price_line_items(
        [{"type": "DGPO Outlet", "count": 107, "description": "double power outlet"}],
        use_cache=False,
    )
    line = priced[0]
    assert line["unit_price"] == 2.0          # cheapest as headline
    assert line["supplier"] == "Cheap Co"
    assert line["total"] == round(2.0 * 107, 2)
    assert line["offer_count"] == 2
    assert len(line["offers"]) == 2           # every offer attached


def test_falls_back_when_no_offers(monkeypatch):
    monkeypatch.setattr(pricing_mod, "scrape_query", lambda q, **k: [])
    line = price_line_items([{"type": "GFCI", "count": 3, "description": "gfci outlet"}],
                            use_cache=False)[0]
    assert line["source"] == "fallback"
    assert line["unit_price"] == 16.0         # keyword fallback
    assert line["total"] == 48.0


def test_cache_dedupes_identical_queries(monkeypatch, tmp_path):
    calls = []

    def counting_scrape(query, *, dump_raw=False):
        calls.append(query)
        return [Offer("S", 1.0)]

    monkeypatch.setattr(pricing_mod, "scrape_query", counting_scrape)
    cache = PriceCache(tmp_path / "c.json")
    items = [
        {"type": "Voice Outlet", "count": 48, "description": "CAT 6 cabling with RJ45 jack"},
        {"type": "Voice Fax Outlet", "count": 1, "description": "CAT 6 cabling with RJ45 jack"},
    ]
    price_line_items(items, cache=cache)
    assert len(calls) == 1                     # same query scraped once, second hit cache


def test_cache_persists_to_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(pricing_mod, "scrape_query", _fake_scrape)
    path = tmp_path / "c.json"
    price_line_items([{"type": "X", "description": "thing"}], cache=PriceCache(path))
    assert path.exists()
    reloaded = json.loads(path.read_text())
    assert any(len(v) == 2 for v in reloaded.values())   # offers persisted


# --- warm cache sanity -------------------------------------------------------
def test_committed_cache_loads():
    cache = PriceCache()  # pricing/price_cache.json
    # Should load without error; may be empty in a fresh checkout but must be valid JSON.
    assert isinstance(cache._data, dict)
