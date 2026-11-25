"""Quality Agent: Visual surface defect inspection for automotive components and steel blanks.
Uses YOLOv8n (trained on NEU-DET surface defect dataset) with a pixel-variance anomaly fallback.
"""
import io
import os
import logging
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from PIL import Image
from ..store import log, gain

logger = logging.getLogger("bharatsetu.quality")

CELL = 20
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_PATH = MODELS_DIR / "surface_defect_yolov8n.pt"
RESULTS_JSON = Path(__file__).resolve().parent.parent.parent / "docs" / "quality_results.json"

def is_model_validated() -> bool:
    """Returns True only if real evaluation results exist in docs/quality_results.json."""
    return RESULTS_JSON.exists()

_yolo_model = None
try:
    yolo_dir = Path(__file__).resolve().parent.parent.parent / ".yolo"
    os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_dir))
    os.environ.setdefault("YOLO_VERBOSE", "False")
    os.environ.setdefault("ULTRALYTICS_AUTOINSTALL", "False")
    from ultralytics import YOLO
    if MODEL_PATH.exists():
        _yolo_model = YOLO(str(MODEL_PATH))
        logger.info(f"Loaded YOLOv8 defect model from {MODEL_PATH}")
except Exception as e:
    logger.warning(f"Could not initialize YOLO model ({e}); pixel fallback will be used.")

def _pixel_check(img: Image.Image) -> Dict[str, Any]:
    """Statistical pixel-anomaly detector as reliable fallback."""
    a = np.asarray(img.convert("L").resize((360, 200)), dtype=float)
    cells = []
    for y in range(0, 200 - CELL + 1, CELL):
        for x in range(0, 360 - CELL + 1, CELL):
            c = a[y:y + CELL, x:x + CELL]
            cells.append((x, y, c.mean(), c.std()))
    means = np.array([c[2] for c in cells])
    mu, sd = means.mean(), max(1.0, means.std())
    flagged = sorted([(abs(m - mu) / sd, x, y) for x, y, m, s in cells if abs(m - mu) / sd > 2.2 or s > 38], reverse=True)
    boxes = [{"x": x, "y": y, "w": CELL, "h": CELL, "label": "surface_anomaly"} for _, x, y in flagged[:4]]
    score = min(99, int(len(boxes) * 22 + (flagged[0][0] * 6 if flagged else 0)))
    return {"boxes": boxes, "score": score}

def inspect_image(data: bytes, msme_id: str = "demo") -> Dict[str, Any]:
    """Inspects machined/stamped part photo for surface defects using YOLO with pixel fallback."""
    try:
        pil_img = Image.open(io.BytesIO(data))
    except Exception:
        raise ValueError("Invalid image file format")

    boxes: List[Dict[str, Any]] = []
    detected_classes = []
    model_used = "pixel_fallback"
    score = 0

    # Try YOLO model first if initialized
    if _yolo_model is not None:
        try:
            results = _yolo_model.predict(source=pil_img, conf=0.25, verbose=False)
            if results and len(results) > 0 and len(results[0].boxes) > 0:
                model_used = "yolov8n_neu_det"
                r = results[0]
                for box in r.boxes:
                    coords = box.xywh.cpu().numpy()[0]  # x_center, y_center, width, height
                    cls_id = int(box.cls.cpu().numpy()[0])
                    conf = float(box.conf.cpu().numpy()[0])
                    cls_name = r.names.get(cls_id, f"defect_{cls_id}")
                    detected_classes.append(cls_name)
                    boxes.append({
                        "x": int(coords[0] - coords[2] / 2),
                        "y": int(coords[1] - coords[3] / 2),
                        "w": int(coords[2]),
                        "h": int(coords[3]),
                        "label": cls_name,
                        "confidence": round(conf, 2)
                    })
                score = min(99, int(len(boxes) * 25 + max(b.get("confidence", 0.5) for b in boxes) * 35))
        except Exception as e:
            logger.warning(f"YOLO inference error ({e}); using pixel fallback.")

    # If YOLO produced no detections or wasn't loaded, run the pixel check
    if not boxes:
        pixel_res = _pixel_check(pil_img)
        if pixel_res["boxes"]:
            boxes = pixel_res["boxes"]
            score = pixel_res["score"]
            model_used = "pixel_fallback"

    verdict = "FAIL" if boxes else "PASS"
    defect_label_str = ", ".join(set(detected_classes)) if detected_classes else "surface scratch / irregularity"

    if verdict == "FAIL":
        gain("qa", 25000, 0, 1.0, msme_id=msme_id)
        note = f"{model_used}: Flagged {len(boxes)} defect region(s) ({defect_label_str})."
        log("Quality Agent", f"{len(boxes)} defect regions detected on component ({model_used})", msme_id=msme_id)
    else:
        gain("qa", 15000, 0, 1.0, msme_id=msme_id)
        note = f"{model_used}: Component verified clean. Zero surface defects detected."
        log("Quality Agent", f"Part inspection PASSED. Zero defects flagged ({model_used})", msme_id=msme_id)

    return {
        "verdict": verdict,
        "defect_score": score,
        "boxes": boxes,
        "model_used": model_used,
        "model_name": "surface_defect_yolov8n.pt",
        "model_validated": is_model_validated(),
        "note": note
    }
