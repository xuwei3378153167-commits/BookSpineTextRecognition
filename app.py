"""Local FastAPI entry point for the book-spine OCR pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "outputs" / "api_runs"
RUNS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Local Book Spine OCR", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": os.getenv("BOOK_SPINE_OCR_ENGINE", "rapid-gpu")}


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "input.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        raise HTTPException(status_code=415, detail="只支持 JPG、PNG、BMP 或 WEBP 图片")
    run_id = f"api-{uuid.uuid4().hex[:12]}"
    run_root = RUNS / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    source = run_root / f"input{suffix}"
    source.write_bytes(await file.read())
    command = [sys.executable, str(ROOT / "scripts/run_book_spine_pipeline.py"),
               "--source", str(source), "--output", str(RUNS), "--keep-run-id", run_id,
               "--detect-device", os.getenv("BOOK_SPINE_DETECT_DEVICE", "0"),
               "--ocr-engine", os.getenv("BOOK_SPINE_OCR_ENGINE", "rapid-gpu")]
    try:
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        summary = json.loads((run_root / "run_summary.json").read_text(encoding="utf-8"))
        structured = json.loads((run_root / "postprocessed" / "books_by_image.json").read_text(encoding="utf-8"))
        return {"run": summary, "result": structured}
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"本地推理失败: {exc.stderr[-2000:]}") from exc
