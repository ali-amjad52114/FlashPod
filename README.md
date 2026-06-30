# FlashPod — Runpod Flash hackathon starter

Python-first serverless GPU on [Runpod Flash](https://docs.runpod.io/flash/quickstart).
No Dockerfile, no image to manage — declare GPU + deps in Python, Flash runs it.

## Setup (done)

- `.venv` on **Python 3.12** (Flash GPU workers run 3.12; your system 3.14 won't work, so this is pinned)
- `runpod-flash` 1.17.0 + `python-dotenv` installed

## ⚠️ Windows note (already fixed, but know why)

Flash isn't officially Windows-supported, and the CLI prints emoji/box-drawing
output that **crashes on Windows' default cp1252 console** with
`UnicodeEncodeError: 'charmap' codec can't encode`. Verified fix: run Python in
UTF-8 mode. This repo's machine now has a **persistent** `PYTHONUTF8=1` user env
var set (`setx PYTHONUTF8 1`), so any new terminal is fine. If you ever see that
crash on another machine, run `setx PYTHONUTF8 1` and open a fresh terminal.
Verified working on Windows: `flash --version`, `flash init`, scaffold + symlink
creation. Auth is done via `.env` (`RUNPOD_API_KEY`), so `flash login`'s browser
flow is not needed. Key is **valid** (checked); the only remaining gap is a **$0
Runpod balance** — add credits before `flash deploy`.

## Files (flat-file workers, mirroring flash-examples conventions)

Each worker is a standalone file with one `@Endpoint async def handler(input_data: dict) -> dict`,
auto-discovered by `flash dev`. This matches `reference/flash-examples/` exactly.

| File | Mirrors | What it is |
|------|---------|------------|
| `gpu_worker.py` | `01_hello_world` | GPU detection — your "is it working" check. Route: `/gpu_worker/runsync` |
| `embeddings_worker.py` | `02_ml_inference` | Real ML: batch text → embeddings (BAAI/bge-small) for semantic search/RAG. Route: `/embeddings_worker/runsync` |
| `brightdata_demo.py` | `03_mixed_workers/pipeline.py` | Imports & awaits `embed` — Bright Data scrape → embed → cosine rank. The venue pairing. |
| `load_test.py` | `04_scaling_performance/01_autoscaling` | 4-phase warm/burst/pause/burst load test — **the autoscaling demo tool.** |
| `scripts/check_account.py` | — | Validate API key + read Runpod balance (no GPU, no cost). |

**Project ideas:** see [IDEAS.md](IDEAS.md). **Account balance is $0** — get Runpod credits before deploying.

## Tomorrow morning, in order

1. **Confirm auth + balance** (key already in `.env`):
   ```bash
   uv run python scripts/check_account.py     # need clientBalance > 0 to deploy
   ```
2. **Local-test a handler** without touching the cloud (runs the `__main__` block; note: heavy
   deps like torch only exist on the worker, so full local runs need `flash dev`):
   ```bash
   uv run flash dev                            # serves all workers at localhost:8888/docs
   ```
   Then open http://localhost:8888/docs, or:
   ```bash
   curl -X POST http://localhost:8888/gpu_worker/runsync -H "Content-Type: application/json" -d '{"message":"hi"}'
   ```
3. **Show autoscaling** (with `flash dev` running in another terminal):
   ```bash
   uv run python load_test.py --requests 30 --concurrency 12
   ```
4. **Deploy for real** when ready:
   ```bash
   uv run flash deploy
   ```

## API cheat-sheet (verified against 1.17.0)

```python
from runpod_flash import Endpoint, GpuType, GpuGroup

@Endpoint(
    name="my_worker",
    gpu=GpuType.NVIDIA_GEFORCE_RTX_4090,   # or GpuGroup.ADA_24 / AMPERE_80 / HOPPER_141 ...
    workers=(0, 3),                        # (min, max); min=0 => scale to zero => no idle cost
    idle_timeout=300,                      # seconds
    dependencies=["sentence-transformers"],   # pip-installed on the worker
)
async def my_worker(input_data: dict) -> dict:   # dict in, dict out
    import torch                                  # remote-dep imports go INSIDE the body
    return {"status": "success"}
```

- Run locally: `flash dev` (auto-discovers workers → `/<filename>/runsync`). Deploy: `flash deploy`.
- Other params: `volume` (NetworkVolume for weight caching), `system_dependencies` (apt), `env`,
  `flashboot`, `max_concurrency`, `gpu_count`. CPU + HTTP routing also exist (`cpu=`, `@api.post`).
- Manage: `uv run flash undeploy list` · `uv run flash undeploy <name>`

## Demo strategy (what wins)

- **Show the superpower live.** Run `load_test.py` against your endpoint with the Runpod console
  next to it — judges *see* workers spin 0→N and the cold-vs-warm latency gap. That's the story.
- **Lead with scale-to-zero cost.** "min=0 means we pay nothing idle, burst to N GPUs on demand."
  Cost awareness is on the judging rubric.
- **Pair with Bright Data** — real scrape feeding real GPU inference covers the bonus categories.
- **One workload, deep.** Swap the `embed` body for Whisper / captioning / SDXL — same structure.
- **Have a fallback.** `brightdata_demo.py` keeps a sample-data path so a live hiccup never blanks the screen.
