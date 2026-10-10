"""Run the local book-spine pipeline from detection through structured results."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="One image or a directory of images")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/pipeline_runs")
    parser.add_argument("--weights", type=Path, default=ROOT / "outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt")
    parser.add_argument("--detect-device", default="0", help="YOLO device: 0, cpu, or auto")
    parser.add_argument("--ocr-engine", choices=["rapid-gpu", "paddle-cpu"], default="rapid-gpu")
    parser.add_argument("--ocr-device", choices=["cpu", "gpu:0"], default="cpu")
    parser.add_argument("--keep-run-id", default="", help="Use a stable output directory name")
    return parser.parse_args()


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    run_id = args.keep_run_id.strip() or f"run-{uuid.uuid4().hex[:12]}"
    run_root = args.output.resolve() / run_id
    detected = run_root / "detected"
    preprocessed = run_root / "preprocessed"
    ocr_output = run_root / "ocr"
    postprocessed = run_root / "postprocessed"
    run_root.mkdir(parents=True, exist_ok=True)
    python = sys.executable

    run([python, str(ROOT / "scripts/detect_and_crop_spines.py"), "--source", str(source),
         "--weights", str(args.weights.resolve()), "--output", str(detected), "--device", args.detect_device])
    run([python, str(ROOT / "scripts/rectify_and_enhance_spines.py"), "--manifest",
         str(detected / "detections.json"), "--output", str(preprocessed)])
    detected_manifest = json.loads((detected / "detections.json").read_text(encoding="utf-8"))
    preprocess_manifest = json.loads((preprocessed / "preprocess.json").read_text(encoding="utf-8"))
    detected_count = sum(len(row.get("detections", [])) for row in detected_manifest.get("images", []))
    if detected_count and not preprocess_manifest.get("items"):
        raise RuntimeError("检测到了书脊，但预处理没有生成任何图片；请检查输出路径和图像编码。")

    empty_resume = run_root / "empty_resume.json"
    empty_resume.write_text('{"records": []}', encoding="utf-8")
    if args.ocr_engine == "rapid-gpu":
        run([python, str(ROOT / "scripts/ocr_book_spines_rapid_gpu.py"), "--input", str(preprocessed),
             "--output", str(ocr_output), "--resume-from", str(empty_resume)])
    else:
        run([python, str(ROOT / "scripts/ocr_book_spines.py"), "--input", str(preprocessed),
             "--output", str(ocr_output), "--device", args.ocr_device])
    run([python, str(ROOT / "scripts/postprocess_ocr_results.py"), "--ocr", str(ocr_output / "ocr_results.json"),
         "--preprocess", str(preprocessed / "preprocess.json"), "--detections", str(detected / "detections.json"),
         "--output", str(postprocessed)])

    summary = json.loads((postprocessed / "summary.json").read_text(encoding="utf-8"))
    result = {"run_id": run_id, "run_root": str(run_root), "summary": summary,
              "structured_results": str(postprocessed / "books_by_image.json")}
    (run_root / "run_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
