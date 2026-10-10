"""Evaluate the finished best checkpoint on the held-out test split."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'dependencies/ultralytics-config'))

from ultralytics import YOLO

def main():
    weights = ROOT / 'outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt'
    if not weights.is_file():
        raise FileNotFoundError(weights)

    metrics = YOLO(str(weights)).val(
        data=str(ROOT / 'data.yaml'),
        split='test',
        imgsz=1024,
        batch=2,
        device=0,
        workers=0,
        project=str(ROOT / 'outputs/training'),
        name='book-spine-test-evaluation',
        exist_ok=True,
        plots=True,
    )
    print({key: round(float(value), 6) for key, value in metrics.results_dict.items()})


if __name__ == '__main__':
    from multiprocessing import freeze_support

    freeze_support()
    main()
