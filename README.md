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
  "priced_items": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 42, "unit_price": 4.25, "total": 178.50, "boxes": [[420,310,24,24], ...] } ],
  "proposal": "FlashPod Electrical Proposal ..."
}
```
The frontend highlights `priced_items[].boxes` when a proposal line is clicked.

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
- [`load_test.py`](load_test.py) — autoscaling/load demo against the endpoint
- [`scripts/check_account.py`](scripts/check_account.py) — validate API key + balance
