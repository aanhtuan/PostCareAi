"""Lệnh CLI `postcare`: version, seed, simulate, probe, openapi."""

import json
import sys
import time
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import httpx
import typer
from sqlalchemy import select

from postcare.db.models import Bed
from postcare.db.session import make_engine, make_session_factory, reset_schema
from postcare.db.types import utcnow
from postcare.domain.seed import SEED_USERS, seed_base, seed_history
from postcare.settings import get_settings

# Console Windows (cp1252) không in được tiếng Việt: ép UTF-8 cho stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="PostCare AI - công cụ dòng lệnh (prototype)", no_args_is_help=True)


@app.command()
def version() -> None:
    """In phiên bản package `postcare` đã cài."""
    typer.echo(f"postcare {package_version('postcare')}")


@app.command()
def seed(
    history: Annotated[
        bool, typer.Option(help="Thêm phiên mở và sự kiện quá khứ cho A02/A03")
    ] = True,
) -> None:
    """XÓA và tạo lại toàn bộ dữ liệu mẫu (tài khoản, ca, giường A01–A03, camera, BN-001…)."""
    settings = get_settings()
    engine = make_engine(settings.database_url)
    reset_schema(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        seed_base(db, settings.seed_password)
        if history:
            seed_history(db, utcnow())
    typer.echo(f"Đã tạo dữ liệu mẫu tại {engine.url.render_as_string(hide_password=True)}")
    typer.echo("Tài khoản (mật khẩu = SEED_PASSWORD, mặc định 'postcare'):")
    for username, full_name, role in SEED_USERS:
        typer.echo(f"  {username:<8} {role.value:<13} {full_name}")
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
) -> None:
    """Kiểm tra nguồn video (F05): in FPS thực, độ phân giải, số khung bỏ, số lần mất kết nối."""
    from postcare.vision.camera import SourceOpenError, guess_source_type, open_source

    if seconds <= 0 or max_fps <= 0:
        raise typer.BadParameter("seconds và max-fps phải > 0")
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
        raise typer.Exit(1) from exc
    started = time.monotonic()
    try:
        while time.monotonic() - started < seconds:
            if src.read(timeout_s=1.0) is None and src.ended:
                break
    except KeyboardInterrupt:
        typer.echo("Đã dừng.")
    finally:
        elapsed = time.monotonic() - started
        src.close()
    stats = src.stats
    typer.echo(f"Độ phân giải: {stats.width}x{stats.height}")
    typer.echo(f"Số khung đã xử lý: {stats.frames} (trong {elapsed:.1f} s)")
    typer.echo(f"FPS thực (theo ts_ms): {stats.fps:.1f}")
    typer.echo(f"FPS xử lý (đồng hồ máy): {stats.frames / elapsed if elapsed > 0 else 0:.1f}")
    typer.echo(f"Số khung bỏ: {stats.dropped_frames}")
    typer.echo(f"Số lần mất kết nối: {stats.disconnects}")
    if src.ended:
        typer.echo("Đã đọc hết file.")
    if stats.frames == 0:
        typer.echo("Không nhận được khung hình nào.", err=True)
        raise typer.Exit(1)


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
