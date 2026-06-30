# FlashPod frontend

React + TypeScript (Vite) UI for FlashPod electrical takeoff. **Talks to the FastAPI backend
(`../backend`), not Runpod directly** — the backend holds `RUNPOD_API_KEY` + Bright Data config,
calls the Runpod worker, overlays live prices, and persists takeoffs.

## Run

```bash
# 1) start the backend first (see ../backend)
cd ../backend && uvicorn app.main:app --reload      # serves http://localhost:8000

# 2) start the frontend
cd ../frontend
cp .env.example .env        # VITE_API_URL defaults to http://localhost:8000
npm install
npm run dev                 # http://localhost:5173
```

## Flow (aligned to the backend contract)

`Upload → Symbols → Run → Results`

1. **Upload** — `POST /projects` then `POST /projects/{id}/drawings` (multipart; no base64 in the UI).
2. **Symbols** — draw a box on the drawing to crop each symbol; each crop is uploaded via
   `POST /projects/{id}/templates` (multipart `sym_type,label,threshold,file`).
3. **Run** — `POST /projects/{id}/takeoff {drawing_id}`. This **blocks** until the worker finishes +
   Bright Data overlay (cold start ~30–120 s); the UI shows an honest "warming up" state. No job
   polling (the backend takeoff is synchronous).
4. **Results** — `TakeoffOut` drives everything: SVG box overlays from `detections` (scaled via
   `viewBox`), a line-item table from `priced_items` (with `price_source` provenance + live-price
   links), and the proposal. Click a line item → highlight that type on the drawing (and back).
   Manual edits call `PATCH /takeoffs/{id}/items/{sym_type}` (`price_source: "manual"`).

## Notes / honest scope
- **Money is backend-owned.** The UI sums backend line `total`s for the material subtotal and shows
  `unit_price`/`total` as returned. **Labor** is a clearly-labeled UI estimate (% of material) because
  the backend prices materials only — adjust the % in the table.
- **PDF is client-side** (`jsPDF`) because the backend's `/proposal/export` is a 501 stub. Swap to the
  server endpoint once implemented.
- **Jobs history** keeps a tiny local index of takeoff IDs (no base64 → no quota issue) and rehydrates
  from `GET /takeoffs/{id}`. Upgrade: a backend list-takeoffs endpoint.
- Honesty badge ("Runpod CPU endpoint · template-match MVP") is always visible.

## Structure
- `src/api.ts` — typed client for the FastAPI backend
- `src/types.ts` — mirrors `backend/app/models.py`
- `src/components/*` — TopBar, Upload, Symbols (crop), Run, Results, DrawingCanvas, LineItemTable, ProposalPanel, JobsView
- `src/pdf.ts` — client-side proposal PDF · `src/lib.ts` — colors, totals, formatting
