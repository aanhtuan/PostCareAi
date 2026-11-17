"""Bước 6–9: rule sự kiện, vận động, khuôn mặt, debounce (event-engine.md mục 3).

`RuleSet` ghép các rule (`rules/body.py` F15, `rules/movement.py` F23, `rules/observation.py` F17;
F26, F27 thêm sau) rồi lọc
bằng một `Debouncer` chung (`engine/debounce.py`). Mức ưu tiên lấy từ catalog
`postcare/schemas/events.py`.
"""

from collections.abc import Sequence

from postcare.engine.activity import ActivityReading
from postcare.engine.debounce import Debouncer
from postcare.engine.pipeline import FrameAssessment
from postcare.engine.rules.body import BodyRules
from postcare.engine.rules.movement import MovementRules
from postcare.engine.rules.observation import ObservationRules
from postcare.engine.state_machine import StateRecord
from postcare.schemas.engine_config import EngineConfig
from postcare.schemas.events import EngineEvent, EventCode, default_priority
from postcare.schemas.state import BodyState

__all__ = ["RuleSet"]


class RuleSet:
    """Một instance cho một `Engine`: phạm vi debounce = vòng đời engine (F15 R8)."""

    def __init__(self, config: EngineConfig, config_hash: str) -> None:
        self._config_hash = config_hash
        self._body = BodyRules(config)
        self._movement = MovementRules(config)
        self._observation = ObservationRules(config)
        self._debouncer = Debouncer(config.debounce.same_code_same_session_s)

    def evaluate(
        self,
        ts_ms: int,
        assessment: FrameAssessment,
        body_state: BodyState,
        history: Sequence[StateRecord],
        activity: ActivityReading,
    ) -> list[EngineEvent]:
        events: list[EngineEvent] = []
        drafts = self._body.evaluate(ts_ms, assessment, body_state, history)
        drafts.extend(self._movement.evaluate(ts_ms, assessment, activity))
        drafts.extend(self._observation.evaluate(ts_ms, assessment, body_state))
        for draft in drafts:
            if not self._debouncer.allow(draft.code.value, draft.detected_at_ms):
                continue
            if draft.code == EventCode.OBSERVATION_LOST:
                # RESTORED chỉ phát khi LOST của chuỗi này thực sự được phát (F17 R16).
                self._observation.confirm_lost()
            events.append(
                EngineEvent(
                    code=draft.code,
                    priority=default_priority(draft.code),
                    occurred_at_ms=draft.occurred_at_ms,
                    detected_at_ms=draft.detected_at_ms,
                    confidence=draft.confidence,
                    observation_quality=draft.observation_quality,
                    explanation=draft.explanation,
                    config_hash=self._config_hash,
                )
            )
        return events
