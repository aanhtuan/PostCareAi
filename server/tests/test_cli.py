"""F00 AC3 (R9) và AC6 (R12): CLI `postcare` và kiểm tra OpenAPI đã sinh còn khớp."""

import json
import re
from importlib.metadata import version
from pathlib import Path

from typer.testing import CliRunner

from postcare.cli.main import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "version" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert version("postcare") in result.output


def test_unknown_command_fails() -> None:
    result = runner.invoke(app, ["lenh-khong-ton-tai"])
    assert result.exit_code != 0


def _write_spec(out: Path) -> dict:
    result = runner.invoke(app, ["openapi", "--out", str(out)])
    assert result.exit_code == 0, result.output
    return json.loads(out.read_text(encoding="utf-8"))


def test_openapi_writes_lf_newlines(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    _write_spec(out)
    assert b"\r\n" not in out.read_bytes()


def test_openapi_check_passes_when_fresh(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    _write_spec(out)
    before = out.read_bytes()
    result = runner.invoke(app, ["openapi", "--out", str(out), "--check"])
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == before, "--check không được ghi file"


def test_openapi_check_ignores_line_endings(tmp_path: Path) -> None:
    """So nội dung JSON đã parse, không so văn bản (CRLF trên Windows vẫn khớp)."""
    out = tmp_path / "openapi.json"
    _write_spec(out)
    out.write_bytes(out.read_bytes().replace(b"\n", b"\r\n"))
    result = runner.invoke(app, ["openapi", "--out", str(out), "--check"])
    assert result.exit_code == 0, result.output


def test_openapi_check_fails_when_stale(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    spec = _write_spec(out)
    spec["paths"]["/api/v1/endpoint-thua"] = {"get": {"responses": {"200": {"description": "x"}}}}
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["openapi", "--out", str(out), "--check"])
    assert result.exit_code == 1, result.output
    assert "make gen-api-types" in result.output


def test_openapi_check_fails_when_endpoint_missing(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    spec = _write_spec(out)
    spec["paths"].pop("/api/v1/health")
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["openapi", "--out", str(out), "--check"])
    assert result.exit_code == 1, result.output


def test_openapi_check_fails_when_file_missing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["openapi", "--out", str(tmp_path / "chua-sinh.json"), "--check"])
    assert result.exit_code != 0


def test_seed_help_lists_reset_option() -> None:
    """F01 R7: `postcare seed` có trong CLI; `--reset` là chế độ dữ liệu demo của prototype."""
    # CI (GITHUB_ACTIONS) bật màu cho rich: mã ANSI chen giữa "-" và "-reset".
    result = runner.invoke(
        app, ["seed", "--help"], env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}
    )
    assert result.exit_code == 0, result.output
    plain = re.sub(r"\[[0-9;]*m", "", result.output)
    assert "--reset" in plain


def test_worker_command_help_lists_camera_id() -> None:
    """F06 R11: `postcare worker --camera-id N`."""
    from typer.testing import CliRunner

    from postcare.cli.main import app

    result = CliRunner().invoke(app, ["worker", "--help"])
    assert result.exit_code == 0, result.output
    assert "--camera-id" in result.output
