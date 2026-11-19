"""File-demo EOF must flush actual events and distinguish retry failure from completion."""

import pytest

from postcare.worker.loop import WorkerStopError
from tests.worker.helpers import make_harness


def test_stop_at_end_flushes_last_frame_event():
    h = make_harness(script=lambda: [0, 100, 200], engine_kwargs={"events_at": {2}})
    h.api.event_statuses = [500, 201]
    h.worker.run(stop_at_end=True)
    assert h.worker.pending_events == 0
    assert len(h.api.paths("/events")) == 2
    assert h.time.t < 110


def test_stop_at_end_does_not_claim_success_when_events_cannot_be_delivered():
    h = make_harness(script=lambda: [0], engine_kwargs={"events_at": {0}})
    h.api.event_statuses = [500] * 100
    with pytest.raises(WorkerStopError, match="Không gửi hết"):
        h.worker.run(stop_at_end=True)
    assert h.worker.pending_events == 1
    assert h.time.t < 140
