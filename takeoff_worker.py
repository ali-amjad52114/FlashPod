# FlashPod -- single Runpod Flash endpoint for electrical-drawing takeoff.
# run with: flash dev   (route: /takeoff_worker/runsync)
#
# MVP design (honest): ONE CPU endpoint runs the whole pipeline inline --
#   decode -> detect symbols (OpenCV template matching) -> count -> price -> proposal.
# No GPU and no trained model today; the architecture is ready to move detection to a
# GPU endpoint with a fine-tuned vision model in production.
#
# Flash wiring grounded in the reference examples + official skill (.agents/skills/flash):
#   - @Endpoint(name=..., cpu=..., workers=..., dependencies=[...]) on an async function (QB mode)
#   - SKILL Gotcha #1: ONLY the function body ships under `flash dev`, so ALL imports,
#     constants, and helpers live INSIDE the body (a module-level name would NameError remotely).
from runpod_flash import Endpoint


@Endpoint(
    name="flashpod-takeoff",
    cpu="cpu5c-4-8",            # 4 vCPU / 8GB -- enough for OpenCV template matching
    workers=(1, 1),            # keep 1 worker warm -> no cold start during the demo
    dependencies=["opencv-python", "pillow", "numpy", "requests"],
)
async def analyze_drawing(payload: dict) -> dict:
    """
    Input:
        project_name: str
        image_base64: str                     - the drawing (PNG/JPG) as base64
        templates: list[dict] (optional)      - symbol crops to match, each:
            { "type": str, "label": str, "template_base64": str, "threshold": float? }
        labor_pct: float (optional, default 35) - labor as a % of material subtotal

    Output:
        detections:   [{ type, label, x, y, w, h, confidence }]   - one per detected symbol
        priced_items: [{ type, label, quantity, unit_price, total, boxes,
                         price_source, pricing_asof }]            - grouped + priced (+ provenance)
        totals:       { material_subtotal, labor_pct, labor_total, grand_total }
        proposal:     str                                          - formatted proposal text
        project_name, image_size, timestamp

    Note: when called over HTTP, Runpod nests this whole dict under `output`
    (alongside a top-level job status). The frontend uses detections for the canvas
    (they carry confidence) and priced_items[].boxes per type for the highlight feature.
    """
    import base64
    from datetime import datetime
    from io import BytesIO

    import cv2
    import numpy as np
    from PIL import Image

    # --- constants/helpers live INSIDE the body (SKILL Gotcha #1) ---
    PRICE_MAP = {
        "duplex_outlet": 4.25,
        "gfci_outlet": 18.50,
        "data_drop": 12.00,
        "switch": 3.25,
        "light": 45.00,
        "panel": 320.00,
    }
    LABELS = {
        "duplex_outlet": "Duplex Outlet",
        "gfci_outlet": "GFCI Outlet",
        "data_drop": "Data Drop",
        "switch": "Switch",
        "light": "Light Fixture",
        "panel": "Panel",
    }
    DEFAULT_UNIT_PRICE = 5.00

    def decode_gray(b64: str) -> "np.ndarray":
        raw = base64.b64decode(b64)
        pil = Image.open(BytesIO(raw)).convert("L")   # Pillow load -> grayscale
        return np.array(pil)

    def nms(boxes, scores, iou_thresh=0.3):
        if not boxes:
            return []
        b = np.array(boxes, dtype=float)
        x1, y1 = b[:, 0], b[:, 1]
        x2, y2 = b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = np.argsort(scores)[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            order = order[1:][iou < iou_thresh]
        return keep

    # --- 1. validate + decode ---
    project_name = payload.get("project_name", "Electrical Takeoff")
    image_b64 = payload.get("image_base64")
    templates = payload.get("templates") or []
    labor_pct = float(payload.get("labor_pct", 35.0))   # labor as % of material subtotal
    if not image_b64:
        return {"status": "error", "error": "Provide 'image_base64'."}

    try:
        drawing = decode_gray(image_b64)

        # --- 2. detect symbols (multi-scale OpenCV template matching) ---
        detections = []
        for tpl in templates:
            sym_type = tpl.get("type", "symbol")
            label = tpl.get("label", LABELS.get(sym_type, sym_type.replace("_", " ").title()))
            tpl_b64 = tpl.get("template_base64")
            threshold = float(tpl.get("threshold", 0.7))
            if not tpl_b64:
                continue
            template = decode_gray(tpl_b64)

            boxes, scores = [], []
            for scale in (0.8, 0.9, 1.0, 1.1, 1.25):
                th = max(8, int(template.shape[0] * scale))
                tw = max(8, int(template.shape[1] * scale))
                if th >= drawing.shape[0] or tw >= drawing.shape[1]:
                    continue
                resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(drawing, resized, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(res >= threshold)
                for x, y in zip(xs.tolist(), ys.tolist()):
                    boxes.append([int(x), int(y), int(tw), int(th)])
                    scores.append(float(res[y, x]))

            for i in nms(boxes, scores, iou_thresh=0.3):
                x, y, w, h = boxes[i]
                detections.append(
                    {
                        "type": sym_type,
                        "label": label,
                        "x": x, "y": y, "w": w, "h": h,
                        "confidence": round(scores[i], 3),
                    }
                )

        # --- 3 + 4. count + price (group detections by type) ---
        # price_source/pricing_asof are provenance fields: "static" today; Bright Data (Phase 7)
        # sets them to "brightdata" + an as-of timestamp without changing this shape.
        priced_items = []
        material_subtotal = 0.0
        types_in_order = []
        for d in detections:
            if d["type"] not in types_in_order:
                types_in_order.append(d["type"])
        for sym_type in types_in_order:
            group = [d for d in detections if d["type"] == sym_type]
            qty = len(group)
            unit = float(PRICE_MAP.get(sym_type, DEFAULT_UNIT_PRICE))
            total = round(unit * qty, 2)
            material_subtotal += total
            priced_items.append(
                {
                    "type": sym_type,
                    "label": group[0]["label"],
                    "quantity": qty,
                    "unit_price": unit,
                    "total": total,
                    "boxes": [[d["x"], d["y"], d["w"], d["h"]] for d in group],
                    "price_source": "static",
                    "pricing_asof": None,
                }
            )

        # totals (backend is the single pricing authority; labor = % of material subtotal)
        material_subtotal = round(material_subtotal, 2)
        labor_total = round(material_subtotal * labor_pct / 100.0, 2)
        grand_total = round(material_subtotal + labor_total, 2)
        totals = {
            "material_subtotal": material_subtotal,
            "labor_pct": labor_pct,
            "labor_total": labor_total,
            "grand_total": grand_total,
        }

        # --- 5. proposal ---
        lines = [f"FlashPod Electrical Proposal — {project_name}",
                 f"Date: {datetime.now():%Y-%m-%d}", ""]
        lines.append(f"{'Item':<20}{'Qty':>6}{'Unit':>12}{'Total':>14}")
        lines.append("-" * 52)
        for it in priced_items:
            lines.append(f"{it['label']:<20}{it['quantity']:>6}{it['unit_price']:>12.2f}{it['total']:>14.2f}")
        lines.append("-" * 52)
        lines.append(f"{'MATERIAL SUBTOTAL':<38}{material_subtotal:>14.2f}")
        lines.append(f"{f'LABOR ({labor_pct:.0f}%)':<38}{labor_total:>14.2f}")
        lines.append(f"{'GRAND TOTAL':<38}{grand_total:>14.2f}")

        # --- 6. return JSON ---
        return {
            "status": "success",
            "project_name": project_name,
            "detections": detections,
            "priced_items": priced_items,
            "totals": totals,
            "proposal": "\n".join(lines),
            "image_size": {"width": int(drawing.shape[1]), "height": int(drawing.shape[0])},
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import asyncio

    # NOTE: an @Endpoint call dispatches to a worker -- run under `flash dev`, not bare python.
    print(asyncio.run(analyze_drawing({"project_name": "Test", "image_base64": "", "templates": []})))
