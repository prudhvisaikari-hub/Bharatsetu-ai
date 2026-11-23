"""Ultralytics YOLOv8 Evaluation Script for Surface Defect Detection.
Evaluates the model against NEU-DET validation split and saves real benchmark metrics
to `docs/quality_results.json`. Never writes estimated or synthetic numbers.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def evaluate(weights_path: str = "models/surface_defect_yolov8n.pt", data_yaml: str = "data/neu-det/data.yaml"):
    weights = ROOT / weights_path
    data_file = ROOT / data_yaml
    out_json = ROOT / "docs" / "quality_results.json"

    if not weights.exists():
        print(f"❌ Error: Weights file not found at {weights}")
        return 1

    if not data_file.exists():
        print(f"❌ Error: Dataset config not found at {data_file}.")
        print("To evaluate, download NEU-DET to data/neu-det/ with data.yaml as described in docs/QUALITY_MODEL.md.")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ Error: ultralytics is not installed.")
        return 1

    print(f"📊 Evaluating {weights} on {data_file}...")
    model = YOLO(str(weights))
    metrics = model.val(data=str(data_file), split="val", save_json=False)

    results = {
        "model_name": Path(weights_path).name,
        "dataset": "NEU-DET",
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "mAP50": round(float(metrics.box.map50), 4),
        "mAP50_95": round(float(metrics.box.map), 4),
        "classes": list(metrics.names.values()) if hasattr(metrics, "names") else []
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2))
    print(f"✅ Real validation metrics written to {out_json}")
    print(json.dumps(results, indent=2))
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate YOLO surface defect detector")
    parser.add_argument("--weights", default="models/surface_defect_yolov8n.pt", help="Path to weights file")
    parser.add_argument("--data", default="data/neu-det/data.yaml", help="Path to data.yaml")
    args = parser.parse_args()
    sys.exit(evaluate(args.weights, args.data))
