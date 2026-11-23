# Quality Agent: YOLOv8 Surface Defect Detection & Model Benchmarks

## 1. Overview
The Quality Agent provides computer-vision object detection for automotive components and steel blanks based on **Ultralytics YOLOv8n**, fine-tuned for surface defect inspection.

The detector is designed for photographs of machined, turned, stamped, or cast automotive components commonly manufactured in the Pithampur Auto Cluster and Sanwer Road industrial belts.

## 2. Dataset: NEU-DET Benchmark
- **Dataset:** Northeastern University (NEU) Surface Defect Database.
- **Classes (6 categories):**
  1. `crazing` (micro-cracking)
  2. `inclusion` (foreign material / slag trapped during rolling)
  3. `patches` (surface irregular scaling / oxidation patches)
  4. `pitted_surface` (cavities / pinholes from corrosion or casting voids)
  5. `rolled-in_scale` (scale rolled into the surface during hot forming)
  6. `scratches` (mechanical scoring, handling tool gouges)
- **Model Architecture:** YOLOv8n (Nano), 3.2M parameters.

---

## 3. Validation Metrics & Status

> **Validation Status: Not yet validated in this repository.**

In accordance with our strict honesty rules, estimated or unverified performance figures are not published in this repository. Benchmark numbers will only be recorded once evaluated against a local held-out test split using the reproducible scripts below.

### Reproducing Training & Evaluation:

1. **Download NEU-DET Dataset:**
   Download the Northeastern University (NEU-DET) dataset from Kaggle or the official repository and place it in `data/neu-det/` with the following structure:
   ```
   data/neu-det/
     ├── data.yaml
     ├── images/
     │   ├── train/
     │   └── val/
     └── labels/
         ├── train/
         └── val/
   ```

2. **Run Training:**
   ```bash
   python training/train_yolo.py --data data/neu-det/data.yaml --epochs 50 --batch 16
   ```

3. **Run Evaluation:**
   ```bash
   python training/evaluate.py --weights models/surface_defect_yolov8n.pt --data data/neu-det/data.yaml
   ```
   Evaluation writes measured metrics directly to `docs/quality_results.json`. Once validated, the API and web UI automatically update `model_validated: true`.

---

## 4. Known Failure Modes & Limitations
1. **Curved and Machined Cylindrical Parts:** Highly reflective turned cylindrical pins (e.g. gudgeon pins) can produce specular highlights that may trigger false positive detections under harsh lighting.
2. **Dust and Coolant Drops:** Water-soluble coolant droplets can occasionally be misclassified as pitting or inclusion. Operators are advised to blow dry parts prior to capture.
3. **Low-Contrast Micro-Crazing:** Microscopic crazing cracks below 0.1 mm width require macro-lens magnification and can be missed under standard smartphone cameras.

---

## 5. Dual-Mode Fallback Architecture
To ensure zero service failure on shopfloors:
- **Primary:** YOLOv8n inference on GPU/CPU with confidence threshold $C \ge 0.25$.
- **Fallback:** If PyTorch/Ultralytics is unavailable or if YOLO detections return zero but the component exhibits severe statistical pixel gradient anomalies, the system activates the local statistical variance fallback detector.
- **Model artifacts:** Saved under `models/surface_defect_yolov8n.pt`.
