# proposal worker -- assembles priced line items into a proposal document.
# run with: flash dev
#
# Flash wiring grounded in reference/flash-examples/01_getting_started/02_cpu_worker/cpu_worker.py
#   @Endpoint(name=..., cpu=CpuInstanceType.CPU3C_1_2)
from runpod_flash import Endpoint, CpuInstanceType


@Endpoint(name="flashpod_proposal", cpu=CpuInstanceType.CPU3C_1_2, workers=(0, 3))
async def build(input_data: dict) -> dict:
    """
    Build a proposal from priced line items.

    Input:
        line_items: [{ "type", "count", "unit_price", "total", "boxes" }]
        project_name: str (optional)

    Returns:
        proposal_text (formatted), total
    """
    from datetime import datetime

    line_items = input_data.get("line_items") or []
    project_name = input_data.get("project_name", "Electrical Takeoff")

    lines = [f"PROPOSAL — {project_name}", f"Date: {datetime.now():%Y-%m-%d}", ""]
    lines.append(f"{'Item':<24}{'Qty':>6}{'Unit':>12}{'Total':>14}")
    lines.append("-" * 56)

    total = 0.0
    for item in line_items:
        name = str(item.get("type", "")).replace("_", " ").title()
        qty = int(item.get("count", 0))
        unit = float(item.get("unit_price", 0.0))
        line_total = float(item.get("total", 0.0))
        total += line_total
        lines.append(f"{name:<24}{qty:>6}{unit:>12.2f}{line_total:>14.2f}")

    lines.append("-" * 56)
    lines.append(f"{'SUBTOTAL':<42}{total:>14.2f}")

    return {
        "status": "success",
        "proposal_text": "\n".join(lines),
        "total": round(total, 2),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import asyncio

    sample = {
        "line_items": [
            {"type": "duplex_receptacle", "count": 42, "unit_price": 2.85, "total": 119.70}
        ]
    }
    print(asyncio.run(build(sample))["proposal_text"])
