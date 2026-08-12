from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

DEFAULT_CATEGORIES = [
    {"id": "dovme", "label": "Dövme Salonları", "icon": "pen-tool"},
    {"id": "guzellik", "label": "Güzellik Salonları", "icon": "sparkles"},
    {"id": "berber", "label": "Berberler", "icon": "scissors"},
]

DEFAULT_TAGS = [
    {"id": "vip", "label": "VIP", "color": "amber"},
    {"id": "sicak-musteri", "label": "Sıcak Müşteri", "color": "orange"},
    {"id": "soguk", "label": "Soğuk", "color": "blue"},
    {"id": "kararsiz", "label": "Kararsız", "color": "purple"},
    {"id": "rakip-kullaniyor", "label": "Rakip Kullanıyor", "color": "slate"},
]

INDIVIDUAL_DEFAULT_CATEGORIES = [
    {"id": "genel", "label": "Müşterilerim", "icon": "users"},
]

ACCOUNT_TYPE_INDIVIDUAL = "individual"
ACCOUNT_TYPE_COMPANY = "company"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="owner", nullable=False, index=True)
    account_type = Column(String(20), default="company", nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    company_name = Column(String(255), nullable=True)
    display_name = Column(String(255), default="")
    email_verified = Column(Boolean, default=False, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CategoryModel(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "id", name="uq_user_category"),)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id = Column(String(50), primary_key=True)
    label = Column(String(255), nullable=False)
    icon = Column(String(50), default="building-2")
    created_at = Column(DateTime, default=datetime.utcnow)


class TagModel(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "id", name="uq_user_tag"),)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id = Column(String(50), primary_key=True)
    label = Column(String(255), nullable=False)
    color = Column(String(20), default="slate")
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadTag(Base):
    __tablename__ = "lead_tags"
    __table_args__ = (UniqueConstraint("lead_id", "tag_id", name="uq_lead_tag"),)

    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String(50), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


class LeadImportBatch(Base):
    __tablename__ = "lead_import_batches"
    __table_args__ = (Index("ix_lead_import_batches_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    filename = Column(String(255), default="")
    created_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    skipped_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_user_category", "user_id", "category"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    import_batch_id = Column(
        Integer,
        ForeignKey("lead_import_batches.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    isletme_adi = Column(String(255), nullable=False)
    yetkili = Column(String(255), default="")
    sehir = Column(String(100), default="")
    instagram = Column(String(255), default="")
    whatsapp = Column(String(50), default="")
    eposta = Column(String(255), default="")
    ilk_iletisim_kanali = Column(String(100), default="")
    ilk_mesaj_tarihi = Column(String(20), default="")
    ilk_mesaj_saati = Column(String(10), default="")
    durum = Column(String(100), default="Yeni")
    oncelik = Column(String(20), default="orta", index=True)
    takip_1 = Column(String(255), default="")
    takip_2 = Column(String(255), default="")
    demo_gonderildi = Column(Boolean, default=False)
    demo_tarihi = Column(String(20), default="")
    gorusme_tarihi = Column(String(20), default="")
    gorusme_saati = Column(String(10), default="")
    teklif = Column(String(255), default="")
    sonuc = Column(String(255), default="")
    satis_tutari = Column(Numeric(12, 2), default=0)
    satis_tarihi = Column(String(20), default="")
    notlar = Column(Text, default="")

    intelligence_score = Column(Integer, nullable=True)
    intelligence_updated_at = Column(DateTime, nullable=True)

    google_place_id = Column(String(255), nullable=True, index=True)
    source = Column(String(50), default="manual", nullable=False)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    google_rating = Column(Numeric(3, 2), nullable=True)
    google_rating_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"
    __table_args__ = (UniqueConstraint("user_id", "month", "sku_type", name="uq_api_usage_user_month_sku"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    sku_type = Column(String(80), nullable=False, default="text_search_enterprise_atmosphere")
    query_count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LeadDiscoveryScan(Base):
    __tablename__ = "lead_discovery_scans"
    __table_args__ = (Index("ix_lead_discovery_scans_user_region", "user_id", "region_key"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    region_key = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), default="")
    sector_keyword = Column(String(100), nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    activity_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadAttachment(Base):
    __tablename__ = "lead_attachments"
    __table_args__ = (Index("ix_lead_attachments_user_lead", "user_id", "lead_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    label = Column(String(255), default="")
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(64), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    version_number = Column(Integer, nullable=False, default=1)
    replaces_attachment_id = Column(
        Integer, ForeignKey("lead_attachments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    archived_at = Column(DateTime, nullable=True, index=True)
    archived_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadRequest(Base):
    __tablename__ = "lead_requests"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)

    isletme_adi = Column(String(255), nullable=False)
    yetkili = Column(String(255), default="")
    sehir = Column(String(100), default="")
    instagram = Column(String(255), default="")
    whatsapp = Column(String(50), default="")
    eposta = Column(String(255), default="")
    ilk_iletisim_kanali = Column(String(100), default="")
    ilk_mesaj_tarihi = Column(String(20), default="")
    ilk_mesaj_saati = Column(String(10), default="")
    durum = Column(String(100), default="Yeni")
    oncelik = Column(String(20), default="orta")
    takip_1 = Column(String(255), default="")
    takip_2 = Column(String(255), default="")
    demo_gonderildi = Column(Boolean, default=False)
    demo_tarihi = Column(String(20), default="")
    gorusme_tarihi = Column(String(20), default="")
    gorusme_saati = Column(String(10), default="")
    teklif = Column(String(255), default="")
    sonuc = Column(String(255), default="")
    notlar = Column(Text, default="")
    tag_ids_json = Column(Text, default="[]")

    rejection_note = Column(String(500), default="")
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (Index("ix_ai_runs_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    run_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")
    input_json = Column(Text, nullable=False, default="{}")
    output_json = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    provider = Column(String(40), nullable=True)
    model = Column(String(80), nullable=True)
    prompt_version = Column(String(120), nullable=True)
    steps_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BusinessEvent(Base):
    __tablename__ = "business_events"
    __table_args__ = (Index("ix_business_events_user_occurred", "user_id", "occurred_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    payload_json = Column(Text, nullable=False, default="{}")
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OrgIntelligenceProfile(Base):
    __tablename__ = "org_intelligence_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile_json = Column(Text, nullable=False, default="{}")
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    version = Column(String(20), nullable=False, default="v1")


class AiUsageMonthly(Base):
    __tablename__ = "ai_usage_monthly"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_ai_usage_user_month"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    tokens_total = Column(Integer, nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntelligenceInsight(Base):
    __tablename__ = "intelligence_insights"
    __table_args__ = (Index("ix_intelligence_insights_user_entity", "user_id", "entity_type", "entity_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="medium")
    entity_type = Column(String(20), nullable=False, default="lead")
    entity_id = Column(Integer, nullable=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False, default="")
    evidence_json = Column(Text, nullable=False, default="{}")
    source = Column(String(20), nullable=False, default="deterministic")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class IntelligenceRecommendation(Base):
    __tablename__ = "intelligence_recommendations"
    __table_args__ = (Index("ix_intelligence_rec_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False, default="medium")
    score = Column(Integer, nullable=False, default=0)
    reasons_json = Column(Text, nullable=False, default="[]")
    insight_ids_json = Column(Text, nullable=False, default="[]")
    ai_run_id = Column(Integer, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)
    user_action = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActionProposal(Base):
    """Faz 2 schema only — onay UI Faz 3."""

    __tablename__ = "action_proposals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    proposed_action = Column(String(80), nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AiAction(Base):
    """DE-4 persisted action proposals (PROPOSE only — execution in Stage 4.2)."""

    __tablename__ = "ai_actions"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_ai_actions_org_idempotency"),
        Index("ix_ai_actions_org_status", "organization_id", "status"),
        Index("ix_ai_actions_org_created", "organization_id", "created_at"),
        Index("ix_ai_actions_source_diagnosis", "organization_id", "source_diagnosis_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(String(36), nullable=False, unique=True, index=True)
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(80), nullable=False, index=True)
    target_entity = Column(String(40), nullable=False, default="lead")
    target_entity_id = Column(Integer, nullable=True, index=True)
    parameters_json = Column(Text, nullable=False, default="{}")
    reason = Column(String(600), nullable=False, default="")
    source_diagnosis_id = Column(String(80), nullable=True)
    source_interpret_run_id = Column(Integer, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    status = Column(String(20), nullable=False, default="proposed")
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    execution_result_json = Column(Text, nullable=True)


class DiagnosisCase(Base):
    """DE-5.0 — org-scoped current diagnosis identity + lifecycle state."""

    __tablename__ = "diagnosis_cases"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "diagnosis_id",
            "period_key",
            name="uq_diagnosis_cases_org_diagnosis_period",
        ),
        Index("ix_diagnosis_cases_org_state", "organization_id", "state"),
        Index("ix_diagnosis_cases_org_last_seen", "organization_id", "last_seen_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnosis_id = Column(String(80), nullable=False)
    diagnosis_type = Column(String(40), nullable=False)
    period_key = Column(String(20), nullable=False)
    state = Column(String(20), nullable=False, default="new")
    severity = Column(String(20), nullable=False, default="medium")
    title = Column(String(255), nullable=False, default="")
    metric = Column(String(80), nullable=False, default="")
    current_value = Column(Float, nullable=True)
    engine_previous_value = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    affected_lead_count = Column(Integer, nullable=False, default=0)
    fingerprint = Column(String(64), nullable=False, default="")
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    # Pointer only — no FK (avoids circular create with diagnosis_snapshots).
    latest_snapshot_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DiagnosisSnapshot(Base):
    """DE-5.0 — append-only diagnosis observation history."""

    __tablename__ = "diagnosis_snapshots"
    __table_args__ = (
        Index("ix_diagnosis_snapshots_case_observed", "case_id", "observed_at"),
        Index("ix_diagnosis_snapshots_org_observed", "organization_id", "observed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(
        Integer,
        ForeignKey("diagnosis_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_id = Column(String(80), nullable=False)
    period_key = Column(String(20), nullable=False)
    anchor = Column(String(32), nullable=False, default="")
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    state = Column(String(20), nullable=False, default="new")
    severity = Column(String(20), nullable=False, default="medium")
    metric = Column(String(80), nullable=False, default="")
    current_value = Column(Float, nullable=True)
    engine_previous_value = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    affected_lead_count = Column(Integer, nullable=False, default=0)
    impact_json = Column(Text, nullable=False, default="{}")
    top_leads_json = Column(Text, nullable=False, default="[]")
    evidence_json = Column(Text, nullable=False, default="{}")
    fingerprint = Column(String(64), nullable=False, default="")
    trigger = Column(String(40), nullable=False, default="sync")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AssistantConversation(Base):
    """DE-6 — org-scoped Sales Assistant conversation (soft-archive)."""

    __tablename__ = "assistant_conversations"
    __table_args__ = (
        Index("ix_assistant_conversations_org_updated", "organization_id", "updated_at"),
        Index("ix_assistant_conversations_org_user", "organization_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    # DE-6.7 — minimal active conversational entity pointer (JSON); never full CRM dump.
    active_entity_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    archived_at = Column(DateTime, nullable=True)


class AssistantMessage(Base):
    """DE-6 — append-only Sales Assistant messages."""

    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("ix_assistant_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_assistant_messages_org_created", "organization_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    run_id = Column(Integer, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    from migrate_auth import run_migrations, seed_admin_user

    db = SessionLocal()
    try:
        run_migrations(db)
        seed_admin_user(db)
        run_migrations(db)
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
