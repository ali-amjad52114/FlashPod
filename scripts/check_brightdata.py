"""Validate the Bright Data SERP credentials with one tiny live request.

    uv run python scripts/check_brightdata.py

Confirms BRIGHTDATA_API_KEY + zone work before running a full catalog build. Costs ~1 SERP
request (< $0.002). Mirrors scripts/check_account.py for Runpod.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("BRIGHTDATA_API_KEY")
zone = os.environ.get("BRIGHTDATA_SERP_ZONE", "serp_api")
if not token:
    raise SystemExit("BRIGHTDATA_API_KEY not set in .env")

print(f"Testing zone '{zone}' with a Google Shopping probe...")
resp = requests.post(
    "https://api.brightdata.com/request",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "zone": zone,
        "url": "https://www.google.com/search?q=duplex+receptacle&udm=28&brd_json=1&gl=us&hl=en",
        "format": "raw",
    },
    timeout=60,
)
print("HTTP", resp.status_code)

if resp.status_code != 200:
    print("FAILED:", resp.text[:400])
    raise SystemExit(
        "Check that the zone name matches your SERP API zone in the Bright Data dashboard "
        "and that the token has access to it."
    )

try:
    data = resp.json()
except ValueError:
    print("VALID KEY ✓ but response wasn't JSON (brd_json may be off):")
    print(resp.text[:400])
    raise SystemExit(0)

top_keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
print("VALID KEY ✓  parsed JSON top-level keys:", top_keys)
print("Next: `uv run python -m pricing.build_catalog` to refresh real prices.")
