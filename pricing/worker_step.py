"""Step-04 PRICE — self-contained version to inline into the Flash takeoff worker.

The takeoff worker ships ONLY its function body (Flash skill Gotcha #1), so it can't import the
`pricing` package. This file is the same logic as `pricing.pricing`, collapsed into one function
with EVERY import/helper inside it — copy `price_line_items_inline`'s body into `analyze_drawing`
after the vision LLM has produced `line_items`, e.g.:

    detections = run_vision_llm(image)            # [{type, count, description}, ...]  (teammate)
    priced_items = price_line_items_inline(detections)   # <-- this step
    proposal = build_proposal(priced_items)

Needs BRIGHTDATA_API_KEY (+ BRIGHTDATA_SERP_ZONE) as Flash worker secrets, and "requests" in the
endpoint dependencies (already present). Cache is in-memory per invocation (the diagram's
"in-memory / run"); the file-backed cache only exists in the standalone `pricing` package.
"""
from __future__ import annotations


def price_line_items_inline(line_items: list[dict]) -> list[dict]:
    """Price [{type, count, description}] via Bright Data SERP. Returns ALL offers per line."""
    import os
    import re
    from urllib.parse import quote_plus

    import requests

    API_URL = "https://api.brightdata.com/request"
    token = os.environ.get("BRIGHTDATA_API_KEY")
    zone = os.environ.get("BRIGHTDATA_SERP_ZONE", "serp_api1")

    QUERY_ALIASES = {
        "dgpo": "double power outlet receptacle",
        "gpo": "power outlet receptacle",
        "data outlet": "cat6 rj45 data jack wall outlet",
        "voice": "rj45 voice phone jack wall outlet",
        "tv antenna": "tv antenna coax wall outlet",
    }
    FALLBACK_PRICES = {
        "gfci": 16.0, "outlet": 3.0, "receptacle": 3.0, "switch": 3.0,
        "data": 4.0, "cat6": 4.0, "rj45": 4.0, "voice": 4.0,
        "antenna": 12.0, "light": 45.0, "panel": 140.0,
    }
    RESULT_KEYS = ("shopping", "shopping_results", "products", "organic", "results")

    def build_query(item):
        base = (item.get("description") or item.get("type") or "").strip()
        label = (item.get("type") or "").lower()
        for key, sharper in QUERY_ALIASES.items():
            if key in label or key in base.lower():
                return f"{base} {sharper}".strip()
        return base

    def fallback_price(query):
        q = query.lower()
        for keyword, price in FALLBACK_PRICES.items():
            if keyword in q:
                return price
        return 5.0

    def to_price(value):
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        if not isinstance(value, str):
            return None
        m = re.search(r"\d[\d,]*\.?\d*", value.replace(",", ""))
        return round(float(m.group()), 2) if m else None

    def scrape(query):
        url = f"https://www.google.com/search?q={quote_plus(query)}&udm=28&brd_json=1&gl=us&hl=en"
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"zone": zone, "url": url, "format": "raw"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        results = next((data[k] for k in RESULT_KEYS if isinstance(data.get(k), list)), [])
        offers = []
        for it in results:
            if not isinstance(it, dict):
                continue
            price = to_price(it.get("price") or it.get("extracted_price"))
            if not price or price <= 0:
                continue
            offers.append({
                "supplier": str(it.get("shop") or it.get("source") or it.get("title") or "Unknown").strip(),
                "price": price,
                "url": str(it.get("link") or ""),
                "title": str(it.get("title") or ""),
            })
        return sorted(offers, key=lambda o: o["price"])

    cache: dict[str, list[dict]] = {}
    priced = []
    for item in line_items:
        count = int(item.get("count", item.get("quantity", 1)))
        query = build_query(item)
        if query in cache:
            offers, source = cache[query], "cache"
        else:
            try:
                offers, source = scrape(query), "serp"
            except Exception:                       # never let one bad query sink the run
                offers, source = [], "fallback"
            cache[query] = offers

        best = offers[0] if offers else None
        if best:
            unit_price, supplier, source_url = best["price"], best["supplier"], best["url"]
        else:
            unit_price, supplier, source_url, source = fallback_price(query), "estimate", "", "fallback"

        priced.append({
            "type": item.get("type", "item"),
            "label": item.get("label") or item.get("type") or "Item",
            "description": item.get("description", ""),
            "count": count,
            "unit_price": unit_price,
            "supplier": supplier,
            "source_url": source_url,
            "total": round(unit_price * count, 2),
            "source": source,
            "offer_count": len(offers),
            "offers": offers,
        })
    return priced
