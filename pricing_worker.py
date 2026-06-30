# pricing worker -- maps symbol counts to material unit prices and line totals.
# run with: flash dev
#
# Flash wiring grounded in reference/flash-examples/01_getting_started/02_cpu_worker/cpu_worker.py
#   @Endpoint(name=..., cpu=CpuInstanceType.CPU3C_1_2)
#
# v1 pricing = a static price map. Phase 7 replaces this with Bright Data live supplier prices
# (see brightdata_demo.py), keeping this static map as the fallback.
from runpod_flash import Endpoint, CpuInstanceType


@Endpoint(name="flashpod_pricing", cpu=CpuInstanceType.CPU3C_1_2, workers=(0, 3))
async def price(input_data: dict) -> dict:
    """
    Add unit_price + total to each line item and compute the subtotal.

    Input:
        line_items: [{ "type", "count", "boxes": [...] }]
        price_map: dict (optional) - overrides the static PRICE_MAP (e.g. live Bright Data prices)

    Returns:
        line_items (with unit_price + total added, boxes preserved), subtotal
    """
    from datetime import datetime

    # Defined INSIDE the body: flash dev ships only the body (SKILL Gotcha #1).
    # Static unit prices (USD) by symbol type; Phase 7 overrides via price_map (Bright Data).
    PRICE_MAP = {
        "duplex_receptacle": 2.85,
        "gfci_receptacle": 18.50,
        "data_drop": 12.00,
        "switch": 3.25,
        "light": 45.00,
        "panel": 320.00,
    }
    DEFAULT_UNIT_PRICE = 5.00

    line_items = input_data.get("line_items") or []
    price_map = {**PRICE_MAP, **(input_data.get("price_map") or {})}

    priced = []
    subtotal = 0.0
    for item in line_items:
        sym = item.get("type", "")
        count = int(item.get("count", 0))
        unit = float(price_map.get(sym, DEFAULT_UNIT_PRICE))
        total = round(unit * count, 2)
        subtotal += total
        priced.append(
            {
                "type": sym,
                "count": count,
                "boxes": item.get("boxes", []),   # preserved for traceability
                "unit_price": unit,
                "total": total,
            }
        )

    return {
        "status": "success",
        "line_items": priced,
        "subtotal": round(subtotal, 2),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import asyncio

    sample = {"line_items": [{"type": "duplex_receptacle", "count": 42, "boxes": []}]}
    print("Pricing test:", asyncio.run(price(sample)))
