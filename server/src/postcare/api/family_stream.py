"""Bản chiếu realtime cho người nhà (F36 R12–R14): một `FamilyProjection` cho mỗi kết nối.

Hub gửi mọi message cho bản chiếu; bản chiếu trả về các message `family.*` (có thể rỗng) cho
đúng các grant của kết nối đó. Không bao giờ chuyển nguyên message của nhân viên: chỉ chép các
trường cho phép (không có mã bệnh nhân, tên người, `note`, `explanation`, `face_*`, ảnh).

Mọi hàm chạy trong event loop của hub (một luồng), nên không cần khóa.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

from postcare.domain.cameras import BED_SKELETON
from postcare.domain.family_access import GRANT_ENDED
from postcare.schemas.enums import FamilyAccessEndReason, Priority, ShareLevel

Message = dict[str, Any]

CLOSE_FAMILY = 4403
SKELETON_MIN_INTERVAL_S = 0.2  # ~5 lần/giây (F36 R13, như A03)
EXPIRY_CHECK_S = 0.5  # chu kỳ kiểm tra hết hạn ≤ 1 s (F36 R14)
CLOSE_MESSAGE = "__close__"
FAMILY_ONLY_TYPES = frozenset({BED_SKELETON, GRANT_ENDED})
"""Message nội bộ chỉ dành cho bản chiếu người nhà: kết nối nhân viên không nhận."""

STATE_FIELDS = ("body_state", "observation_quality", "activity_level", "rest_status", "updated_at")


def envelope(type_: str, payload: dict[str, Any]) -> Message:
    return {"type": type_, "payload": payload, "sent_at": datetime.now(UTC).isoformat()}


def staff_accept(message: Message) -> bool:
    """Bộ lọc cho kết nối nhân viên: bỏ message nội bộ của người nhà (F36 R13)."""
    type_ = str(message.get("type", ""))
    return type_ not in FAMILY_ONLY_TYPES and not type_.startswith("family.")


@dataclass
class GrantStream:
    grant_id: int
    session_id: int
    bed_id: int
    share_level: ShareLevel
    expires_at: datetime | None
    capture_paused: bool
    state: dict[str, Any] | None = None
    """Trạng thái gần nhất (chỉ các trường của `STATE_FIELDS`), để gửi lại khi tạm dừng/tiếp tục."""
    last_skeleton_at: float = field(default=float("-inf"))


class FamilyProjection:
    def __init__(
        self,
        grants: list[GrantStream],
        *,
        monotonic: Callable[[], float] = time.monotonic,
        skeleton_min_interval_s: float = SKELETON_MIN_INTERVAL_S,
    ) -> None:
        self._grants: dict[int, GrantStream] = {g.grant_id: g for g in grants}
        self._monotonic = monotonic
        self._skeleton_interval = skeleton_min_interval_s

    @property
    def grant_ids(self) -> list[int]:
        return list(self._grants)

    # ---- message gửi cho client ----
    def _state_msg(self, g: GrantStream) -> Message:
        state = g.state or {}
        payload = {"grant_id": g.grant_id, **{k: state.get(k) for k in STATE_FIELDS}}
        payload["capture_paused"] = g.capture_paused
        return envelope("family.state", payload)

    def initial(self) -> list[Message]:
        return [self._state_msg(g) for g in self._grants.values()]

    def _end(self, grant_id: int, reason: FamilyAccessEndReason) -> list[Message]:
        if self._grants.pop(grant_id, None) is None:
            return []
        out = [envelope("family.access_ended", {"grant_id": grant_id, "reason": reason.value})]
        if not self._grants:  # hết grant cuối: đóng kết nối 4403 sau khi gửi access_ended
            out.append({"type": CLOSE_MESSAGE, "code": CLOSE_FAMILY})
        return out

    def end_all(self, reason: FamilyAccessEndReason) -> list[Message]:
        """Báo hết quyền cho mọi grant (tài khoản bị khóa / đổi vai trò), không kèm lệnh đóng."""
        out = [
            envelope("family.access_ended", {"grant_id": gid, "reason": reason.value})
            for gid in self._grants
        ]
        self._grants.clear()
        return out

    def expire(self, now: datetime) -> list[Message]:
        out: list[Message] = []
        for g in list(self._grants.values()):
            if g.expires_at is not None and g.expires_at <= now:
                out += self._end(g.grant_id, FamilyAccessEndReason.EXPIRED)
        return out

    # ---- chiếu message của hub ----
    def project(self, message: Message) -> list[Message]:
        type_ = message.get("type")
        p: dict[str, Any] = message.get("payload") or {}
        handler = self._handlers.get(str(type_))
        return handler(self, p) if handler else []

    def _on_event(self, p: dict[str, Any]) -> list[Message]:
        if p.get("priority") == Priority.LOG.value:
            return []
        return [
            envelope(
                "family.event",
                {
                    "grant_id": g.grant_id,
                    "event_id": p.get("id"),
                    "time": p.get("occurred_at"),
                    "code": p.get("code"),
                    "priority": p.get("priority"),
                    "alert_status": p.get("alert_status"),
                },
            )
            for g in self._grants.values()
            if g.session_id == p.get("session_id")
        ]

    def _on_alert(self, p: dict[str, Any]) -> list[Message]:
        session = p.get("session") or {}
        event = p.get("event") or {}
        return self._on_event(
            {
                "id": event.get("id"),
                "session_id": session.get("id"),
                "occurred_at": event.get("occurred_at"),
                "code": event.get("code"),
                "priority": event.get("priority"),
                "alert_status": p.get("status"),
            }
        )

    def _on_bed_state(self, p: dict[str, Any]) -> list[Message]:
        out = []
        for g in self._grants.values():
            if g.bed_id == p.get("bed_id"):
                g.state = {k: p.get(k) for k in STATE_FIELDS}
                out.append(self._state_msg(g))
        return out

    def _on_session(self, p: dict[str, Any]) -> list[Message]:
        out: list[Message] = []
        for g in list(self._grants.values()):
            if g.session_id != p.get("id"):
                continue
            if p.get("ended_at") is not None:  # kết thúc phiên hoặc chuyển giường (F04)
                out += self._end(g.grant_id, FamilyAccessEndReason.SESSION_ENDED)
                continue
            paused = p.get("paused_at") is not None
            if paused != g.capture_paused:
                g.capture_paused = paused
                out.append(self._state_msg(g))
        return out

    def _on_skeleton(self, p: dict[str, Any]) -> list[Message]:
        out = []
        now = self._monotonic()
        for g in self._grants.values():
            if g.share_level is not ShareLevel.SKELETON or g.bed_id != p.get("bed_id"):
                continue
            if g.capture_paused or now - g.last_skeleton_at < self._skeleton_interval:
                continue
            g.last_skeleton_at = now
            out.append(
                envelope(
                    "family.skeleton",
                    {
                        "grant_id": g.grant_id,
                        "keypoints": p.get("keypoints"),
                        "roi_polygon": p.get("roi_polygon"),
                        "ts": p.get("ts"),
                    },
                )
            )
        return out

    def _on_grant_ended(self, p: dict[str, Any]) -> list[Message]:
        gid = p.get("grant_id")
        if not isinstance(gid, int):
            return []
        return self._end(gid, FamilyAccessEndReason(p.get("reason", "REVOKED")))

    _handlers: ClassVar[
        dict[str, Callable[["FamilyProjection", dict[str, Any]], list[Message]]]
    ] = {
        "event.created": _on_event,
        "alert.updated": _on_alert,
        "bed.state": _on_bed_state,
        "session.updated": _on_session,
        BED_SKELETON: _on_skeleton,
        GRANT_ENDED: _on_grant_ended,
    }
