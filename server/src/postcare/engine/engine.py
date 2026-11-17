"""Lớp `Engine`: ghép các bước pipeline. `Engine.process(obs)` là API duy nhất cho worker/replay.

Engine thuần và xác định: cùng chuỗi `FrameObservation` + cùng cấu hình → cùng output. Thời gian
chỉ lấy từ `obs.ts_ms` (AGENTS.md quy tắc 5; event-engine.md mục 1).
"""

from postcare.engine.features import FeatureExtractor
from postcare.engine.pipeline import FrameAssessment, RuleSet
from postcare.engine.quality import QualityGate, assess_quality
from postcare.engine.state_machine import BodyStateMachine as StateMachine
from postcare.engine.state_machine import Explanation, StateRecord
from postcare.engine.target import TargetSelector
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
        self._features = FeatureExtractor(config, context.roi_polygon)
        self._gate = QualityGate(config)
        self._state_machine = StateMachine(config)
        self._rules = RuleSet(config)
        self._last_ts_ms: int | None = None
        self._last_snapshot: BodyStateSnapshot | None = None
        self._body_state = BodyState.NO_OBSERVATION

    @property
    def state_history(self) -> tuple[StateRecord, ...]:
        """Các trạng thái ổn định gần nhất (cũ → mới) kèm explanation, cho F15 (F14 R11)."""
        return self._state_machine.history

    @property
    def state(self) -> BodyStateSnapshot:
        """Trạng thái hiện tại; trước frame đầu tiên là trạng thái khởi tạo `NO_OBSERVATION`."""
        if self._last_snapshot is not None:
            return self._last_snapshot
        return _snapshot(self._body_state, ObservationQuality.NO_PERSON)

    def process(self, obs: FrameObservation) -> EngineOutput:
        """Xử lý một khung hình. `ts_ms` phải tăng ngặt; sai camera → `ValueError`."""
        self._check_input(obs)
        assessment = self._assess(obs)
        if not assessment.observable:
            # Cổng chất lượng đóng: luôn NO_OBSERVATION, không bao giờ OUT_OF_BED (F14 R8).
            self._state_machine.lose_observation(assessment.quality, obs.ts_ms)
            body_state = BodyState.NO_OBSERVATION
        elif assessment.features is None:
            # Frame kém nhưng chưa đủ lâu: giữ trạng thái, không phân loại từ frame xấu (F13 R7).
            body_state = self._state_machine.interrupt(obs.ts_ms)
        else:
            body_state = self._state_machine.update(assessment, obs.ts_ms)
        self._body_state = body_state
        snapshot = _snapshot(body_state, assessment.quality, self._state_machine.explanation)
        events = self._rules.evaluate(obs, assessment, self._last_snapshot, snapshot)
        # Output đầu tiên luôn là "đổi" để worker gửi trạng thái ban đầu (giả định F10).
        changed = snapshot != self._last_snapshot
        self._last_ts_ms = obs.ts_ms
        self._last_snapshot = snapshot
        return EngineOutput(state=snapshot, state_changed=changed, events=events)

    def _assess(self, obs: FrameObservation) -> FrameAssessment:
        """Bước 1–3: mục tiêu, chất lượng frame, cổng chất lượng, đặc trưng đã làm mượt (F13)."""
        selection = self._target.select(obs)
        quality = assess_quality(obs, selection, self.config)
        was_observable = self._gate.observable
        observable = self._gate.update(quality, obs.ts_ms)
        if not observable and selection.target is None:
            # Đã ở NO_OBSERVATION và không còn bám được ai: lần sau phải nhận mục tiêu từ ROI.
            self._target.forget()
        # Reset làm mượt khi đổi mục tiêu hoặc khi thoát NO_OBSERVATION (giả định R4).
        if selection.is_new or (observable and not was_observable):
            self._features.reset()
        features = None
        if quality == ObservationQuality.GOOD and selection.target is not None:
            features = self._features.update(selection.target, obs)
        return FrameAssessment(
            quality=quality,
            target=selection.target,
            features=features,
            observable=observable,
            persons_in_roi=selection.persons_in_roi,
        )

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


def _snapshot(
    body_state: BodyState, quality: ObservationQuality, explanation: Explanation | None = None
) -> BodyStateSnapshot:
    # Vận động, nghỉ, khuôn mặt chưa suy ra (F23, F26, F27): luôn UNKNOWN / NOT_VISIBLE,
    # không bao giờ mặc định là "bình thường" (HS §9.1).
    return BodyStateSnapshot(
        body_state=body_state,
        observation_quality=quality,
        activity_level=ActivityLevel.UNKNOWN,
        rest_status=RestStatus.UNKNOWN,
        face_status=FaceStatus.NOT_VISIBLE,
        face_signals=FaceSignals(),
        explanation=explanation,
    )
