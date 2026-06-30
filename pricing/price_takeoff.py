"""Price a takeoff table end-to-end (the vision LLM's output) and print/write the result.

    uv run python -m pricing.price_takeoff                       # uses data/sample_takeoff.json
    uv run python -m pricing.price_takeoff path/to/takeoff.json  # custom line items
    uv run python -m pricing.price_takeoff --no-cache            # force live scrape

Input JSON: a list of { type, count, description }. Output: priced lines (every offer kept),
written to data/priced_takeoff.json and summarised to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .pricing import price_line_items

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "sample_takeoff.json"
OUTPUT = DATA_DIR / "priced_takeoff.json"


def main() -> None:
    load_dotenv(".env")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_cache = "--no-cache" not in sys.argv
    input_path = Path(args[0]) if args else DEFAULT_INPUT

    items = json.loads(input_path.read_text())
    print(f"Pricing {len(items)} line items from {input_path.name} "
          f"({'cache+live' if use_cache else 'live only'})...\n")

    priced = price_line_items(items, use_cache=use_cache)

    subtotal = sum(p["total"] for p in priced)
    print(f"{'Item':<22}{'Qty':>5}{'Unit':>10}{'Line':>12}   {'Cheapest of N':<14} via")
    print("-" * 84)
    for p in priced:
        print(f"{p['label'][:21]:<22}{p['count']:>5}{p['unit_price']:>10.2f}{p['total']:>12.2f}"
              f"   {p['supplier'][:12]:<12} ({p['offer_count']:>2}) {p['source']}")
    print("-" * 84)
    print(f"{'SUBTOTAL':<49}{round(subtotal, 2):>12.2f}")

    OUTPUT.write_text(json.dumps(priced, indent=2) + "\n")
    print(f"\nFull priced output (all offers per line) -> {OUTPUT.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
