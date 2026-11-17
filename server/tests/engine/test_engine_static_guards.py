"""Chặn tĩnh: `postcare.engine` không đọc đồng hồ hệ thống (AGENTS.md quy tắc 5; review F10).

Import-linter đã chặn cv2/mediapipe/fastapi/sqlalchemy/httpx. Test này quét AST để chặn thêm các
module stdlib cho phép đọc thời gian hoặc sinh ngẫu nhiên (phá tính xác định).
"""

import ast
from pathlib import Path

import postcare.engine

FORBIDDEN = {"time", "datetime", "random"}
ENGINE_DIR = Path(postcare.engine.__file__).parent


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
        ):
            roots.add("__import__")
    return roots


def test_engine_does_not_import_clock_or_random_modules() -> None:
    files = sorted(ENGINE_DIR.rglob("*.py"))
    assert files, ENGINE_DIR
    offenders = {}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        bad = _imported_roots(tree) & (FORBIDDEN | {"__import__"})
        if bad:
            offenders[path.relative_to(ENGINE_DIR).as_posix()] = sorted(bad)
    assert not offenders, f"postcare.engine import module bị cấm: {offenders}"


def test_guard_detects_forbidden_imports() -> None:
    src = "import time\nfrom datetime import datetime\nimport os.path\nimport random as r\n"
    assert _imported_roots(ast.parse(src)) & FORBIDDEN == {"time", "datetime", "random"}
