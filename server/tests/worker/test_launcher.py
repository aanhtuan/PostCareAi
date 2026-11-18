"""F31 R2, R4 (AC2, AC4): launcher nhiều worker, mỗi camera một tiến trình con.

Test tiến trình dùng tiến trình con thật (`sys.executable -c …`) để kiểm tra dừng/dọn trên cả
Windows và Linux; không cần model hay API.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from postcare.worker.launcher import (
    LauncherError,
    WorkerLauncher,
    WorkerSpec,
    parse_video_args,
    worker_command,
)

SLEEP = "import time; time.sleep(60)"
FAIL = "import sys; sys.exit(1)"
IGNORE_SIGINT = "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); time.sleep(60)"


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _wait(cond: object, timeout_s: float = 15.0) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if cond():  # type: ignore[operator]
            return
        time.sleep(0.05)
    raise AssertionError("hết thời gian chờ")


# ---- dựng lệnh ----
def test_worker_command_uses_current_python_and_camera() -> None:
    cmd = worker_command(WorkerSpec(camera_id=2, video=Path("clip.mp4")), extra_args=["-v"])
    assert cmd[:3] == [sys.executable, "-m", "postcare"]
    assert cmd[3:] == ["worker", "--camera-id", "2", "--video", "clip.mp4", "-v"]


def test_worker_command_without_video() -> None:
    cmd = worker_command(WorkerSpec(camera_id=1))
    assert cmd[3:] == ["worker", "--camera-id", "1"]
    assert "--video" not in cmd


def test_parse_video_args_maps_camera_to_file() -> None:
    assert parse_video_args(["2=D:/clips/a 1.mp4"], [1, 2]) == {2: Path("D:/clips/a 1.mp4")}
    assert parse_video_args([], [1, 2]) == {}


@pytest.mark.parametrize("arg", ["clip.mp4", "x=clip.mp4", "=clip.mp4", "2="])
def test_parse_video_args_rejects_bad_format(arg: str) -> None:
    with pytest.raises(LauncherError):
        parse_video_args([arg], [1, 2])


def test_parse_video_args_rejects_unknown_camera() -> None:
    with pytest.raises(LauncherError):
        parse_video_args(["3=clip.mp4"], [1, 2])


def test_parse_video_args_rejects_duplicate_camera() -> None:
    with pytest.raises(LauncherError):
        parse_video_args(["2=a.mp4", "2=b.mp4"], [1, 2])


def test_launcher_rejects_duplicate_or_empty_specs() -> None:
    with pytest.raises(LauncherError):
        WorkerLauncher([WorkerSpec(1), WorkerSpec(1)])
    with pytest.raises(LauncherError):
        WorkerLauncher([])


# ---- tiến trình con thật ----
def test_starts_one_process_per_camera_and_stops_all() -> None:
    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2)], command=lambda spec: _py(SLEEP), log=lambda _m: None
    )
    launcher.start()
    try:
        assert sorted(launcher.alive()) == [1, 2]
        pids = launcher.pids()
        assert len(set(pids.values())) == 2
    finally:
        launcher.stop(timeout_s=5)
    assert launcher.alive() == []


def test_child_exit_does_not_stop_others() -> None:
    logs: list[str] = []
    cmds = {1: _py(SLEEP), 2: _py(FAIL), 3: _py(SLEEP)}
    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2), WorkerSpec(3)],
        command=lambda spec: cmds[spec.camera_id],
        log=logs.append,
    )
    launcher.start()
    try:
        exited: dict[int, int] = {}
        _wait(lambda: bool(exited.update(launcher.poll()) or 2 in exited))
        assert exited == {2: 1}
        assert sorted(launcher.alive()) == [1, 3]
        assert any("2" in m for m in logs)
    finally:
        launcher.stop(timeout_s=5)
    assert launcher.alive() == []


def test_stop_kills_child_that_ignores_interrupt() -> None:
    launcher = WorkerLauncher(
        [WorkerSpec(1)], command=lambda spec: _py(IGNORE_SIGINT), log=lambda _m: None
    )
    launcher.start()
    time.sleep(0.5)  # để tiến trình con kịp cài handler
    t0 = time.monotonic()
    launcher.stop(timeout_s=1)
    assert launcher.alive() == []
    assert time.monotonic() - t0 < 10


def test_run_returns_when_all_children_exit_with_worst_code() -> None:
    cmds = {1: _py("pass"), 2: _py(FAIL)}
    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2)],
        command=lambda spec: cmds[spec.camera_id],
        log=lambda _m: None,
    )
    assert launcher.run(poll_s=0.05) == 1
    assert launcher.alive() == []


def test_run_stops_all_when_asked() -> None:
    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2)], command=lambda spec: _py(SLEEP), log=lambda _m: None
    )
    t0 = time.monotonic()
    code = launcher.run(should_stop=lambda: time.monotonic() - t0 > 0.5, poll_s=0.05)
    assert code == 0
    assert launcher.alive() == []


def test_start_failure_of_one_camera_keeps_others() -> None:
    missing = str(Path(sys.executable).with_name("khong-ton-tai-postcare.exe"))
    cmds = {1: _py(SLEEP), 2: [missing]}
    logs: list[str] = []
    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2)], command=lambda spec: cmds[spec.camera_id], log=logs.append
    )
    launcher.start()
    try:
        assert launcher.alive() == [1]
        assert launcher.poll() == {2: -1}
    finally:
        launcher.stop(timeout_s=5)


def test_run_stops_started_children_when_start_fails_midway() -> None:
    calls: list[str] = []

    def log(message: str) -> None:
        calls.append(message)
        raise RuntimeError("console lỗi")  # vd. stdout không in được tiếng Việt

    launcher = WorkerLauncher(
        [WorkerSpec(1), WorkerSpec(2)], command=lambda spec: _py(SLEEP), log=log
    )
    with pytest.raises(RuntimeError):
        launcher.run(poll_s=0.05)
    assert launcher.pids()  # đã khởi động ít nhất một worker trước khi lỗi
    assert launcher.alive() == []
