"""Tải model AI pretrained theo manifest và kiểm tra sha256 (F11 R1, R2; ADR-0003).

- Manifest: `config/models.yaml` (URL có số phiên bản cố định, tên file, sha256).
- Tải bằng `urllib` của thư viện chuẩn (chạy được trên Windows và Linux, không cần curl/wget),
  ghi ra file tạm `.part` rồi mới đổi tên, nên không bao giờ để lại file model dở dang.
- File đã có và đúng sha256 → bỏ qua. Sai sha256 → xóa file tải về, báo lỗi.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_CHUNK = 1 << 20
DOWNLOAD_TIMEOUT_S = 60.0  # (giả định) timeout mỗi lần đọc mạng


class ManifestError(ValueError):
    """Manifest model sai định dạng hoặc không có biến thể được hỏi."""


class ChecksumMismatchError(RuntimeError):
    """File tải về không khớp sha256 trong manifest."""


class DownloadError(RuntimeError):
    """Không tải được file model (mạng, URL sai…)."""


class ModelEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[str, Field(min_length=1)]
    url: Annotated[str, Field(min_length=1)]
    filename: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]+$")]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("url")
    @classmethod
    def _pinned_url(cls, url: str) -> str:
        if re.search(r"latest", url, re.IGNORECASE):
            raise ValueError("URL không được dùng 'latest' (cần số phiên bản cố định)")
        return url


class PoseModels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default: str
    variants: Annotated[list[ModelEntry], Field(min_length=1)]

    @model_validator(mode="after")
    def _check(self) -> PoseModels:
        names = [v.name for v in self.variants]
        if len(set(names)) != len(names):
            raise ValueError(f"tên biến thể trùng: {names}")
        if self.default not in names:
            raise ValueError(f"default '{self.default}' không có trong {names}")
        return self


class ModelManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    pose: PoseModels

    def pose_entry(self, variant: str | None = None) -> ModelEntry:
        """Biến thể pose theo tên; `None` → biến thể mặc định của manifest."""
        name = variant or self.pose.default
        for entry in self.pose.variants:
            if entry.name == name:
                return entry
        names = ", ".join(v.name for v in self.pose.variants)
        raise ManifestError(f"Không có biến thể pose '{name}'. Chọn một trong: {names}")


def load_manifest(path: Path | str) -> ModelManifest:
    path = Path(path)
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"Không đọc được manifest model {path}: {exc}") from exc
    try:
        return ModelManifest.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ManifestError(f"Manifest model {path} không hợp lệ: {problems}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


Opener = Callable[[str], IO[bytes]]


def _default_opener(url: str) -> IO[bytes]:
    # Chỉ https (model chính thức) và file (test, bản sao cục bộ); không http, ftp...
    if not url.startswith(("https://", "file:")):
        raise DownloadError(f"Chỉ hỗ trợ URL https hoặc file: {url}")
    return urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S)  # type: ignore[no-any-return]


@dataclass(frozen=True)
class EnsureResult:
    entry: ModelEntry
    path: Path
    downloaded: bool


def ensure_model(
    entry: ModelEntry, dest_dir: Path, *, opener: Opener | None = None
) -> EnsureResult:
    """Bảo đảm `dest_dir/entry.filename` có và đúng sha256; tải khi thiếu hoặc sai."""
    target = dest_dir / entry.filename
    if target.is_file() and sha256_file(target) == entry.sha256:
        return EnsureResult(entry, target, downloaded=False)
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        try:
            with (opener or _default_opener)(entry.url) as resp, part.open("wb") as out:
                shutil.copyfileobj(resp, out, _CHUNK)
        except OSError as exc:  # URLError, HTTPError, timeout đều là OSError
            raise DownloadError(f"Không tải được {entry.url}: {exc}") from exc
        actual = sha256_file(part)
        if actual != entry.sha256:
            raise ChecksumMismatchError(
                f"{entry.filename}: sha256 không khớp (manifest {entry.sha256}, tải về {actual}). "
                "Đã xóa file tải về."
            )
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return EnsureResult(entry, target, downloaded=True)
