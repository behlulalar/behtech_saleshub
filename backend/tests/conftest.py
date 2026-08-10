"""Shared fixtures for DE-4 tests (local DB isolation)."""

from __future__ import annotations

import pytest

from database import AiAction, SessionLocal, User

_ACTIVE = ("proposed", "approved", "executing")


@pytest.fixture(autouse=True)
def de4_clear_active_actions_before_test(request):
    """Prevent cross-test pollution for operational duplicate guards."""
    nodeid = request.node.nodeid
    if (
        "test_de4_actions" not in nodeid
        and "test_de4_duplicate" not in nodeid
        and "test_de4_action_management" not in nodeid
    ):
        yield
        return

    db = SessionLocal()
    try:
        owners = db.query(User).filter(User.role == "owner").all()
        org_ids = [u.id for u in owners]
        if org_ids:
            db.query(AiAction).filter(
                AiAction.organization_id.in_(org_ids),
                AiAction.status.in_(_ACTIVE),
            ).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()
    yield
