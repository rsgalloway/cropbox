import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage


@dataclass(frozen=True)
class ThumbnailRequest:
    job_id: int
    media_path: Path
    start_ms: int
    end_ms: int
    thumb_width: int
    thumb_height: int
    count: int


class ThumbnailGenerator(QObject):
    thumbnailReady = Signal(int, int, int, QImage)
    jobFinished = Signal(int, bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._requests: "queue.Queue[Optional[ThumbnailRequest]]" = queue.Queue()
        self._lock = threading.Lock()
        self._latest_job_id = 0
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="cropbox-thumbnail-generator",
            daemon=True,
        )
        self._thread.start()

    def submit(self, request: ThumbnailRequest) -> None:
        with self._lock:
            self._latest_job_id = request.job_id
        self._requests.put(request)

    def cancel_pending(self) -> None:
        with self._lock:
            self._latest_job_id += 1
        self._requests.put(None)

    def stop(self) -> None:
        self._stop_event.set()
        self._requests.put(None)
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            request = self._requests.get()
            if request is None:
                continue
            while True:
                try:
                    newer_request = self._requests.get_nowait()
                except queue.Empty:
                    break
                if newer_request is not None:
                    request = newer_request

            cancelled = self._process_request(request)
            self.jobFinished.emit(request.job_id, cancelled)

    def _process_request(self, request: ThumbnailRequest) -> bool:
        if request.count <= 0 or request.thumb_width <= 0 or request.thumb_height <= 0:
            return False

        if self._is_stale(request.job_id):
            return True

        span_ms = max(request.end_ms - request.start_ms, 1)
        if request.count == 1:
            sample_positions = [request.start_ms + (span_ms // 2)]
        else:
            step = span_ms / float(request.count)
            sample_positions = [
                min(
                    request.end_ms,
                    max(request.start_ms, int(round(request.start_ms + (step * (index + 0.5))))),
                )
                for index in range(request.count)
            ]

        for index, position_ms in enumerate(sample_positions):
            if self._is_stale(request.job_id):
                return True
            image = self._extract_thumbnail(
                request.media_path,
                position_ms,
                request.thumb_width,
                request.thumb_height,
            )
            if self._is_stale(request.job_id):
                return True
            if image is None or image.isNull():
                continue
            self.thumbnailReady.emit(request.job_id, index, position_ms, image)
        return False

    def _is_stale(self, job_id: int) -> bool:
        with self._lock:
            return job_id != self._latest_job_id

    def _extract_thumbnail(
        self,
        media_path: Path,
        position_ms: int,
        width: int,
        height: int,
    ) -> Optional[QImage]:
        time_value = max(position_ms, 0) / 1000.0
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x2a2f38"
        )
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{time_value:.3f}",
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
        if not result.stdout:
            return None
        image = QImage.fromData(result.stdout, "PNG")
        if image.isNull():
            return None
        if image.format() != QImage.Format_RGB32:
            image = image.convertToFormat(QImage.Format_RGB32)
        return image
