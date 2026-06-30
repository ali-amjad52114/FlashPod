"""Validate the Runpod API key and print account balance. No GPU spin-up, no cost.

    uv run python scripts/check_account.py
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("RUNPOD_API_KEY")
if not key:
    raise SystemExit("RUNPOD_API_KEY not set in .env")

url = "https://api.runpod.io/graphql"
query = {"query": "query { myself { id email clientBalance currentSpendPerHr } }"}

r = requests.post(url, params={"api_key": key}, json=query, timeout=20)
print("HTTP", r.status_code)
data = r.json()

if data.get("errors"):
    print("ERRORS:", json.dumps(data["errors"], indent=2)[:600])

me = (data.get("data") or {}).get("myself")
if me:
    email = me.get("email") or ""
    masked = (email[:2] + "***@" + email.split("@")[1]) if "@" in email else email
    print("VALID KEY ✓")
    print("  user id:          ", me.get("id"))
    print("  email:            ", masked)
    print("  clientBalance ($):", me.get("clientBalance"))
    print("  spend/hr ($):     ", me.get("currentSpendPerHr"))
else:
    print("No 'myself' returned — key may be invalid or insufficiently scoped.")
