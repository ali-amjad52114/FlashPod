# Meta-prompt — generate the FlashPod UI build prompt

> Paste everything below the line into a capable agent. Its job is to OUTPUT a single,
> self-contained prompt that a coding agent will use to build the FlashPod web UI. It is
> NOT to build the UI itself.

---

You are a senior product engineer and prompt architect. Produce **one complete, self-contained
prompt** that another coding agent will use to build the **FlashPod** web UI (React + TypeScript).
Output **only that prompt** — no preamble, no explanation of your process.

## Step 0 — Ground yourself in the real system first (do not skip)

Read these local files before writing anything, and make the prompt you produce consistent with them:
- `CLAUDE.md` and `README.md` (app, architecture, honest scope)
- `takeoff_worker.py` (the actual endpoint: input/output shape)
- `reference/flash/docs/Flash_Deploy_Guide.md`, `reference/flash/docs/Flash_SDK_Reference.md`,
  `reference/flash/docs/Cross_Endpoint_Routing.md`, `reference/flash/docs/Load_Balancer_Endpoints.md`
- `.agents/skills/flash/SKILL.md`
Do not invent any Flash behavior that contradicts these files. If something is unspecified, say so
in the prompt rather than guessing.

## What FlashPod is (encode this in the prompt)

An AI electrical-estimating tool. The user uploads an electrical drawing; the backend detects and
counts electrical symbols, prices materials, and generates a proposal. **The wow feature is
traceability:** clicking a proposal line ("Duplex Outlet: 42") highlights all 42 detected symbols on
the drawing. The UI's whole job is upload → run → show results → make every number clickable back to
the drawing. Honest scope: today's backend is OpenCV template matching on a Runpod Flash **CPU**
endpoint (no GPU, no trained model).

## NON-NEGOTIABLE technical facts the produced prompt MUST state verbatim

### Exact API contract (must match the worker)
Request payload (the user data):
```json
{ "project_name": "Office Electrical Takeoff",
  "image_base64": "<drawing PNG/JPG as base64>",
  "templates": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "template_base64": "<crop>", "threshold": 0.7 } ] }
```
Response:
```json
{ "status": "success",
  "detections":   [ { "type": "duplex_outlet", "label": "Duplex Outlet", "x": 420, "y": 310, "w": 24, "h": 24, "confidence": 0.91 } ],
  "priced_items": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 42, "unit_price": 4.25, "total": 178.50, "boxes": [[420,310,24,24]] } ],
  "proposal": "FlashPod Electrical Proposal ...",
  "image_size": { "width": 1654, "height": 1169 } }
```
Boxes are `[x, y, w, h]` in **original image pixels**; the UI must scale them to the displayed image.

### How the UI calls Flash (queue-based endpoint, after `flash deploy`)
- **Async (use this for cold starts):** `POST https://api.runpod.ai/v2/{ENDPOINT_ID}/run`, then poll
  `GET https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{JOB_ID}` until terminal.
- **Sync (≤60s only):** `POST https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync`.
- Header: `Authorization: Bearer <RUNPOD_API_KEY>`, `Content-Type: application/json`.
- **Body MUST be wrapped:** `{"input": { project_name, image_base64, templates } }` — the worker's
  `payload` arg is the value of `input`.
- Job states: `IN_QUEUE`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`. `runsync` times out at
  60s; cold starts can exceed it, so prefer `/run` + status polling and show a "warming up" state.
- Local dev route (for testing before deploy): `POST http://localhost:8888/takeoff_worker/runsync`.

### SECURITY — mandatory
The `RUNPOD_API_KEY` must **never** ship in browser code. The produced prompt must require a **thin
server-side proxy** (e.g. a Next.js Route Handler / small Node server) that holds the key as a
server env var and forwards requests to Runpod. The React app calls the proxy, not Runpod directly.

### Progress between workers — state the truth, don't fake it
Flash does **not** expose intra-job stage progress (no SSE, no in-handler progress events). A single
orchestrated endpoint returns only the final result. The produced prompt must pick and clearly state
ONE of these, and must NOT animate fake per-stage completion as if the backend reported it:
- **Option A (real per-stage progress):** split the pipeline into separate Flash endpoints
  (`detect` → `price` → `proposal`) and have the proxy call them in sequence; the UI lights up each
  stage as its call returns. This is genuine progress and matches the documented production split.
- **Option B (single-endpoint MVP):** one `/run` job; the stage tracker reflects the real job
  lifecycle (`IN_QUEUE` → `IN_PROGRESS` → `COMPLETED`); the internal stages (detect/price/proposal)
  are shown as labeled steps that complete together when the job finishes — honestly labeled as such.
Recommend Option A if real inter-stage progress is a hard requirement; otherwise Option B is simpler.

## UI/UX the produced prompt must specify

Screens / flow:
1. **Upload** — project name + drawing image; show the drawing.
2. **Select symbols** — user draws boxes on the drawing (legend or any instance) to crop each symbol
   → produces the `templates[]` array (`type`, `label`, `template_base64` from the crop, tunable
   `threshold`). This is required because template matching needs templates.
3. **Run** — call the proxy; show the stage/progress tracker (per the chosen progress option) with a
   "warming up" state for cold starts and a clear `FAILED` state.
4. **Results** —
   - drawing canvas with **bounding-box overlays** (scale `[x,y,w,h]` from image_size to display size; responsive),
   - **line-item table** (label, quantity, unit_price, total, subtotal),
   - **proposal** text panel.
5. **Traceability (the wow feature)** — clicking a line item highlights that type's `boxes` on the
   drawing (and scrolls/zooms to them); hovering a box shows its type/confidence. Different symbol
   types get distinct colors.

Also require: loading/empty/error states; handling `status:"error"` and `FAILED` jobs; mobile-reasonable
layout; and a small "Runpod CPU endpoint · template-matching MVP" honesty badge.

## Output format the produced prompt must follow
Structure the final UI prompt as: Goal → Tech stack → API contract & proxy spec (verbatim) →
Progress design (state Option A or B) → Screen-by-screen spec → Box-overlay coordinate math →
Acceptance criteria. Make it copy-paste ready for a coding agent. Output ONLY that prompt.
