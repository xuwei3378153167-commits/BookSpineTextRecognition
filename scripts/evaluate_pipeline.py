"""Evaluate the held-out detection run and summarize local OCR quality signals."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "dependencies/ultralytics-config"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=ROOT / "outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt")
    parser.add_argument("--data", type=Path, default=ROOT / "data.yaml")
    parser.add_argument("--postprocessed", type=Path, default=ROOT / "outputs/ocr_postprocessed/ocr_postprocessed.json")
    parser.add_argument("--detections", type=Path, default=ROOT / "crops/detected_test/detections.json")
    parser.add_argument("--preprocess", type=Path, default=ROOT / "crops/preprocessed_test/preprocess.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/evaluation")
    parser.add_argument("--device", default="0")
    parser.add_argument("--skip-yolo", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_test_labels() -> tuple[int, int]:
    image_count = len(list((ROOT / "dataset/images/test").glob("*")))
    instances = 0
    for path in (ROOT / "dataset/labels/test").glob("*.txt"):
        instances += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return image_count, instances


def load_training_metrics() -> dict[str, float]:
    path = ROOT / "outputs/training/book-spine-yolo11n-seg-20261008/results.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = rows[-1]
    keys = ["metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)",
            "metrics/precision(M)", "metrics/recall(M)", "metrics/mAP50(M)", "metrics/mAP50-95(M)"]
    return {key: float(row[key]) for key in keys}


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    detections = read_json(args.detections.resolve())
    preprocess = read_json(args.preprocess.resolve())
    postprocessed = read_json(args.postprocessed.resolve())
    test_images, test_instances = count_test_labels()
    detection_rows = detections.get("images", [])
    detected = sum(len(item.get("detections", [])) for item in detection_rows)
    ocr_summary = postprocessed.get("summary", {})
    report: dict[str, Any] = {
        "dataset": {"test_images": test_images, "test_instances": test_instances},
        "detection": {"images_processed": len(detection_rows), "detections": detected,
                      "manifest_errors": sum(bool(item.get("error")) for item in detection_rows)},
        "preprocessing": {"items": len(preprocess.get("items", [])), "failures": len(preprocess.get("failures", []))},
        "ocr": ocr_summary,
        "training_final_metrics": load_training_metrics(),
    }
    if not args.skip_yolo:
        from ultralytics import YOLO
        metrics = YOLO(str(args.weights.resolve())).val(
            data=str(args.data.resolve()), split="test", imgsz=1024, batch=2,
            device=args.device, workers=0, project=str(output), name="yolo_test", exist_ok=True,
            plots=True,
        )
        report["yolo_test_metrics"] = {key: round(float(value), 6) for key, value in metrics.results_dict.items()}
    (output / "evaluation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
