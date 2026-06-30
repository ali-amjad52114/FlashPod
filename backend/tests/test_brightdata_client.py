"""Tests for brightdata_client.py.

Covers:
- _parse_prices: both response shapes, edge cases (zero/negative prices, malformed rows)
- fetch_unit_prices: unset-URL no-op, empty items, timeout, HTTP error, malformed JSON,
  structured {"prices":[...]} shape, plain {sym_type: price} map
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.brightdata_client import (
    PriceQuote,
    _parse_prices,
    fetch_unit_prices,
)


# ---------------------------------------------------------------------------
# _parse_prices — pure function, no mocking needed
# ---------------------------------------------------------------------------

def test_parse_prices_structured_shape():
    data = {
        "prices": [
            {
                "sym_type": "duplex_outlet",
                "unit_price": 4.25,
                "vendor": "Home Depot",
                "source_url": "https://homedepot.com/p/123",
                "matched_title": "15A Duplex Outlet",
            },
            {"sym_type": "gfci_outlet", "unit_price": 18.50},
        ]
    }
    result = _parse_prices(data)
    assert set(result.keys()) == {"duplex_outlet", "gfci_outlet"}
    assert result["duplex_outlet"].unit_price == 4.25
    assert result["duplex_outlet"].vendor == "Home Depot"
    assert result["duplex_outlet"].source_url == "https://homedepot.com/p/123"
    assert result["gfci_outlet"].unit_price == 18.50
    assert result["gfci_outlet"].vendor is None


def test_parse_prices_accepts_type_key_alias():
    """Some rows may use "type" instead of "sym_type"."""
    data = {"prices": [{"type": "switch", "unit_price": 3.25}]}
    result = _parse_prices(data)
    assert "switch" in result
    assert result["switch"].unit_price == 3.25


def test_parse_prices_plain_map():
    data = {"duplex_outlet": 4.25, "switch": 3.25}
    result = _parse_prices(data)
    assert result["duplex_outlet"].unit_price == 4.25
    assert result["switch"].unit_price == 3.25


def test_parse_prices_list_shape():
    rows = [{"sym_type": "light", "unit_price": 45.00, "source_url": "https://example.com"}]
    result = _parse_prices(rows)
    assert "light" in result
    assert result["light"].source_url == "https://example.com"


def test_parse_prices_skips_zero_price():
    result = _parse_prices({"duplex_outlet": 0, "switch": 3.25})
    assert "duplex_outlet" not in result
    assert "switch" in result


def test_parse_prices_skips_negative_price():
    result = _parse_prices({"duplex_outlet": -5.0, "switch": 3.25})
    assert "duplex_outlet" not in result


def test_parse_prices_skips_non_numeric_price():
    data = {"prices": [{"sym_type": "light", "unit_price": "call-for-price"}]}
    result = _parse_prices(data)
    assert "light" not in result


def test_parse_prices_skips_row_missing_sym_type():
    data = {"prices": [{"unit_price": 5.0}, {"sym_type": "switch", "unit_price": 3.25}]}
    result = _parse_prices(data)
    assert len(result) == 1
    assert "switch" in result


def test_parse_prices_skips_row_missing_price():
    data = {"prices": [{"sym_type": "light"}, {"sym_type": "switch", "unit_price": 3.25}]}
    result = _parse_prices(data)
    assert "light" not in result
    assert "switch" in result


def test_parse_prices_unknown_type_returns_empty():
    assert _parse_prices(42) == {}
    assert _parse_prices(None) == {}
    assert _parse_prices("string") == {}


def test_parse_prices_prices_key_with_null_list():
    result = _parse_prices({"prices": None})
    assert result == {}


def test_parse_prices_rounds_to_two_decimal_places():
    result = _parse_prices({"switch": 3.999})
    assert result["switch"].unit_price == 4.00


# ---------------------------------------------------------------------------
# fetch_unit_prices — async, uses httpx internally
# ---------------------------------------------------------------------------

def _make_mock_client(response_json):
    """Build a mock httpx.AsyncClient context manager that returns response_json."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = response_json

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm, mock_client


@pytest.mark.asyncio
async def test_fetch_unset_url_is_noop():
    """When BRIGHTDATA_PRICING_URL is unset, no HTTP call is made and {} is returned."""
    import app.services.brightdata_client as mod
    # Ensure it's unset (default fixture state)
    original = mod.BRIGHTDATA_PRICING_URL
    mod.BRIGHTDATA_PRICING_URL = ""
    try:
        with patch("app.services.brightdata_client.httpx.AsyncClient") as mock_cls:
            result = await fetch_unit_prices([{"sym_type": "light", "label": "Light"}])
        mock_cls.assert_not_called()
        assert result == {}
    finally:
        mod.BRIGHTDATA_PRICING_URL = original


@pytest.mark.asyncio
async def test_fetch_empty_items_is_noop(enable_brightdata):
    with patch("app.services.brightdata_client.httpx.AsyncClient") as mock_cls:
        result = await fetch_unit_prices([])
    mock_cls.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_structured_response(enable_brightdata):
    mock_cm, _ = _make_mock_client(
        {"prices": [{"sym_type": "duplex_outlet", "unit_price": 4.99, "vendor": "Grainger"}]}
    )
    with patch("app.services.brightdata_client.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_unit_prices([{"sym_type": "duplex_outlet", "label": "Duplex Outlet"}])

    assert "duplex_outlet" in result
    assert result["duplex_outlet"].unit_price == 4.99
    assert result["duplex_outlet"].vendor == "Grainger"


@pytest.mark.asyncio
async def test_fetch_plain_map_response(enable_brightdata):
    mock_cm, _ = _make_mock_client({"duplex_outlet": 5.99, "switch": 3.50})
    with patch("app.services.brightdata_client.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_unit_prices([
            {"sym_type": "duplex_outlet", "label": "Duplex Outlet"},
            {"sym_type": "switch", "label": "Switch"},
        ])

    assert result["duplex_outlet"].unit_price == 5.99
    assert result["switch"].unit_price == 3.50


@pytest.mark.asyncio
async def test_fetch_timeout_returns_empty(enable_brightdata):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("simulated timeout"))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.brightdata_client.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_unit_prices([{"sym_type": "light", "label": "Light"}])

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_http_error_returns_empty(enable_brightdata):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=MagicMock()
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.brightdata_client.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_unit_prices([{"sym_type": "light", "label": "Light"}])

    assert result == {}


@pytest.mark.asyncio
async def test_fetch_malformed_json_returns_empty(enable_brightdata):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = ValueError("not valid JSON")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.brightdata_client.httpx.AsyncClient", return_value=mock_cm):
        result = await fetch_unit_prices([{"sym_type": "light", "label": "Light"}])

    assert result == {}
