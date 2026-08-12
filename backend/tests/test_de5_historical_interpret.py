"""DE-5.1-C — historical diagnosis AI interpretation tests (mocked provider)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from config import settings
from database import AiAction, AiRun, DiagnosisCase, DiagnosisSnapshot, SessionLocal, User
from main import app
from migrate_auth import run_migrations
from security import hash_password


URL = "/api/ai/diagnosis/history/interpret"
SYNC_URL = "/api/intelligence/diagnoses/sync"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _valid_json(**overrides) -> str:
    payload = {
        "summary": "Idle takip sorunu kötüleşiyor.",
        "what_changed": "Idle gün sayısı ve etkilenen lead arttı.",
        "why_it_matters": "Takip gecikmesi satış fırsatını zayıflatır.",
        "key_points": ["Severity yükseldi", "Idle 5→12"],
        "confidence": "medium",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _owner_token(db) -> tuple[str, User]:
    user = db.query(User).filter(User.role == "owner").order_by(User.id.asc()).first()
    if not user:
        pytest.skip("No owner")
    token, _ = create_access_token(user.id, user.username, token_version=user.token_version or 0)
    return token, user


def _employee_token(db, owner_id: int) -> tuple[str, User]:
    emp = db.query(User).filter(User.role == "employee", User.owner_id == owner_id).first()
    if not emp:
        pytest.skip("No employee")
    token, _ = create_access_token(emp.id, emp.username, token_version=emp.token_version or 0)
    return token, emp


def _cleanup_org(db, org_id: int) -> None:
    db.query(DiagnosisSnapshot).filter(DiagnosisSnapshot.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.query(DiagnosisCase).filter(DiagnosisCase.organization_id == org_id).delete(
        synchronize_session=False
    )
    db.query(AiRun).filter(AiRun.user_id == org_id, AiRun.run_type == "diagnosis_history_interpret").delete(
        synchronize_session=False
    )
    db.commit()


def _follow_up(*, current_value: float = 7.0, severity: str = "medium", affected: int = 1) -> dict:
    return {
        "diagnosis_id": "follow_up_idle_leads",
        "type": "follow_up",
        "severity": severity,
        "title": "Takip",
        "description": "idle",
        "metric": "days_since_last_contact",
        "current_value": current_value,
        "previous_value": None,
        "change_percent": None,
        "affected_lead_count": affected,
        "evidence": {
            "affected_lead_count": affected,
            "oldest_days_idle": int(current_value),
            "secret_raw": {"x": 1},
        },
        "detected_at": datetime.utcnow().isoformat(),
        "impact": {
            "affected_lead_count": affected,
            "high_priority_count": affected,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        },
        "top_priority_leads": [{"lead_id": 10, "priority": "high", "lead_name": "Secret Co"}],
    }


def _payload(items: list[dict]) -> dict:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "duration_ms": 1,
        "period_type": "monthly",
        "anchor": "2026-08-11",
        "items": items,
    }


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def flags_on():
    prev = {
        "ai": settings.ai_enabled,
        "engine": settings.diagnosis_engine_enabled,
        "hist": settings.ai_diagnosis_history_interpret_enabled,
        "key": settings.openai_api_key,
    }
    settings.ai_enabled = True
    settings.diagnosis_engine_enabled = True
    settings.ai_diagnosis_history_interpret_enabled = True
    if not (settings.openai_api_key or "").strip():
        settings.openai_api_key = "sk-test-de51c-not-real"
    try:
        yield
    finally:
        settings.ai_enabled = prev["ai"]
        settings.diagnosis_engine_enabled = prev["engine"]
        settings.ai_diagnosis_history_interpret_enabled = prev["hist"]
        settings.openai_api_key = prev["key"]


@pytest.fixture
def owner_ctx(flags_on):
    db = SessionLocal()
    run_migrations(db)
    token, user = _owner_token(db)
    _cleanup_org(db, user.id)
    try:
        yield token, user
    finally:
        _cleanup_org(db, user.id)
        db.close()


def _sync(client, token: str, items: list[dict]):
    with patch(
        "intelligence.diagnosis.sync.compute_diagnoses",
        return_value=_payload(items),
    ):
        r = client.post(SYNC_URL, json={"period": "monthly"}, headers=_auth(token))
    assert r.status_code == 200


def _llm_ok(raw: str | None = None):
    text = raw if raw is not None else _valid_json()
    return text, {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}


def _case_snap_state(org_id: int):
    db = SessionLocal()
    try:
        case = (
            db.query(DiagnosisCase)
            .filter(
                DiagnosisCase.organization_id == org_id,
                DiagnosisCase.diagnosis_id == "follow_up_idle_leads",
            )
            .one()
        )
        snaps = (
            db.query(DiagnosisSnapshot)
            .filter(DiagnosisSnapshot.case_id == case.id)
            .order_by(DiagnosisSnapshot.id.asc())
            .all()
        )
        return {
            "state": case.state,
            "severity": case.severity,
            "fingerprint": case.fingerprint,
            "latest_snapshot_id": case.latest_snapshot_id,
            "current_value": case.current_value,
            "affected": case.affected_lead_count,
            "snap_ids": [s.id for s in snaps],
            "snap_fps": [s.fingerprint for s in snaps],
            "snap_count": len(snaps),
        }
    finally:
        db.close()


def test_A_owner_can_interpret(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["diagnosis_id"] == "follow_up_idle_leads"
    assert body["period_key"] == "current"
    assert body["interpretation"]["summary"]
    assert body["cached"] is False
    assert "recommended_actions" not in (body.get("interpretation") or {})


def test_B_employee_forbidden(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up()])
    db = SessionLocal()
    try:
        emp_token, _ = _employee_token(db, user.id)
    finally:
        db.close()
    r = client.post(
        URL,
        headers=_auth(emp_token),
        json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
    )
    assert r.status_code in (401, 403)


def test_C_unauthenticated(client, flags_on):
    r = client.post(URL, json={"diagnosis_id": "follow_up_idle_leads"})
    assert r.status_code == 401


def test_D_org_isolation(client, owner_ctx, flags_on):
    token_a, _ = owner_ctx
    _sync(client, token_a, [_follow_up()])
    db = SessionLocal()
    try:
        other = User(
            username=f"hist_iso_{uuid.uuid4().hex[:8]}",
            email=f"hist_iso_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("testpass123"),
            role="owner",
            email_verified=True,
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        uid_b = other.id
        token_b, _ = create_access_token(other.id, other.username, token_version=0)
        _cleanup_org(db, uid_b)
    finally:
        db.close()

    r = client.post(
        URL,
        headers=_auth(token_b),
        json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
    )
    assert r.status_code == 404

    db = SessionLocal()
    try:
        _cleanup_org(db, uid_b)
        db.query(User).filter(User.id == uid_b).delete()
        db.commit()
    finally:
        db.close()


def test_E_case_not_found(client, owner_ctx):
    token, _ = owner_ctx
    r = client.post(
        URL,
        headers=_auth(token),
        json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
    )
    assert r.status_code == 404


def test_F_period_mismatch(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up()])
    r = client.post(
        URL,
        headers=_auth(token),
        json={"diagnosis_id": "follow_up_idle_leads", "period_key": "not-a-period"},
    )
    assert r.status_code == 422


def test_G_ai_disabled(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up()])
    prev = settings.ai_diagnosis_history_interpret_enabled
    settings.ai_diagnosis_history_interpret_enabled = False
    try:
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
        assert r.status_code == 503
    finally:
        settings.ai_diagnosis_history_interpret_enabled = prev


def test_H_provider_success(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=12, severity="high", affected=3)])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    assert r.json()["trend_direction"] == "worsening"
    assert r.json()["interpretation"]["what_changed"]


def test_I_provider_error(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up()])
    before = _case_snap_state(user.id)
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        side_effect=RuntimeError("boom"),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 502
    assert _case_snap_state(user.id) == before


def test_J_malformed_provider_output(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up()])
    bad = ("not-json{", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        side_effect=[bad, bad],
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["interpretation"] is None
    assert body["error_code"] == "invalid_llm_output"


def test_K_L_M_N_O_context_whitelist(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    captured: dict = {}

    def _capture(**kw):
        captured["user"] = kw.get("user") or ""
        return _llm_ok()

    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        side_effect=_capture,
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    blob = captured["user"]
    assert "organization_id" not in blob
    assert "secret_raw" not in blob
    assert "Secret Co" not in blob
    assert "evidence_json" not in blob
    assert '"case_id"' not in blob
    assert '"latest_snapshot_id"' not in blob
    start = blob.find("{")
    assert start >= 0
    ctx = json.loads(blob[start:])
    dumped = json.dumps(ctx)
    assert "fingerprint" not in dumped
    assert ctx["diagnosis"]["diagnosis_id"] == "follow_up_idle_leads"
    assert "reason_codes" in ctx["trend"]
    for snap in ctx["history"]["substantive_snapshots"]:
        assert "id" not in snap
        assert "fingerprint" not in snap
        assert "evidence" not in snap


def test_P_Q_bridge_not_called_no_action(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up()])
    db = SessionLocal()
    try:
        before_actions = db.query(AiAction).filter(AiAction.organization_id == user.id).count()
    finally:
        db.close()

    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"), patch(
        "ai.actions.proposal_bridge.bridge_recommended_actions_to_proposals"
    ) as bridge:
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    bridge.assert_not_called()
    db = SessionLocal()
    try:
        after_actions = db.query(AiAction).filter(AiAction.organization_id == user.id).count()
    finally:
        db.close()
    assert after_actions == before_actions
    assert "proposal_bridge" not in r.json()


def test_R_S_case_snapshot_unchanged(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    _sync(client, token, [_follow_up(current_value=9)])
    before = _case_snap_state(user.id)
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        assert client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        ).status_code == 200
    assert _case_snap_state(user.id) == before


def test_T_cache_hit(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ) as llm, patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r1 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
        r2 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
    assert r2.json()["run_id"] == r1.json()["run_id"]
    assert llm.call_count == 1


def test_U_new_snapshot_invalidates_cache(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=5)])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ) as llm, patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r1 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
        assert r1.status_code == 200
        _sync(client, token, [_follow_up(current_value=15, severity="high", affected=4)])
        r2 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r2.status_code == 200
    assert r2.json()["cached"] is False
    assert r2.json()["run_id"] != r1.json()["run_id"]
    assert llm.call_count == 2


def test_V_resolve_reopen_new_context(client, owner_ctx):
    token, _ = owner_ctx
    _sync(client, token, [_follow_up(current_value=7)])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ) as llm, patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r1 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
        _sync(client, token, [])  # resolve
        r2 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
        _sync(client, token, [_follow_up(current_value=8)])  # reopen
        r3 = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r1.json()["cached"] is False
    assert r2.json()["trend_direction"] == "resolved"
    assert r2.json()["cached"] is False
    assert r3.json()["trend_direction"] == "reopened"
    assert r3.json()["cached"] is False
    assert llm.call_count == 3


def test_W_run_type(client, owner_ctx):
    token, user = owner_ctx
    _sync(client, token, [_follow_up()])
    with patch(
        "ai.capabilities.diagnosis_history_interpreter.chat_completion_structured",
        return_value=_llm_ok(),
    ), patch("ai.capabilities.diagnosis_history_interpreter.ensure_quota"):
        r = client.post(
            URL,
            headers=_auth(token),
            json={"diagnosis_id": "follow_up_idle_leads", "period_key": "current"},
        )
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    db = SessionLocal()
    try:
        run = db.query(AiRun).filter(AiRun.id == run_id).one()
        assert run.run_type == "diagnosis_history_interpret"
        assert run.user_id == user.id
        inp = json.loads(run.input_json or "{}")
        assert inp["period_key"] == "current"
        assert "trend_fingerprint" in inp
        assert "latest_snapshot_id" in inp
    finally:
        db.close()


def test_status_flag(client, owner_ctx):
    token, _ = owner_ctx
    r = client.get("/api/ai/status", headers=_auth(token))
    assert r.status_code == 200
    assert "diagnosis_history_interpret_available" in r.json()
