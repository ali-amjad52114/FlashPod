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

    Output:
        detections:   [{ type, label, x, y, w, h, confidence }]   - one per detected symbol
        priced_items: [{ type, label, quantity, unit_price, total, boxes }]  - grouped + priced
        proposal:     str                                          - formatted proposal text
        project_name, image_size

    The frontend uses priced_items[].boxes for the wow feature:
    click a proposal line -> highlight every matching symbol on the drawing.
    """
    import base64
    from datetime import datetime
    from io import BytesIO

    import cv2
    import numpy as np
    from PIL import Image

    # --- constants/helpers live INSIDE the body (SKILL Gotcha #1) ---
    # Pricebook = real, sourced prices baked from pricing/catalog.json (Bright Data SERP ->
    # Google Shopping) by `python -m pricing.embed_pricebook`. The frontend may override per
    # request with payload["pricebook"]; otherwise this embedded copy is used (demo-safe, no
    # live scraping in the request path). Regenerate this block, don't hand-edit it.
    # >>> PRICEBOOK_START
    EMBEDDED_PRICEBOOK = {
        "duplex_outlet": {"label": 'Duplex Outlet', "unit_price": 1.55, "sku": 'Leviton CBR15-W', "supplier": 'Leviton e-Store', "source_url": 'https://www.google.com/search?ibp=oshop&q=15+Amp+125+Volt+NEMA+5-15R+2P+3W+Contractor+Pack15+Amp+125+Volt+NEMA+5-15R+2P+3W+Contractor+Pack&prds=catalogid%3A7116039229633873349%2Cgpcid%3A12947354356641829289%2CimageDocid%3A5535766061077255691%2Cproductid%3A18288011663734150479&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
        "gfci_outlet": {"label": 'GFCI Outlet', "unit_price": 16.59, "sku": 'Leviton GFNT2-W', "supplier": 'SupplyHouse.com', "source_url": 'https://www.google.com/search?ibp=oshop&q=Leviton+SmartlockPro+Slim+GFCI+ReceptacleLeviton+SmartlockPro+Slim+GFCI+Receptacle&prds=catalogid%3A53964250601653404%2Cgpcid%3A8197523473656457626%2CimageDocid%3A7541868368990475074%2Cproductid%3A6356380476501243508&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
        "data_drop": {"label": 'Data Drop (Cat6)', "unit_price": 1.71, "sku": 'Cat6 RJ45 Keystone Jack', "supplier": 'CablesAndKits.com', "source_url": 'https://www.google.com/search?ibp=oshop&q=CablesAndKits+Cat6+Rj45+110+Type+Keystone+Jack+KEY110-6CablesAndKits+Cat6+Rj45+110+Type+Keystone+Jack+KEY110-6&prds=catalogid%3A4821789462863043640%2Cgpcid%3A2858765303885047818%2CimageDocid%3A4858507702383649817%2Cproductid%3A17935077814640507381&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
        "switch": {"label": 'Switch', "unit_price": 1.19, "sku": 'Leviton CS115-2W', "supplier": 'Leviton e-Store', "source_url": 'https://www.google.com/search?ibp=oshop&q=Leviton+Toggle+Switch+CSB2-20ILeviton+Toggle+Switch+CSB2-20I&prds=catalogid%3A6345518674821234026%2Cgpcid%3A14850473835050576701%2CimageDocid%3A15708073692363749914%2Cproductid%3A9613270085794110108&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
        "light": {"label": 'Light Fixture', "unit_price": 42.49, "sku": '2x4 LED Troffer', "supplier": 'Sunco Lighting', "source_url": 'https://www.google.com/search?ibp=oshop&q=Sunco+Lighting+Sunco+2x4+LED+Flat+Panel+Light+Drop+Ceiling+Office+FixtureSunco+Lighting+Sunco+2x4+LED+Flat+Panel+Light+Drop+Ceiling+Office+Fixture&prds=catalogid%3A15911788851794910235%2Cgpcid%3A3137338517961806168%2CimageDocid%3A13249523128873280315%2Cproductid%3A10950530735660362537&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
        "panel": {"label": 'Panel', "unit_price": 75.99, "sku": 'Square D Homeline 200A', "supplier": 'menards', "source_url": 'https://www.google.com/search?ibp=oshop&q=Square+D+HOM3060M200PCVP+Homeline+200+Amp+30-Space+60-Circuit+Indoor+Main+Breaker+Plug-On+Neutral+Load+Center+with+Cover%28HOM3060M200PCVP%29Square+D+HOM3060M200PCVP+Homeline+200+Amp+30-Space+60-Circuit+Indoor+Main+Breaker+Plug-On+Neutral+Load+Center+with+Cover%28HOM3060M200PCVP%29&prds=imageDocid%3A7734948543441387062%2Cproductid%3A15766802451237324944&pvorigin=25&hl=en&gl=us&udm=28&shndl=37&shem=pvflt%2Cshrtsdl&source=sh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1&utm_source=pvflt%2Cshrtsdl%2Csh%2Fx%2Fprdct%2Fhdr%2Fm1%2F1', "unit": 'each'},
    }
    # <<< PRICEBOOK_END
    DEFAULT_UNIT_PRICE = 5.00

    def label_for(sym_type: str) -> str:
        entry = pricebook.get(sym_type) or {}
        return entry.get("label") or sym_type.replace("_", " ").title()

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
    pricebook = payload.get("pricebook") or EMBEDDED_PRICEBOOK
    if not image_b64:
        return {"status": "error", "error": "Provide 'image_base64'."}

    try:
        drawing = decode_gray(image_b64)

        # --- 2. detect symbols (multi-scale OpenCV template matching) ---
        detections = []
        for tpl in templates:
            sym_type = tpl.get("type", "symbol")
            label = tpl.get("label") or label_for(sym_type)
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
        priced_items = []
        subtotal = 0.0
        types_in_order = []
        for d in detections:
            if d["type"] not in types_in_order:
                types_in_order.append(d["type"])
        for sym_type in types_in_order:
            group = [d for d in detections if d["type"] == sym_type]
            qty = len(group)
            entry = pricebook.get(sym_type) or {}
            unit = float(entry.get("unit_price", DEFAULT_UNIT_PRICE))
            total = round(unit * qty, 2)
            subtotal += total
            priced_items.append(
                {
                    "type": sym_type,
                    "label": group[0]["label"],
                    "quantity": qty,
                    "unit_price": unit,
                    "total": total,
                    "sku": entry.get("sku", ""),         # real product behind the price
                    "supplier": entry.get("supplier", ""),  # cheapest in-stock supplier
                    "source_url": entry.get("source_url", ""),
                    "boxes": [[d["x"], d["y"], d["w"], d["h"]] for d in group],
                }
            )

        # --- 5. proposal ---
        lines = [f"FlashPod Electrical Proposal — {project_name}",
                 f"Date: {datetime.now():%Y-%m-%d}", ""]
        lines.append(f"{'Item':<20}{'Qty':>6}{'Unit':>12}{'Total':>14}")
        lines.append("-" * 52)
        for it in priced_items:
            lines.append(f"{it['label']:<20}{it['quantity']:>6}{it['unit_price']:>12.2f}{it['total']:>14.2f}")
        lines.append("-" * 52)
        lines.append(f"{'SUBTOTAL':<38}{round(subtotal, 2):>14.2f}")

        # --- 6. return JSON ---
        return {
            "status": "success",
            "project_name": project_name,
            "detections": detections,
            "priced_items": priced_items,
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
