"""Review only low-confidence local OCR results with an OpenAI-compatible vision API.

The script deliberately keeps the local OCR result unchanged.  It writes a new
review package that records both engines' output and a merged result, so every
cloud-assisted change remains traceable.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np


PROMPT = """你是图书书脊文字转录员。请只转录这张书脊裁剪图中实际可见的文字。
要求：保留原有语言、大小写、数字和必要标点；竖排文字按从上到下顺序输出；不要猜测、补全、翻译或解释；图片没有可辨文字时输出空字符串。只输出转录结果本身，不要使用引号、Markdown 或说明。"""
VISION_MODEL_HINT = re.compile(r"vision|vl|gpt-4o|gpt-4\.1|gemini|claude|qwen|glm-4v|internvl|yi-vl", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use a vision API to review low-confidence book-spine OCR only.")
    parser.add_argument("--input", type=Path, default=Path("outputs/ocr_rapid_gpu_test/ocr_results.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/vlm_review_low_confidence"))
    parser.add_argument("--threshold", type=float, default=0.55, help="Review local OCR below this confidence (default: 0.55).")
    parser.add_argument("--base-url", default=os.getenv("VLM_BASE_URL", ""), help="OpenAI-compatible API base URL, normally ending in /v1.")
    parser.add_argument("--api-key", default=os.getenv("VLM_API_KEY", ""), help="API key. Prefer the VLM_API_KEY environment variable.")
    parser.add_argument("--model", default=os.getenv("VLM_MODEL", ""), help="Vision model name. Omit to query /models and choose a likely vision model.")
    parser.add_argument("--max-images", type=int, default=0, help="Maximum number of candidates for a trial run.")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--interval", type=float, default=0.25, help="Seconds between API requests.")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-side", type=int, default=2400, help="Largest image side sent to the API.")
    parser.add_argument("--dry-run", action="store_true", help="Write the candidate manifest without contacting an API.")
    return parser.parse_args()


def api_root(base_url: str) -> str:
    root = base_url.strip().rstrip("/")
    if not root:
        raise ValueError("缺少 Base URL。请通过 --base-url 或 VLM_BASE_URL 提供 OpenAI 兼容 API 地址。")
    if root.endswith("/chat/completions"):
        return root[: -len("/chat/completions")]
    return root


def read_records(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取 OCR 结果 {path}: {exc}") from exc
    if not isinstance(records, list):
        raise RuntimeError("OCR 结果中的 records 不是列表。")
    return records


def wants_review(record: dict, threshold: float) -> bool:
    if record.get("error"):
        return True
    text = str(record.get("text") or "").strip()
    try:
        confidence = float(record.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return not text or confidence < threshold


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def image_data_url(path: Path, max_side: int) -> str:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("图片无法读取")
    height, width = image.shape[:2]
    scale = min(1.0, max_side / max(height, width))
    if scale < 1.0:
        image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("图片 JPEG 编码失败")
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")


def request_json(url: str, key: str, body: dict, timeout: int, retries: int) -> dict:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    for attempt in range(retries + 1):
        try:
            request = Request(url, data=raw, headers=headers, method="POST")
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace").replace("\n", " ")
            retryable = exc.code == 429 or exc.code >= 500
            message = f"HTTP {exc.code}: {detail}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            retryable = True
            message = f"{type(exc).__name__}: {exc}"
        if not retryable or attempt >= retries:
            raise RuntimeError(message)
        time.sleep(min(12, 2 ** attempt))
    raise AssertionError("unreachable")


def choose_model(root: str, key: str, timeout: int, requested: str) -> str:
    if requested.strip():
        return requested.strip()
    request = Request(root + "/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urlopen(request, timeout=timeout) as response:
            models = json.loads(response.read().decode("utf-8")).get("data", [])
    except Exception as exc:
        raise RuntimeError("未指定模型且无法从 /models 查询模型；请提供 VLM_MODEL 或 --model。") from exc
    ids = [str(item.get("id", "")) for item in models if isinstance(item, dict) and item.get("id")]
    matches = [model for model in ids if VISION_MODEL_HINT.search(model)]
    if not matches:
        raise RuntimeError("/models 未返回可识别的视觉模型；请通过 VLM_MODEL 或 --model 指定支持图片输入的模型。")
    return matches[0]


def extract_text(payload: dict) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"API 响应没有 choices[0].message.content: {str(payload)[:500]}") from exc
    if isinstance(content, list):
        content = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    text = str(content or "").strip()
    text = re.sub(r"^```(?:text)?\s*|\s*```$", "", text, flags=re.I).strip()
    return " ".join(text.split())


def review_one(root: str, key: str, model: str, record: dict, timeout: int, retries: int, max_side: int) -> dict:
    image = Path(str(record.get("image", "")))
    if not image.is_file():
        raise RuntimeError(f"找不到裁剪图: {image}")
    body = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": image_data_url(image, max_side), "detail": "high"}},
        ]}],
    }
    response = request_json(root + "/chat/completions", key, body, timeout, retries)
    return {"text": extract_text(response), "model": model, "usage": response.get("usage", {}), "reviewed_at": datetime.now(timezone.utc).isoformat()}


def write_outputs(output: Path, input_path: Path, threshold: float, model: str | None, records: list[dict], reviews: dict[str, dict], dry_run: bool) -> None:
    merged = []
    review_items = []
    for record in records:
        item = dict(record)
        key = str(record.get("image", ""))
        review = reviews.get(key)
        if review:
            item["vlm_review"] = review
            if review.get("text"):
                item["text"] = review["text"]
                item["engine"] = "rapidocr-onnx-gpu+vlm-review"
                item["quality"] = "vlm_reviewed"
            item["local_ocr"] = {"text": record.get("text", ""), "confidence": record.get("confidence", 0), "quality": record.get("quality", "")}
            review_items.append({"image": key, "local_text": record.get("text", ""), "local_confidence": record.get("confidence", 0), "vlm_text": review.get("text", ""), "model": review.get("model", model or ""), "error": review.get("error", "")})
        merged.append(item)
    save_json(output / "review_results.json", {"input": str(input_path), "threshold": threshold, "model": model, "dry_run": dry_run, "reviewed_records": sorted(reviews.values(), key=lambda x: str(x.get("image", "")))})
    save_json(output / "ocr_results_merged.json", {"input": str(input_path), "engine": "local OCR plus optional VLM review", "records": merged})
    with (output / "review_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "local_text", "local_confidence", "vlm_text", "model", "error"])
        writer.writeheader(); writer.writerows(review_items)
    save_json(output / "summary.json", {"input_records": len(records), "threshold": threshold, "candidates": sum(wants_review(record, threshold) for record in records), "completed_reviews": sum(not item.get("error") for item in reviews.values()), "failed_reviews": sum(bool(item.get("error")) for item in reviews.values()), "model": model, "dry_run": dry_run})


def main() -> int:
    opt = parse_args()
    if not 0 <= opt.threshold <= 1:
        raise ValueError("--threshold 必须在 0 到 1 之间。")
    records = read_records(opt.input.resolve())
    candidates = [record for record in records if wants_review(record, opt.threshold)]
    if opt.max_images:
        candidates = candidates[:opt.max_images]
    output = opt.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    previous_path = output / "review_results.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")).get("reviewed_records", []) if previous_path.exists() else []
    reviews = {str(item.get("image", "")): item for item in previous if item.get("image")}
    if opt.dry_run:
        write_outputs(output, opt.input.resolve(), opt.threshold, opt.model or None, records, reviews, True)
        print(f"已生成候选清单：{len(candidates)} 个，未发送任何图片。")
        return 0
    if not opt.api_key:
        raise ValueError("缺少 API Key。请通过 VLM_API_KEY 或 --api-key 提供。")
    root = api_root(opt.base_url)
    model = choose_model(root, opt.api_key, opt.timeout, opt.model)
    pending = [record for record in candidates if str(record.get("image", "")) not in reviews or reviews[str(record.get("image", ""))].get("error")]
    print(f"模型：{model}；待复核 {len(pending)} / {len(candidates)} 个低置信度书脊。")
    for index, record in enumerate(pending, 1):
        key = str(record.get("image", ""))
        try:
            review = review_one(root, opt.api_key, model, record, opt.timeout, opt.max_retries, opt.max_side)
            review["image"] = key
        except Exception as exc:
            review = {"image": key, "model": model, "error": f"{type(exc).__name__}: {exc}"}
        reviews[key] = review
        write_outputs(output, opt.input.resolve(), opt.threshold, model, records, reviews, False)
        status = "失败" if review.get("error") else review.get("text", "")[:50]
        print(f"[{index}/{len(pending)}] {Path(key).name}: {status}")
        if index < len(pending) and opt.interval:
            time.sleep(opt.interval)
    write_outputs(output, opt.input.resolve(), opt.threshold, model, records, reviews, False)
    print(f"完成，结果目录：{output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
