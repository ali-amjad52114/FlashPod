"""HTTP client for the Runpod Flash endpoint.

Reads RUNPOD_API_KEY and RUNPOD_ENDPOINT_URL from the environment.
RUNPOD_ENDPOINT_URL defaults to the `flash dev` local server URL so
the backend works out-of-the-box when running `uv run flash dev` alongside it.
"""

import base64
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

RUNPOD_API_KEY: str = os.getenv("RUNPOD_API_KEY", "")
# flash dev route: /takeoff_worker/runsync  (file-namespaced by Flash)
RUNPOD_ENDPOINT_URL: str = os.getenv(
    "RUNPOD_ENDPOINT_URL",
    "http://localhost:8888/takeoff_worker/runsync",
)
# Workers can be cold — give them up to 120 s to warm up and respond.
TIMEOUT: float = float(os.getenv("RUNPOD_TIMEOUT", "120"))


async def call_analyze_drawing(
    project_name: str,
    image_path: Path,
    templates: list[dict],
) -> dict:
    """Build the Runpod payload and POST to the analyze_drawing endpoint.

    Args:
        project_name: project label forwarded to the worker.
        image_path: local path to the drawing file.
        templates: list of dicts with keys sym_type, label, filepath, threshold.

    Returns:
        The JSON response from the worker:
        { status, project_name, detections, priced_items, proposal, image_size, timestamp }

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx from the worker.
        httpx.TimeoutException: if the worker doesn't respond in TIMEOUT seconds.
    """
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()

    template_payloads = []
    for t in templates:
        tpl_b64 = base64.b64encode(Path(t["filepath"]).read_bytes()).decode()
        template_payloads.append(
            {
                "type": t["sym_type"],
                "label": t["label"],
                "template_base64": tpl_b64,
                "threshold": float(t.get("threshold", 0.7)),
            }
        )

    payload = {
        "project_name": project_name,
        "image_base64": image_b64,
        "templates": template_payloads,
    }

    headers: dict[str, str] = {}
    if RUNPOD_API_KEY:
        headers["Authorization"] = f"Bearer {RUNPOD_API_KEY}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(RUNPOD_ENDPOINT_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return _unwrap(resp.json())


def _unwrap(data: dict) -> dict:
    """Return the worker's result dict regardless of which runtime answered.

    - ``flash dev`` returns the worker's dict directly.
    - A deployed Runpod serverless endpoint wraps it:
      ``{ "status": "COMPLETED", "output": {<worker dict>} }`` on success, or
      ``{ "status": "FAILED", "error": "..." }`` on failure.

    This normalizes both so the rest of the backend always sees the worker shape
    (``{ status, detections, priced_items, proposal, ... }``).
    """
    if not isinstance(data, dict):
        return {"status": "error", "error": f"Unexpected worker response: {data!r}"}

    status = data.get("status")

    # Runpod serverless envelope: result lives under "output".
    if "output" in data and isinstance(data["output"], dict):
        return data["output"]

    # Runpod job-level failure (no output produced).
    if status in {"FAILED", "CANCELLED", "TIMED_OUT"}:
        return {
            "status": "error",
            "error": data.get("error") or f"Runpod job {status}",
        }

    # flash dev / already-unwrapped worker dict.
    return data
