# FlashPod — agent guide

AI electrical-takeoff tool: upload an electrical drawing → detect/count symbols → price
materials → generate a proposal, where **every quantity links back to highlighted symbols**
on the drawing (the traceability wow-feature). Runpod Flash is the remote compute layer; the
React frontend only uploads and displays.

## Hard rules (read before writing any Flash code)

1. **Ground all Flash code in the reference examples.** Copy patterns from `reference/flash-examples/`
   and the official skill at `.agents/skills/flash/SKILL.md` (+ `evals/`). Do **not** invent Flash
   patterns, endpoint signatures, or invocation styles. If no reference covers it, say so and adapt
   the closest example. Use `@Endpoint` (current API) — never the deprecated `@remote`.
2. **Only the function body ships to the worker** (skill Gotcha #1). Put every import, constant, and
   helper **inside** the decorated body. A module-level name used in the body raises `NameError`
   under `flash dev` (deploy masks it). See `evals/fixtures/dev-loop/main.py` for the canonical bug.
3. **An `@Endpoint` call can't run as bare `python file.py`** — it dispatches to a deployed worker
   (`deploy it first`). Offline checks are syntax only; real runs need `flash dev` (provisions live
   workers = costs money).

## Architecture (MVP = one CPU endpoint)

`flashpod-takeoff` → `takeoff_worker.py` → `analyze_drawing(payload)` runs the whole pipeline
inline: decode → detect (OpenCV multi-scale template matching + NMS) → count → price → proposal.

- `cpu="cpu5c-4-8"`, `workers=(1, 1)` (one warm worker, no cold start during the demo).
- deps: `opencv-python`, `pillow`, `numpy`, `requests`.
- **Honest scope:** CPU + template matching, **no GPU, no trained model**. Production can split
  detection into a GPU endpoint with a fine-tuned detector (YOLO11/ultralytics) — see README.
- One endpoint = fewer workers/configs/failure points. Don't add endpoints without a reason.

### I/O contract
- **In:** `{ project_name, image_base64, templates: [{ type, label, template_base64, threshold? }] }`
  — the frontend sends symbol crops as `templates` (template matching needs them).
- **Out:** `{ detections: [{type,label,x,y,w,h,confidence}], priced_items: [{type,label,quantity,unit_price,total,boxes}], proposal }`
  — frontend highlights `priced_items[].boxes` on line-item click.

## Commands

```bash
uv run python scripts/check_account.py   # validate RUNPOD_API_KEY + balance (must be > 0 to run)
uv run flash dev                         # local server; functions run on remote Runpod workers
#   route: POST http://localhost:8888/takeoff_worker/runsync   (routes are file-namespaced)
#   run flash dev in the BACKGROUND; read the real port from its log (8888 bumps if taken)
uv run flash deploy                      # ship a stable endpoint
uv run flash undeploy --all --force      # tear down workers (workers=(1,1) bills while warm)
```

## Environment notes

- **Windows:** the Flash CLI crashes on cp1252 consoles (`UnicodeEncodeError`). Fixed via a
  persistent `PYTHONUTF8=1` user env var. Open a fresh terminal if you hit it.
- **Python:** local venv is 3.12 (Flash workers run 3.12; SDK supports 3.10–3.13). Use `uv run`.
- **Auth:** `RUNPOD_API_KEY` in `.env` (gitignored). `flash login`'s browser flow is unnecessary —
  resolution is env var > `.env` > config.
- **CPU endpoints** run in datacenter `EU_RO_1` only.
- **Not committed:** `.env`, `.venv/`, `reference/` (upstream clones), `.agents/` (skill bundle).

## Files
- `takeoff_worker.py` — the single CPU endpoint (full pipeline)
- `load_test.py` — 4-phase autoscaling/load demo against the endpoint
- `scripts/check_account.py` — validate API key + read Runpod balance
