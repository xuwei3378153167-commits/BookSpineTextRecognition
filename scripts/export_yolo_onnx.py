"""Export the trained YOLO segmentation checkpoint to a local ONNX model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=ROOT / "outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/models")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exported = YOLO(str(args.weights.resolve())).export(format="onnx", imgsz=args.imgsz, simplify=True, opset=17)
    exported_path = Path(str(exported)).resolve()
    target = args.output.resolve() / exported_path.name
    if exported_path != target:
        target.write_bytes(exported_path.read_bytes())
    import onnx
    model = onnx.load(str(target))
    onnx.checker.check_model(model)
    result = {"source": str(args.weights.resolve()), "onnx": str(target), "size": target.stat().st_size,
              "imgsz": args.imgsz, "validated": True}
    (args.output.resolve() / "onnx_export.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
