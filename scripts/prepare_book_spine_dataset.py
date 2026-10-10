"""Prepare the downloaded LabelMe dataset; run with the project venv Python."""
import hashlib
import json
import math
import random
import shutil
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'dataset/raw'
SOURCE = RAW / 'book-spine-dataset-main'
OUT = ROOT / 'outputs/dataset_preparation'


def clip_polygon(points, width, height):
    # Sutherland-Hodgman clipping preserves edge intersections at image borders.
    for axis, bound, lower in [(0, 0, True), (0, width, False),
                                (1, 0, True), (1, height, False)]:
        result = []
        if not points:
            break
        previous = points[-1]
        def inside(p):
            return p[axis] >= bound if lower else p[axis] <= bound
        for current in points:
            if inside(current) != inside(previous):
                t = (bound - previous[axis]) / (current[axis] - previous[axis])
                result.append([previous[k] + t * (current[k] - previous[k]) for k in (0, 1)])
            if inside(current):
                result.append(current)
            previous = current
        points = result
    clean = []
    for point in points:
        if not clean or point != clean[-1]:
            clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return clean


def main():
    # Refuse to mix this dataset into existing prepared images/labels.
    for kind in ('images', 'labels'):
        if any(p.is_file() and p.name != '.gitkeep' for p in (ROOT / 'dataset' / kind).rglob('*')):
            raise RuntimeError('Prepared dataset is not empty; preserve it before rerunning.')
    OUT.mkdir(parents=True, exist_ok=True)
    archive = RAW / 'book-spine-dataset-main.zip'
    if not SOURCE.exists():
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                target = (RAW / member.filename).resolve()
                if not target.is_relative_to(RAW.resolve()):
                    raise ValueError('Unsafe archive path')
            z.extractall(RAW)
    counts, issues, records, seen = Counter(), [], [], {}
    annotations = sorted((SOURCE / 'labelme_jsons').glob('*.json'))
    images = {p.stem: p for p in (SOURCE / 'origin_images').iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png')}
    for annotation in annotations:
        data = json.loads(annotation.read_text(encoding='utf-8-sig'))
        path = images[annotation.stem]
        with Image.open(path) as im:
            im.load()
            width, height = im.size
            if im.getexif().get(274, 1) != 1:
                raise ValueError(f'EXIF orientation needs review: {path.name}')
            digest = hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()
        if (width, height) != (data['imageWidth'], data['imageHeight']):
            raise ValueError(f'Image dimensions mismatch: {path.name}')
        if digest in seen:
            issues.append({'file': path.name, 'reason': 'duplicate image', 'original': seen[digest]})
            counts['duplicate_images'] += 1
            continue
        seen[digest] = path.name
        lines = []
        for index, shape in enumerate(data['shapes']):
            kind = shape['shape_type']
            counts['source_' + kind] += 1
            if annotation.name == '342.json' and index == 1:
                counts['duplicate_instances'] += 1
                issues.append({'file': path.name, 'shape': index, 'reason': 'visually confirmed overlapping annotation of shape 0'})
                continue
            if shape['label'].strip().lower() not in ('book', '1', 'pp'):
                raise ValueError(f'Unexpected class {shape["label"]!r}')
            if shape['label'] != 'book':
                counts['corrected_class_names'] += 1
                issues.append({'file': path.name, 'shape': index, 'reason': 'visually confirmed spine class alias', 'old_label': shape['label']})
            points = shape['points']
            if kind == 'rectangle' and len(points) == 2:
                (x1, y1), (x2, y2) = points
                points = [[min(x1,x2),min(y1,y2)], [max(x1,x2),min(y1,y2)],
                          [max(x1,x2),max(y1,y2)], [min(x1,x2),max(y1,y2)]]
            elif kind not in ('polygon', 'oriented_rectangle'):
                raise ValueError(f'Unsupported shape: {kind}')
            if kind == 'oriented_rectangle' and len(points) != 4:
                raise ValueError(f'Expected four rotated rectangle corners: {path.name}')
            if not all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in points):
                raise ValueError(f'Invalid coordinates in {path.name}')
            if any(not (0 <= x <= width and 0 <= y <= height) for x, y in points):
                counts['clipped_instances'] += 1
            points = clip_polygon(points, width, height)
            area = abs(sum(points[i-1][0]*p[1] - p[0]*points[i-1][1] for i,p in enumerate(points))) / 2
            if len(points) < 3 or area < 1:
                issues.append({'file': path.name, 'shape': index, 'reason': 'degenerate polygon'})
                counts['skipped_instances'] += 1
                continue
            values = [value for x,y in points for value in (x/width, y/height)]
            line = '0 ' + ' '.join(f'{v:.8f}' for v in values)
            if line in lines:
                counts['duplicate_instances'] += 1
                issues.append({'file': path.name, 'shape': index, 'reason': 'duplicate polygon'})
                continue
            lines.append(line)
        if not lines:
            raise ValueError(f'No usable instances: {path.name}')
        records.append((path, lines, digest))
    if set(images) != {p.stem for p in annotations}:
        raise ValueError('Image/annotation pairs do not match')
    random.Random(42).shuffle(records)
    records = records[:500]
    total = len(records)
    train_end, val_end = int(total*.8), int(total*.8) + int(total*.1)
    manifest = []
    for index, (path, lines, digest) in enumerate(records):
        split = 'train' if index < train_end else 'val' if index < val_end else 'test'
        for kind in ('images', 'labels'):
            (ROOT / 'dataset' / kind / split).mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, ROOT / 'dataset/images' / split / path.name)
        (ROOT / 'dataset/labels' / split / (path.stem+'.txt')).write_text('\n'.join(lines)+'\n', encoding='utf-8')
        counts[split + '_images'] += 1
        counts[split + '_instances'] += len(lines)
        manifest.append({'image': path.name, 'split': split, 'instances': len(lines), 'pixel_sha256': digest})
    # Verify the serialized labels, image pairs and disjoint image hashes.
    for row in manifest:
        label = ROOT / 'dataset/labels' / row['split'] / (Path(row['image']).stem+'.txt')
        for line in label.read_text().splitlines():
            tokens = line.split()
            assert tokens[0] == '0' and len(tokens) >= 7 and len(tokens) % 2 == 1
            assert all(0 <= float(v) <= 1 for v in tokens[1:])
    assert len({r['pixel_sha256'] for r in manifest}) == len(manifest)
    report = {'source': 'https://github.com/wenrenchuyu/book-spine-dataset',
              'archive_sha256': hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest(),
              'seed': 42, 'source_images': len(images), 'prepared_images': total,
              'counts': dict(counts), 'issues': issues, 'manifest': manifest}
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    canvas = Image.new('RGB', (1200, 900), 'white')
    for index, (path, lines, _) in enumerate(records[:9]):
        with Image.open(path) as original:
            im = original.convert('RGB')
        width, height = im.size
        im.thumbnail((390, 270))
        draw = ImageDraw.Draw(im)
        for line in lines:
            values = list(map(float, line.split()[1:]))
            points = [(values[i]*im.width, values[i+1]*im.height) for i in range(0,len(values),2)]
            draw.line(points+[points[0]], fill=(0,255,60), width=2)
        x,y = (index%3)*400, (index//3)*300
        canvas.paste(im,(x,y+22))
        ImageDraw.Draw(canvas).text((x+5,y+3),path.name,fill='black')
    canvas.save(OUT / 'annotation_preview.jpg')
    (ROOT / 'data.yaml').write_text('path: ' + json.dumps(ROOT.as_posix(), ensure_ascii=False) + '\ntrain: dataset/images/train\nval: dataset/images/val\ntest: dataset/images/test\n\nnames:\n  0: spine\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'manifest'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
