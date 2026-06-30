# FlashPod — project concepts

Picked for one thing: each **visibly needs** auto-scaling GPU, so the demo *shows*
Flash's superpower instead of asserting it. All four pair with Bright Data (the venue's
happy path) and map onto the starter in `src/`.

Judging signals to hit in every demo: **scale-to-zero cost**, **workers climbing under
load** (Runpod console next to terminal), **flat wall-clock as data grows**, **a real
workflow** (scrape -> process -> usable output), not a toy.

---

## 1. "Ask the freshly-scraped web" — semantic search / RAG  ⭐ recommended primary

**What:** Bright Data scrapes N live pages (listings, docs, news) → Flash embeds them on
GPU (this is literally `src/fanout.py`) → a query ranks results by similarity
(`src/brightdata_demo.py`). Optionally feed top-k into an LLM for a cited answer.

**Why it wins:** lowest risk — it's your starter, already built. Clean story: "fresh data,
embedded in parallel, searchable in seconds." Embedding thousands of docs is the obvious
GPU-fan-out case.

**Stack:** `sentence-transformers` (BAAI/bge-small) → embeddings; cosine rank; optional
LLM endpoint for synthesis. NetworkVolume caches the model.

**Demo beat:** scrape a category live, type a natural-language query, show ranked hits.
Then 10× the doc count and show wall-clock barely move as workers scale.

**Scope:** ✅ achievable solo in a day. The risky part (Flash plumbing) is done.

---

## 2. Bulk media transcription + search (Whisper)  ⭐ best "GPU obviously needed" demo

**What:** collect audio/video URLs at scale (podcasts, earnings calls, YouTube) → Flash
Whisper fan-out transcribes them in parallel → searchable transcript index (reuse #1's
embeddings for semantic search over transcripts).

**Why it wins:** Whisper is unambiguously GPU-bound and slow serially — a backlog of 20
clips finishing in roughly the time of one is a *jaw-drop* fan-out moment. Strong cost
story: scale to zero between batches.

**Stack:** `faster-whisper` or `openai-whisper` on GpuGroup.ADA_24; class endpoint loads
the model once; NetworkVolume caches weights.

**Demo beat:** drop 20 audio URLs, watch workers spin 0→N in the console, transcripts
stream back; then search across all of them.

**Scope:** ✅ solo-doable. Main risk: audio fetch/format handling — keep a few known-good
sample files as fallback.

---

## 3. Visual product intelligence (CLIP/BLIP)

**What:** Bright Data scrapes product images at scale → Flash runs CLIP embeddings + BLIP
captions on GPU → visual dedup ("same product, different sellers"), "find similar",
catalog enrichment.

**Why it wins:** vision models = clear GPU need; "find visual duplicates across 500
scraped listings" is a tangible business workflow. Differentiated from text-only entries.

**Stack:** `transformers` + CLIP/BLIP; image embeddings; cosine for dedup/similarity.

**Demo beat:** scrape a product category, surface near-duplicate images across different
sellers / flag mispriced identical items.

**Scope:** ⚠️ moderate — image pipeline + dedup logic. Doable but tighter than #1/#2.

---

## 4. On-demand batch image generation (SDXL)  — pure Flash showcase

**What:** queue many prompts → Flash fans out SDXL across workers → gallery fills in.
This is the `SimpleSD` example pattern, scaled.

**Why it wins:** the most visceral "scale-up" demo — a wall of images materializing as
workers spin up. Weakest Bright Data tie-in, so lean on it for a bonus/creative category.

**Stack:** `diffusers` SDXL on GpuGroup.ADA_48_PRO+; class endpoint + NetworkVolume
(weights are large — caching matters most here).

**Demo beat:** submit 50 prompts, watch the gallery and the worker count grow together.

**Scope:** ⚠️ model size + VRAM + cold starts. Highest infra risk; NetworkVolume is
mandatory, not optional.

---

## My recommendation

**Build #1 as the spine** (it's done) and **bolt on #2 (Whisper)** if time allows — together
they're "scrape → transcribe → embed → search," a complete pipeline that hammers every
judging signal. Pitch with the 4-phase `load_test.py` (from `reference/flash-examples`)
pointed at your endpoint so the autoscaling story tells itself.

Avoid spreading thin across multiple ideas — one deep, working pipeline beats four demos
that half-run.
