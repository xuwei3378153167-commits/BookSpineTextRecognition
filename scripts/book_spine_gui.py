"""Temporary desktop GUI for local book-spine detection and OCR.

The GUI copies/downloads the requested image into a temporary directory, runs
the existing local pipeline, displays the annotated image and OCR text, and
removes the temporary directory when the window closes.
"""

from __future__ import annotations

import atexit
import json
import mimetypes
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, X, Y, StringVar, Tk, messagebox
from tkinter import filedialog, ttk


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


class BookSpineGui:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("本地书脊文字识别")
        self.root.geometry("1180x780")
        self.root.minsize(900, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.address = StringVar()
        self.engine = StringVar(value="rapid-gpu")
        self.detect_device = StringVar(value="0")
        self.status = StringVar(value="请输入本地图片路径或图片 URL")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.temp_root = Path(tempfile.mkdtemp(prefix="book_spine_gui_"))
        atexit.register(shutil.rmtree, self.temp_root, ignore_errors=True)
        self.preview_image = None

        self._build_ui()
        self._poll_events()

    def _build_ui(self) -> None:
        controls = ttk.Frame(self.root, padding=12)
        controls.pack(fill=X)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="图片地址").grid(row=0, column=0, padx=(0, 8), pady=4)
        address_entry = ttk.Entry(controls, textvariable=self.address)
        address_entry.grid(row=0, column=1, sticky="ew", pady=4)
        address_entry.bind("<Return>", lambda _event: self.start())
        ttk.Button(controls, text="选择图片", command=self.choose_file).grid(row=0, column=2, padx=8, pady=4)

        ttk.Label(controls, text="OCR 引擎").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
        engine_box = ttk.Combobox(
            controls,
            textvariable=self.engine,
            values=("rapid-gpu", "paddle-cpu"),
            state="readonly",
            width=18,
        )
        engine_box.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(controls, text="GPU 检测设备").grid(row=1, column=1, padx=(190, 8), pady=4, sticky="w")
        ttk.Entry(controls, textvariable=self.detect_device, width=8).grid(row=1, column=1, padx=(290, 0), pady=4, sticky="w")

        self.start_button = ttk.Button(controls, text="开始识别", command=self.start)
        self.start_button.grid(row=0, column=3, rowspan=2, padx=(12, 0), pady=4, ipadx=10)
        ttk.Button(controls, text="清空结果", command=self.clear).grid(row=0, column=4, rowspan=2, padx=(8, 0), pady=4)

        ttk.Label(self.root, textvariable=self.status, padding=(12, 0, 12, 8)).pack(fill=X)

        content = ttk.PanedWindow(self.root, orient="horizontal")
        content.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        image_frame = ttk.LabelFrame(content, text="检测结果图", padding=8)
        result_frame = ttk.LabelFrame(content, text="识别文字", padding=8)
        content.add(image_frame, weight=3)
        content.add(result_frame, weight=2)

        self.image_label = ttk.Label(image_frame, anchor="center")
        self.image_label.pack(fill=BOTH, expand=True)

        self.result_text = ttk.Treeview(
            result_frame,
            columns=("id", "text", "confidence", "quality", "direction"),
            show="headings",
        )
        for column, title, width in (
            ("id", "序号", 55),
            ("text", "文字", 180),
            ("confidence", "置信度", 75),
            ("quality", "质量", 65),
            ("direction", "方向", 105),
        ):
            self.result_text.heading(column, text=title)
            self.result_text.column(column, width=width, anchor="center")
        result_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=result_scroll.set)
        self.result_text.pack(side=LEFT, fill=BOTH, expand=True)
        result_scroll.pack(side=RIGHT, fill=Y)

        self.log = ttk.Label(self.root, text="", anchor="w", padding=(12, 0, 12, 10))
        self.log.pack(fill=X)

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择书架图片",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有文件", "*.*")],
        )
        if path:
            self.address.set(path)

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        address = self.address.get().strip()
        if not address:
            messagebox.showwarning("缺少图片地址", "请输入本地图片路径或图片 URL。")
            return
        if not DEFAULT_WEIGHTS.is_file():
            messagebox.showerror("找不到模型", f"未找到训练权重：\n{DEFAULT_WEIGHTS}")
            return
        if self.engine.get() == "rapid-gpu" and not self.detect_device.get().strip():
            messagebox.showwarning("缺少设备", "RapidOCR GPU 模式需要填写 YOLO 检测设备。")
            return

        self.clear()
        self.start_button.configure(state="disabled")
        self.status.set("正在准备图片和本地推理环境，请稍候……")
        engine = self.engine.get()
        detect_device = self.detect_device.get().strip() or "cpu"
        self.worker = threading.Thread(
            target=self._run,
            args=(address, engine, detect_device),
            daemon=True,
        )
        self.worker.start()

    def _run(self, address: str, engine: str, detect_device: str) -> None:
        run_root = self.temp_root / "runs"
        run_id = f"session-{uuid.uuid4().hex[:12]}"
        try:
            source = self._materialize_source(address)
            command = [
                sys.executable,
                str(ROOT / "scripts" / "run_book_spine_pipeline.py"),
                "--source",
                str(source),
                "--output",
                str(run_root),
                "--weights",
                str(DEFAULT_WEIGHTS),
                "--detect-device",
                detect_device,
                "--ocr-engine",
                engine,
                "--keep-run-id",
                run_id,
            ]
            self.events.put(("status", "正在运行 YOLO 分割、图像矫正和本地 OCR……"))
            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "未知错误")[-3000:]
                raise RuntimeError(detail)
            session = run_root / run_id
            structured = json.loads((session / "postprocessed" / "books_by_image.json").read_text(encoding="utf-8"))
            annotated = self._find_annotated(session / "detected")
            self.events.put(("result", {"data": structured, "annotated": annotated}))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _materialize_source(self, address: str) -> Path:
        parsed = urllib.parse.urlparse(address)
        if parsed.scheme in {"http", "https"}:
            request = urllib.request.Request(address, headers={"User-Agent": "BookSpineOCR/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = response.headers.get_content_type()
                suffix = Path(urllib.parse.urlparse(response.geturl()).path).suffix.lower()
                if suffix not in IMAGE_SUFFIXES:
                    suffix = mimetypes.guess_extension(content_type) or ".jpg"
                if suffix not in IMAGE_SUFFIXES:
                    raise ValueError("URL 没有返回支持的图片类型。")
                data = response.read(MAX_DOWNLOAD_BYTES + 1)
                if len(data) > MAX_DOWNLOAD_BYTES:
                    raise ValueError("图片超过 50 MB，已停止下载。")
            destination = self.temp_root / f"input{suffix}"
            destination.write_bytes(data)
            return destination

        source = Path(address).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"找不到图片：{source}")
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError("只支持 JPG、PNG、BMP 和 WEBP 图片。")
        destination = self.temp_root / f"input{source.suffix.lower()}"
        shutil.copyfile(source, destination)
        return destination

    @staticmethod
    def _find_annotated(directory: Path) -> Path | None:
        paths = sorted(directory.glob("*_detected.*"))
        return paths[0] if paths else None

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(str(payload))
                elif kind == "result":
                    self._show_result(payload)
                elif kind == "error":
                    self.status.set("识别失败")
                    self.log.configure(text=str(payload))
                    messagebox.showerror("识别失败", str(payload))
                    self.start_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    def _show_result(self, payload: object) -> None:
        result = payload["data"]  # type: ignore[index]
        annotated = payload["annotated"]  # type: ignore[index]
        for item in self.result_text.get_children():
            self.result_text.delete(item)
        books = [book for image in result.get("images", []) for book in image.get("books", [])]
        for book in books:
            self.result_text.insert(
                "",
                END,
                values=(
                    book.get("id", ""),
                    book.get("text", "") or "（未识别）",
                    f"{float(book.get('confidence', 0)):.3f}",
                    book.get("quality", ""),
                    book.get("direction", ""),
                ),
            )
        if annotated:
            try:
                from PIL import Image, ImageTk

                image = Image.open(annotated)
                image.thumbnail((680, 560))
                self.preview_image = ImageTk.PhotoImage(image)
                self.image_label.configure(image=self.preview_image, text="")
            except Exception as exc:
                self.image_label.configure(image="", text=f"检测图展示失败：{exc}")
        self.status.set(f"识别完成，共检测到 {len(books)} 个书脊")
        self.log.configure(text="结果仅保存在临时目录，关闭窗口后会自动清理。")
        self.start_button.configure(state="normal")

    def clear(self) -> None:
        for item in self.result_text.get_children():
            self.result_text.delete(item)
        self.image_label.configure(image="", text="")
        self.preview_image = None
        self.log.configure(text="")

    def close(self) -> None:
        self.root.destroy()
        shutil.rmtree(self.temp_root, ignore_errors=True)


def main() -> None:
    root = Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except Exception:
        pass
    BookSpineGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
