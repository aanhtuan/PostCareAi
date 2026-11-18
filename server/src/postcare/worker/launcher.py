"""Chạy nhiều worker cùng lúc, mỗi camera một tiến trình con (F31 R1, R2, R4).

Mỗi tiến trình là `python -m postcare worker --camera-id N [--video …]`: engine, model, nguồn
và kết nối API riêng, nên một worker lỗi hay mất nguồn không kéo theo worker khác (R2).
Launcher chỉ khởi động, theo dõi và dừng; không tự khởi động lại worker đã thoát (giả định:
worker đã tự thử lại API và nguồn, thoát nghĩa là lỗi cần người sửa).

SIGTERM tới launcher (POSIX) được xử lý như Ctrl+C: dừng mọi worker rồi thoát.
Dừng: POSIX gửi SIGINT (worker đóng nguồn gọn) rồi `terminate()`/`kill()` khi quá hạn;
Windows dùng `terminate()` (TerminateProcess). Ctrl+C trong console tới mọi tiến trình con cùng
nhóm, nên launcher chỉ chờ chúng thoát rồi dọn phần còn lại.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LauncherError(ValueError):
    """Tham số launcher không hợp lệ (danh sách camera, `--video`)."""


@dataclass(frozen=True)
class WorkerSpec:
    camera_id: int
    video: Path | None = None


def parse_video_args(values: Iterable[str], camera_ids: Sequence[int]) -> dict[int, Path]:
    """`["2=D:/clips/a.mp4"]` → `{2: Path(...)}`. Camera phải nằm trong `camera_ids`."""
    result: dict[int, Path] = {}
    for value in values:
        cam, sep, path = value.partition("=")
        if not sep or not cam.strip().isdigit() or not path.strip():
            raise LauncherError(f"--video phải có dạng <camera_id>=<file>, nhận được: {value!r}")
        camera_id = int(cam)
        if camera_id not in camera_ids:
            raise LauncherError(f"--video cho camera {camera_id} không nằm trong danh sách worker")
        if camera_id in result:
            raise LauncherError(f"--video lặp lại cho camera {camera_id}")
        result[camera_id] = Path(path.strip())
    return result


def worker_command(
    spec: WorkerSpec, *, extra_args: Sequence[str] = (), python: str | None = None
) -> list[str]:
    """Lệnh của một tiến trình worker; dùng đúng trình thông dịch đang chạy (venv của uv)."""
    cmd = [python or sys.executable, "-m", "postcare", "worker", "--camera-id", str(spec.camera_id)]
    if spec.video is not None:
        cmd += ["--video", str(spec.video)]
    return cmd + list(extra_args)


Popen = Callable[[list[str]], "subprocess.Popen[bytes]"]


class WorkerLauncher:
    def __init__(
        self,
        specs: Sequence[WorkerSpec],
        *,
        command: Callable[[WorkerSpec], list[str]] = worker_command,
        popen: Popen = subprocess.Popen,
        log: Callable[[str], object] = print,
    ) -> None:
        ids = [s.camera_id for s in specs]
        if not ids:
            raise LauncherError("Không có camera nào để chạy worker")
        if len(set(ids)) != len(ids):
            raise LauncherError("Mỗi camera chỉ một worker")
        self.specs = list(specs)
        self._command = command
        self._popen = popen
        self._log = log
        self._procs: dict[int, subprocess.Popen[bytes]] = {}
        self._failed_start: dict[int, int] = {}
        self._reported: set[int] = set()

    # ---- thông tin ----
    def alive(self) -> list[int]:
        return sorted(cid for cid, p in self._procs.items() if p.poll() is None)

    def pids(self) -> dict[int, int]:
        return {cid: p.pid for cid, p in self._procs.items()}

    # ---- vòng đời ----
    def start(self) -> None:
        for spec in self.specs:
            cmd = self._command(spec)
            try:
                self._procs[spec.camera_id] = self._popen(cmd)
            except OSError as exc:
                self._log(f"Không khởi động được worker camera {spec.camera_id}: {exc}")
                self._failed_start[spec.camera_id] = -1
                continue
            src = f"file {spec.video}" if spec.video else "nguồn trong cấu hình camera"
            pid = self._procs[spec.camera_id].pid
            self._log(f"Worker camera {spec.camera_id} (pid {pid}, {src})")

    def poll(self) -> dict[int, int]:
        """Worker vừa thoát (chưa báo lần nào) → mã thoát. Worker khác vẫn chạy (R2)."""
        exited: dict[int, int] = {}
        for cid, failed in self._failed_start.items():
            if cid not in self._reported:
                exited[cid] = failed
        for cid, proc in self._procs.items():
            code = proc.poll()
            if code is not None and cid not in self._reported:
                exited[cid] = code
                self._log(f"Worker camera {cid} đã dừng (mã {code}); các worker khác vẫn chạy")
        self._reported.update(exited)
        return exited

    def stop(self, timeout_s: float = 5.0, *, interrupted: bool = False) -> None:
        """Dừng mọi worker còn sống; quá `timeout_s` thì buộc dừng. Không để tiến trình mồ côi.

        `interrupted`: Ctrl+C đã tới các tiến trình con (cùng console), chỉ chờ chúng tự thoát.
        """
        running = [p for p in self._procs.values() if p.poll() is None]
        if not running:
            return
        if not interrupted:
            for proc in running:
                _interrupt(proc)
        deadline = time.monotonic() + timeout_s
        for proc in running:
            _wait(proc, deadline - time.monotonic())
        for proc in running:
            if proc.poll() is None:
                proc.terminate()
        for proc in running:
            if not _wait(proc, 3.0):
                proc.kill()
                proc.wait()

    def run(self, should_stop: Callable[[], bool] = lambda: False, *, poll_s: float = 0.5) -> int:
        """Khởi động, chờ mọi worker thoát hoặc `should_stop()`/Ctrl+C rồi dừng hết.

        Trả mã thoát lớn nhất của worker tự thoát (0 nếu người dùng dừng trước).
        """
        worst = 0
        interrupted = False
        previous = _install_sigterm()
        try:
            self.start()  # trong try: lỗi giữa chừng vẫn dừng các worker đã khởi động
            while True:
                for code in self.poll().values():
                    worst = max(worst, abs(code))
                if not self.alive():
                    break
                if should_stop():
                    break
                time.sleep(poll_s)
        except KeyboardInterrupt:
            interrupted = True  # Ctrl+C đã tới các worker cùng console
            self._log("Đang dừng các worker…")
        except _TerminatedError:
            self._log("Nhận SIGTERM: đang dừng các worker…")  # worker chưa nhận tín hiệu
        finally:
            self.stop(interrupted=interrupted)
            _restore_sigterm(previous)
        return worst


class _TerminatedError(Exception):
    """SIGTERM tới launcher (POSIX: `kill`, systemd, docker stop)."""


def _raise_terminated(signum: int, frame: object) -> None:
    raise _TerminatedError


def _install_sigterm() -> Any:
    """POSIX: SIGTERM → dừng mọi worker như Ctrl+C. Windows/luồng phụ: không đổi gì."""
    if os.name == "nt" or threading.current_thread() is not threading.main_thread():
        return None
    return signal.signal(signal.SIGTERM, _raise_terminated)


def _restore_sigterm(previous: Any) -> None:
    if previous is not None:
        signal.signal(signal.SIGTERM, previous)


def _interrupt(proc: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        proc.terminate()  # không có SIGINT cho tiến trình riêng trên Windows
        return
    with contextlib.suppress(ProcessLookupError):
        proc.send_signal(signal.SIGINT)


def _wait(proc: subprocess.Popen[bytes], timeout_s: float) -> bool:
    try:
        proc.wait(timeout=max(timeout_s, 0.0))
    except subprocess.TimeoutExpired:
        return False
    return True
