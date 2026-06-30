# FlashPod API front door -- single URL the frontend calls.
# run with: flash dev
#
# Grounded in:
#   - load-balanced Endpoint with HTTP routes (@api.get/@api.post):
#       reference/flash-examples/03_advanced_workers/05_load_balancer/gpu_lb.py
#   - cross-worker orchestration (import other workers, await them):
#       reference/flash-examples/01_getting_started/03_mixed_workers/pipeline.py
from runpod_flash import Endpoint

# CPU load balancer that orchestrates the GPU/CPU workers (it does no heavy work itself).
# Same shape as pipeline.py: Endpoint(... cpu=..., workers=(1, N)) + route decorators.
api = Endpoint(name="flashpod_api", cpu="cpu3c-1-2", workers=(1, 3))


@api.get("/health")
async def health() -> dict:
    """Health check (mirrors gpu_lb.py /health)."""
    return {"status": "healthy", "service": "flashpod-api"}


@api.post("/analyze")
async def analyze(data: dict) -> dict:
    """
    Full takeoff pipeline: detect symbols -> price -> proposal.

    Input (data):
        drawing_base64: str
        templates: list[dict]   - see takeoff_worker.detect
        run_ocr: bool (optional)

    Returns:
        line_items with counts + boxes + pricing, plus proposal_text.
        Boxes are passed straight through so the frontend can highlight per line item.
    """
    # Cross-worker imports + await -- exactly the pipeline.py pattern.
    from takeoff_worker import detect
    from pricing_worker import price
    from proposal_worker import build

    det = await detect(
        {
            "drawing_base64": data.get("drawing_base64"),
            "detector": data.get("detector", "template"),   # "yolo" | "template"
            "templates": data.get("templates") or [],
            "weights": data.get("weights", "electrical.pt"),
            "conf": data.get("conf", 0.25),
            "run_ocr": data.get("run_ocr", True),
        }
    )
    if det.get("status") != "success":
        return {"status": "error", "stage": "detect", "error": det.get("error")}

    priced = await price({"line_items": det["line_items"]})
    proposal = await build({"line_items": priced["line_items"]})

    return {
        "status": "success",
        "line_items": priced["line_items"],   # each: type, count, boxes, unit_price, total
        "subtotal": priced.get("subtotal"),
        "proposal_text": proposal.get("proposal_text"),
        "ocr": det.get("ocr", []),
        "image_size": det.get("image_size"),
    }


if __name__ == "__main__":
    import asyncio

    print("Health:", asyncio.run(health()))
    # /analyze needs the worker deps -> run under `flash dev`.
