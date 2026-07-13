import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QProcess, Signal


LOGGER = logging.getLogger(__name__)


class Exporter(QObject):
    finished = Signal(Path)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._process = QProcess(self)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.readyReadStandardError.connect(self._read_standard_error)
        self._process.readyReadStandardOutput.connect(self._read_standard_output)
        self._output_path: Path = Path()
        self._stderr_chunks: List[str] = []
        self._stdout_chunks: List[str] = []

    def start(self, command: List[str], output_path: Path) -> None:
        if not command:
            self.failed.emit("Empty export command")
            return
        self._stderr_chunks = []
        self._stdout_chunks = []
        self._output_path = output_path
        program = command[0]
        arguments = command[1:]
        LOGGER.info("Starting export: %s %s", program, " ".join(arguments))
        self._process.start(program, arguments)

    def cancel(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            LOGGER.warning("Cancelling export for %s", self._output_path)
            self._process.kill()

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_standard_output()
        self._read_standard_error()
        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            LOGGER.info("Export finished: %s", self._output_path)
            self.finished.emit(self._output_path)
            return
        stderr = "".join(self._stderr_chunks).strip()
        stdout = "".join(self._stdout_chunks).strip()
        message = self._summarize_failure(stderr or stdout)
        LOGGER.error("Export failed for %s: %s", self._output_path, message)
        self.failed.emit(message)

    def _on_error(self, _error: QProcess.ProcessError) -> None:
        self._read_standard_output()
        self._read_standard_error()
        stderr = "".join(self._stderr_chunks).strip()
        message = self._summarize_failure(stderr) or "Failed to start ffmpeg process"
        LOGGER.error("ffmpeg process error for %s: %s", self._output_path, message)
        self.failed.emit(message)

    def _read_standard_error(self) -> None:
        raw_stderr = self._process.readAllStandardError().data()
        if not raw_stderr:
            return
        text = bytes(raw_stderr).decode("utf-8", errors="replace")
        self._stderr_chunks.append(text)
        for line in text.splitlines():
            if line.strip():
                LOGGER.error("ffmpeg: %s", line)

    def _read_standard_output(self) -> None:
        raw_stdout = self._process.readAllStandardOutput().data()
        if not raw_stdout:
            return
        text = bytes(raw_stdout).decode("utf-8", errors="replace")
        self._stdout_chunks.append(text)
        for line in text.splitlines():
            if line.strip():
                LOGGER.info("ffmpeg: %s", line)

    def _summarize_failure(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Export failed"
        return "\n".join(lines[-12:])
