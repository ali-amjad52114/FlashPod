"""Symbol -> SKU mapping: the bridge between a detected drawing symbol and a real,
priceable product.

Each detected symbol `type` (the same keys the takeoff worker emits) maps to ONE concrete
product line. `search_query` is what we send to Google Shopping (via Bright Data SERP) to
pull live multi-supplier prices; `fallback_price` keeps the pipeline working offline if a
scrape returns nothing.

This is intentionally the single source of truth for *what* we price. The scraper, the
cached catalog, and the worker's embedded pricebook all key off these `type` values.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkuSpec:
    """One symbol type -> one product line."""

    type: str            # detector symbol type (matches takeoff_worker output)
    label: str           # human label shown on the proposal
    sku: str             # representative manufacturer SKU / model
    description: str     # what an estimator actually buys
    search_query: str    # Google Shopping query for live pricing
    unit: str            # billing unit ("each", "ft", ...)
    fallback_price: float  # used when no live offer is available


# Ordered so the proposal reads device-by-device. Add a row here to price a new symbol type.
SKU_SPECS: tuple[SkuSpec, ...] = (
    SkuSpec(
        type="duplex_outlet",
        label="Duplex Outlet",
        sku="Leviton CBR15-W",
        description="15 Amp 125V Commercial Grade Duplex Receptacle",
        search_query="Leviton CBR15-W 15 amp commercial duplex receptacle",
        unit="each",
        fallback_price=3.20,
    ),
    SkuSpec(
        type="gfci_outlet",
        label="GFCI Outlet",
        sku="Leviton GFNT2-W",
        description="20 Amp 125V Self-Test SmartlockPro Duplex GFCI Outlet",
        search_query="Leviton GFNT2 20 amp self-test GFCI outlet",
        unit="each",
        fallback_price=16.97,
    ),
    SkuSpec(
        type="data_drop",
        label="Data Drop (Cat6)",
        sku="Cat6 RJ45 Keystone Jack",
        description="Cat6 RJ45 Punch-Down Keystone Jack (data drop termination)",
        search_query="Cat6 RJ45 punch down keystone jack",
        unit="each",
        fallback_price=3.50,
    ),
    SkuSpec(
        type="switch",
        label="Switch",
        sku="Leviton CS115-2W",
        description="15 Amp Single-Pole Commercial Grade Toggle Switch",
        search_query="Leviton CS115 15 amp single pole commercial switch",
        unit="each",
        fallback_price=2.80,
    ),
    SkuSpec(
        type="light",
        label="Light Fixture",
        sku="2x4 LED Troffer",
        description="2 ft x 4 ft LED Troffer Recessed Panel Light",
        search_query="2x4 LED troffer recessed panel light",
        unit="each",
        fallback_price=48.00,
    ),
    SkuSpec(
        type="panel",
        label="Panel",
        sku="Square D Homeline 200A",
        description="200 Amp Main Breaker Load Center / Panel",
        search_query="Square D Homeline 200 amp main breaker load center",
        unit="each",
        fallback_price=139.00,
    ),
)

# type -> SkuSpec for quick lookup.
SKU_BY_TYPE: dict[str, SkuSpec] = {spec.type: spec for spec in SKU_SPECS}
