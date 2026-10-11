"""Run local PaddleOCR on preprocessed book-spine crops.

The script is deliberately independent from the YOLO stage.  It consumes the
*_clahe.jpg files produced by rectify_and_enhance_spines.py and writes a
resumable JSON/CSV result set.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

DLL_DIRECTORY_HANDLES = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch OCR book-spine crops locally")
    parser.add_argument("--input", type=Path, default=Path("crops/preprocessed_test"))
    parser.add_argument("--output", type=Path, default=Path("outputs/ocr_test"))
    parser.add_argument("--device", default="cpu", choices=["cpu", "gpu:0"])
    parser.add_argument(
        "--directions",
        default="normal,clockwise,counterclockwise,180",
        help="Comma-separated candidate directions",
    )
    parser.add_argument("--max-images", type=int, default=0, help="0 means all images")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=None)
    return parser.parse_args()


def configure_paddle_windows_dlls() -> None:
    """Make project-local native DLLs visible before PaddleX/PaddleOCR imports."""
    if os.name != "nt":
        return
    import sysconfig

    packages = Path(sysconfig.get_paths()["purelib"])
    dll_dirs = [packages / "paddle" / "libs"]
    dll_dirs.extend(sorted((packages / "nvidia").glob("*/bin")))
    # PaddleX can import packages that expect PyTorch DLLs to be discoverable.
    dll_dirs.append(packages / "torch" / "lib")
    valid_dirs = [directory for directory in dll_dirs if directory.exists()]
    for directory in valid_dirs:
        DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))
    os.environ["PATH"] = ";".join(str(directory) for directory in valid_dirs) + ";" + os.environ.get("PATH", "")


def clean_text(text: str) -> str:
    text = str(text or "").replace(" ", "").replace("\n", "")
    text = text.replace("|", "一")
    return re.sub(r"[^\u3400-\u9fffA-Za-z0-9，。！？：、（）《》“”‘’\-·]", "", text)


def direction_image(image, direction: str):
    if direction == "normal":
        return image
    if direction == "clockwise":
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if direction == "counterclockwise":
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if direction == "180":
        return cv2.rotate(image, cv2.ROTATE_180)
    raise ValueError(f"Unsupported direction: {direction}")


def json_value(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def result_to_dict(result: Any) -> dict[str, Any]:
    raw = getattr(result, "json", None)
    if callable(raw):
        raw = raw()
    if raw is not None:
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict) and "res" in raw and isinstance(raw["res"], dict):
            raw = raw["res"]
        return json_value(raw)
    if isinstance(result, dict):
        return json_value(result)
    return json_value(vars(result)) if hasattr(result, "__dict__") else {}


def run_one(ocr, image_path: Path, directions: list[str]) -> dict[str, Any]:
    # cv2.imread may fail on Windows when the path contains non-ASCII text.
    image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"无法读取图片: {image_path}")

    candidates: list[dict[str, Any]] = []
    for direction in directions:
        oriented = direction_image(image, direction)
        result_list = ocr.predict(oriented)
        result = next(iter(result_list), None)
        data = result_to_dict(result) if result is not None else {}
        texts = [str(x) for x in data.get("rec_texts", [])]
        scores = [float(x) for x in data.get("rec_scores", [])]
        nonempty = [(clean_text(t), s) for t, s in zip(texts, scores) if clean_text(t)]
        text = "".join(x[0] for x in nonempty)
        mean_score = sum(x[1] for x in nonempty) / len(nonempty) if nonempty else 0.0
        # Prefer readable candidates, then confidence, then amount of text.
        selection_score = mean_score + min(len(text), 24) * 0.002
        candidates.append(
            {
                "direction": direction,
                "text": text,
                "confidence": round(mean_score, 6),
                "selection_score": round(selection_score, 6),
                "raw_texts": texts,
                "raw_scores": scores,
            }
        )

    selected = max(candidates, key=lambda x: x["selection_score"], default={})
    confidence = float(selected.get("confidence", 0.0))
    quality = "high" if confidence >= 0.80 else "medium" if confidence >= 0.55 else "low"
    return {
        "image": str(image_path),
        "text": selected.get("text", ""),
        "confidence": round(confidence, 6),
        "quality": quality,
        "direction": selected.get("direction"),
        "candidates": candidates,
    }


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = ["image", "engine", "text", "confidence", "quality", "direction", "error"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def main() -> int:
    args = parse_args()
    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "ocr_results.json"
    csv_path = output_dir / "ocr_results.csv"
    directions = [x.strip() for x in args.directions.split(",") if x.strip()]
    image_paths = sorted(input_dir.rglob("*_clahe.jpg"))
    if args.max_images > 0:
        image_paths = image_paths[: args.max_images]
    if not image_paths:
        raise SystemExit(f"未找到 *_clahe.jpg: {input_dir}")

    records: list[dict[str, Any]] = []
    if result_path.exists() and not args.overwrite:
        try:
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            records = previous.get("records", []) if isinstance(previous, dict) else []
        except (OSError, json.JSONDecodeError):
            records = []
    completed = {str(Path(x.get("image", "")).resolve()) for x in records if x.get("image")}

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    # PaddleOCR 3.x loads PaddleX and may resolve native dependencies from
    # PyTorch even for CPU inference. Configure the project-local DLL search
    # path before importing PaddleOCR in every mode.
    configure_paddle_windows_dlls()
    # The GPU wheel also loads CUDA DLLs when CPU inference is selected.
    # Import it before PaddleX can load conflicting native libraries.
    import paddle

    paddle.set_device(args.device)
    print(f"Paddle device: {paddle.device.get_device()}")
    from paddleocr import PaddleOCR

    ocr_kwargs = {
        "lang": "ch",
        "device": args.device,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": True,
        # Avoid unsupported oneDNN PIR attributes with Paddle GPU wheels on CPU.
        "enable_mkldnn": False,
    }
    if args.model_dir:
        # PaddleOCR 3.x accepts model directories through these optional keys.
        ocr_kwargs.update(
            {
                "text_detection_model_dir": str(args.model_dir / "det"),
                "text_recognition_model_dir": str(args.model_dir / "rec"),
            }
        )
    ocr = PaddleOCR(**ocr_kwargs)

    started = time.time()
    total = len(image_paths)
    for index, image_path in enumerate(image_paths, 1):
        key = str(image_path.resolve())
        if key in completed and not args.overwrite:
            print(f"[{index}/{total}] 跳过已完成: {image_path.name}")
            continue
        try:
            record = run_one(ocr, image_path, directions)
            record["engine"] = "paddleocr-gpu" if args.device.startswith("gpu") else "paddleocr-cpu"
        except Exception as exc:  # keep the batch resumable
            record = {
                "image": str(image_path),
                "engine": "paddleocr-gpu" if args.device.startswith("gpu") else "paddleocr-cpu",
                "error": f"{type(exc).__name__}: {exc}",
            }
        records = [x for x in records if str(Path(x.get("image", "")).resolve()) != key]
        records.append(record)
        result_path.write_text(
            json.dumps(
                {
                    "input": str(input_dir),
                    "device": args.device,
                    "directions": directions,
                    "total": total,
                    "processed": len(records),
                    "records": records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        write_csv(csv_path, records)
        text = record.get("text", "")
        print(f"[{index}/{total}] {image_path.name}: {text[:40]} ({record.get('confidence', 0):.3f})")

    summary = {
        "total_files": total,
        "records": len(records),
        "errors": sum(1 for x in records if x.get("error")),
        "nonempty_text": sum(1 for x in records if x.get("text")),
        "high_quality": sum(1 for x in records if x.get("quality") == "high"),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
