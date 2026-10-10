"""Train the project YOLO instance segmentation model on the prepared dataset."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'dependencies/ultralytics-config'))

def main():
    import torch
    from ultralytics import YOLO, settings

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is not available; refusing to start CPU training.')

    gpu = torch.cuda.get_device_properties(0)
    if gpu.major < 12:
        raise RuntimeError(f'Unexpected GPU architecture: {gpu.name} sm_{gpu.major}{gpu.minor}')

    # Exercise CUDA before starting the training run.
    a = torch.randn((1024, 1024), device='cuda')
    b = a @ a
    torch.cuda.synchronize()
    print(f'GPU smoke test passed: {gpu.name}, {gpu.total_memory // (1024**3)} GiB')
    del a, b
    torch.cuda.empty_cache()

    settings.update({
        'weights_dir': str(ROOT / 'weights'),
        'runs_dir': str(ROOT / 'outputs/training'),
    })

    checkpoint = ROOT / 'outputs/training/book-spine-yolo11n-seg-20261008/weights/last.pt'
    resume = checkpoint.is_file() and os.environ.get('SPINE_RESUME', '1') == '1'
    model = YOLO(str(checkpoint if resume else ROOT / 'weights/yolo11n-seg.pt'))
    train_args = dict(
        data=str(ROOT / 'data.yaml'),
        task='segment',
        epochs=100,
        patience=20,
        imgsz=1024,
        batch=2,
        device=0,
        workers=4,
        project=str(ROOT / 'outputs/training'),
        name='book-spine-yolo11n-seg-20261008',
        exist_ok=True,
        pretrained=True,
        seed=42,
        deterministic=False,
        amp=True,
        cache=False,
        close_mosaic=10,
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
        resume=resume,
    )
    if not resume:
        train_args['optimizer'] = 'auto'
    results = model.train(**train_args)
    print(f'Training finished. Results: {results.save_dir}')


if __name__ == '__main__':
    from multiprocessing import freeze_support

    freeze_support()
    main()
