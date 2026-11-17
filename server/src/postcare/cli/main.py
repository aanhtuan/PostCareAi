"""Lệnh CLI `postcare`: version, seed, simulate, probe, replay, models, openapi."""

import json
import os
import sys
import time
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated, Any, NoReturn

import httpx
import typer
from sqlalchemy import select

from postcare.db.migrate import reset_schema
from postcare.db.models import Bed
from postcare.db.session import make_engine, make_session_factory
from postcare.db.types import utcnow
from postcare.domain.seed import SEED_USERS, seed_base, seed_demo, seed_history
from postcare.eval.matching import DEFAULT_TOL_AFTER_S, DEFAULT_TOL_BEFORE_S
from postcare.settings import REPO_ROOT, get_settings

# Console Windows (cp1252) không in được tiếng Việt: ép UTF-8 cho stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="PostCare AI - công cụ dòng lệnh (prototype)", no_args_is_help=True)

DEFAULT_MODELS_MANIFEST = REPO_ROOT / "config" / "models.yaml"
DEFAULT_MODELS_DIR = REPO_ROOT / "models"
DEFAULT_ENGINE_CONFIG = REPO_ROOT / "config" / "engine.default.yaml"


@app.command()
def version() -> None:
    """In phiên bản package `postcare` đã cài."""
    typer.echo(f"postcare {package_version('postcare')}")


@app.command()
def seed(
    reset: Annotated[
        bool,
        typer.Option(
            "--reset",
            help="Prototype: XÓA toàn bộ dữ liệu, tạo lại schema bằng migration, thêm dữ liệu demo",
        ),
    ] = False,
    history: Annotated[
        bool, typer.Option(help="Cùng --reset: thêm phiên mở và sự kiện quá khứ cho A01–A03")
    ] = True,
) -> None:
    """Tạo dữ liệu mẫu còn thiếu: 4 tài khoản, 3 ca, giường A01–A03, camera A01 (chạy lại an toàn).

    Cần schema mới nhất (`make db-upgrade`). `--reset` (`make seed`) thêm dữ liệu demo của
    prototype: camera A02/A03, bệnh nhân BN-001…BN-005, phiên và sự kiện quá khứ.
    """
    settings = get_settings()
    engine = make_engine(settings.database_url)
    if reset:
        reset_schema(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        created = seed_base(db, settings.seed_password)
        if reset:
            seed_demo(db)
            if history:
                seed_history(db, utcnow())
    typer.echo(f"Dữ liệu mẫu tại {engine.url.render_as_string(hide_password=True)}")
    typer.echo("Bản ghi mới: " + ", ".join(f"{k}={v}" for k, v in created.items()))
    typer.echo("Tài khoản (mật khẩu = SEED_PASSWORD, mặc định 'postcare'):")
    for username, full_name, role in SEED_USERS:
        typer.echo(f"  {username:<8} {role.value:<13} {full_name}")
    if reset:
        typer.echo("Nếu API đang chạy, nên khởi động lại để xóa trạng thái giường trong RAM.")


def _camera_for_bed(bed_code: str) -> int:
    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database_url))
    with factory() as db:
        bed = db.scalar(select(Bed).where(Bed.code == bed_code))
        if bed is None or bed.camera is None:
            raise typer.BadParameter(f"Không tìm thấy giường {bed_code} hoặc giường chưa có camera")
        return bed.camera.id


@app.command()
def simulate(
    bed: Annotated[str, typer.Option(help="Mã giường, ví dụ A01")] = "A01",
    scenario: Annotated[
        str,
        typer.Option(
            help="bed-exit | observation-lost | abnormal-movement | face-attention | posture-change"
        ),
    ] = "bed-exit",
    speed: Annotated[float, typer.Option(help="Hệ số tốc độ (2 = nhanh gấp đôi)")] = 1.0,
    away: Annotated[float, typer.Option(help="Số giây ở ngoài giường trước khi quay lại")] = 10.0,
    repeat: Annotated[int, typer.Option(help="Số lượt lặp kịch bản")] = 1,
    gap: Annotated[float, typer.Option(help="Số giây nghỉ giữa các lượt")] = 5.0,
    hold: Annotated[
        bool, typer.Option(help="Giữ heartbeat sau khi chạy xong (Ctrl+C để dừng)")
    ] = False,
    camera_id: Annotated[
        int | None, typer.Option(help="Bỏ qua tra cứu DB, dùng camera id này")
    ] = None,
    api: Annotated[str | None, typer.Option(help="Địa chỉ API, mặc định API_BASE_URL")] = None,
) -> None:
    """Giả lập worker AI cho một giường (gửi state + events qua API nội bộ)."""
    from postcare.cli.simulator import SCENARIOS, Simulator

    if scenario not in SCENARIOS:
        raise typer.BadParameter(f"Kịch bản không hợp lệ. Chọn: {', '.join(SCENARIOS)}")
    if speed <= 0 or repeat < 1:
        raise typer.BadParameter("speed phải > 0 và repeat ≥ 1")
    settings = get_settings()
    cam = camera_id or _camera_for_bed(bed)
    sim = Simulator(
        base_url=api or settings.api_base_url, worker_token=settings.worker_token, camera_id=cam
    )
    try:
        try:
            cfg = sim.config()
        except httpx.HTTPError as exc:
            typer.echo(f"Không kết nối được API ({exc}). API đã chạy chưa? WORKER_TOKEN đúng chưa?")
            raise typer.Exit(1) from exc
        if cfg["active_session_id"] is None:
            typer.echo(
                f"Giường {bed} chưa có phiên theo dõi. Mở phiên ở màn hình 'Quản lý giường' "
                "hoặc chạy `postcare seed`."
            )
            raise typer.Exit(1)
        typer.echo(
            f"Giả lập giường {bed} (camera {cam}, phiên {cfg['active_session_id']}), "
            f"kịch bản '{scenario}', tốc độ x{speed}"
        )
        sim.heartbeat_once()
        sim.start_heartbeat()
        sim.run(scenario, speed=speed, away_s=away, repeat=repeat, gap_s=gap)
        if hold:
            typer.echo("Đang giữ heartbeat. Nhấn Ctrl+C để dừng.")
            while True:
                sim.sleep(1)
    except KeyboardInterrupt:
        typer.echo("Đã dừng.")
    finally:
        sim.stop()
    typer.echo("Xong. Camera sẽ chuyển 'Mất kết nối' sau vài giây khi không còn heartbeat.")


@app.command()
def probe(
    source: Annotated[
        str,
        typer.Option(
            help="Index webcam (0), URL http(s)/rtsp (DroidCam, IP Webcam) hoặc file video"
        ),
    ],
    seconds: Annotated[float, typer.Option(help="Số giây đọc nguồn")] = 10.0,
    max_fps: Annotated[float, typer.Option(help="Giới hạn FPS xử lý (A03)")] = 15.0,
    pose: Annotated[
        bool, typer.Option("--pose", help="Chạy MediaPipe Pose trên từng khung, đo FPS/CPU/RAM")
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(help="Biến thể pose: lite | full | heavy (mặc định: config/models.yaml)"),
    ] = None,
    models_dir: Annotated[
        Path, typer.Option(help="Thư mục chứa file model (make models)")
    ] = DEFAULT_MODELS_DIR,
) -> None:
    """Kiểm tra nguồn video (F05); `--pose` đo thêm hiệu năng pose (F11): FPS, CPU %, RAM MB."""
    from postcare.vision.camera import SourceOpenError, guess_source_type, open_source

    if seconds <= 0 or max_fps <= 0:
        raise typer.BadParameter("seconds và max-fps phải > 0")
    runner = _PoseRunner.create(model, models_dir) if pose else None
    kind, value = guess_source_type(source)
    src = open_source(
        kind,
        value,
        max_fps=max_fps,
        on_status_change=lambda s: typer.echo(f"[{time.strftime('%H:%M:%S')}] Trạng thái: {s}"),
    )
    typer.echo(f"Nguồn: {kind} {value} (đọc {seconds:g} s, max-fps {max_fps:g})")
    try:
        src.open()
    except SourceOpenError as exc:
        typer.echo(f"Không mở được nguồn: {exc}", err=True)
        if runner:
            runner.close()
        raise typer.Exit(1) from exc
    started = time.monotonic()
    if runner:
        runner.start()
    try:
        while time.monotonic() - started < seconds:
            frame = src.read(timeout_s=1.0)
            if frame is None:
                if src.ended:
                    break
                continue
            if runner:
                runner.process(frame)
    except KeyboardInterrupt:
        typer.echo("Đã dừng.")
    finally:
        elapsed = time.monotonic() - started
        src.close()
        if runner:
            runner.close()
    stats = src.stats
    typer.echo(f"Độ phân giải: {stats.width}x{stats.height}")
    typer.echo(f"Số khung đã xử lý: {stats.frames} (trong {elapsed:.1f} s)")
    typer.echo(f"FPS thực (theo ts_ms): {stats.fps:.1f}")
    typer.echo(f"FPS xử lý (đồng hồ máy): {stats.frames / elapsed if elapsed > 0 else 0:.1f}")
    typer.echo(f"Số khung bỏ: {stats.dropped_frames}")
    typer.echo(f"Số lần mất kết nối: {stats.disconnects}")
    if runner:
        runner.report(elapsed)
    if src.ended:
        typer.echo("Đã đọc hết file.")
    if stats.frames == 0:
        typer.echo("Không nhận được khung hình nào.", err=True)
        raise typer.Exit(1)


class _PoseRunner:
    """Phần `--pose` của `probe`: chạy adapter, đo thời gian suy luận, CPU, RAM, độ đầy đủ."""

    def __init__(self, adapter: Any, label: str, coverage: Any) -> None:
        import psutil

        self.adapter = adapter
        self.label = label
        self.coverage = coverage
        self.proc = psutil.Process()
        self.n_cpu = psutil.cpu_count(logical=True) or 1
        self.infer_s = 0.0
        self.peak_rss = 0
        self.cpu_percent = 0.0

    @classmethod
    def create(cls, variant: str | None, models_dir: Path) -> "_PoseRunner":
        from postcare.schemas.engine_config import EngineConfig
        from postcare.vision.inference.base import ModelNotFoundError
        from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter
        from postcare.vision.inference.stats import PoseCoverage
        from postcare.vision.models import ManifestError, load_manifest

        config = EngineConfig.load(DEFAULT_ENGINE_CONFIG)
        try:
            entry = load_manifest(DEFAULT_MODELS_MANIFEST).pose_entry(variant)
            adapter = MediaPipePoseAdapter.from_config(models_dir / entry.filename, config)
        except (ManifestError, ModelNotFoundError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        coverage = PoseCoverage(config.pose.required_keypoints, config.pose.min_keypoint_visibility)
        return cls(
            adapter, f"{entry.name} ({entry.filename}, num_poses {config.pose.num_poses})", coverage
        )

    def start(self) -> None:
        self.proc.cpu_percent(None)  # mốc đo CPU

    def process(self, frame: Any) -> None:
        t0 = time.perf_counter()
        obs = self.adapter.observe(frame, camera_id=0)
        self.infer_s += time.perf_counter() - t0
        self.coverage.add(obs)
        self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss)

    def close(self) -> None:
        if self.cpu_percent == 0.0:
            self.cpu_percent = self.proc.cpu_percent(None)
        self.adapter.close()

    def report(self, elapsed: float) -> None:
        n = self.coverage.frames
        cov = self.coverage
        typer.echo(f"Model pose: {self.label}")
        typer.echo(f"Số khung đã chạy pose: {n}")
        typer.echo(
            f"FPS xử lý pose (khung đã chạy pose / giây): {n / elapsed if elapsed else 0:.1f}"
        )
        if n:
            ms = self.infer_s * 1000 / n
            typer.echo(f"Thời gian suy luận trung bình: {ms:.1f} ms/khung (≈ {1000 / ms:.1f} FPS)")
        typer.echo(
            f"CPU tiến trình: {self.cpu_percent:.0f} % "
            f"(≈ {self.cpu_percent / self.n_cpu:.0f} % tổng máy, {self.n_cpu} luồng logic)"
        )
        typer.echo(f"RAM tiến trình (đỉnh): {self.peak_rss / 2**20:.0f} MB")
        typer.echo(f"Khung có người: {cov.frames_with_person}/{n} ({cov.person_ratio:.0%})")
        typer.echo(
            f"Khung thấy đủ keypoint thân: {cov.frames_with_torso}/{n} ({cov.torso_ratio:.0%})"
        )


def _fail(message: str, code: int = 1) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code)


def _default_models_dir() -> Path:
    env = os.environ.get("POSTCARE_MODELS_DIR")
    return Path(env) if env else DEFAULT_MODELS_DIR


@app.command()
def replay(
    camera_config: Annotated[
        Path, typer.Option(help="File cấu hình camera config/cameras/<setup>.yaml (ROI, ngưỡng)")
    ],
    video: Annotated[
        Path | None, typer.Option(help="File video (chạy pose MediaPipe + engine)")
    ] = None,
    from_observations: Annotated[
        Path | None,
        typer.Option(help="observations.jsonl của lần chạy trước: chạy lại chỉ engine"),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Thư mục kết quả, ví dụ runs/<id>/ (không commit)")
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Ghi đè khi --out đã có dữ liệu")
    ] = False,
    preview: Annotated[
        bool,
        typer.Option("--preview", help="Ghi preview.mp4: skeleton, ROI, trạng thái (chỉ --video)"),
    ] = False,
    engine_config: Annotated[
        Path, typer.Option(help="Ngưỡng mặc định của engine")
    ] = DEFAULT_ENGINE_CONFIG,
    model: Annotated[
        str | None,
        typer.Option(help="Biến thể pose: lite | full | heavy (mặc định: config/models.yaml)"),
    ] = None,
    models_dir: Annotated[
        Path | None,
        typer.Option(help="Thư mục model (mặc định POSTCARE_MODELS_DIR hoặc models/)"),
    ] = None,
    max_fps: Annotated[
        float, typer.Option(help="Giới hạn FPS xử lý theo thời gian video (A03); 0 = mọi khung")
    ] = 15.0,
    start_s: Annotated[
        float | None, typer.Option(help="Chỉ lấy observation từ giây này (--from-observations)")
    ] = None,
    end_s: Annotated[
        float | None, typer.Option(help="Chỉ lấy observation tới giây này (--from-observations)")
    ] = None,
    save_observations: Annotated[
        Path | None,
        typer.Option(help="Ghi đoạn đã cắt làm fixture, ví dụ tests/fixtures/<scenario>.jsonl"),
    ] = None,
    save_expected: Annotated[
        bool,
        typer.Option("--save-expected", help="Ghi thêm <scenario>.expected.json (sự kiện engine)"),
    ] = False,
) -> None:
    """Chạy pipeline worker trên file video, hoặc chỉ engine trên observations.jsonl (F12).

    Ghi observations.jsonl, events.jsonl, frames.jsonl, run.json vào --out. Không gọi API, không
    cần DB. Cắt fixture: --from-observations … --start-s A --end-s B --save-observations F
    --save-expected.
    """
    from postcare.replay.camera_config import CameraConfigError, load_camera_config
    from postcare.replay.runner import OutputExistsError

    if (video is None) == (from_observations is None):
        _fail("Cần đúng một trong hai: --video hoặc --from-observations.", 2)
    if video is not None:
        if start_s is not None or end_s is not None or save_observations or save_expected:
            _fail(
                "--start-s, --end-s, --save-observations, --save-expected chỉ dùng với "
                "--from-observations.",
                2,
            )
        if out is None:
            _fail("Thiếu --out (ví dụ runs/<id>/).", 2)
    else:
        if preview:
            _fail("--preview cần --video (observations không có khung hình).", 2)
        if save_expected and save_observations is None:
            _fail("--save-expected cần --save-observations.", 2)
        if out is None and save_observations is None:
            _fail("Thiếu --out (hoặc --save-observations khi cắt fixture).", 2)
        if start_s is not None and end_s is not None and start_s > end_s:
            _fail(f"--start-s ({start_s:g}) phải ≤ --end-s ({end_s:g}).", 2)
    if max_fps < 0:
        _fail("--max-fps phải ≥ 0.", 2)

    try:
        camera = load_camera_config(camera_config)
        config = camera.engine_config(engine_config)
    except CameraConfigError as exc:
        _fail(str(exc))
    meta: dict[str, Any] = {
        "camera_config": str(camera_config),
        "engine_config": str(engine_config),
    }
    try:
        if video is not None:
            assert out is not None
            summary = _replay_video(
                video, camera, config, out, overwrite, preview, model, models_dir, max_fps, meta
            )
        else:
            assert from_observations is not None
            summary = _replay_observations(
                from_observations,
                camera,
                config,
                out,
                overwrite,
                (start_s, end_s),
                save_observations,
                save_expected,
                meta,
            )
    except OutputExistsError as exc:
        _fail(str(exc))
    if summary is not None:
        run = summary.run
        typer.echo(f"Đã ghi {summary.out_dir}: {summary.frames} khung, {summary.events} sự kiện")
        typer.echo(
            f"config_hash {run['config_hash'][:12]}…, FPS xử lý {run['fps_processing']}, "
            f"CPU {run['cpu_percent']} %, RAM đỉnh {run['ram_peak_mb']} MB, "
            f"khung bỏ {run['dropped_frames']}"
        )


def _replay_video(
    video: Path,
    camera: Any,
    config: Any,
    out: Path,
    overwrite: bool,
    preview: bool,
    model: str | None,
    models_dir: Path | None,
    max_fps: float,
    meta: dict[str, Any],
) -> Any:
    from postcare.replay.runner import replay_video, video_duration_s
    from postcare.vision.camera import FileSource, SourceOpenError
    from postcare.vision.inference.base import ModelNotFoundError
    from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter
    from postcare.vision.models import ManifestError, load_manifest

    directory = models_dir or _default_models_dir()
    try:
        entry = load_manifest(DEFAULT_MODELS_MANIFEST).pose_entry(model)
        adapter = MediaPipePoseAdapter.from_config(directory / entry.filename, config)
    except (ManifestError, ModelNotFoundError) as exc:
        _fail(str(exc))
    meta.update(
        video=str(video),
        model={"variant": entry.name, "file": entry.filename},
        max_fps=max_fps or None,
        video_duration_s=video_duration_s(video),
    )
    source = FileSource(video, max_fps=max_fps or None)
    typer.echo(f"Replay {video} (pose {entry.name}, max-fps {max_fps:g}) → {out}")
    try:
        return replay_video(
            source, adapter, camera, config, out, overwrite=overwrite, preview=preview, meta=meta
        )
    except SourceOpenError as exc:
        _fail(f"Không mở được video: {exc}")
    finally:
        adapter.close()


def _replay_observations(
    path: Path,
    camera: Any,
    config: Any,
    out: Path | None,
    overwrite: bool,
    range_s: tuple[float | None, float | None],
    save_observations: Path | None,
    save_expected: bool,
    meta: dict[str, Any],
) -> Any:
    from postcare.replay.fixtures import (
        ObservationFileError,
        cut_range,
        read_observations,
        write_fixture,
    )
    from postcare.replay.runner import replay_observations, source_run_info, summarize

    try:
        observations = cut_range(read_observations(path), *range_s)
    except ObservationFileError as exc:
        _fail(str(exc))
    if not observations:
        _fail(f"Không có observation nào trong {path} ở khoảng đã chọn.")
    meta.update(source_run_info(path))
    meta.update(observations=str(path), range_s=list(range_s))
    summary = None
    if out is not None:
        summary = replay_observations(
            observations, camera, config, out, overwrite=overwrite, meta=meta
        )
    if save_observations is not None:
        expected = write_fixture(
            save_observations,
            observations,
            camera,
            config,
            range_s=range_s,
            save_expected=save_expected,
        )
        typer.echo(f"Fixture {save_observations}: {summarize(observations)}")
        if expected is not None:
            typer.echo(f"Kỳ vọng {expected}: xem lại so với ground truth trước khi commit.")
    return summary


eval_app = typer.Typer(
    help="Đánh giá trên tập phát triển (F16): replay từng video của manifest, tính metric.",
    invoke_without_command=True,
)
app.add_typer(eval_app, name="eval")

DEFAULT_CAMERAS_DIR = REPO_ROOT / "config" / "cameras"


def _default_data_dir() -> Path:
    env = os.environ.get("POSTCARE_DATA_DIR")
    return Path(env) if env else REPO_ROOT / "data"


def _print_validation(result: Any) -> None:
    for w in result.warnings:
        typer.echo(f"Cảnh báo: {w}")
    for e in result.errors:
        typer.echo(f"Lỗi: {e}", err=True)


def _hardware() -> str:
    import platform

    import psutil

    ram_gb = psutil.virtual_memory().total / 2**30
    cpu = platform.processor() or platform.machine()
    return (
        f"{platform.system()} {platform.release()}, {cpu}, "
        f"{psutil.cpu_count(logical=True)} luồng logic, RAM {ram_gb:.1f} GB"
    )


@eval_app.command("check")
def eval_check(
    manifest: Annotated[Path | None, typer.Option(help="Mặc định <data>/eval/manifest.csv")] = None,
    truth: Annotated[Path | None, typer.Option(help="Mặc định <data>/eval/truth.csv")] = None,
) -> None:
    """Kiểm tra manifest.csv và truth.csv (F16 R2). Lỗi → exit 1; trùng người/phiên → cảnh báo."""
    from postcare.eval.manifest import validate_files

    data_dir = _default_data_dir()
    m = manifest or data_dir / "eval" / "manifest.csv"
    t = truth or data_dir / "eval" / "truth.csv"
    result = validate_files(m, t)
    _print_validation(result)
    if not result.ok:
        _fail(f"{len(result.errors)} lỗi trong {m} / {t}.")
    counts = ", ".join(f"{s}: {len(result.rows(s))}" for s in ("dev", "test"))
    typer.echo(f"Hợp lệ: {len(result.manifest)} video ({counts}), {len(result.truth)} dòng truth.")


@eval_app.callback()
def eval_command(
    ctx: typer.Context,
    split: Annotated[str, typer.Option(help="Chỉ hỗ trợ dev (tập test: F29 với --frozen)")] = "dev",
    manifest: Annotated[Path | None, typer.Option(help="Mặc định <data>/eval/manifest.csv")] = None,
    truth: Annotated[Path | None, typer.Option(help="Mặc định <data>/eval/truth.csv")] = None,
    tol_before_s: Annotated[
        float, typer.Option(help="Tolerance trước start_s (A06)")
    ] = DEFAULT_TOL_BEFORE_S,
    tol_after_s: Annotated[
        float, typer.Option(help="Tolerance sau end_s (A06)")
    ] = DEFAULT_TOL_AFTER_S,
    runs_dir: Annotated[
        Path | None, typer.Option(help="Thư mục kết quả replay, mặc định runs/eval-<split>/")
    ] = None,
    from_observations: Annotated[
        Path | None,
        typer.Option(help="Thư mục runs/ trước đó: chạy lại chỉ engine từ <dir>/<video_id>/"),
    ] = None,
    reuse: Annotated[
        bool, typer.Option("--reuse", help="Dùng lại kết quả trong --runs-dir nếu cùng config_hash")
    ] = False,
    report: Annotated[
        Path | None,
        typer.Option(help="File báo cáo, mặc định reports/eval-<split>-<ngày>.local.md (+ .json)"),
    ] = None,
    camera_config: Annotated[
        Path, typer.Option(help="Cấu hình camera khi video không có cấu hình riêng")
    ] = DEFAULT_CAMERAS_DIR / "example.yaml",
    engine_config: Annotated[
        Path, typer.Option(help="Ngưỡng mặc định của engine")
    ] = DEFAULT_ENGINE_CONFIG,
    model: Annotated[
        str | None, typer.Option(help="Biến thể pose: lite | full | heavy (mặc định models.yaml)")
    ] = None,
    models_dir: Annotated[
        Path | None, typer.Option(help="Thư mục model (mặc định POSTCARE_MODELS_DIR hoặc models/)")
    ] = None,
    max_fps: Annotated[float, typer.Option(help="Giới hạn FPS xử lý (A03); 0 = mọi khung")] = 15.0,
    video_id: Annotated[
        list[str] | None, typer.Option(help="Chỉ chạy video này (lặp lại được)")
    ] = None,
    limit: Annotated[int | None, typer.Option(help="Chỉ chạy N video đầu (sau lọc)")] = None,
) -> None:
    """Chạy `postcare eval --split dev`: replay từng video, ghép với truth, ghi báo cáo (F16).

    Lệnh con `postcare eval check` chỉ kiểm tra manifest/truth.
    """
    if ctx.invoked_subcommand is not None:
        return
    from datetime import date

    from postcare.eval.manifest import validate_files
    from postcare.eval.report import EvalReport, render_markdown, report_json
    from postcare.eval.runner import VideoRun, run_split, score_runs
    from postcare.replay.runner import code_version
    from postcare.replay.writers import write_json

    if split == "test":
        _fail(
            "postcare eval (F16) chỉ chạy --split dev. Tập test chỉ đánh giá một lần sau khi chốt "
            "cấu hình: dùng lệnh của F29 với --frozen <config_hash> (HS §8.2).",
            2,
        )
    if split != "dev":
        _fail(f"--split '{split}' không hợp lệ; chỉ hỗ trợ dev.", 2)
    if tol_before_s < 0 or tol_after_s < 0 or max_fps < 0:
        _fail("--tol-before-s, --tol-after-s, --max-fps phải ≥ 0.", 2)
    data_dir = _default_data_dir()
    m = manifest or data_dir / "eval" / "manifest.csv"
    t = truth or data_dir / "eval" / "truth.csv"
    result = validate_files(m, t)
    _print_validation(result)
    if not result.ok:
        _fail(f"{len(result.errors)} lỗi trong manifest/truth; sửa trước khi chạy eval.")
    rows = result.rows(split)
    if video_id:
        wanted = set(video_id)
        unknown = wanted - {r.video_id for r in rows}
        if unknown:
            _fail(f"Không có video {', '.join(sorted(unknown))} trong split {split}.")
        rows = [r for r in rows if r.video_id in wanted]
    if limit is not None:
        rows = rows[: max(limit, 0)]
    if not rows:
        _fail(f"Split {split} không có video nào.")

    runs = runs_dir or REPO_ROOT / "runs" / f"eval-{split}"
    if from_observations is not None and from_observations.resolve() == runs.resolve():
        _fail("--from-observations phải khác --runs-dir (không ghi đè observation nguồn).", 2)
    adapter_factory = None
    model_info: dict[str, Any] | None = None
    if from_observations is None:
        adapter_factory, model_info = _pose_adapter_factory(model, models_dir)
    if model_info is None:
        mode = f"observations (chỉ engine, từ {from_observations})"
    else:
        mode = f"video (pose {model_info['variant']}, {model_info['file']}, max-fps {max_fps:g})"

    typer.echo(f"Eval split {split}: {len(rows)} video → {runs}")
    results = run_split(
        rows,
        runs_dir=runs,
        engine_config=engine_config,
        default_camera_config=camera_config,
        cameras_dir=DEFAULT_CAMERAS_DIR,
        data_dir=data_dir,
        adapter_factory=adapter_factory,
        from_observations=from_observations,
        reuse=reuse,
        max_fps=max_fps or None,
        model_info=model_info,
        on_progress=lambda i, n, row, status: typer.echo(f"[{i}/{n}] {row.video_id}: {status}"),
    )
    videos, failures = score_runs(
        results, result.truth_by_video(), tol_before_s=tol_before_s, tol_after_s=tol_after_s
    )
    hashes = list(dict.fromkeys(r.run["config_hash"] for r in results if isinstance(r, VideoRun)))
    notes: list[str] = []
    if video_id or limit is not None:
        total = len(result.rows(split))
        notes.append(f"Tập con: {len(rows)}/{total} video của split (--video-id/--limit)")
    today = date.today().isoformat()
    ev = EvalReport(
        split=split,
        created=today,
        videos=videos,
        failures=failures,
        tol_before_s=tol_before_s,
        tol_after_s=tol_after_s,
        config_hashes=hashes,
        commit=code_version()["commit"],
        hardware=_hardware(),
        mode=mode + (", dùng lại runs/ cùng config_hash" if reuse else ""),
        manifest=str(m),
        notes=notes,
    )
    out = report or REPO_ROOT / "reports" / f"eval-{split}-{today}.local.md"
    if not out.stem.endswith(".local"):
        # Chỉ reports/*.local.md, *.local.json bị gitignore: thêm `.local` để không commit nhầm.
        fixed = out.with_name(f"{out.stem}.local{out.suffix or '.md'}")
        typer.echo(f"Cảnh báo: --report {out.name} không có '.local'; ghi vào {fixed.name}.")
        out = fixed
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(render_markdown(ev))
    write_json(out.with_suffix(".json"), report_json(ev))
    typer.echo(f"Báo cáo: {out} (+ {out.with_suffix('.json').name})")
    if failures:
        _fail(f"{len(failures)} video lỗi (xem mục 'Video lỗi' trong báo cáo).")


def _pose_adapter_factory(model: str | None, models_dir: Path | None) -> tuple[Any, dict[str, Any]]:
    from postcare.vision.inference.base import ModelNotFoundError
    from postcare.vision.inference.pose_mediapipe import MediaPipePoseAdapter
    from postcare.vision.models import ManifestError, load_manifest

    directory = models_dir or _default_models_dir()
    try:
        entry = load_manifest(DEFAULT_MODELS_MANIFEST).pose_entry(model)
    except ManifestError as exc:
        _fail(str(exc))
    path = directory / entry.filename
    if not path.is_file():
        _fail(f"Không tìm thấy model {path}. Chạy `make models` hoặc đặt POSTCARE_MODELS_DIR.")

    def factory(config: Any) -> Any:
        try:
            return MediaPipePoseAdapter.from_config(path, config)
        except ModelNotFoundError as exc:
            raise RuntimeError(str(exc)) from exc

    return factory, {"variant": entry.name, "file": entry.filename}


@app.command()
def models(
    variant: Annotated[
        list[str] | None,
        typer.Option(help="Chỉ tải biến thể này (lặp lại được); mặc định tải mọi biến thể"),
    ] = None,
    manifest: Annotated[Path, typer.Option(help="File manifest model")] = DEFAULT_MODELS_MANIFEST,
    dest: Annotated[Path, typer.Option(help="Thư mục lưu model")] = DEFAULT_MODELS_DIR,
) -> None:
    """Tải model pose MediaPipe `.task` vào models/ và kiểm tra sha256 (F11; ADR-0003)."""
    from postcare.vision.models import (
        ChecksumMismatchError,
        DownloadError,
        ManifestError,
        ensure_model,
        load_manifest,
    )

    try:
        loaded = load_manifest(manifest)
        entries = [loaded.pose_entry(v) for v in variant] if variant else list(loaded.pose.variants)
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    for entry in entries:
        typer.echo(f"{entry.filename}: kiểm tra…")
        try:
            result = ensure_model(entry, dest)
        except (ChecksumMismatchError, DownloadError) as exc:
            typer.echo(f"Lỗi: {exc}", err=True)
            raise typer.Exit(1) from exc
        if result.downloaded:
            typer.echo(f"{entry.filename}: đã tải, sha256 khớp → {result.path}")
        else:
            typer.echo(f"{entry.filename}: đã có, sha256 khớp, bỏ qua")
    typer.echo(f"Biến thể pose mặc định: {loaded.pose.default}")


@app.command()
def openapi(
    out: Annotated[Path, typer.Option(help="File JSON đầu ra")] = Path(
        "../web/src/api/openapi.json"
    ),
    check: Annotated[
        bool, typer.Option("--check", help="Chỉ so file với OpenAPI hiện tại, không ghi")
    ] = False,
) -> None:
    """Xuất OpenAPI của API ra file (dùng sinh type TypeScript)."""
    from postcare.api.main import create_app

    spec = create_app(watch_cameras=False).openapi()
    if check:
        # So nội dung JSON đã parse (không so văn bản): CRLF/LF không làm lệch kết quả.
        try:
            current = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            typer.echo(f"Không đọc được {out} ({exc}). Chạy `make gen-api-types`.", err=True)
            raise typer.Exit(1) from exc
        if current != spec:
            typer.echo(
                f"{out} không khớp OpenAPI hiện tại. Chạy `make gen-api-types` rồi commit.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(f"{out} khớp OpenAPI hiện tại.")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    typer.echo(f"Đã ghi {out}")


if __name__ == "__main__":
    app()
