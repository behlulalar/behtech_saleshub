"""DE-4 duplicate proposal / recommendation hardening tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from ai.actions.proposal_bridge import bridge_recommended_actions_to_proposals
from ai.actions.propose_service import propose_ai_action
from ai.actions.recommendation_dedup import dedupe_recommended_actions_by_operation
from ai.actions.mapper import MapperContext
from ai.store import create_run, finish_run_success
from auth import create_access_token
from config import settings
from database import AiAction, Lead, SessionLocal, User
from main import app
from schemas import DiagnosisRecommendedAction
from tests.test_de4_actions_stage44 import (
    _bridge,
    _cleanup_actions_and_run,
    _create_interpret_run,
    _recs,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def ai_on():
    prev = settings.ai_enabled
    settings.ai_enabled = True
    try:
        yield
    finally:
        settings.ai_enabled = prev


@pytest.fixture
def bridge_on():
    prev = settings.ai_de4_interpret_proposal_bridge_enabled
    settings.ai_de4_interpret_proposal_bridge_enabled = True
    try:
        yield
    finally:
        settings.ai_de4_interpret_proposal_bridge_enabled = prev


def _owner_lead():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "owner").first()
        if not user:
            pytest.skip("No owner")
        lead = db.query(Lead).filter(Lead.user_id == user.id).first()
        if not lead:
            pytest.skip("No lead")
        return db, user, lead
    except Exception:
        db.close()
        raise


def test_two_follow_up_recommendations_one_proposal(bridge_on):
    db, user, lead = _owner_lead()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [
            DiagnosisRecommendedAction(title="Togi için takip yap", reason="Idle müşteri takip", priority="high"),
            DiagnosisRecommendedAction(
                title="Togi ile iletişime geç",
                reason="Bekleyen takip planı oluştur",
                priority="medium",
            ),
        ]
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.proposed_count == 1
        assert len(summary.action_ids) == 1
        assert (
            db.query(AiAction)
            .filter(
                AiAction.organization_id == user.id,
                AiAction.action_type == "propose_follow_up_task",
                AiAction.target_entity_id == lead.id,
                AiAction.status.in_(("proposed", "approved", "executing")),
            )
            .count()
            == 1
        )
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_same_lead_different_action_types_two_proposals(bridge_on):
    db, user, lead = _owner_lead()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(
            ("Takip yap", "Müşteri idle takip"),
            ("Öncelik yükselt", "Yüksek öncelik ver"),
        )
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        types = {
            db.query(AiAction).filter(AiAction.action_id == aid).first().action_type
            for aid in summary.action_ids
        }
        assert "propose_follow_up_task" in types
        assert "propose_priority_change" in types
        assert summary.proposed_count == 2
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_different_leads_same_action_type_two_proposals(bridge_on):
    db, user, lead = _owner_lead()
    try:
        lead2 = (
            db.query(Lead)
            .filter(Lead.user_id == user.id, Lead.id != lead.id)
            .first()
        )
        if not lead2:
            pytest.skip("Need second lead")
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [DiagnosisRecommendedAction(title="Takip", reason="t1", priority="low")]
        s1 = _bridge(db, user, user.id, lead.id, run_id, recs)
        s2 = _bridge(db, user, user.id, lead2.id, run_id, recs)
        db.commit()
        assert s1.action_ids != s2.action_ids
        assert len({*s1.action_ids, *s2.action_ids}) == 2
        _cleanup_actions_and_run(db, run_id, [*s1.action_ids, *s2.action_ids])
    finally:
        db.close()


def test_duplicate_in_same_run_list_deduped(bridge_on):
    db, user, lead = _owner_lead()
    try:
        run_id = _create_interpret_run(db, user.id, user.id)
        recs = [
            DiagnosisRecommendedAction(title="Not ekle", reason="Aynı not bir", priority="low"),
            DiagnosisRecommendedAction(title="Müşteri notu", reason="Not ekle ikinci satır", priority="low"),
        ]
        ctx = MapperContext(lead_id=lead.id, diagnosis_id="follow_up_idle_leads")
        deduped, skipped = dedupe_recommended_actions_by_operation(recs, ctx)
        assert skipped == 1
        assert len(deduped) == 1
        summary = bridge_recommended_actions_to_proposals(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            diagnosis_id="follow_up_idle_leads",
            interpret_run_id=run_id,
            recommended_actions=recs,
            primary_lead_id=lead.id,
        )
        db.commit()
        assert summary.proposed_count == 1
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
    finally:
        db.close()


def test_cross_run_reuses_active_proposal(bridge_on):
    db, user, lead = _owner_lead()
    try:
        run1 = _create_interpret_run(db, user.id, user.id)
        run2 = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Takip yap", "Cross run takip"))
        s1 = _bridge(db, user, user.id, lead.id, run1, recs)
        s2 = _bridge(db, user, user.id, lead.id, run2, recs)
        db.commit()
        assert s1.action_ids == s2.action_ids
        _cleanup_actions_and_run(db, run1, s1.action_ids)
        _cleanup_actions_and_run(db, run2, [])
    finally:
        db.close()


def test_after_executed_allows_new_proposal(bridge_on):
    db, user, lead = _owner_lead()
    try:
        row, _ = propose_ai_action(
            db,
            user_id=user.id,
            org_id=user.id,
            role="owner",
            action_type="propose_note_append",
            target_entity="lead",
            target_entity_id=lead.id,
            parameters={"lead_id": lead.id, "note_text": "done"},
            reason="first",
            idempotency_key=f"dedup-exec-{uuid.uuid4().hex[:12]}",
        )
        row.status = "executed"
        db.commit()

        run_id = _create_interpret_run(db, user.id, user.id)
        recs = _recs(("Not ekle", "Yeni operasyonel ihtiyaç"))
        summary = _bridge(db, user, user.id, lead.id, run_id, recs)
        db.commit()
        assert summary.created_count == 1
        assert summary.action_ids[0] != row.action_id
        _cleanup_actions_and_run(db, run_id, summary.action_ids)
        db.query(AiAction).filter(AiAction.action_id == row.action_id).delete()
        db.commit()
    finally:
        db.close()


def test_cross_org_isolation(bridge_on):
    db = SessionLocal()
    try:
        owners = db.query(User).filter(User.role == "owner").limit(2).all()
        if len(owners) < 2:
            pytest.skip("Need two owners")
        u1, u2 = owners[0], owners[1]
        l1 = db.query(Lead).filter(Lead.user_id == u1.id).first()
        l2 = db.query(Lead).filter(Lead.user_id == u2.id).first()
        if not l1 or not l2:
            pytest.skip("Need leads per org")
        run_id = _create_interpret_run(db, u1.id, u1.id)
        recs = _recs(("Takip yap", "org1"))
        s1 = _bridge(db, u1, u1.id, l1.id, run_id, recs)
        s2 = _bridge(db, u2, u2.id, l2.id, run_id, recs)
        db.commit()
        assert s1.action_ids != s2.action_ids
        _cleanup_actions_and_run(db, run_id, s1.action_ids)
        db.query(AiAction).filter(AiAction.action_id.in_(s2.action_ids)).delete()
        db.commit()
    finally:
        db.close()
