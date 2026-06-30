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

## Flow — 3 pages (`Project → Review → Proposal`)

1. **Project / Upload** — start a takeoff (`POST /projects` + `POST /projects/{id}/drawings`,
   multipart) or **Use mock drawing** (a client-side synthetic drawing + detections, so the app is
   demoable with no live worker). Existing proposals show as cards (from the local job index).
   Symbol-example cropping is a **compact modal** (`POST /projects/{id}/templates`), not a page.
2. **Detect & Review** — `POST /projects/{id}/takeoff {drawing_id}` (blocks; honest "warming up"
   state, no faked per-stage progress). Then a **Detection Inspector**: click boxes, retype, exclude
   false positives, restore, add missed devices (draw a box), and adjust unit prices. Edits live in
   a local **review model** derived from `detections` + `priced_items`; price confirms call
   `PATCH /takeoffs/{id}/items/{sym_type}`.
3. **Quantity Takeoff & Proposal** — clean table + proposal sections (Scope, Quantity Takeoff,
   Material Pricing, Assumptions, Exclusions, Estimated Total) with material subtotal + contingency.
   Export **PDF / CSV / JSON**. Traceability everywhere: click a row/Trace → highlight that type.

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
