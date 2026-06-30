"""Refresh the cached catalog from live Bright Data prices.

    uv run python -m pricing.build_catalog

Scrapes Google Shopping for every SKU, picks the best offer per item, and writes
pricing/catalog.json. Requires BRIGHTDATA_API_KEY (won't clobber the cached catalog with
fallback-only data if the key is missing). Run `python -m pricing.embed_pricebook` afterward
to push the new prices into the takeoff worker.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dotenv import load_dotenv

from .catalog import CATALOG_PATH, assemble_catalog
from .scraper import BrightDataError, _credentials, scrape_all

import json


def main() -> None:
    load_dotenv()
    try:
        _credentials()  # fail fast before clobbering catalog.json with fallbacks
    except BrightDataError as exc:
        raise SystemExit(f"{exc}\nThe cached catalog.json is left untouched.")

    print("Scraping live prices via Bright Data SERP (Google Shopping)...")
    scraped = scrape_all()
    if not any(scraped.values()):
        raise SystemExit(
            "Bright Data returned no offers for any SKU. "
            "The cached catalog.json is left untouched."
        )
    catalog = assemble_catalog(
        scraped,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source="brightdata-serp-google-shopping",
    )
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n")

    print(f"\nWrote {CATALOG_PATH.relative_to(CATALOG_PATH.parent.parent)}")
    for sym_type, item in catalog["items"].items():
        sel = item["selected"]
        print(
            f"  {item['label']:<18} ${sel['price']:>8.2f}  "
            f"{sel['supplier']:<22} ({item['offer_count']} offers)"
        )


if __name__ == "__main__":
    main()
