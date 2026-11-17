"""Lớp `Engine`: ghép các bước pipeline. `Engine.process(obs)` là API duy nhất cho worker/replay.

Engine thuần và xác định: cùng chuỗi `FrameObservation` + cùng cấu hình → cùng output. Thời gian
chỉ lấy từ `obs.ts_ms` (AGENTS.md quy tắc 5; event-engine.md mục 1).
"""

from postcare.engine.pipeline import (
    FrameAssessment,
    QualityAssessor,
    RuleSet,
    StateMachine,
    TargetSelector,
)
from postcare.schemas.context import EngineContext
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineOutput
from postcare.schemas.observation import FrameObservation
from postcare.schemas.state import (
    ActivityLevel,
    BodyState,
    BodyStateSnapshot,
    FaceSignals,
    FaceStatus,
    ObservationQuality,
    RestStatus,
)


class Engine:
    """Một instance = một phiên theo dõi trên một camera (event-engine.md mục 2)."""

    def __init__(self, config: EngineConfig, context: EngineContext) -> None:
        self.config = config
        self.context = context
        self.config_hash = config.config_hash()
        self._target = TargetSelector(config, context)
        self._quality = QualityAssessor(config)
        self._state_machine = StateMachine(config)
        self._rules = RuleSet(config)
        self._last_ts_ms: int | None = None
        self._last_snapshot: BodyStateSnapshot | None = None

    @property
    def state(self) -> BodyStateSnapshot:
        """Trạng thái hiện tại; trước frame đầu tiên là trạng thái khởi tạo `NO_OBSERVATION`."""
        if self._last_snapshot is not None:
            return self._last_snapshot
        return _snapshot(self._state_machine.state, ObservationQuality.NO_PERSON)

    def process(self, obs: FrameObservation) -> EngineOutput:
        """Xử lý một khung hình. `ts_ms` phải tăng ngặt; sai camera → `ValueError`."""
        self._check_input(obs)
        target = self._target.select(obs)
        assessment = FrameAssessment(self._quality.assess(obs, target), target)
        body_state = self._state_machine.update(assessment, obs.ts_ms)
        snapshot = _snapshot(body_state, assessment.quality)
        events = self._rules.evaluate(obs, assessment, self._last_snapshot, snapshot)
        # Output đầu tiên luôn là "đổi" để worker gửi trạng thái ban đầu (giả định F10).
        changed = snapshot != self._last_snapshot
        self._last_ts_ms = obs.ts_ms
        self._last_snapshot = snapshot
        return EngineOutput(state=snapshot, state_changed=changed, events=events)

    def _check_input(self, obs: FrameObservation) -> None:
        if obs.camera_id != self.context.camera_id:
            raise ValueError(
                f"camera_id {obs.camera_id} khác camera_id của engine {self.context.camera_id}"
            )
        if self._last_ts_ms is not None and obs.ts_ms <= self._last_ts_ms:
            raise ValueError(
                f"ts_ms phải tăng ngặt: nhận {obs.ts_ms} sau {self._last_ts_ms} "
                f"(frame_index {obs.frame_index})"
            )


def _snapshot(body_state: BodyState, quality: ObservationQuality) -> BodyStateSnapshot:
    # Vận động, nghỉ, khuôn mặt chưa suy ra (F23, F26, F27): luôn UNKNOWN / NOT_VISIBLE,
    # không bao giờ mặc định là "bình thường" (HS §9.1).
    return BodyStateSnapshot(
        body_state=body_state,
        observation_quality=quality,
        activity_level=ActivityLevel.UNKNOWN,
        rest_status=RestStatus.UNKNOWN,
        face_status=FaceStatus.NOT_VISIBLE,
        face_signals=FaceSignals(),
    )
