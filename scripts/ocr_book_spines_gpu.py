"""Batch local GPU OCR for preprocessed book-spine images using EasyOCR.

EasyOCR uses the existing CUDA-enabled PyTorch installation.  This avoids the
Paddle GPU DLL conflict while keeping detection, recognition and results fully
local after the first model download.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GPU OCR on book-spine crops")
    parser.add_argument("--input", type=Path, default=Path("crops/preprocessed_test"))
    parser.add_argument("--output", type=Path, default=Path("outputs/ocr_gpu_test"))
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=Path("outputs/ocr_test/ocr_results.json"),
        help="Existing Paddle/previous OCR JSON to retain and skip",
    )
    parser.add_argument("--model-dir", type=Path, default=Path("dependencies/ocr-models"))
    parser.add_argument(
        "--directions", default="normal,clockwise,counterclockwise,180",
        help="Comma-separated direction candidates",
    )
    parser.add_argument("--max-images", type=int, default=0, help="0 processes all remaining images")
    parser.add_argument("--overwrite", action="store_true", help="Reprocess existing records")
    return parser.parse_args()


def clean_text(text: str) -> str:
    text = str(text or "").replace(" ", "").replace("\n", "")
    text = text.replace("|", "一")
    return re.sub(r"[^\u3400-\u9fffA-Za-z0-9，。！？：、（）《》“”‘’\-·]", "", text)


def load_image(path: Path) -> np.ndarray:
    """Read paths containing Chinese characters on Windows."""
    raw = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"无法读取图片: {path}")
    return image


def rotate(image: np.ndarray, direction: str) -> np.ndarray:
    mapping = {
        "normal": None,
        "clockwise": cv2.ROTATE_90_CLOCKWISE,
        "counterclockwise": cv2.ROTATE_90_COUNTERCLOCKWISE,
        "180": cv2.ROTATE_180,
    }
    if direction not in mapping:
        raise ValueError(f"不支持的方向: {direction}")
    return image if mapping[direction] is None else cv2.rotate(image, mapping[direction])


def recognize_one(reader: Any, image_path: Path, directions: list[str]) -> dict[str, Any]:
    image = load_image(image_path)
    candidates = []
    for direction in directions:
        lines = reader.readtext(rotate(image, direction), detail=1, paragraph=False)
        parsed = []
        for box, text, score in lines:
            clean = clean_text(text)
            if not clean:
                continue
            parsed.append({"polygon": [[round(float(x), 2), round(float(y), 2)] for x, y in box], "text": clean, "confidence": round(float(score), 6)})
        text = "".join(item["text"] for item in parsed)
        confidence = sum(item["confidence"] for item in parsed) / len(parsed) if parsed else 0.0
        candidates.append(
            {
                "direction": direction,
                "text": text,
                "confidence": round(confidence, 6),
                "selection_score": round(confidence + min(len(text), 24) * 0.002, 6),
                "lines": parsed,
            }
        )
    selected = max(candidates, key=lambda item: item["selection_score"], default={})
    confidence = float(selected.get("confidence", 0.0))
    quality = "high" if confidence >= 0.80 else "medium" if confidence >= 0.55 else "low"
    return {
        "image": str(image_path),
        "engine": "easyocr-gpu",
        "text": selected.get("text", ""),
        "confidence": round(confidence, 6),
        "quality": quality,
        "direction": selected.get("direction"),
        "lines": selected.get("lines", []),
        "candidates": candidates,
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded.get("records", []) if isinstance(loaded, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def write_outputs(output_dir: Path, input_dir: Path, records: list[dict[str, Any]], directions: list[str], started: float) -> None:
    records = sorted(records, key=lambda x: str(x.get("image", "")))
    errors = sum(1 for item in records if item.get("error"))
    payload = {
        "input": str(input_dir),
        "engine": "easyocr-gpu",
        "directions": directions,
        "records": records,
    }
    (output_dir / "ocr_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["image", "engine", "text", "confidence", "quality", "direction", "error"]
    with (output_dir / "ocr_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: item.get(field, "") for field in fields} for item in records)
    summary = {
        "records": len(records),
        "errors": errors,
        "nonempty_text": sum(1 for item in records if item.get("text")),
        "high_quality": sum(1 for item in records if item.get("quality") == "high"),
        "easyocr_gpu_records": sum(1 for item in records if item.get("engine") == "easyocr-gpu"),
        "elapsed_seconds_this_run": round(time.time() - started, 2),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    args.model_dir.mkdir(parents=True, exist_ok=True)
    directions = [item.strip() for item in args.directions.split(",") if item.strip()]
    images = sorted(input_dir.rglob("*_clahe.jpg"))
    if not images:
        raise SystemExit(f"未找到 *_clahe.jpg: {input_dir}")

    records = [] if args.overwrite else read_records(args.resume_from)
    records.extend([] if args.overwrite else read_records(output_dir / "ocr_results.json"))
    indexed = {str(Path(item["image"]).resolve()): item for item in records if item.get("image")}
    pending = images if args.overwrite else [path for path in images if str(path.resolve()) not in indexed]
    if args.max_images > 0:
        pending = pending[: args.max_images]

    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 PyTorch CUDA，不能启动 GPU OCR")
    import easyocr
    print(f"使用 GPU: {torch.cuda.get_device_name(0)}")
    reader = easyocr.Reader(["ch_sim", "en"], gpu=True, model_storage_directory=str(args.model_dir), verbose=False)

    started = time.time()
    total = len(pending)
    for index, image_path in enumerate(pending, 1):
        try:
            record = recognize_one(reader, image_path, directions)
        except Exception as exc:
            record = {"image": str(image_path), "engine": "easyocr-gpu", "error": f"{type(exc).__name__}: {exc}"}
        indexed[str(image_path.resolve())] = record
        write_outputs(output_dir, input_dir, list(indexed.values()), directions, started)
        print(f"[{index}/{total}] {image_path.name}: {record.get('text', '')[:40]} ({record.get('confidence', 0):.3f})")
    write_outputs(output_dir, input_dir, list(indexed.values()), directions, started)
    print((output_dir / "summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
