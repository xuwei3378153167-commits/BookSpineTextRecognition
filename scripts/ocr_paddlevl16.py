"""Offline PaddleOCR-VL 1.6 inference using the official Transformers backend."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "dependencies" / "huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
PROMPTS = {"ocr": "OCR:", "spotting": "Spotting:", "table": "Table Recognition:",
           "formula": "Formula Recognition:", "chart": "Chart Recognition:",
           "seal": "Seal Recognition:"}


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Image or directory; relative paths use project root")
    parser.add_argument("--output", default="outputs/paddlevl16")
    parser.add_argument("--model", default="weights/PaddleOCR-VL-1.6")
    parser.add_argument("--task", choices=PROMPTS, default="ocr")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0,
                        help="Rotate counterclockwise before recognition")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--max-pixels", type=int, default=1003520)
    parser.add_argument("--max-images", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--book-spines", action="store_true",
                        help="Consume only rectified crops and emit the book-spine pipeline schema")
    args = parser.parse_args()
    source, out, model_path = map(project_path, [args.input, args.output, args.model])
    if not source.exists():
        parser.error(f"Input does not exist: {source}")
    if not (model_path / "model.safetensors").is_file():
        parser.error(f"Model missing: {model_path}; run scripts/install_paddlevl16.ps1")
    files = [source] if source.is_file() else sorted(
        p for p in source.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        and (not args.book_spines or p.stem.endswith("_rectified")))
    if args.max_images:
        files = files[:args.max_images]
    if not files:
        if args.book_spines:
            out.mkdir(parents=True, exist_ok=True)
            (out / "ocr_results.json").write_text('{"records": [], "results": []}', encoding="utf-8")
            return
        parser.error("No images found")

    import torch
    from PIL import Image, ImageOps
    from transformers import AutoModelForImageTextToText, AutoProcessor
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; use --device cpu explicitly for CPU inference")
    dtype = torch.bfloat16 if args.device.startswith("cuda") else torch.float32
    started = time.perf_counter()
    model = AutoModelForImageTextToText.from_pretrained(
        str(model_path), dtype=dtype, local_files_only=True,
        attn_implementation="sdpa").to(args.device).eval()
    processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
    runtime = {name: importlib.metadata.version(name) for name in ("torch", "transformers", "accelerate")}
    load_seconds = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    target = out / "ocr_results.json"
    existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() and not args.overwrite else {}
    records = existing.get("results", [])
    completed = {(r["image"], r.get("task"), r.get("rotate")) for r in records if not r.get("error")}
    for path in files:
        if (str(path), args.task, args.rotate) in completed:
            continue
        started = time.perf_counter()
        record = {"image": str(path), "task": args.task, "rotate": args.rotate}
        if args.book_spines:
            record.update(engine="paddlevl16", confidence=None, confidence_available=False,
                          direction={0: "normal", 90: "counterclockwise", 180: "180", 270: "clockwise"}[args.rotate])
        try:
            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
            if args.rotate:
                image = image.rotate(args.rotate, expand=True)
            if args.task == "spotting" and max(image.size) < 1500:
                image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
            messages = [{"role": "user", "content": [
                {"type": "image", "image": image}, {"type": "text", "text": PROMPTS[args.task]}]}]
            inputs = processor.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                return_tensors="pt", processor_kwargs={"images_kwargs": {"size": {
                    "shortest_edge": processor.image_processor.size["shortest_edge"],
                    "longest_edge": args.max_pixels}}}).to(model.device)
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
            tokens = generated[0, inputs["input_ids"].shape[-1]:]
            record["text"] = processor.decode(tokens, skip_special_tokens=True)
            record["generated_tokens"] = len(tokens)
            record["hit_token_limit"] = len(tokens) >= args.max_new_tokens
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        record["seconds"] = round(time.perf_counter() - started, 3)
        records = [r for r in records if (r["image"], r.get("task"), r.get("rotate")) !=
                   (str(path), args.task, args.rotate)] + [record]
        report = {"model": "PaddlePaddle/PaddleOCR-VL-1.6", "model_path": str(model_path),
                  "backend": "transformers", "device": args.device, "dtype": str(dtype), "runtime": runtime,
                  "load_seconds": round(load_seconds, 3), "results": records}
        if args.device.startswith("cuda"):
            report["peak_cuda_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 1024**2, 1)
        if args.book_spines:
            report["records"] = records
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        (out / "ocr_results.txt").write_text("\n\n".join(
            f"{r['image']}\n{r.get('text', r.get('error', ''))}" for r in records), encoding="utf-8-sig")
        print(json.dumps(record, ensure_ascii=False), flush=True)
    if any(r.get("error") for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
