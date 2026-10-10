"""Resumable local GPU OCR using PP-OCR ONNX models through RapidOCR."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import sysconfig
import time
from pathlib import Path

import cv2
import numpy as np

DLL_HANDLES = []


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPU batch OCR for book spines")
    parser.add_argument("--input", type=Path, default=Path("crops/preprocessed_test"))
    parser.add_argument("--output", type=Path, default=Path("outputs/ocr_rapid_gpu_test"))
    parser.add_argument("--resume-from", type=Path, default=Path("outputs/ocr_test/ocr_results.json"))
    parser.add_argument("--max-images", type=int, default=0)
    return parser.parse_args()


def prepare_cuda() -> None:
    packages = Path(sysconfig.get_paths()["purelib"])
    # ONNX Runtime GPU 1.30 uses the CUDA 13 DLLs packaged with PyTorch.
    torch_lib = packages / "torch" / "lib"
    if not torch_lib.exists():
        raise RuntimeError(f"未找到 CUDA DLL 目录: {torch_lib}")
    DLL_HANDLES.append(os.add_dll_directory(str(torch_lib)))
    os.environ["PATH"] = str(torch_lib) + ";" + os.environ.get("PATH", "")


def clean(text: str) -> str:
    text = str(text or "").replace(" ", "").replace("\n", "").replace("|", "一")
    return re.sub(r"[^\u3400-\u9fffA-Za-z0-9，。！？：、（）《》“”‘’\-·]", "", text)


def read_json(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("records", []) if path.exists() else []
    except (OSError, json.JSONDecodeError):
        return []


def rotate(image: np.ndarray, label: str) -> np.ndarray:
    codes = {"normal": None, "clockwise": cv2.ROTATE_90_CLOCKWISE, "counterclockwise": cv2.ROTATE_90_COUNTERCLOCKWISE, "180": cv2.ROTATE_180}
    return image if codes[label] is None else cv2.rotate(image, codes[label])


def recognize(ocr, path: Path) -> dict:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("图片无法读取")
    candidates = []
    for direction in ("normal", "clockwise", "counterclockwise", "180"):
        rows, _ = ocr(rotate(image, direction))
        lines = []
        for polygon, text, score in rows or []:
            text = clean(text)
            if text:
                lines.append({"polygon": polygon, "text": text, "confidence": round(float(score), 6)})
        text = "".join(line["text"] for line in lines)
        confidence = sum(line["confidence"] for line in lines) / len(lines) if lines else 0.0
        candidates.append({"direction": direction, "text": text, "confidence": round(confidence, 6), "selection_score": round(confidence + min(24, len(text)) * 0.002, 6), "lines": lines})
    selected = max(candidates, key=lambda item: item["selection_score"])
    confidence = selected["confidence"]
    return {"image": str(path), "engine": "rapidocr-onnx-gpu", "text": selected["text"], "confidence": confidence, "quality": "high" if confidence >= .8 else "medium" if confidence >= .55 else "low", "direction": selected["direction"], "lines": selected["lines"], "candidates": candidates}


def save(output: Path, input_dir: Path, records: dict[str, dict], elapsed: float) -> None:
    items = sorted(records.values(), key=lambda item: item["image"])
    (output / "ocr_results.json").write_text(json.dumps({"input": str(input_dir), "engine": "rapidocr-onnx-gpu", "records": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["image", "engine", "text", "confidence", "quality", "direction", "error"]
    with (output / "ocr_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({field: item.get(field, "") for field in fields} for item in items)
    summary = {"records": len(items), "errors": sum(bool(item.get("error")) for item in items), "nonempty_text": sum(bool(item.get("text")) for item in items), "rapidocr_gpu_records": sum(item.get("engine") == "rapidocr-onnx-gpu" for item in items), "elapsed_seconds_this_run": round(time.time() - elapsed, 2)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    opt = args(); output = opt.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    images = sorted(opt.input.resolve().rglob("*_clahe.jpg"))
    prior = read_json(opt.resume_from) + read_json(output / "ocr_results.json")
    records = {str(Path(item["image"]).resolve()): item for item in prior if item.get("image")}
    pending = [path for path in images if str(path.resolve()) not in records]
    if opt.max_images: pending = pending[:opt.max_images]
    prepare_cuda()
    import onnxruntime as ort
    if "CUDAExecutionProvider" not in ort.get_available_providers(): raise RuntimeError("未检测到 ONNX CUDA Provider")
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR(det_use_cuda=True, det_model_path=None, rec_use_cuda=True, rec_model_path=None, cls_use_cuda=True, cls_model_path=None, text_score=0)
    started = time.time()
    for index, path in enumerate(pending, 1):
        try: record = recognize(ocr, path)
        except Exception as exc: record = {"image": str(path), "engine": "rapidocr-onnx-gpu", "error": f"{type(exc).__name__}: {exc}"}
        records[str(path.resolve())] = record; save(output, opt.input.resolve(), records, started)
        print(f"[{index}/{len(pending)}] {path.name}: {record.get('text','')[:40]} ({record.get('confidence',0):.3f})")
    save(output, opt.input.resolve(), records, started); print((output / "summary.json").read_text(encoding="utf-8")); return 0


if __name__ == "__main__": sys.exit(main())
