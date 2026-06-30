# FlashPod

**Turn an electrical drawing into a priced proposal where every quantity links back to the drawing.**

Upload a drawing → FlashPod detects and counts electrical symbols, prices the materials against
live supplier offers, and generates a proposal. The wow feature is **traceability**: click
*"Duplex Outlet: 42"* and the drawing highlights all 42 detected symbols — so the estimate is
explainable, not just automated.

> Estimators don't just need a quote. They need to prove where the quote came from. FlashPod
> turns electrical drawings into priced proposals, and every number links back to the drawing.

## System at a glance

```
React frontend ──▶ FastAPI backend ──▶ Runpod Flash endpoint ──▶ Bright Data (live pricing)
 (upload + view)    (persist + orchestrate)  (detect → count → price → proposal)
        ▲                                            │
        └────────── detections + priced_items + proposal (JSON) ◀──┘
```

- **`frontend/`** — React + TS UI: upload, line-item table, click-to-highlight on the drawing.
- **`backend/`** — FastAPI: projects/drawings/takeoffs, persistence (SQLite), calls the Flash
  endpoint, manual line-item corrections, proposal export.
- **Runpod Flash endpoint** — the remote compute: detect symbols, count, price, write the proposal.
- **`pricing/` + Bright Data** — live, description-driven material pricing (no fixed catalog).

## How FlashPod uses Runpod

Runpod Flash is our **remote execution layer**. An endpoint is a Python function decorated with
`@Endpoint`; it runs on a Runpod worker instead of the browser. When called, Flash provisions or
reuses a warm worker, ships the function body + input, runs it, and returns structured JSON.

There are **two interchangeable detection endpoints** — they return the **same output contract**, so
the backend and frontend don't care which one is live:

| Endpoint | File | Hardware | Detection | Templates? |
|----------|------|----------|-----------|-----------|
| `flashpod-takeoff` | [`takeoff_worker.py`](takeoff_worker.py) | **CPU** `cpu5c-4-8` | OpenCV multi-scale template matching + NMS | **required** (symbol crops) |
| `flashpod-detect-vl` | [`detect_symbols.py`](detect_symbols.py) | **GPU** `ADA_24` (RTX 4090) | **Qwen2.5-VL** vision grounding | **none** (semantic) |

- **CPU / OpenCV (default, demo-reliable):** cheap, fast, deterministic — but it can only find a
  symbol you hand it a crop of, and it's sensitive to rotation/scale. This endpoint also runs the
  **live Bright Data pricing** step inline.
- **GPU / Qwen2.5-VL (no templates):** a vision LLM reads the drawing and locates symbols
  semantically from a text catalog (`{type, desc}`) — no crops needed, and it returns bounding
  boxes for the highlight feature. Loads the 3B model once per warm worker; HuggingFace weights
  persist on a NetworkVolume across cold starts.

**Honest scope:** we did **not** train a model. OpenCV is classical template matching; the VL path
is **zero-shot** Qwen2.5-VL grounding (no fine-tuning). Both run as one warm worker for the demo.

## API contract (same for both endpoints)

**Request** (`POST /takeoff_worker/runsync` or `/detect_symbols/runsync`):
```json
{ "project_name": "Office Electrical Takeoff", "image_base64": "...",
  "templates": [ { "type": "switch", "label": "Switch", "template_base64": "...", "threshold": 0.7 } ],
  "symbols":   [ { "type": "switch", "label": "Switch", "desc": "orange circle with letter 'S'" } ] }
```
- `templates` → used by the **OpenCV** endpoint (symbol crops to match).
- `symbols` → optional catalog for the **VL** endpoint (`desc` helps the model); omit to use its
  built-in default catalog.

**Response:**
```json
{
  "detections":   [ { "type": "switch", "label": "Switch", "x": 420, "y": 310, "w": 24, "h": 24, "confidence": 0.91 } ],
  "priced_items": [ { "type": "switch", "label": "Switch", "quantity": 42,
                      "unit_price": 3.25, "total": 136.50, "price_source": "brightdata",
                      "supplier": "Menards", "source_url": "https://…",
                      "offers": [ { "supplier": "Menards", "price": 3.25, "url": "…" }, … ],
                      "boxes": [ [420,310,24,24], … ] } ],
  "totals": { "material_subtotal": 136.50, "labor_pct": 35, "labor_total": 47.78, "grand_total": 184.28 },
  "proposal": "FlashPod Electrical Proposal ..."
}
```
The frontend highlights `priced_items[].boxes` when a proposal line is clicked. `price_source` is
`"brightdata"` when a live offer was found, else `"static"` (PRICE_TABLE fallback) — so the demo
never breaks when pricing is offline.

> **Note (current state):** the FastAPI backend dispatches **image-only** (it does not send template
> crops), which pairs with the VL endpoint. To drive the OpenCV endpoint end-to-end, send
> `templates` in the payload (the backend's templates router is deprecated but the worker still
> accepts them).

## Pricing — Bright Data (dynamic, per line item)

Material prices come from **live supplier offers**, not a hardcoded catalog. The
[`pricing/`](pricing/) package (also inlined into `takeoff_worker.py`) turns each line item's
**description/label** into a **Bright Data SERP → Google Shopping** query (`udm=28`, one request =
offers from many suppliers), keeps **every** offer (nothing filtered), defaults the headline
`unit_price` to the cheapest, and multiplies by quantity. The full `offers` list rides along for a
compare/expand UI.

```text
{type, count, description}  ──build_query──▶  Bright Data SERP (Google Shopping, US)
                                                       │  ~40 supplier offers
                                                       ▼
   priced line { unit_price=cheapest, total=unit×count, offers:[…all…] }  ◀── keep everything
```

Demo-safety: a query-keyed cache ([`pricing/price_cache.json`](pricing/price_cache.json)) makes warm
runs instant and survives a flaky network; the static `PRICE_TABLE` covers an empty scrape. Cost
~$1.50 / 1k requests — a whole takeoff is well under a cent.

## Run it

```bash
# --- Flash endpoints (remote compute) ---
uv run python scripts/check_account.py     # confirm Runpod key + balance (> 0 to run)
uv run python scripts/check_brightdata.py  # confirm Bright Data key + SERP zone
uv run flash dev                           # local server; functions run on remote Runpod workers
#   OpenCV (CPU):  POST http://localhost:8888/takeoff_worker/runsync
#   Qwen-VL (GPU): POST http://localhost:8888/detect_symbols/runsync
uv run flash deploy                        # ship stable endpoints
uv run flash undeploy --all --force        # tear down workers when done (stop billing)

# --- Pricing (standalone) ---
uv run python -m pricing.price_takeoff             # price data/sample_takeoff.json (live + cache)
uv run python -m pricing.price_takeoff --no-cache  # force a fresh scrape
uv run --extra dev pytest                          # pricing unit tests (no network)

# --- Backend API ---
cd backend && uvicorn app.main:app --reload        # FastAPI on http://localhost:8000 (/docs)

# --- Frontend ---
cd frontend && npm install && npm run dev          # Vite dev server
```

Auth: put `RUNPOD_API_KEY` and `BRIGHTDATA_API_KEY` (+ `BRIGHTDATA_SERP_ZONE`) in `.env` (see
[`.env.example`](.env.example)). On Windows, `PYTHONUTF8=1` avoids a CLI console-encoding crash.

## Files

**Flash endpoints**
- [`takeoff_worker.py`](takeoff_worker.py) — CPU OpenCV endpoint (detect → count → Bright Data price → proposal)
- [`detect_symbols.py`](detect_symbols.py) — GPU Qwen2.5-VL endpoint (template-free semantic detection)
- [`load_test.py`](load_test.py) — autoscaling/load demo against an endpoint

**Pricing** — [`pricing/`](pricing/) (Bright Data dynamic pricing, no fixed catalog)
- `scraper.py` — Bright Data SERP client; one query → all supplier offers
- `pricing.py` — query builder + `price_line_items()` + file cache + fallback
- `price_takeoff.py` — CLI to price a takeoff table (`data/sample_takeoff.json`)
- `worker_step.py` — self-contained step-04 to inline into a Flash worker

**Backend** — [`backend/`](backend/) (FastAPI orchestration)
- `app/routers/` — projects, drawings, takeoffs (templates router deprecated)
- `app/services/runpod_client.py` — calls the Flash endpoint, normalizes the response
- `app/models.py`, `app/db.py` — SQLAlchemy models + SQLite

**Frontend** — [`frontend/`](frontend/) — React + TS UI (upload, line items, click-to-highlight)

**Scripts / data / tests**
- [`scripts/check_account.py`](scripts/check_account.py) — validate Runpod key + balance
- [`scripts/check_brightdata.py`](scripts/check_brightdata.py) — validate Bright Data key + zone
- `data/sample_takeoff.json` — sample line items for the pricing CLI
- `tests/test_pricing.py` — pricing unit tests
- `templates/*.png` — sample symbol crops for the OpenCV endpoint
