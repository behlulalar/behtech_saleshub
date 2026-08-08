"""Optional AI paragraph for automation emails (Faz 4)."""

from sqlalchemy.orm import Session

from ai.deps import ai_is_configured
from ai.llm_client import chat_completion
from ai.llm_config import provider_and_model
from ai.store import create_run, finish_run_failed, finish_run_success
from config import settings
from intelligence.company_profile import get_org_profile
from intelligence.insights import insight_to_dict, list_active_insights


def build_daily_email_paragraph(db: Session, org_id: int, *, requested_by: int | None = None) -> str | None:
    if not settings.ai_enabled or not settings.ai_daily_email:
        return None
    if not ai_is_configured():
        return None

    profile = get_org_profile(db, org_id, refresh=False)
    insights = list_active_insights(db, org_id, limit=3)
    insight_lines = [f"- {insight_to_dict(i)['title']}" for i in insights]

    facts = [
        f"Dönem: {profile.get('period_label') or '—'}",
        f"Yeni kayıt: {profile.get('yeni_kayit', 0)}",
        f"Yeni müşteri: {profile.get('yeni_musteri', 0)}",
        f"Satış dönüşüm %: {profile.get('satis_donusum_orani', 0)}",
        f"Cevap bekleyen: {profile.get('cevap_bekleyen_sayisi', 0)}",
    ]
    best = profile.get("best_lead_source")
    if isinstance(best, dict) and best.get("label"):
        facts.append(
            f"En iyi kaynak ({best.get('label')}): %{best.get('win_rate_pct')} ({best.get('sample_size')} lead)"
        )

    system = (
        "BehTech Sales Hub satış özeti asistanısın. Yalnızca verilen sayıları kullan; uydurma. "
        "3-4 kısa Türkçe cümle, motive edici ama abartısız."
    )
    user = "Sayılar:\n" + "\n".join(facts) + "\n\nInsight:\n" + ("\n".join(insight_lines) or "—")

    provider, model = provider_and_model()
    run = create_run(
        db,
        org_id=org_id,
        requested_by=requested_by,
        run_type="daily_email_paragraph",
        input_data={"facts": facts},
        provider=provider,
        model=model,
        prompt_version="daily_email_v1",
    )
    try:
        text, usage = chat_completion(system=system, user=user)
        paragraph = (text or "").strip()
        if not paragraph:
            finish_run_failed(db, run, error_code="empty")
            return None
        finish_run_success(
            db,
            run,
            output_data={"chars": len(paragraph)},
            tokens_total=usage.get("total_tokens"),
        )
        return paragraph
    except Exception:
        finish_run_failed(db, run, error_code="llm_error")
        return None
