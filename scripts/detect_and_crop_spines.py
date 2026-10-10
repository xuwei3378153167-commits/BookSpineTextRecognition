"""Detect book spines with YOLO segmentation and save OCR-ready crops."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='An image file or a directory of images.')
    parser.add_argument('--weights', type=Path, default=root / 'outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt')
    parser.add_argument('--output', type=Path, default=root / 'crops/detected')
    parser.add_argument('--conf', type=float, default=0.35)
    parser.add_argument('--iou', type=float, default=0.50)
    parser.add_argument('--imgsz', type=int, default=1024)
    parser.add_argument('--margin', type=float, default=0.04, help='Relative padding around each mask bounding box.')
    parser.add_argument('--device', default='0', help='GPU index, cpu, or auto (default: 0).')
    parser.add_argument('--save-raw', action=argparse.BooleanOptionalAction, default=True)
    return parser


def image_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    raise FileNotFoundError(f'Source does not exist: {source}')


def crop_from_mask(image: np.ndarray, mask: np.ndarray, margin: float) -> tuple[np.ndarray, np.ndarray, list[int]]:
    height, width = image.shape[:2]
    ys, xs = np.where(mask)
    if len(xs) < 4:
        raise ValueError('Mask has fewer than four pixels')
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    pad_x = max(2, int((x2 - x1) * margin))
    pad_y = max(2, int((y2 - y1) * margin))
    x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    x2, y2 = min(width, x2 + pad_x), min(height, y2 + pad_y)
    local_mask = mask[y1:y2, x1:x2]
    crop = image[y1:y2, x1:x2].copy()
    # White outside the book spine keeps OCR input clean while preserving the mask interior.
    crop[~local_mask] = 255
    return crop, image[y1:y2, x1:x2], [x1, y1, x2, y2]


def polygon_from_mask(mask: np.ndarray, x1: int, y1: int) -> list[list[int]]:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea).reshape(-1, 2)
    return [[int(x + x1), int(y + y1)] for x, y in contour]


def main() -> None:
    args = build_parser().parse_args()
    if not args.weights.is_file():
        raise FileNotFoundError(f'Weights do not exist: {args.weights}')
    if not 0 <= args.conf <= 1 or not 0 <= args.iou <= 1:
        raise ValueError('--conf and --iou must be between 0 and 1')
    if args.margin < 0:
        raise ValueError('--margin must be non-negative')
    files = image_files(args.source)
    if not files:
        raise ValueError(f'No images found in {args.source}')
    args.output.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.weights))
    records: list[dict] = []
    for path in files:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            records.append({'image': path.name, 'error': 'OpenCV could not read image'})
            continue
        result = model.predict(source=image, conf=args.conf, iou=args.iou, imgsz=args.imgsz,
                               retina_masks=True, device=args.device, verbose=False)[0]
        annotated = result.plot(boxes=True, labels=True, masks=True)
        image_out = args.output / f'{path.stem}_detected{path.suffix.lower()}'
        cv2.imwrite(str(image_out), annotated)
        image_dir = args.output / path.stem
        image_dir.mkdir(parents=True, exist_ok=True)
        detections = []
        masks = result.masks.data.cpu().numpy() if result.masks is not None else np.empty((0, 1, 1))
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else np.empty((0, 4))
        scores = result.boxes.conf.cpu().numpy() if result.boxes is not None else np.empty((0,))
        for index, (raw_mask, score) in enumerate(zip(masks, scores), start=1):
            mask = cv2.resize(raw_mask.astype(np.uint8), (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            try:
                crop, raw_crop, crop_box = crop_from_mask(image, mask, args.margin)
            except ValueError:
                continue
            name = f'spine_{index:03d}.jpg'
            crop_path = image_dir / name
            cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            raw_path = None
            if args.save_raw:
                raw_path = image_dir / f'spine_{index:03d}_raw.jpg'
                cv2.imwrite(str(raw_path), raw_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            x1, y1, x2, y2 = crop_box
            detections.append({
                'index': index,
                'class_id': int(result.boxes.cls[index - 1].item()),
                'confidence': round(float(score), 6),
                'bbox_xyxy': [float(v) for v in boxes[index - 1]],
                'crop_box_xyxy': crop_box,
                'polygon': polygon_from_mask(mask[y1:y2, x1:x2], x1, y1),
                'crop_path': str(crop_path.relative_to(args.output.parent)),
                'raw_crop_path': str(raw_path.relative_to(args.output.parent)) if raw_path else None,
            })
        records.append({'image': str(path), 'annotated_path': str(image_out), 'detections': detections})
    manifest = args.output / 'detections.json'
    manifest.write_text(json.dumps({'weights': str(args.weights), 'conf': args.conf, 'iou': args.iou,
                                    'imgsz': args.imgsz, 'margin': args.margin, 'images': records},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    total = sum(len(row.get('detections', [])) for row in records)
    print(json.dumps({'images': len(records), 'detections': total, 'output': str(args.output), 'manifest': str(manifest)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
