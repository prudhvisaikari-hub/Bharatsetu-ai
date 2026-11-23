"""Ultralytics YOLOv8 Training Script for Surface Defect Detection on NEU-DET.

Prerequisites:
1. Download the NEU-DET dataset to `data/neu-det/` (e.g. from Kaggle or official Northeastern University portal).
2. Ensure directory contains:
   data/neu-det/
     ├── data.yaml
     ├── images/train, images/val
     └── labels/train, labels/val
3. Run training:
   python training/train_yolo.py --epochs 50 --imgsz 640 --batch 16
"""
import argparse
import sys
from pathlib import Path

def train(data_yaml: str = "data/neu-det/data.yaml", epochs: int = 50, imgsz: int = 640, batch: int = 16):
    data_path = Path(data_yaml)
    if not data_path.exists():
        print(f"❌ Error: Dataset config {data_path} not found.")
        print("Please download the NEU-DET dataset into data/neu-det/ following docs/QUALITY_MODEL.md.")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ Error: ultralytics is not installed. Run: pip install ultralytics")
        return 1

    print(f"🏋️ Starting YOLOv8n fine-tuning on {data_yaml} ({epochs} epochs, imgsz={imgsz})...")
    model = YOLO("yolov8n.pt")
    results = model.train(
        data=str(data_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project="models",
        name="surface_defect_run"
    )
    print("✅ Training completed. Best checkpoint saved to models/surface_defect_run/weights/best.pt")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 on NEU-DET surface defect dataset")
    parser.add_argument("--data", default="data/neu-det/data.yaml", help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    args = parser.parse_args()
    sys.exit(train(args.data, args.epochs, args.imgsz, args.batch))
