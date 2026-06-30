# FlashPod

**Turn an electrical drawing into a priced proposal where every quantity links back to the drawing.**

Upload a drawing → FlashPod detects and counts electrical symbols, prices the materials, and
generates a proposal. The wow feature is **traceability**: click *"Duplex Outlet: 42"* and the
drawing highlights all 42 detected symbols — so the estimate is explainable, not just automated.

> Estimators don't just need a quote. They need to prove where the quote came from. FlashPod
> turns electrical drawings into priced proposals, and every number links back to the drawing.

## How FlashPod uses Runpod

Runpod Flash is our **remote execution layer**. An endpoint is a Python function decorated with
`@Endpoint`; it runs on a Runpod worker instead of the browser. When called, Flash provisions or
reuses a worker, ships the code + input, runs it, and returns the result.

> FlashPod runs the drawing-takeoff pipeline as a remote Python endpoint on Runpod Flash. A warm
> Runpod worker receives the uploaded drawing, runs OpenCV-based symbol detection, counts items,
> attaches pricing, and returns structured JSON. The React frontend only displays the result and
> handles the interactive highlight feature. For the hackathon we use **one CPU endpoint** for
> reliability; the production version can split detection into a **GPU endpoint** running a
> fine-tuned vision model.

**Honest scope:** today's MVP is OpenCV template matching on a **CPU** endpoint — it genuinely
doesn't need a GPU, and we did **not** train a model. The architecture is ready for a fine-tuned
detector on GPU (see *Production* below).

## Endpoint design (MVP = one endpoint)

`flashpod-takeoff` → [`takeoff_worker.py`](takeoff_worker.py) → `analyze_drawing()` does the whole
pipeline inline: decode → detect → count → price → proposal. One endpoint = one worker, one config,
one failure point — buildable fast and reliable for the demo.

```python
@Endpoint(
    name="flashpod-takeoff",
    cpu="cpu5c-4-8",
    workers=(1, 1),            # keep 1 worker warm -> no cold start during the pitch
    dependencies=["opencv-python", "pillow", "numpy", "requests"],
)
async def analyze_drawing(payload: dict) -> dict:
    import cv2, numpy as np            # imports INSIDE the body (only the body ships to the worker)
    ...
```

## API contract

**Frontend → Runpod** (`POST /takeoff_worker/runsync`):
```json
{ "project_name": "Office Electrical Takeoff", "image_base64": "...",
  "templates": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "template_base64": "...", "threshold": 0.7 } ] }
```

**Runpod → Frontend:**
```json
{
  "detections":   [ { "type": "duplex_outlet", "label": "Duplex Outlet", "x": 420, "y": 310, "w": 24, "h": 24, "confidence": 0.91 } ],
  "priced_items": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 42, "unit_price": 2.98, "total": 125.16,
                      "sku": "Leviton CBR15-W", "supplier": "The Home Depot", "source_url": "https://www.homedepot.com/p/202066707",
                      "boxes": [[420,310,24,24], ...] } ],
  "proposal": "FlashPod Electrical Proposal ..."
}
```
The frontend highlights `priced_items[].boxes` when a proposal line is clicked. `unit_price`
is a real, sourced price (`sku` + `supplier` + `source_url`) — see **Pricing** below.

Optionally the frontend can send `"pricebook": { ... }` in the request to override prices per
run; otherwise the worker uses its embedded catalog snapshot.

> **Note:** template matching needs symbol templates. The MVP accepts them as an optional
> `templates` array (legend crops sent by the frontend). Production replaces this with a trained
> detector that needs no templates.

## Run it

```bash
uv run python scripts/check_account.py   # confirm Runpod key + balance (> 0 to run)
uv run flash dev                         # local server; functions run on a remote Runpod worker
# POST a drawing to http://localhost:8888/takeoff_worker/runsync
uv run flash deploy                      # ship a stable endpoint
uv run flash undeploy --all --force      # tear down workers when done (stop billing)
```

Auth: put `RUNPOD_API_KEY` in `.env` (see `.env.example`). On Windows, `PYTHONUTF8=1` avoids a
CLI console-encoding crash.

## Pricing — Bright Data (real, sourced, cached)

The `unit_price` on every line item is a real price, not a guess. The [`pricing/`](pricing/)
package maps each detected symbol to a concrete product and pulls live multi-supplier prices
via **Bright Data's SERP API → Google Shopping** (`udm=28`, one request returns offers from
Home Depot, Lowe's, Grainger, Walmart, …). It picks the cheapest in-stock offer and caches the
result so the demo never scrapes in the request path.

```text
symbol type ──symbol_sku──▶ product + search query
                                   │  Bright Data SERP (Google Shopping)
                                   ▼
                       multi-supplier offers ──select cheapest──▶ catalog.json (cached)
                                                                        │ embed_pricebook
                                                                        ▼
                                                   EMBEDDED_PRICEBOOK in takeoff_worker.py
```

```bash
uv run python scripts/check_brightdata.py     # validate BRIGHTDATA_API_KEY + zone (~$0.002)
uv run python -m pricing.build_catalog        # scrape live prices -> pricing/catalog.json
uv run python -m pricing.embed_pricebook      # bake catalog prices into the worker
uv run --extra dev pytest                     # pricing unit tests (no network)
```

Without a key the committed [`pricing/catalog.json`](pricing/catalog.json) (seeded with
researched prices) drives the demo. Set `BRIGHTDATA_API_KEY` (+ `BRIGHTDATA_SERP_ZONE`) in
`.env`, then `build_catalog` → `embed_pricebook` to swap in live prices. Cost is ~$1.50/1k
requests, so a full 6-SKU refresh is under a cent. Why cached, not live-per-request: Flash
ships only the function body (can't read a file on the worker), and a live scrape mid-pitch
adds latency + rate-limit risk — so prices are baked at deploy and overridable via payload.

## Production (future, not built today)

Split into focused endpoints; move detection to GPU:

| Stage | Endpoint | Hardware | Model |
|-------|----------|----------|-------|
| Detect symbols | `detect_symbols_gpu()` | Runpod GPU | fine-tuned YOLO-style detector |
| OCR / legend | `ocr_and_parse()` | CPU/GPU | PaddleOCR |
| Price | `price_items()` | CPU | Bright Data + normalization |
| Proposal | `generate_proposal()` | CPU/GPU | LLM or template |

## Files
- [`takeoff_worker.py`](takeoff_worker.py) — the single CPU endpoint (full pipeline)
- [`pricing/`](pricing/) — Bright Data scraper + symbol→SKU mapping + cached catalog
  - `symbol_sku.py` — symbol type → product + Google Shopping query
  - `scraper.py` — Bright Data SERP client (multi-supplier offers)
  - `catalog.py` — offer selection + `catalog.json` + worker pricebook
  - `build_catalog.py` / `embed_pricebook.py` — refresh cache / bake into worker
- [`load_test.py`](load_test.py) — autoscaling/load demo against the endpoint
- [`scripts/check_account.py`](scripts/check_account.py) — validate Runpod API key + balance
- [`scripts/check_brightdata.py`](scripts/check_brightdata.py) — validate Bright Data key + zone
