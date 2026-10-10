"""Validate all pairs with Ultralytics, recording any JPEG repairs."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = ROOT / 'dependencies/ultralytics-config'
config.mkdir(parents=True, exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(config)
from ultralytics.data.utils import verify_image_label

report_path = ROOT / 'outputs/dataset_preparation/report.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
messages, errors, total = [], [], 0
for row in report['manifest']:
    image = ROOT / 'dataset/images' / row['split'] / row['image']
    label = ROOT / 'dataset/labels' / row['split'] / (image.stem + '.txt')
    args = (str(image), str(label), '', False, 1, 0, 0, False)
    result = verify_image_label(args)
    if result[9]:
        messages.append(result[9])
        result = verify_image_label(args)
    if any(result[i] for i in (5, 7, 8)) or result[9] or len(result[3]) != row['instances']:
        errors.append({'image': row['image'], 'message': result[9]})
    total += len(result[3]) if result[3] is not None else 0
summary = {'images': len(report['manifest']), 'segments': total,
           'repair_messages': messages, 'errors': errors}
(ROOT / 'outputs/dataset_preparation/yolo_validation_final.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'images': summary['images'], 'segments': total, 'errors': errors}))
if errors:
    raise SystemExit(1)
