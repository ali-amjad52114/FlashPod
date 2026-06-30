# Build prompt — FlashPod web UI (contract-aligned)

You are building the **FlashPod** web UI (React + TypeScript). Build the real application described
below — not a throwaway demo. A clickable prototype with mock data exists and is the reference for
look, feel, and feature scope; build the production version against the real Flash backend, preserving
that UX.

## Step 0 — Ground yourself in the real system first (do not skip)
Read these local files before writing code; if anything below contradicts them, the files win — flag it.
- `CLAUDE.md`, `README.md` — app, architecture, honest scope
- `takeoff_worker.py` — the actual endpoint; its input/output is the source of truth
- `reference/flash/docs/Flash_Deploy_Guide.md`, `Flash_SDK_Reference.md`, `Cross_Endpoint_Routing.md`, `Load_Balancer_Endpoints.md`
- `.agents/skills/flash/SKILL.md`
The raw Runpod HTTP job envelope is NOT fully quoted in these files — for exact `/run`, `/status`,
`/runsync` response shapes, cite **Runpod Serverless API docs** (https://docs.runpod.io). Do not invent
Flash behavior that contradicts the local files.

## Goal
An AI electrical-estimating tool. Upload an electrical drawing → the backend detects and counts
electrical symbols, prices materials, and produces a proposal. The signature feature is
**traceability**: clicking a proposal line ("Duplex Outlet — 42") highlights all 42 detected symbols
on the drawing and dims the rest. Flow: upload → select symbols → run → results → every number clicks
back to the drawing → export a proposal PDF.

**Honest scope (show in UI):** today's backend is OpenCV template matching on a Runpod Flash **CPU**
endpoint — no GPU, no trained model. Never imply more.

## Tech stack
- React + TypeScript; **Next.js preferred** (its Route Handlers give you the required server-side proxy).
- A thin **server-side proxy** (see Security). The React app never talks to Runpod directly.
- PDF client-side (`pdf-lib` or `jsPDF`).
- React state/hooks are enough; no global state lib.
- Quality floor: responsive to mobile, visible focus, `prefers-reduced-motion`, labeled icon controls.

## API contract & proxy spec (must match `takeoff_worker.py` — state verbatim)

**Request payload** (the user data):
```json
{ "project_name": "Office Electrical Takeoff",
  "image_base64": "<drawing PNG/JPG as base64>",
  "templates": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "template_base64": "<crop>", "threshold": 0.7 } ],
  "labor_pct": 35 }
```

**Worker result** (the dict the handler returns — see envelope note below for where it lands):
```json
{ "status": "success",
  "project_name": "Office Electrical Takeoff",
  "image_size": { "width": 1654, "height": 1169 },
  "detections":   [ { "type": "duplex_outlet", "label": "Duplex Outlet", "x": 420, "y": 310, "w": 24, "h": 24, "confidence": 0.91 } ],
  "priced_items": [ { "type": "duplex_outlet", "label": "Duplex Outlet", "quantity": 42, "unit_price": 4.25, "total": 178.50,
                      "boxes": [[420,310,24,24]], "price_source": "static", "pricing_asof": null } ],
  "totals": { "material_subtotal": 178.50, "labor_pct": 35, "labor_total": 62.48, "grand_total": 240.98 },
  "proposal": "FlashPod Electrical Proposal ...",
  "timestamp": "2026-06-30T..." }
```
- Boxes are `[x, y, w, h]` in **original image pixels**; scale to displayed size (see coordinate math).
- **Render the drawing overlays from `detections`** (they carry `confidence`, used on hover). Use
  `priced_items` for the table + per-type grouping; join the two by `type`.
- **All money comes from the backend** (`unit_price`, `total`, `totals`). The UI may expose a labor-%
  control that recomputes `labor_total = material_subtotal * pct/100` and `grand_total` **locally**
  (a policy formula only). It must NEVER recompute material `unit_price` — Bright Data owns those.
- **Provenance:** if `price_source === "brightdata"`, show "Live price · Bright Data" + `pricing_asof`
  date in the table/PDF; `"static"` → show "list price" (or nothing). Fields are null until Phase 7.

**Runpod envelope (CRITICAL — the proxy must handle this):**
```
POST  https://api.runpod.ai/v2/{ENDPOINT_ID}/run
      body: { "input": <Request payload above> }      ->  { "id": "...", "status": "IN_QUEUE" }
GET   https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{JOB_ID}
      ->  { "status": "IN_QUEUE|IN_PROGRESS|COMPLETED|FAILED|CANCELLED",
            "output": <Worker result above>,           // present when COMPLETED
            "error": "<message>" }                      // present when FAILED
Header on both: Authorization: Bearer <RUNPOD_API_KEY>
Sync alt (<=60s only): POST /v2/{ENDPOINT_ID}/runsync   (also returns { "status", "output" })
Local dev: POST http://localhost:8888/takeoff_worker/runsync   (body ALSO wrapped { "input": ... }; result ALSO under "output")
```
- **Two different `status` fields — do not confuse them:** the top-level Runpod **job** `status`
  (`IN_QUEUE → IN_PROGRESS → COMPLETED/FAILED`) drives the progress UI; the worker's
  **`output.status`** (`"success"`/`"error"`) is app-level. The real results live in `output`.
- Prefer `/run` + polling (cold starts can exceed the 60s `runsync` limit). Show a "warming up" state.

**Security — mandatory:** the `RUNPOD_API_KEY` must **never** ship in browser code. Implement a thin
server-side proxy (Next.js Route Handler / small Node server) holding secrets as server env vars:
- `RUNPOD_API_KEY`, `ENDPOINT_ID` (from `flash deploy`), and optional `FLASH_DEV_URL` (local-dev mode).
- Proxy endpoints: `POST /api/run` (starts a job; injects auth + `{"input": ...}` wrapping) and
  `GET /api/status/{jobId}` (polls; returns `{ jobStatus, output, error }` already unwrapped).
- The React app calls the proxy, never Runpod.

## Progress design — Option B (honest), state it in code + subtly in UI
Flash exposes no intra-job stage progress (no SSE, no in-handler events); one job returns only the
final result. So:
- One `/run` job; the stage tracker reflects the **real job lifecycle** (`IN_QUEUE` → `IN_PROGRESS` →
  `COMPLETED`). Show a distinct **"warming up — cold start"** state during `IN_QUEUE`/first
  `IN_PROGRESS`, and a clear `FAILED` state (with the `error` and a retry).
- The internal stages (Detect → Price → Proposal) are shown as labeled steps that **complete together**
  when the single job finishes — labeled honestly as such. Do NOT animate fake per-stage completion.
- *(Comment only)* Option A upgrade: split into `detect → price → proposal` endpoints called in
  sequence by the proxy for genuine per-stage progress; implement only if it becomes a hard requirement.

## Design language (match the prototype)
A precise estimating instrument, not a generic SaaS dashboard. Spend boldness only on the traceability
interaction; keep everything else quiet.
- **Tokens:** workspace `#EAEDF1`, panels `#FFFFFF`, sheet `#FBFCFD`, ink `#16191D`, secondary `#5A636E`,
  hairline `#D8DEE6`, primary accent `#2D5BFF`. **Functional symbol-type colors** reused everywhere a
  type appears (legend, table chip, box, PDF swatch), stable per `type`: duplex outlet `#E8833A`,
  light fixture `#7C5CFF`, switch `#159C8C`, panel `#E0475B`, junction box `#3B82C4`. Assign a stable
  color per new `type` the backend reports.
- **Type:** clean sans for prose/labels; **monospace for all data** (quantities, prices, confidence,
  coordinates, proposal figures) — the mono numerals are the "instrument" signature.
- The **drawing is the hero** on Results (larger pane; table/proposal beside it).
- Restrained motion: subtle pulse ring on highlighted symbols; spinner only during cold-start. Respect reduced-motion.
- **Honesty badge** always visible in the top bar (e.g. "Runpod CPU endpoint · template-match MVP").
- Active-voice, end-user copy ("Run takeoff", "Create PDF", "Adjust symbols"). Errors explain what
  happened + how to fix; empty states invite the next action.

## Screens
**Top bar (persistent):** FlashPod wordmark, step indicator (Upload · Symbols · Run · Results), a Jobs
button with count badge, the honesty badge.

1. **Upload** — project-name field + drawing upload (drag-drop/picker, PNG/JPG). Show the drawing + its
   dimensions. Encode to base64 for the payload. "Next: pick symbols" disabled until a drawing loads.
2. **Select symbols** — the user draws a box on the drawing (legend or any instance) to crop each
   symbol; each crop becomes a `templates[]` entry `{ type, label, template_base64, threshold }`.
   Per-template threshold slider (default 0.7) and a name/label field. Required — matching needs
   templates. "Run takeoff" disabled until ≥1 template exists. (Optional: a labor-% input, default 35.)
3. **Run** — call `/api/run`, then poll `/api/status/{jobId}`. Stage tracker per Option B: real
   lifecycle, "warming up (cold start)" state, labeled steps resolving together, explicit `FAILED`
   (with `error` + retry). Also handle `output.status === "error"` distinctly from network/`FAILED`.
4. **Results** —
   - Drawing canvas with **bounding-box overlays from `detections`** (scale `[x,y,w,h]` by
     `image_size`; responsive). Distinct color per `type`.
   - **Line-item table** from `priced_items`: label, quantity, unit_price, total; then `totals`
     (material_subtotal, labor (labor_pct%), grand_total) — all monospaced, all from the backend.
   - **Proposal panel** (tabbed with the table): styled proposal + **Create PDF**. Bottom actions:
     **Adjust symbols** and **Create PDF** (no "send to scheduler").
   - **Traceability:** clicking a line item highlights that type's symbols (others dim to ~15% +
     desaturate), subtle pulse, scroll/zoom into view, and highlights the row. Clicking a box selects
     its type (and row). Hovering a box shows type + `confidence`. Empty-canvas click clears. Show a
     "showing N of M — {type}" chip with a clear button.

**Jobs view** — history of completed runs: project name, date, status pill, symbol count, grand_total.
Click → reopen that run's Results. Persist client-side, but **do NOT store the base64 drawing in
`localStorage`** (≈5MB quota — it will overflow). Store run metadata + results in `localStorage`, and
put the image in **IndexedDB** (or omit the image from history and re-upload to view boxes). Note
`/api/jobs` server store as the upgrade. List starts empty with an inviting empty state.

**Global:** loading/empty/error states everywhere; distinguish network error vs `FAILED` job vs
`output.status: "error"`; Results stacks vertically on mobile (drawing on top, panel below).

## Box-overlay coordinate math
Compute overlay positions from the **rendered** image size, not assumed dimensions:
```
scale  = renderedImageWidth / image_size.width      // === renderedImageHeight / image_size.height
left   = box.x * scale ; top = box.y * scale ; width = box.w * scale ; height = box.h * scale
```
Recompute on resize via `ResizeObserver`. **Recommended:** render the drawing in an SVG whose `viewBox`
is `0 0 image_size.width image_size.height` and place boxes in image-pixel coords — they scale for free.

## Create PDF — engineering-proposal layout
Downloadable, print-ready (one-page Letter base; paginate large takeoffs). Driven by the **real
`priced_items` + `totals`** (prefer the worker's `proposal` text where it fits, but structured
table/totals take precedence):
- **Letterhead:** FlashPod wordmark + "ELECTRICAL ESTIMATING", thin accent rule, right block: "PROPOSAL",
  a stable proposal number per job, the date.
- **Meta grid:** Project, Prepared for, Sheet, Date + a one-line scope statement.
- **Takeoff table:** banded header (ITEM / QTY / UNIT PRICE / AMOUNT), a color swatch per row matching
  the symbol-type color, right-aligned monospace numerics, zebra rows; show price provenance when present.
- **Totals:** material_subtotal, labor (labor_pct%), ruled divider, emphasized **GRAND TOTAL (USD)** in
  the accent color — all from `totals`.
- **Notes & terms:** numbered clauses (budgetary basis, verify quantities before bid, labor
  assumptions/exclusions, validity).
- **Signature block:** "Prepared by" / "Accepted by" with signature/date lines.
- **Footer:** contact line, page marker, and the honest "counts via template matching — verify before
  issuing for bid" disclaimer.
- Filename: sanitized project name. TODOs (don't block MVP): company logo, marked-up drawing as page 2,
  multi-page flow.

## Acceptance criteria
1. No `RUNPOD_API_KEY` in client-shipped code; all Runpod calls go through the proxy, which injects auth
   + the `{"input": ...}` wrapper and **unwraps `output`**.
2. Upload → Symbols → Run → Results works end to end against a deployed endpoint and the local dev route.
3. Run uses `/run` + status polling; shows a cold-start "warming up" state; surfaces `FAILED` (top-level)
   and `output.status: "error"` distinctly from network errors, with the message + retry.
4. Progress is honest (Option B): tracker reflects the real job lifecycle; stages labeled as resolving together.
5. Box overlays align to the drawing at any container size (verified after resize) via rendered-size math.
6. Overlays come from `detections` (hover shows confidence); table from `priced_items`; joined by `type`;
   stable color per type across drawing, table, and PDF.
7. Traceability both ways: line item → highlight+dim+scroll; box → select type + row; empty click → clear.
8. Money is backend-driven: `unit_price`/`total`/`totals` displayed as returned; labor-% control (if shown)
   only recomputes labor/grand totals locally, never material prices; provenance shown when present.
9. Jobs view persists across reloads WITHOUT putting base64 drawings in `localStorage`; reopening restores Results.
10. Create PDF downloads a valid PDF matching the layout, driven by real `priced_items` + `totals`.
11. Honesty badge present; active-voice copy; empty/loading/error states on every screen; responsive,
    keyboard-focusable, reduced-motion respected.

Build cleanly; comment the proxy, the envelope-unwrapping, and the Option-B progress choice. Keep the
design quiet everywhere except the traceability moment.
