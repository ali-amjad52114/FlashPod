# electrical-drawing takeoff worker -- detects + counts symbols, returns bounding boxes + OCR.
# run with: flash dev
#
# Two detectors, one worker (choose per-request via "detector"):
#   "yolo"     -> YOLO11 (ultralytics) inference on a fine-tuned electrical model. BEST accuracy.
#                 Reference for YOLO-on-drawings: https://github.com/DynMEP/YOLOplan (YOLO11).
#                 Weights (.pt) live on the NetworkVolume; fine-tune ~20-50 labeled crops.
#   "template" -> OpenCV multi-scale template matching using your own symbol crops. Works today,
#                 zero training, exact boxes -- the guaranteed floor for the demo.
#
# Flash wiring is grounded in the reference examples (per project rule); only the CV/OCR logic
# inside the body is app domain code (reference ships no CV worker):
#   - model-in-body + deps + status dict:  02_ml_inference/01_text_to_speech/gpu_worker.py
#   - NetworkVolume + env weight-cache + datacenter:  05_data_workflows/01_network_volumes/gpu_worker.py
#   - opencv-python + system_dependencies ["ffmpeg","libgl1"]:  01_getting_started/04_dependencies/gpu_worker.py
#   - handler signature async def fn(input_data: dict) -> dict:  01_hello_world/gpu_worker.py
from runpod_flash import Endpoint, GpuGroup, DataCenter, NetworkVolume

MODEL_PATH = "/runpod-volume/models"          # weights + OCR cache persist here across cold starts
volume = NetworkVolume(
    name="flashpod-takeoff-volume",
    size=20,
    datacenter=DataCenter.EU_RO_1,
)


@Endpoint(
    name="flashpod_takeoff",
    gpu=GpuGroup.ADA_24,
    workers=(0, 3),
    idle_timeout=300,
    datacenter=DataCenter.EU_RO_1,
    volume=volume,
    env={"HF_HUB_CACHE": MODEL_PATH, "EASYOCR_MODULE_PATH": MODEL_PATH},
    dependencies=["ultralytics", "opencv-python", "easyocr", "numpy"],
    system_dependencies=["ffmpeg", "libgl1"],
)
async def detect(input_data: dict) -> dict:
    """
    Detect + count electrical symbols on a drawing, returning per-symbol bounding boxes.

    Input:
        drawing_base64: str         - the drawing image (PNG/JPG) as base64
        detector: "yolo" | "template"  (default "template")
        run_ocr: bool               - also OCR text labels/panels (default True)

      detector="yolo":
        weights: str                - .pt filename on the volume (default "electrical.pt")
        conf: float                 - confidence threshold (default 0.25)
      detector="template":
        templates: [{ "type", "template_base64", "threshold"? }]

    Returns:
        status, line_items: [{ "type", "count", "boxes": [[x,y,w,h], ...] }], ocr, image_size

    boxes power the traceability wow-feature: clicking "Duplex: 42" highlights those boxes.
    """
    import base64
    import os
    from datetime import datetime

    import cv2
    import numpy as np

    # Flash dev ships ONLY this body -- define paths here, not at module level (SKILL Gotcha #1).
    model_path = os.getenv("EASYOCR_MODULE_PATH") or "/runpod-volume/models"

    def _decode_gray(b64: str) -> "np.ndarray":
        buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("could not decode image from base64")
        return img

    def _nms(boxes, scores, iou_thresh=0.3):
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

    def _detect_yolo(drawing_b64: str, weights: str, conf: float) -> list:
        """YOLO11 inference -> line_items grouped by class. BEST accuracy path."""
        from collections import defaultdict

        from ultralytics import YOLO

        weights_path = os.path.join(model_path, weights)
        if not os.path.exists(weights_path):
            raise FileNotFoundError(
                f"YOLO weights not found at {weights_path}. Upload a fine-tuned .pt to the volume, "
                f"or use detector='template'."
            )
        buf = np.frombuffer(base64.b64decode(drawing_b64), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)

        model = YOLO(weights_path)
        result = model.predict(img, conf=conf, verbose=False)[0]
        names = result.names
        grouped = defaultdict(list)
        for box in result.boxes:
            cls = names[int(box.cls[0])]
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            grouped[cls].append([x1, y1, x2 - x1, y2 - y1])
        return [{"type": t, "count": len(b), "boxes": b} for t, b in grouped.items()]

    def _detect_template(drawing: "np.ndarray", templates: list) -> list:
        """OpenCV multi-scale template matching -> line_items. Works today with your crops."""
        line_items = []
        for tpl in templates:
            sym_type = tpl.get("type", "symbol")
            tpl_b64 = tpl.get("template_base64")
            threshold = float(tpl.get("threshold", 0.7))
            if not tpl_b64:
                continue
            template = _decode_gray(tpl_b64)
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
            keep = _nms(boxes, scores, iou_thresh=0.3)
            kept = [boxes[i] for i in keep]
            line_items.append({"type": sym_type, "count": len(kept), "boxes": kept})
        return line_items

    drawing_b64 = input_data.get("drawing_base64")
    detector = input_data.get("detector", "template")
    run_ocr = input_data.get("run_ocr", True)

    if not drawing_b64:
        return {"status": "error", "error": "Provide 'drawing_base64'."}

    try:
        drawing = _decode_gray(drawing_b64)

        if detector == "yolo":
            line_items = _detect_yolo(
                drawing_b64,
                input_data.get("weights", "electrical.pt"),
                float(input_data.get("conf", 0.25)),
            )
        else:
            line_items = _detect_template(drawing, input_data.get("templates") or [])

        ocr_results = []
        if run_ocr:
            import easyocr

            reader = easyocr.Reader(
                ["en"],
                gpu=True,
                model_storage_directory=model_path,
            )
            for bbox, text, conf in reader.readtext(drawing):
                xs = [int(p[0]) for p in bbox]
                ys = [int(p[1]) for p in bbox]
                ocr_results.append(
                    {
                        "text": text,
                        "confidence": round(float(conf), 3),
                        "box": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                    }
                )

        return {
            "status": "success",
            "detector": detector,
            "line_items": line_items,
            "ocr": ocr_results,
            "image_size": {"width": int(drawing.shape[1]), "height": int(drawing.shape[0])},
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import asyncio

    # Mirrors the reference __main__ blocks. NOTE: an @Endpoint call dispatches to a deployed
    # worker -- run under `flash dev` (or after `flash deploy`), not as bare `python takeoff_worker.py`.
    payload = {"drawing_base64": "", "detector": "template", "templates": [], "run_ocr": False}
    print("Takeoff worker smoke test (empty payload -> expect validation error):")
    print(asyncio.run(detect(payload)))
