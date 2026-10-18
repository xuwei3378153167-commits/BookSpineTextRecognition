"""Resume the official model weight download in verified HTTP ranges."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time

import httpx
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
REVISION = "c5630abae1d940eafe0697512a0325494b02ab42"
REPO = "PaddlePaddle/PaddleOCR-VL-1.6"


def main():
    info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
    weight = next(f for f in info.siblings if f.rfilename == "model.safetensors")
    total = weight.size
    expected = weight.lfs.sha256
    directory = ROOT / "weights" / "PaddleOCR-VL-1.6"
    directory.mkdir(parents=True, exist_ok=True)
    chunks = ROOT / "dependencies" / "downloads" / "paddlevl16"
    chunks.mkdir(parents=True, exist_ok=True)
    target = directory / "model.safetensors"
    if target.is_file() and hashlib.file_digest(target.open("rb"), "sha256").hexdigest() == expected:
        print("Model already verified", flush=True)
        return
    size = 8 * 1024 * 1024
    url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/model.safetensors"
    def download(index):
        start, end = index * size, min((index + 1) * size, total) - 1
        part = chunks / f"{index:04d}.part"
        if part.exists() and part.stat().st_size == end - start + 1:
            return index
        for attempt in range(5):
            try:
                with httpx.Client(follow_redirects=True, timeout=60) as client:
                    response = client.get(url + f"?chunk={index}", headers={"Range": f"bytes={start}-{end}"})
                    response.raise_for_status()
                    if response.status_code != 206 or response.headers.get("content-range") != f"bytes {start}-{end}/{total}":
                        raise RuntimeError("Unexpected range response")
                    if len(response.content) != end - start + 1:
                        raise RuntimeError("Incomplete range")
                    part.write_bytes(response.content)
                    return index
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2)
    count = (total + size - 1) // size
    with ThreadPoolExecutor(max_workers=16) as pool:
        for done, _ in enumerate(as_completed([pool.submit(download, i) for i in range(count)]), 1):
            _.result()
            if done % 10 == 0 or done == count:
                print(f"Downloaded {done}/{count} chunks", flush=True)
    temporary = target.with_suffix(".partial")
    digest = hashlib.sha256()
    with temporary.open("wb") as output:
        for index in range(count):
            data = (chunks / f"{index:04d}.part").read_bytes()
            digest.update(data)
            output.write(data)
    if digest.hexdigest() != expected:
        raise RuntimeError("SHA256 mismatch")
    temporary.replace(target)
    (directory / "deployment.json").write_text(json.dumps({
        "repo": REPO, "revision": REVISION, "weight_bytes": total,
        "sha256": expected, "verified": True}, indent=2), encoding="utf-8")
    for part in chunks.glob("*.part"):
        part.unlink()
    print("Weight SHA256 verified", flush=True)


if __name__ == "__main__":
    main()
