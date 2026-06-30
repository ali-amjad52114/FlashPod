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
  "priced_items": [ { "type": "DGPO Outlet", "label": "DGPO Outlet", "count": 107,
                      "unit_price": 0.67, "total": 71.69, "supplier": "Menards", "source_url": "https://…",
                      "offer_count": 40, "offers": [ { "supplier": "Menards", "price": 0.67, "url": "…" }, … ] } ],
  "proposal": "FlashPod Electrical Proposal ..."
}
```
`unit_price` defaults to the cheapest of `offers` (nothing filtered); the frontend can render the
full `offers` list as a compare/expand UI and let the user re-pick — see **Pricing** below.

> **Detection** is a vision LLM (Qwen-VL / Claude vision on Runpod) that emits the priced line
> items as `{type, count, description}` — variable per drawing. The `description` is what pricing
> searches on, so any symbol type prices automatically.

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

## Pricing — Bright Data (dynamic, per line item)

The vision LLM emits variable line items per drawing — `{type, count, description}` — so there's
no fixed catalog. The [`pricing/`](pricing/) package turns each line's **description** into a
**Bright Data SERP → Google Shopping** query (`udm=28`, one request = offers from many suppliers),
keeps **every** offer (nothing filtered), defaults the headline `unit_price` to the cheapest, and
multiplies by `count`. The full `offers` list rides along for the compare UI.

```text
{type, count, description}  ──build_query (description)──▶  Bright Data SERP (Google Shopping, US)
                                                                     │  ~40 supplier offers
                                                                     ▼
   priced line { unit_price=cheapest, total=unit×count, offers:[…all…] }  ◀── keep everything
```

```bash
uv run python scripts/check_brightdata.py                 # validate BRIGHTDATA_API_KEY + zone
uv run python -m pricing.price_takeoff                    # price data/sample_takeoff.json (live+cache)
uv run python -m pricing.price_takeoff --no-cache         # force a fresh scrape
uv run --extra dev pytest                                 # pricing unit tests (no network)
```

**Where it runs:** pricing is **step 04 inside the Flash worker** — drop
[`pricing/worker_step.py`](pricing/worker_step.py)'s `price_line_items_inline` into
`analyze_drawing` after the vision LLM produces `line_items` (it's self-contained because Flash
ships only the function body). Set `BRIGHTDATA_API_KEY` (+ `BRIGHTDATA_SERP_ZONE`) as worker
secrets. Demo-safety: a query-keyed cache ([`pricing/price_cache.json`](pricing/price_cache.json))
makes warm runs instant and survives a flaky network; a tiny keyword fallback covers an empty
scrape. Cost ~$1.50/1k requests — a whole takeoff is well under a cent.

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
- [`pricing/`](pricing/) — Bright Data dynamic pricing (per line item, no fixed catalog)
  - `scraper.py` — Bright Data SERP client; one query → all supplier offers
  - `pricing.py` — query builder + `price_line_items()` + file cache + fallback
  - `price_takeoff.py` — CLI to price a takeoff table (`data/sample_takeoff.json`)
  - `worker_step.py` — self-contained step-04 to inline into the Flash worker
- [`load_test.py`](load_test.py) — autoscaling/load demo against the endpoint
- [`scripts/check_account.py`](scripts/check_account.py) — validate Runpod API key + balance
- [`scripts/check_brightdata.py`](scripts/check_brightdata.py) — validate Bright Data key + zone
