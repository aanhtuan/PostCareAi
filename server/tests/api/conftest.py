"""Fixture cho test API của F36 (người nhà)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.family_utils import FakeClock, add_family_user


@pytest.fixture
def clock(app: Any) -> FakeClock:
    c = FakeClock()
    app.state.clock = c
    return c


@pytest.fixture
def fam(client: TestClient, db: Session) -> int:
    return add_family_user(db, "family")


@pytest.fixture
def fam2(client: TestClient, db: Session) -> int:
    return add_family_user(db, "family2")
