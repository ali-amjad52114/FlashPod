# FlashPod -- GPU vision-detection endpoint (Qwen2.5-VL) for electrical takeoff.
# run with: flash dev   (route: /detect_symbols/runsync)
#
# This is the "Future / GPU" detector from the architecture diagram: instead of
# OpenCV template matching (takeoff_worker.py), a vision LLM reads the drawing and
# locates electrical symbols semantically -- no template crops required.
#
# Flash wiring grounded in the skill (.agents/skills/flash/SKILL.md):
#   - Mode 1 (queue-based decorator) on an async GPU function.
#   - Gotcha #1: ONLY the body ships under `flash dev`, so EVERY import/constant/
#     helper lives INSIDE the body.
#   - The 16GB model is loaded ONCE per warm worker via a runtime globals() cache
#     (standard Python process memory -- persists across invocations on a warm
#     worker; this is NOT a shipped module global, so Gotcha #1 does not apply).
#   - NetworkVolume holds the HuggingFace cache so weights download once, not per
#     cold start (mount path /runpod-volume per the skill's dev-loop fixture).
import os

from runpod_flash import DataCenter, Endpoint, GpuGroup, NetworkVolume

# Search every datacenter for GPU supply (module-level constant is fine in a
# decorator arg — Gotcha #1 only applies to the function body). Maximizes the
# chance of finding an available GPU when one region is out of stock.
ALL_DATACENTERS = [
    DataCenter.US_CA_2, DataCenter.US_IL_1, DataCenter.US_KS_2, DataCenter.US_MO_1,
    DataCenter.US_MO_2, DataCenter.US_NC_2, DataCenter.US_NE_1, DataCenter.US_WA_1,
    DataCenter.EU_CZ_1, DataCenter.EU_RO_1, DataCenter.EUR_NO_1,
]


@Endpoint(
    name="flashpod-detect-vl",
    gpu=GpuGroup.ADA_24,             # RTX 4090 24GB -- most-available Runpod serverless GPU; fits the 3B VLM
    workers=(1, 1),                  # one warm GPU worker (bills while up -> undeploy when done)
    dependencies=[
        "torch", "torchvision",
        "transformers>=4.49.0",      # Qwen2.5-VL support landed in 4.49
        "accelerate", "qwen-vl-utils", "pillow",
    ],
    volume=NetworkVolume(name="flashpod-hf-cache", size=100),
    env={"HF_HOME": "/runpod-volume/hf"},   # persist model weights across cold starts
    datacenter=ALL_DATACENTERS,             # search all regions for GPU supply
)
async def detect_symbols(payload: dict) -> dict:
    """
    Input:
        project_name: str
        image_base64: str                 - the drawing (PNG/JPG) as base64
        symbols: list[dict] (optional)     - catalog to look for, each:
            { "type": str, "label": str, "desc": str }   (desc helps the VLM)
        max_long_side: int (optional, 1568) - resize cap fed to the model

    Output: same contract as takeoff_worker.py
        detections, priced_items, proposal, meta, image_size, project_name
    """
    import base64
    import json
    import re
    from datetime import datetime
    from io import BytesIO

    import torch
    from PIL import Image
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"   # 3B fits a 24GB GPU; bump to 7B on a 48/80GB card

    # --- constants/helpers INSIDE the body (Gotcha #1) ---
    PRICE_TABLE = {
        "duplex_receptacle": 4.25, "gfci_receptacle": 18.75, "data_outlet": 12.00,
        "tv_outlet": 9.50, "switch": 3.25, "light": 45.00, "smoke_detector": 22.00,
    }
    DEFAULT_LABELS = {
        "duplex_receptacle": "Duplex Receptacle", "gfci_receptacle": "GFCI Receptacle",
        "data_outlet": "Data Outlet", "tv_outlet": "TV Outlet",
        "switch": "Single-Pole Switch", "light": "Ceiling Light Fixture",
        "smoke_detector": "Smoke Detector",
    }
    DEFAULT_CATALOG = [
        {"type": "duplex_receptacle", "desc": "blue circle with two vertical bars"},
        {"type": "gfci_receptacle", "desc": "red circle with two vertical bars, 'GFI' label"},
        {"type": "data_outlet", "desc": "green square with letter 'D'"},
        {"type": "tv_outlet", "desc": "purple square with 'TV'"},
        {"type": "switch", "desc": "orange circle with letter 'S'"},
        {"type": "light", "desc": "circle with an X inside (crossed circle)"},
        {"type": "smoke_detector", "desc": "circle with 'SD' inside"},
    ]
    DEFAULT_UNIT_PRICE = 5.00

    # --- load model ONCE per warm worker (runtime process cache) ---
    g = globals()
    if "_VL_MODEL" not in g:
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            MODEL_ID, torch_dtype=torch.bfloat16,
            attn_implementation="sdpa", device_map="auto",
        )
        model.eval()
        processor = AutoProcessor.from_pretrained(MODEL_ID)
        g["_VL_MODEL"], g["_VL_PROC"] = model, processor
    model, processor = g["_VL_MODEL"], g["_VL_PROC"]

    # --- 1. validate + decode ---
    project_name = payload.get("project_name", "Electrical Takeoff")
    image_b64 = payload.get("image_base64")
    if not image_b64:
        return {"status": "error", "error": "Provide 'image_base64'."}

    catalog = payload.get("symbols") or DEFAULT_CATALOG
    labels = {s["type"]: s.get("label", DEFAULT_LABELS.get(s["type"], s["type"])) for s in catalog}
    valid_types = set(labels)

    try:
        img = Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGB")
        W0, H0 = img.size

        # --- resize to a controlled, 28-divisible size; remember scale to map boxes back ---
        max_long = int(payload.get("max_long_side", 1568))
        scale = min(1.0, max_long / max(W0, H0))
        Wr = max(28, round(W0 * scale / 28) * 28)
        Hr = max(28, round(H0 * scale / 28) * 28)
        img_r = img.resize((Wr, Hr), Image.LANCZOS)
        sx, sy = W0 / Wr, H0 / Hr   # resized-space -> original-space

        # --- 2. detect symbols (Qwen2.5-VL grounding) ---
        catalog_txt = "\n".join(f"- {s['type']}: {s['desc']}" for s in catalog)
        prompt = (
            f"This is an electrical floor plan, {Wr}x{Hr} pixels. "
            "Find EVERY electrical symbol on the plan (not the legend or schedule table). "
            f"Symbol types to detect:\n{catalog_txt}\n\n"
            "Return ONLY a JSON array, no prose. Each element must be exactly: "
            '{"type": "<one type key above>", "bbox_2d": [x1, y1, x2, y2]} '
            "with integer pixel coordinates. List every single occurrence."
        )
        messages = [{"role": "user", "content": [
            {"type": "image", "image": img_r},
            {"type": "text", "text": prompt},
        ]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                           padding=True, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**inputs, max_new_tokens=8192, do_sample=False)
        trimmed = [o[len(i):] for i, o in zip(inputs.input_ids, gen)]
        raw = processor.batch_decode(trimmed, skip_special_tokens=True,
                                     clean_up_tokenization_spaces=False)[0]

        # --- parse: salvage each {…} object independently, tolerating a truncated
        # or malformed array tail (the VLM can emit 140+ items and run long, and a
        # single bad entry must not drop the whole detection set). ---
        rows = []
        for obj in re.findall(r"\{[^{}]*\}", raw, re.DOTALL):
            try:
                rows.append(json.loads(obj))
            except Exception:
                continue
        detections = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            t = r.get("type") or r.get("label")
            box = r.get("bbox_2d") or r.get("bbox")
            if t not in valid_types or not box or len(box) != 4:
                continue
            x1, y1, x2, y2 = box
            X1, Y1, X2, Y2 = sorted([x1, x2])[0] * sx, sorted([y1, y2])[0] * sy, \
                sorted([x1, x2])[1] * sx, sorted([y1, y2])[1] * sy
            detections.append({
                "type": t, "label": labels[t],
                "x": int(X1), "y": int(Y1),
                "w": int(X2 - X1), "h": int(Y2 - Y1),
                "confidence": 1.0,   # VLM gives no score; placeholder
            })

        # --- 3 + 4. count + price (static PRICE_TABLE) ---
        priced_items = []
        subtotal = 0.0
        types_in_order = []
        for d in detections:
            if d["type"] not in types_in_order:
                types_in_order.append(d["type"])
        for sym_type in types_in_order:
            grp = [d for d in detections if d["type"] == sym_type]
            qty = len(grp)
            unit = float(PRICE_TABLE.get(sym_type, DEFAULT_UNIT_PRICE))
            total = round(unit * qty, 2)
            subtotal += total
            priced_items.append({
                "type": sym_type, "label": grp[0]["label"], "quantity": qty,
                "unit": "ea", "unit_price": unit, "total": total,
                "price_source": "static",
                "boxes": [[d["x"], d["y"], d["w"], d["h"]] for d in grp],
            })

        # --- 5. proposal ---
        lines = [f"FlashPod Electrical Proposal — {project_name}",
                 f"Date: {datetime.now():%Y-%m-%d}", "",
                 f"{'Item':<22}{'Qty':>6}{'Unit':>12}{'Total':>14}", "-" * 54]
        for it in priced_items:
            lines.append(f"{it['label']:<22}{it['quantity']:>6}{it['unit_price']:>12.2f}{it['total']:>14.2f}")
        lines.append("-" * 54)
        lines.append(f"{'SUBTOTAL':<40}{round(subtotal, 2):>14.2f}")

        return {
            "status": "success",
            "project_name": project_name,
            "detector": "qwen2.5-vl-7b",
            "detections": detections,
            "priced_items": priced_items,
            "proposal": "\n".join(lines),
            "meta": {"image_width": W0, "image_height": H0, "total_symbols": len(detections)},
            "image_size": {"width": W0, "height": H0},
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "trace": traceback.format_exc()[-1500:]}
