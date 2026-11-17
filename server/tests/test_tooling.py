"""F00: kiểm tra tĩnh công cụ dự án (Makefile, dev.ps1, hook, CI, import-linter, cấu hình engine).

Không gọi make, không cần mạng. Chỉ đọc file trong repo (trừ một test chạy `lint-imports`).
"""

import configparser
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
MAKEFILE = ROOT / "Makefile"
DEV_PS1 = ROOT / "scripts" / "dev.ps1"

# R3 + target của prototype được giữ (giả định §7) + check-api-types (§9.2 bước 10).
REQUIRED_TARGETS = {
    "help",
    "setup",
    "dev",
    "dev-api",
    "dev-web",
    "worker",
    "format",
    "format-check",
    "lint",
    "typecheck",
    "lint-imports",
    "test",
    "test-vision",
    "build-web",
    "check",
    "check-api-types",
    "db-upgrade",
    "db-seed",
    "models",
    "gen-api-types",
    "seed",
    "simulate",
}
CHECK_STEPS = [
    "format-check",
    "lint",
    "typecheck",
    "lint-imports",
    "check-api-types",
    "test",
    "build-web",
]
PLACEHOLDER_TARGETS = {"worker": "F06", "models": "F11"}


# --------------------------------------------------------------------------- helpers


def _makefile() -> tuple[dict[str, list[str]], dict[str, list[str]], set[str], str]:
    """Trả về (prerequisites, recipe lines, .PHONY, văn bản) của Makefile."""
    text = MAKEFILE.read_text(encoding="utf-8")
    prereqs: dict[str, list[str]] = {}
    recipes: dict[str, list[str]] = {}
    phony: set[str] = set()
    current: str | None = None
    for raw in text.splitlines():
        if raw.startswith("\t"):
            if current is not None:
                recipes[current].append(raw[1:])
            continue
        line = raw.split("#", 1)[0].rstrip()
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*:(?![:=])\s*(.*)$", line)
        if m:
            name, deps = m.group(1), m.group(2).split()
            if name == ".PHONY":
                phony.update(deps)
                current = None
                continue
            current = name
            prereqs[name] = deps
            recipes[name] = []
        elif line.strip():
            current = None
    return prereqs, recipes, phony, text


def _ps1_tasks() -> set[str]:
    text = DEV_PS1.read_text(encoding="utf-8")
    m = re.search(r"ValidateSet\((.*?)\)\]", text, re.S)
    assert m, "dev.ps1 thiếu [ValidateSet(...)] cho tham số Task"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def _doc_engine_yaml() -> dict[str, Any]:
    doc = (ROOT / "docs" / "02-architecture" / "event-engine.md").read_text(encoding="utf-8")
    section = doc.split("## 6.", 1)[1]
    m = re.search(r"```yaml\n(.*?)```", section, re.S)
    assert m, "event-engine.md §6 không có khối yaml"
    return yaml.safe_load(m.group(1))


def _key_paths(data: Any, prefix: str = "") -> set[str]:
    if not isinstance(data, dict):
        return set()
    out: set[str] = set()
    for k, v in data.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        out.add(path)
        out |= _key_paths(v, path)
    return out


def _load_yaml(path: Path) -> Any:
    assert path.is_file(), f"thiếu {path.relative_to(ROOT)}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- AC1: Makefile, dev.ps1


def test_makefile_has_required_targets() -> None:
    prereqs, _, _, _ = _makefile()
    missing = REQUIRED_TARGETS - prereqs.keys()
    assert not missing, f"Makefile thiếu target: {sorted(missing)}"


def test_makefile_targets_are_phony() -> None:
    prereqs, _, phony, _ = _makefile()
    assert set(prereqs) <= phony, f"target không có trong .PHONY: {sorted(set(prereqs) - phony)}"


def test_check_runs_every_step() -> None:
    prereqs, recipes, _, _ = _makefile()
    deps = prereqs.get("check", [])
    missing = [s for s in CHECK_STEPS if s not in deps]
    assert not missing, (
        f"`check` thiếu bước: {missing} (đang có {deps}, recipe {recipes.get('check')})"
    )


def test_dev_ps1_matches_makefile_targets() -> None:
    _, _, phony, _ = _makefile()
    tasks = _ps1_tasks()
    assert tasks == phony, (
        f"chỉ có trong Makefile: {sorted(phony - tasks)}; "
        f"chỉ có trong dev.ps1: {sorted(tasks - phony)}"
    )


def test_dev_ps1_is_ascii() -> None:
    DEV_PS1.read_bytes().decode("ascii")


def test_dev_ps1_worker_accepts_camera() -> None:
    assert re.search(r"\$Camera\b", DEV_PS1.read_text(encoding="utf-8"))


FORBIDDEN_RECIPE = [
    (r"(^|[\s;&|@-])rm\s", "rm"),
    (r"(^|[\s;&|@-])cp\s", "cp"),
    (r"mkdir\s+-p", "mkdir -p"),
    (r"(^|[\s;&|@-])export\s", "export"),
    (r"\[\s", "[ ]"),
    (r"(^|[;&|]\s*|^[@-]*)test\s+-", "test -x"),
    (r"\$\(shell", "$(shell ...)"),
    (r"'", "dấu nháy đơn"),
    (r"^[@\-+]*\s*[A-Za-z_][A-Za-z0-9_]*=\S*\s+\S", "VAR=x cmd"),
]


def test_makefile_recipes_are_portable() -> None:
    """R4 (ca âm tính AC1): recipe không dùng cú pháp chỉ có trên sh/bash, chỉ ASCII."""
    _, recipes, _, _ = _makefile()
    problems: list[str] = []
    for target, lines in recipes.items():
        for line in lines:
            if not line.isascii():
                problems.append(f"{target}: ký tự ngoài ASCII: {line!r}")
            for pattern, label in FORBIDDEN_RECIPE:
                if re.search(pattern, line):
                    problems.append(f"{target}: {label}: {line!r}")
    assert not problems, "\n".join(problems)


def test_recipe_commands_only_call_uv_npm_or_echo() -> None:
    _, recipes, _, _ = _makefile()
    allowed = ("uv ", "npm ", "echo", "exit ", "$(MAKE)")
    bad = [
        f"{t}: {line!r}"
        for t, lines in recipes.items()
        for line in lines
        if not line.lstrip("@-+ ").startswith(allowed)
    ]
    assert not bad, "\n".join(bad)


def test_help_echo_lines_avoid_shell_metacharacters() -> None:
    _, recipes, _, _ = _makefile()
    lines = recipes.get("help", [])
    assert lines, "`help` không có recipe"
    for line in lines:
        assert line.lstrip("@").startswith("echo"), line
        body = re.sub(r"\$\([A-Za-z_]+\)", "", line)
        assert not re.search(r"[<>|&()]", body), line


def test_placeholder_targets_exit_nonzero() -> None:
    _, recipes, _, _ = _makefile()
    for target, feature in PLACEHOLDER_TARGETS.items():
        body = "\n".join(recipes.get(target, []))
        assert re.search(r"\bexit\s+1\b", body), f"`{target}` phải trả exit khác 0"
        assert feature in body, f"`{target}` phải nhắc {feature}"


def test_db_targets_are_real_commands() -> None:
    """F01 R6, R7: db-upgrade chạy alembic upgrade head, db-seed gọi `postcare seed`."""
    _, recipes, _, _ = _makefile()
    upgrade = "\n".join(recipes.get("db-upgrade", []))
    seed = "\n".join(recipes.get("db-seed", []))
    assert "uv --directory server run alembic upgrade head" in upgrade, upgrade
    assert re.search(r"uv --directory server run postcare seed\s*$", seed, re.M), seed
    for body in (upgrade, seed):
        assert not re.search(r"\bexit\s+1\b", body), body
    prototype = "\n".join(recipes.get("seed", []))
    assert "postcare seed --reset" in prototype, prototype


def test_dev_ps1_db_tasks_match_makefile() -> None:
    text = DEV_PS1.read_text(encoding="utf-8")
    assert re.search(r"'db-upgrade'\s*\{[^}]*'alembic', 'upgrade', 'head'", text)
    assert re.search(r"'db-seed'\s*\{[^}]*'postcare', 'seed'\s*\)", text)
    assert re.search(r"'seed'\s*\{[^}]*'postcare', 'seed', '--reset'", text)


def test_worker_takes_camera_variable() -> None:
    _, _, _, text = _makefile()
    assert re.search(r"^CAMERA\s*\?=", text, re.M)


def test_test_target_excludes_vision_and_test_vision_selects_it() -> None:
    _, recipes, _, _ = _makefile()
    test_body = "\n".join(recipes.get("test", []))
    assert re.search(r"pytest.*-m\s+\"not vision\"", test_body), test_body
    assert "npm --prefix web run test" in test_body
    vision_body = "\n".join(recipes.get("test-vision", []))
    assert re.search(r"pytest.*-m\s+\"?vision\"?", vision_body), vision_body


def test_typecheck_runs_mypy_and_tsc() -> None:
    _, recipes, _, _ = _makefile()
    body = "\n".join(recipes.get("typecheck", []))
    assert "mypy" in body
    assert "npm --prefix web run typecheck" in body


def test_setup_installs_both_git_hooks() -> None:
    _, recipes, _, _ = _makefile()
    body = "\n".join(recipes.get("setup", []))
    assert "uv --directory server sync" in body
    assert "npm --prefix web ci" in body
    assert "pre-commit install" in body
    assert "pre-commit" in body.split("pre-commit install", 1)[1]
    assert "pre-push" in body


def test_dev_runs_procfile_with_honcho() -> None:
    _, recipes, _, _ = _makefile()
    body = "\n".join(recipes.get("dev", []))
    assert "honcho" in body and "Procfile.dev" in body


def test_procfile_dev_has_api_and_web() -> None:
    path = ROOT / "Procfile.dev"
    assert path.is_file(), "thiếu Procfile.dev"
    procs = dict(
        line.split(":", 1) for line in path.read_text(encoding="utf-8").splitlines() if ":" in line
    )
    assert set(procs) == {"api", "web"}
    assert "postcare.api.main:app" in procs["api"] and "0.0.0.0" in procs["api"]
    assert "npm --prefix web run dev" in procs["web"]


# ------------------------------------------------------------------ AC3, AC5: Python tooling


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((SERVER / "pyproject.toml").read_text(encoding="utf-8"))


def test_dev_group_has_tooling() -> None:
    dev = " ".join(_pyproject()["dependency-groups"]["dev"])
    for pkg in ("mypy", "import-linter", "pre-commit", "honcho"):
        assert pkg in dev, f"nhóm dev thiếu {pkg}"


def test_pytest_registers_vision_marker_strictly() -> None:
    opts = _pyproject()["tool"]["pytest"]["ini_options"]
    assert any(m.startswith("vision") for m in opts.get("markers", []))
    assert "--strict-markers" in opts.get("addopts", "")


def test_mypy_is_strict_for_schemas_and_engine() -> None:
    mypy = _pyproject()["tool"].get("mypy", {})
    assert mypy.get("strict") is True
    assert {"postcare.schemas", "postcare.engine"} <= set(mypy.get("packages", []))


# --------------------------------------------------------------------------- AC5: import-linter

IO_LIBS = ["cv2", "mediapipe", "fastapi", "sqlalchemy", "httpx"]
P = "postcare."
REQUIRED_FORBIDDEN: set[tuple[str, str]] = (
    {(P + s, lib) for s in ("engine", "schemas") for lib in IO_LIBS}
    | {
        (P + "schemas", P + m)
        for m in (
            "engine",
            "vision",
            "pipeline",
            "worker",
            "replay",
            "eval",
            "db",
            "domain",
            "api",
            "settings",
            "cli",
        )
    }
    | {(P + "engine", P + m) for m in ("vision", "api", "db", "worker", "pipeline")}
    | {(P + "vision", P + m) for m in ("api", "db", "engine")}
    | {(P + s, P + m) for s in ("pipeline", "worker", "replay", "eval") for m in ("api", "db")}
    | {(P + "db", P + m) for m in ("api", "vision", "engine")}
    | {(P + "domain", P + m) for m in ("api", "vision", "engine")}
    | {(P + "api", P + m) for m in ("vision", "engine")}
)


def _importlinter() -> configparser.ConfigParser:
    path = SERVER / ".importlinter"
    assert path.is_file(), "thiếu server/.importlinter"
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    return cfg


def test_importlinter_declares_every_boundary() -> None:
    cfg = _importlinter()
    assert "postcare" in cfg.get("importlinter", "root_packages", fallback="") + cfg.get(
        "importlinter", "root_package", fallback=""
    )
    assert cfg.getboolean("importlinter", "include_external_packages", fallback=False)
    pairs: set[tuple[str, str]] = set()
    for name in cfg.sections():
        if not name.startswith("importlinter:contract:"):
            continue
        sec = cfg[name]
        if sec.get("type") != "forbidden":
            continue
        sources = sec.get("source_modules", "").split()
        forbidden = sec.get("forbidden_modules", "").split()
        pairs |= {(s, f) for s in sources for f in forbidden}
    missing = REQUIRED_FORBIDDEN - pairs
    assert not missing, f"thiếu ranh giới import: {sorted(missing)}"


def test_lint_imports_passes_on_current_code() -> None:
    _importlinter()
    exe = shutil.which("lint-imports", path=str(Path(sys.executable).parent))
    assert exe, "chưa cài import-linter trong venv của server"
    proc = subprocess.run(
        [exe], cwd=SERVER, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------- AC4: git hook


def _hooks(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {h["id"]: h for repo in cfg.get("repos", []) for h in repo.get("hooks", [])}


def test_precommit_config_installs_both_hook_types() -> None:
    cfg = _load_yaml(ROOT / ".pre-commit-config.yaml")
    assert {"pre-commit", "pre-push"} <= set(cfg.get("default_install_hook_types", []))


def test_precommit_stage_checks_server_and_web_without_fixing() -> None:
    cfg = _load_yaml(ROOT / ".pre-commit-config.yaml")
    hooks = [
        h
        for h in _hooks(cfg).values()
        if "pre-commit" in h.get("stages", ["pre-commit"]) and h["id"] != "make-check"
    ]
    entries = [(h["entry"] + " " + " ".join(h.get("args", [])), h.get("files", "")) for h in hooks]
    assert any("ruff format" in e and "--check" in e and "server" in f for e, f in entries)
    assert any(re.search(r"ruff\b.*\bcheck", e) and "format" not in e for e, _ in entries)
    assert any("prettier" in e and "--check" in e and f.startswith("^web/") for e, f in entries)
    assert any("eslint" in e and f.startswith("^web/") for e, f in entries)
    for e, _ in entries:
        assert "--write" not in e and "--fix" not in e, f"hook không được tự sửa file: {e}"


def test_prepush_stage_runs_make_check() -> None:
    cfg = _load_yaml(ROOT / ".pre-commit-config.yaml")
    hook = _hooks(cfg).get("make-check")
    assert hook, "thiếu hook id make-check"
    assert hook["entry"].strip() == "make check"
    assert hook.get("stages") == ["pre-push"]
    assert hook.get("pass_filenames") is False
    assert hook.get("always_run") is True


# --------------------------------------------------------------------------- AC1: CI


def test_ci_runs_setup_and_check_on_ubuntu() -> None:
    cfg = _load_yaml(ROOT / ".github" / "workflows" / "ci.yml")
    triggers = cfg.get("on", cfg.get(True))  # PyYAML đọc khóa `on` thành True
    names = set(triggers) if isinstance(triggers, (list, dict)) else {triggers}
    assert {"push", "pull_request"} <= names
    jobs = cfg["jobs"]
    job = jobs.get("check") or next(iter(jobs.values()))
    assert job["runs-on"] == "ubuntu-latest"
    runs = [s.get("run", "") for s in job["steps"]]
    assert "make setup" in runs and "make check" in runs
    assert runs.index("make setup") < runs.index("make check")
    node = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/setup-node")]
    assert node and node[0].get("with", {}).get("node-version-file") == "web/.nvmrc"


def test_ci_has_postgres_service_and_test_database_url() -> None:
    """F01 R11: job Ubuntu có service postgres:16 và TEST_DATABASE_URL; job Windows có DB test."""
    cfg = _load_yaml(ROOT / ".github" / "workflows" / "ci.yml")
    jobs = cfg["jobs"]
    check = jobs["check"]
    pg = check.get("services", {}).get("postgres", {})
    assert pg.get("image") == "postgres:16", pg
    env = check.get("env", {})
    assert env.get("TEST_DATABASE_URL", "").endswith("/postcare_test"), env
    win = jobs["windows"]
    assert win.get("env", {}).get("TEST_DATABASE_URL", "").endswith("/postcare_test")
    win_runs = " ".join(str(s.get("run", "")) for s in win["steps"])
    assert "postcare_test" in win_runs, "job Windows phải tạo DB postcare_test"


def test_nvmrc_pins_node_lts() -> None:
    path = ROOT / "web" / ".nvmrc"
    assert path.is_file(), "thiếu web/.nvmrc"
    assert path.read_text(encoding="utf-8").strip().lstrip("v").split(".")[0] in {"22", "24"}


# --------------------------------------------------------------------------- AC6: type API cũ


def test_check_api_types_compares_openapi_and_schema() -> None:
    _, recipes, _, _ = _makefile()
    body = "\n".join(recipes.get("check-api-types", []))
    assert re.search(r"postcare openapi .*--check", body), body
    assert "npm --prefix web run check-api-types" in body
    scripts = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))["scripts"]
    script = scripts.get("check-api-types", "")
    assert "openapi-typescript" in script and "--check" in script


# --------------------------------------------------------------------------- R14: cấu hình engine


@pytest.fixture(scope="module")
def engine_config() -> Any:
    return _load_yaml(ROOT / "config" / "engine.default.yaml")


def test_engine_default_config_has_all_documented_keys(engine_config: Any) -> None:
    missing = _key_paths(_doc_engine_yaml()) - _key_paths(engine_config)
    assert not missing, f"config/engine.default.yaml thiếu khóa: {sorted(missing)}"


def test_engine_default_config_matches_doc_values(engine_config: Any) -> None:
    """Một nguồn sự thật: file khởi điểm chép nguyên khối event-engine.md §6."""
    assert engine_config == _doc_engine_yaml()
