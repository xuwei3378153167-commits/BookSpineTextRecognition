"""Clean, score, sort, and review local book-spine OCR results.

This stage consumes OCR output without changing the original OCR JSON.  It
joins each crop with preprocessing and detection metadata, assigns a quality
level, sorts books in shelf reading order, and writes a review queue.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


ALLOWED_TEXT = re.compile(r"[^\u3400-\u9fffA-Za-z0-9，。！？：、（）《》“”‘’\-·]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post-process local book-spine OCR results")
    parser.add_argument("--ocr", type=Path, default=Path("outputs/ocr_rapid_gpu_test/ocr_results.json"))
    parser.add_argument("--preprocess", type=Path, default=Path("crops/preprocessed_test/preprocess.json"))
    parser.add_argument("--detections", type=Path, default=Path("crops/detected_test/detections.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/ocr_postprocessed"))
    parser.add_argument("--medium-threshold", type=float, default=0.55)
    parser.add_argument("--high-threshold", type=float, default=0.80)
    parser.add_argument("--review-threshold", type=float, default=0.55)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clean_text(value: Any) -> str:
    text = str(value or "").replace(" ", "").replace("\n", "").replace("|", "一")
    return ALLOWED_TEXT.sub("", text)


def quality(confidence: float, medium: float, high: float) -> str:
    if confidence >= high:
        return "high"
    if confidence >= medium:
        return "medium"
    return "low"


def normalize(path: str | Path) -> str:
    return str(Path(path).resolve()).lower()


def crop_key(path: str | Path) -> tuple[str, int | None]:
    value = Path(path)
    match = re.search(r"(?:^|[\\/])(\d+)[\\/]spine_(\d+)(?:_|\.)", str(value))
    if not match:
        return value.stem, None
    return match.group(1), int(match.group(2))


def build_metadata(
    preprocess: dict[str, Any], detections: dict[str, Any]
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, dict[str, Any]]]:
    metadata: dict[tuple[str, int], dict[str, Any]] = {}
    by_crop: dict[str, dict[str, Any]] = {}
    for item in preprocess.get("items", []):
        index = item.get("index")
        source = Path(item.get("image", "")).stem
        if index is not None:
            metadata[(source, int(index))] = dict(item)
        for path_key in ("clahe_path", "rectified_path", "gray_path"):
            if item.get(path_key):
                by_crop[normalize(item[path_key])] = dict(item)

    detection_by_image: dict[str, dict[str, Any]] = {}
    for image in detections.get("images", []):
        source = Path(image.get("image", "")).stem
        detection_by_image[source] = image
        for detection in image.get("detections", []):
            index = detection.get("index")
            if index is None:
                continue
            key = (source, int(index))
            metadata.setdefault(key, {}).update(
                {
                    "source_image": image.get("image"),
                    "detection": detection,
                }
            )
            for path_key in ("clahe_path", "rectified_path", "gray_path"):
                crop_path = metadata[key].get(path_key)
                if crop_path:
                    by_crop[normalize(crop_path)] = metadata[key]
    return metadata, by_crop


def center_and_size(detection: dict[str, Any]) -> tuple[float, float, float]:
    box = detection.get("bbox_xyxy") or [0, 0, 0, 0]
    left, top, right, bottom = (float(item) for item in box)
    return (left + right) / 2, (top + bottom) / 2, max(1.0, bottom - top)


def assign_rows(records: list[dict[str, Any]]) -> None:
    positioned = [record for record in records if record.get("center_y") is not None]
    if not positioned:
        for record in records:
            record["row"] = 1
        return
    heights = [record["box_height"] for record in positioned]
    threshold = max(80.0, median(heights) * 0.45)
    rows: list[list[dict[str, Any]]] = []
    for record in sorted(positioned, key=lambda item: item["center_y"]):
        if not rows or record["center_y"] - median(item["center_y"] for item in rows[-1]) > threshold:
            rows.append([])
        rows[-1].append(record)
    for row_number, row in enumerate(rows, 1):
        for record in row:
            record["row"] = row_number
    for record in records:
        record.setdefault("row", 1)


def review_reasons(record: dict[str, Any], threshold: float) -> list[str]:
    reasons: list[str] = []
    if not record.get("text"):
        reasons.append("empty_text")
    if record.get("confidence") is None:
        reasons.append("confidence_unavailable")
    elif float(record.get("confidence", 0.0)) < threshold:
        reasons.append("low_confidence")
    if record.get("hit_token_limit"):
        reasons.append("output_truncated")
    if len(record.get("text", "")) < 2:
        reasons.append("short_text")
    candidates = record.get("candidates") or []
    scores = sorted((float(item.get("selection_score", 0.0)) for item in candidates), reverse=True)
    if len(scores) >= 2 and scores[0] - scores[1] < 0.03:
        reasons.append("ambiguous_direction")
    if record.get("detection_confidence", 1.0) < 0.50:
        reasons.append("weak_detection")
    return reasons


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "source_image", "book_id", "row", "column", "text", "confidence", "quality",
        "direction", "detection_confidence", "crop_path", "needs_review", "review_reasons",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ocr_payload = load_json(args.ocr.resolve())
    metadata, metadata_by_crop = build_metadata(
        load_json(args.preprocess.resolve()), load_json(args.detections.resolve())
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors = 0
    for source_record in ocr_payload.get("records", []):
        source_path = source_record.get("image", "")
        source, index = crop_key(source_path)
        item = dict(source_record)
        item["text"] = clean_text(item.get("text", ""))
        if source_record.get("confidence_available") is False:
            item["confidence"] = None
            item["quality"] = "unknown"
        else:
            item["confidence"] = round(float(item.get("confidence", 0.0) or 0.0), 6)
            item["quality"] = quality(item["confidence"], args.medium_threshold, args.high_threshold)
        item["book_id"] = index
        item["source_key"] = source
        item["crop_path"] = source_path
        item["error"] = item.get("error", "")
        if item["error"]:
            errors += 1
        meta = metadata_by_crop.get(normalize(source_path), {})
        if not meta:
            meta = metadata.get((source, index or -1), {})
        detection = meta.get("detection", {})
        item["source_image"] = meta.get("image") or meta.get("source_image") or f"{source}.jpg"
        if item["book_id"] is None and meta.get("index") is not None:
            item["book_id"] = int(meta["index"])
        item["detection_confidence"] = round(float(detection.get("confidence", 0.0) or 0.0), 6)
        if detection:
            center_x, center_y, box_height = center_and_size(detection)
            item["center_x"], item["center_y"], item["box_height"] = center_x, center_y, box_height
            item["bbox_xyxy"] = detection.get("bbox_xyxy")
        else:
            item["center_x"] = item["center_y"] = None
            item["box_height"] = 1.0
        item["review_reasons"] = review_reasons(item, args.review_threshold)
        item["needs_review"] = bool(item["review_reasons"])
        grouped[item["source_image"]].append(item)

    all_records: list[dict[str, Any]] = []
    for source_image, records in sorted(grouped.items()):
        assign_rows(records)
        records.sort(key=lambda item: (item.get("row", 1), item.get("center_x") or 0, item.get("book_id") or 0))
        for column, record in enumerate(records, 1):
            record["column"] = column
            record["source_key"] = None
            record.pop("candidates", None)
            record.pop("center_x", None)
            record.pop("center_y", None)
            record.pop("box_height", None)
        all_records.extend(records)

    review_records = [record for record in all_records if record.get("needs_review")]
    payload = {
        "input": str(args.ocr.resolve()),
        "records": all_records,
        "summary": {
            "total": len(all_records),
            "errors": errors,
            "nonempty_text": sum(bool(item.get("text")) for item in all_records),
            "high": sum(item.get("quality") == "high" for item in all_records),
            "medium": sum(item.get("quality") == "medium" for item in all_records),
            "low": sum(item.get("quality") == "low" for item in all_records),
            "unknown": sum(item.get("quality") == "unknown" for item in all_records),
            "needs_review": len(review_records),
            "source_images": len(grouped),
        },
    }
    (output / "ocr_postprocessed.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    grouped_payload = {
        "source": str(args.ocr.resolve()),
        "images": [
            {
                "image": source_image,
                "books": [
                    {
                        "id": item.get("book_id"),
                        "text": item.get("text", ""),
                        "confidence": item.get("confidence", 0.0),
                        "quality": item.get("quality", "low"),
                        "direction": item.get("direction"),
                        "bbox": item.get("bbox_xyxy"),
                        "crop_path": item.get("crop_path"),
                        "row": item.get("row", 1),
                        "column": item.get("column", 1),
                        "needs_review": item.get("needs_review", False),
                        "review_reasons": item.get("review_reasons", []),
                    }
                    for item in records
                ],
            }
            for source_image, records in sorted(grouped.items())
        ],
    }
    (output / "books_by_image.json").write_text(
        json.dumps(grouped_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(output / "ocr_postprocessed.csv", all_records)
    write_csv(output / "review_queue.csv", review_records)
    (output / "summary.json").write_text(json.dumps(payload["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
