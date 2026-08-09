"""
Veritabanı migrasyonu ve admin kullanıcı seed işlemleri.
"""

from datetime import datetime, timedelta

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from config import settings
from database import DEFAULT_CATEGORIES, INDIVIDUAL_DEFAULT_CATEGORIES, CategoryModel, Lead, User
from database import ACCOUNT_TYPE_COMPANY, ACCOUNT_TYPE_INDIVIDUAL
from security import hash_password
from tags import seed_default_tags


def grandfather_legacy_users(db: Session) -> None:
    """Doğrulama öncesi oluşturulan hesapları otomatik doğrula (aktif token yoksa)."""
    inspector = inspect(db.bind)
    if "email_verification_tokens" not in inspector.get_table_names():
        return

    db.execute(
        text(
            """
            UPDATE users
            SET email_verified = TRUE
            WHERE email_verified = FALSE
              AND id NOT IN (
                SELECT user_id FROM email_verification_tokens
                WHERE used_at IS NULL AND expires_at > :now
              )
            """
        ),
        {"now": datetime.utcnow()},
    )
    db.commit()


def run_migrations(db: Session) -> None:
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()

    if "users" not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "role" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'owner'"))
        db.execute(text("UPDATE users SET role = 'owner' WHERE role IS NULL OR role = ''"))
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "owner_id" not in cols:
        db.execute(
            text(
                "ALTER TABLE users ADD COLUMN owner_id INTEGER "
                "REFERENCES users(id) ON DELETE CASCADE"
            )
        )
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "account_type" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN account_type VARCHAR(20) DEFAULT 'company'"))
        db.execute(
            text(
                "UPDATE users SET account_type = 'company' "
                "WHERE account_type IS NULL OR account_type = ''"
            )
        )
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "company_name" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN company_name VARCHAR(255)"))
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "display_name" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR(255) DEFAULT ''"))
        db.execute(text("UPDATE users SET display_name = '' WHERE display_name IS NULL"))
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "email_verified" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE"))
        db.execute(text("UPDATE users SET email_verified = TRUE"))
        db.commit()
        inspector = inspect(db.bind)

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "token_version" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL"))
        db.commit()
        inspector = inspect(db.bind)

    tables = inspector.get_table_names()
    if "email_verification_tokens" not in tables:
        from database import EmailVerificationToken

        EmailVerificationToken.__table__.create(db.bind)
        db.commit()
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()

    if "refresh_sessions" not in tables:
        from database import RefreshSession

        RefreshSession.__table__.create(db.bind)
        db.commit()

    grandfather_legacy_users(db)

    if "categories" in tables:
        cols = {c["name"] for c in inspector.get_columns("categories")}
        if "user_id" not in cols:
            db.execute(text("ALTER TABLE categories ADD COLUMN user_id INTEGER"))
            db.commit()

        admin = db.query(User).filter(User.username == settings.seed_admin_username).first()
        if admin:
            db.execute(
                text("UPDATE categories SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": admin.id},
            )
            db.commit()

            pk = inspector.get_pk_constraint("categories")
            if pk and pk.get("constrained_columns") == ["id"]:
                db.execute(text("ALTER TABLE categories DROP CONSTRAINT categories_pkey"))
                db.execute(text("ALTER TABLE categories ALTER COLUMN user_id SET NOT NULL"))
                db.execute(text("ALTER TABLE categories ADD PRIMARY KEY (user_id, id)"))
                db.commit()

    if "leads" in tables:
        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "user_id" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN user_id INTEGER"))
            db.commit()

        admin = db.query(User).filter(User.username == settings.seed_admin_username).first()
        if admin:
            db.execute(
                text("UPDATE leads SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": admin.id},
            )
            db.execute(text("ALTER TABLE leads ALTER COLUMN user_id SET NOT NULL"))
            db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "gorusme_saati" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN gorusme_saati VARCHAR(10) DEFAULT ''"))
            db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "oncelik" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN oncelik VARCHAR(20) DEFAULT 'orta'"))
            db.execute(text("UPDATE leads SET oncelik = 'orta' WHERE oncelik IS NULL OR oncelik = ''"))
            db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "satis_tutari" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN satis_tutari NUMERIC(12, 2) DEFAULT 0"))
            db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "satis_tarihi" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN satis_tarihi VARCHAR(20) DEFAULT ''"))
            db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "eposta" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN eposta VARCHAR(255) DEFAULT ''"))
            db.commit()

        db.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_user_category ON leads (user_id, category)"))
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "lead_import_batches" not in tables:
        from database import LeadImportBatch

        LeadImportBatch.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    if "leads" in tables:
        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "import_batch_id" not in cols:
            db.execute(
                text(
                    "ALTER TABLE leads ADD COLUMN import_batch_id INTEGER "
                    "REFERENCES lead_import_batches(id) ON DELETE CASCADE"
                )
            )
            db.execute(
                text("CREATE INDEX IF NOT EXISTS ix_leads_import_batch_id ON leads (import_batch_id)")
            )
            db.commit()

        db.execute(
            text(
                """
                UPDATE leads SET
                  yetkili = COALESCE(yetkili, ''),
                  sehir = COALESCE(sehir, ''),
                  instagram = COALESCE(instagram, ''),
                  whatsapp = COALESCE(whatsapp, ''),
                  eposta = COALESCE(eposta, ''),
                  ilk_iletisim_kanali = COALESCE(ilk_iletisim_kanali, ''),
                  ilk_mesaj_tarihi = COALESCE(ilk_mesaj_tarihi, ''),
                  ilk_mesaj_saati = COALESCE(ilk_mesaj_saati, ''),
                  durum = COALESCE(durum, 'Yeni'),
                  takip_1 = COALESCE(takip_1, ''),
                  takip_2 = COALESCE(takip_2, ''),
                  demo_tarihi = COALESCE(demo_tarihi, ''),
                  gorusme_tarihi = COALESCE(gorusme_tarihi, ''),
                  gorusme_saati = COALESCE(gorusme_saati, ''),
                  teklif = COALESCE(teklif, ''),
                  sonuc = COALESCE(sonuc, ''),
                  satis_tarihi = COALESCE(satis_tarihi, ''),
                  notlar = COALESCE(notlar, '')
                WHERE yetkili IS NULL
                   OR sehir IS NULL
                   OR instagram IS NULL
                   OR whatsapp IS NULL
                   OR eposta IS NULL
                   OR ilk_iletisim_kanali IS NULL
                   OR ilk_mesaj_tarihi IS NULL
                   OR ilk_mesaj_saati IS NULL
                   OR durum IS NULL
                   OR takip_1 IS NULL
                   OR takip_2 IS NULL
                   OR demo_tarihi IS NULL
                   OR gorusme_tarihi IS NULL
                   OR gorusme_saati IS NULL
                   OR teklif IS NULL
                   OR sonuc IS NULL
                   OR satis_tarihi IS NULL
                   OR notlar IS NULL
                """
            )
        )
        db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        discovery_columns = [
            ("google_place_id", "VARCHAR(255)"),
            ("source", "VARCHAR(50) DEFAULT 'manual'"),
            ("latitude", "NUMERIC(10, 7)"),
            ("longitude", "NUMERIC(10, 7)"),
            ("google_rating", "NUMERIC(3, 2)"),
            ("google_rating_count", "INTEGER"),
        ]
        for col_name, col_type in discovery_columns:
            cols = {c["name"] for c in inspector.get_columns("leads")}
            if col_name not in cols:
                db.execute(text(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}"))
                db.commit()
        db.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_user_google_place_id "
                "ON leads (user_id, google_place_id) "
                "WHERE google_place_id IS NOT NULL AND google_place_id <> ''"
            )
        )
        db.execute(text("UPDATE leads SET source = 'manual' WHERE source IS NULL OR source = ''"))
        db.commit()

        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "intelligence_score" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN intelligence_score INTEGER"))
            db.commit()
        cols = {c["name"] for c in inspector.get_columns("leads")}
        if "intelligence_updated_at" not in cols:
            db.execute(text("ALTER TABLE leads ADD COLUMN intelligence_updated_at TIMESTAMP"))
            db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "api_usage_logs" not in tables:
        from database import ApiUsageLog

        ApiUsageLog.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "lead_discovery_scans" not in tables:
        from database import LeadDiscoveryScan

        LeadDiscoveryScan.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    if "lead_requests" not in tables:
        from database import LeadRequest

        LeadRequest.__table__.create(bind=db.bind, checkfirst=True)

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "lead_requests" in tables:
        cols = {c["name"] for c in inspector.get_columns("lead_requests")}
        if "eposta" not in cols:
            db.execute(text("ALTER TABLE lead_requests ADD COLUMN eposta VARCHAR(255) DEFAULT ''"))
            db.commit()

    if "lead_activities" in tables:
        from activities import backfill_all_lead_activities, fix_future_gorusme_activities, fix_mesaj_activity_dates

        backfill_all_lead_activities(db)
        fix_future_gorusme_activities(db)
        fix_mesaj_activity_dates(db)

    if "tags" in tables:
        owners = db.query(User).filter(User.owner_id.is_(None)).all()
        for user in owners:
            seed_default_tags(db, user.id)

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "lead_attachments" in tables:
        cols = {c["name"] for c in inspector.get_columns("lead_attachments")}
        if "version_number" not in cols:
            db.execute(text("ALTER TABLE lead_attachments ADD COLUMN version_number INTEGER DEFAULT 1 NOT NULL"))
            db.execute(text("UPDATE lead_attachments SET version_number = 1 WHERE version_number IS NULL"))
            db.commit()
            cols = {c["name"] for c in inspector.get_columns("lead_attachments")}
        if "replaces_attachment_id" not in cols:
            db.execute(
                text(
                    "ALTER TABLE lead_attachments ADD COLUMN replaces_attachment_id INTEGER "
                    "REFERENCES lead_attachments(id) ON DELETE SET NULL"
                )
            )
            db.commit()
            cols = {c["name"] for c in inspector.get_columns("lead_attachments")}
        if "archived_at" not in cols:
            db.execute(text("ALTER TABLE lead_attachments ADD COLUMN archived_at TIMESTAMP"))
            db.commit()
            cols = {c["name"] for c in inspector.get_columns("lead_attachments")}
        if "archived_by" not in cols:
            db.execute(
                text(
                    "ALTER TABLE lead_attachments ADD COLUMN archived_by INTEGER "
                    "REFERENCES users(id) ON DELETE SET NULL"
                )
            )
            db.commit()
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_lead_attachments_archived_at ON lead_attachments (archived_at)"))
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "ai_runs" in tables:
        cols = {c["name"] for c in inspector.get_columns("ai_runs")}
        if "steps_json" not in cols:
            db.execute(text("ALTER TABLE ai_runs ADD COLUMN steps_json TEXT DEFAULT '[]' NOT NULL"))
            db.commit()
        cols = {c["name"] for c in inspector.get_columns("ai_runs")}
        if "updated_at" not in cols:
            db.execute(
                text(
                    "ALTER TABLE ai_runs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL"
                )
            )
            db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "business_events" not in tables:
        from database import BusinessEvent

        BusinessEvent.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "org_intelligence_profiles" not in tables:
        from database import OrgIntelligenceProfile

        OrgIntelligenceProfile.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "ai_actions" not in tables:
        from database import AiAction

        AiAction.__table__.create(bind=db.bind, checkfirst=True)
        db.commit()

    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if "ai_actions" in tables:
        cols = {c["name"] for c in inspector.get_columns("ai_actions")}
        if "execution_result_json" not in cols:
            db.execute(text("ALTER TABLE ai_actions ADD COLUMN execution_result_json TEXT"))
            db.commit()


def seed_user_defaults(db: Session, user_id: int, account_type: str = ACCOUNT_TYPE_COMPANY) -> None:
    categories = (
        DEFAULT_CATEGORIES
        if account_type == ACCOUNT_TYPE_COMPANY
        else INDIVIDUAL_DEFAULT_CATEGORIES
    )
    for cat in categories:
        exists = (
            db.query(CategoryModel)
            .filter(CategoryModel.user_id == user_id, CategoryModel.id == cat["id"])
            .first()
        )
        if not exists:
            db.add(CategoryModel(user_id=user_id, **cat))
    db.commit()
    seed_default_tags(db, user_id)


def seed_admin_user(db: Session) -> None:
    admin = db.query(User).filter(User.username == settings.seed_admin_username).first()
    if not admin:
        admin = User(
            username=settings.seed_admin_username,
            email=settings.seed_admin_email,
            password_hash=hash_password(settings.seed_admin_password),
            role="owner",
            account_type=ACCOUNT_TYPE_COMPANY,
            email_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        for cat in DEFAULT_CATEGORIES:
            db.add(CategoryModel(user_id=admin.id, **cat))
        db.commit()
        seed_default_tags(db, admin.id)
        return

    if db.query(CategoryModel).filter(CategoryModel.user_id == admin.id).count() == 0:
        orphan_cats = db.execute(
            text("SELECT id, label, icon, created_at FROM categories WHERE user_id IS NULL")
        ).fetchall()
        if orphan_cats:
            for row in orphan_cats:
                db.execute(
                    text(
                        "INSERT INTO categories (user_id, id, label, icon, created_at) "
                        "VALUES (:uid, :id, :label, :icon, :created_at) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "uid": admin.id,
                        "id": row.id,
                        "label": row.label,
                        "icon": row.icon,
                        "created_at": row.created_at,
                    },
                )
            db.commit()
        else:
            for cat in DEFAULT_CATEGORIES:
                exists = (
                    db.query(CategoryModel)
                    .filter(CategoryModel.user_id == admin.id, CategoryModel.id == cat["id"])
                    .first()
                )
                if not exists:
                    db.add(CategoryModel(user_id=admin.id, **cat))
            db.commit()


def invalidate_old_reset_tokens(db: Session, user_id: int) -> None:
    from database import PasswordResetToken

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": datetime.utcnow()})
    db.commit()


def create_reset_token(db: Session, user_id: int, token_hash: str) -> None:
    from database import PasswordResetToken

    invalidate_old_reset_tokens(db, user_id)
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    db.commit()


def invalidate_old_verification_tokens(db: Session, user_id: int) -> None:
    from database import EmailVerificationToken

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user_id,
        EmailVerificationToken.used_at.is_(None),
    ).update({"used_at": datetime.utcnow()})
    db.commit()


def create_verification_token(db: Session, user_id: int, token_hash: str) -> None:
    from database import EmailVerificationToken

    invalidate_old_verification_tokens(db, user_id)
    db.add(
        EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=settings.email_verification_expire_hours),
        )
    )
    db.commit()
