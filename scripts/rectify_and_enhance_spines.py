"""Perspective rectify and locally enhance the mask crops produced in step 5."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def order_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2):
        raise ValueError(f'Expected four corners, got {points.shape}')
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).reshape(-1)
    return np.array([
        points[np.argmin(total)], points[np.argmin(diff)],
        points[np.argmax(total)], points[np.argmax(diff)],
    ], dtype=np.float32)


def rectify(image: np.ndarray, polygon: list[list[int]], crop_box: list[int]) -> tuple[np.ndarray, dict]:
    x1, y1, x2, y2 = crop_box
    points = np.asarray(polygon, dtype=np.float32) - np.array([x1, y1], dtype=np.float32)
    points[:, 0] = np.clip(points[:, 0], 0, x2 - x1 - 1)
    points[:, 1] = np.clip(points[:, 1], 0, y2 - y1 - 1)
    if len(points) < 3:
        raise ValueError('Polygon has fewer than three points')
    rect = cv2.minAreaRect(points.reshape(-1, 1, 2))
    corners = order_points(cv2.boxPoints(rect))
    width = max(16, int(round(max(np.linalg.norm(corners[1] - corners[0]), np.linalg.norm(corners[2] - corners[3])))))
    height = max(16, int(round(max(np.linalg.norm(corners[3] - corners[0]), np.linalg.norm(corners[2] - corners[1])))))
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(corners, target)
    warped = cv2.warpPerspective(image, matrix, (width, height), borderValue=(255, 255, 255))
    rotated = False
    if warped.shape[1] > warped.shape[0]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE)
        rotated = True
    return warped, {'source_polygon_points': len(polygon), 'local_corners': corners.round(3).tolist(),
                    'rectified_size': [int(warped.shape[1]), int(warped.shape[0])],
                    'rotated_to_vertical': rotated}


def enhance(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    height = image.shape[0]
    scale = max(1.0, min(2.0, 1600.0 / max(1, height)))
    if scale != 1.0:
        size = (max(16, int(round(image.shape[1] * scale))), max(16, int(round(height * scale))))
        image = cv2.resize(image, size, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = cv2.cvtColor(cv2.merge((clahe.apply(l_channel), a_channel, b_channel)), cv2.COLOR_LAB2BGR)
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    return enhanced, gray


def read_image(path: Path) -> np.ndarray:
    """Read Windows paths containing non-ASCII characters reliably."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'Cannot read crop: {path}')
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    encoded_ok, encoded = cv2.imencode(path.suffix or '.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not encoded_ok:
        raise ValueError(f'Cannot encode image: {path}')
    encoded.tofile(str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True, help='Step 5 detections.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    crop_root = args.manifest.parent.parent
    args.output.mkdir(parents=True, exist_ok=True)
    rows, failures = [], []
    for image_row in manifest['images']:
        for detection in image_row.get('detections', []):
            # The manifest stores paths relative to the crops directory.
            crop_path = crop_root / Path(detection['crop_path'])
            out_dir = args.output / Path(image_row['image']).stem
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = f"spine_{int(detection['index']):03d}"
            try:
                image = read_image(crop_path)
                warped, geometry = rectify(image, detection['polygon'], detection['crop_box_xyxy'])
                enhanced, gray = enhance(warped)
                rectified_path = out_dir / f'{stem}_rectified.jpg'
                enhanced_path = out_dir / f'{stem}_clahe.jpg'
                gray_path = out_dir / f'{stem}_gray.jpg'
                write_image(rectified_path, warped)
                write_image(enhanced_path, enhanced)
                write_image(gray_path, gray)
                rows.append({'image': image_row['image'], 'index': detection['index'],
                             'confidence': detection['confidence'], 'source_crop': str(crop_path),
                             'rectified_path': str(rectified_path), 'clahe_path': str(enhanced_path),
                             'gray_path': str(gray_path), **geometry})
            except Exception as exc:
                failures.append({'image': image_row['image'], 'index': detection['index'], 'error': str(exc)})
    output_manifest = {'source_manifest': str(args.manifest), 'count': len(rows), 'failures': failures, 'items': rows}
    (args.output / 'preprocess.json').write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'processed': len(rows), 'failures': len(failures), 'output': str(args.output)}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
