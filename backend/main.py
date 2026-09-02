from datetime import date, datetime
import logging
import time
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import case, text
from sqlalchemy.orm import Session

from activities import (
    ACTIVITY_TYPES,
    activities_for_lead_update,
    activities_for_new_lead,
    ensure_lead_activities,
    fix_mesaj_activity_dates,
    log_activity,
    record_activities,
    sync_gorusme_activity_on_update,
    sync_lead_mesaj_activity_date,
    sync_mesaj_activity_on_update,
)
from analytics import build_analytics, build_daily_contact_analytics, parse_analytics_anchor
from auth import authenticate_user, bump_token_version, create_access_token, require_verified_user, verify_token
from config import settings
from database import CategoryModel, EmailVerificationToken, Lead, LeadActivity, LeadAttachment, LeadRequest, LeadTag, PasswordResetToken, TagModel, User, get_db, init_db
from ai.router import router as ai_router
from intelligence.router import router as intelligence_router
from intelligence.business_events import LEAD_CREATED, OFFER_SENT, TASK_COMPLETED, emit_business_event, emit_stage_change_if_needed
from logging_config import log_event, setup_logging
from app_timezone import local_today
from email_service import generate_reset_token, hash_token, send_password_reset_email, send_verification_email
from lead_automation import apply_lead_automation
from lead_import import (
    build_import_template_xlsx,
    delete_import_batch,
    import_leads_from_rows,
    list_import_batches,
    parse_leads_from_xlsx,
)
from lead_discovery import (
    DiscoveryError,
    QuotaExceededError,
    discover_leads,
    get_usage_summary,
    import_discovered_leads,
)
from lead_attachments import (
    archive_attachment,
    attachment_response,
    delete_attachment_record,
    delete_attachments_for_lead,
    delete_attachments_for_org,
    get_attachment_or_404,
    list_attachments,
    prepare_replacement,
    read_upload_limited,
    save_attachment_file,
    stored_file_path,
    uploader_map,
    validate_upload,
)
from lead_requests import (
    approve_lead_request,
    create_lead_request,
    pending_request_count,
    reject_lead_request,
    request_response,
)
from refresh_sessions import (
    clear_refresh_cookie,
    create_refresh_session,
    revoke_all_refresh_sessions,
    revoke_refresh_from_request,
    rotate_refresh_session,
)
from migrate_auth import create_reset_token, create_verification_token, seed_user_defaults
from dashboard import build_dashboard
from funnel import build_sales_funnel
from report_export import export_report_csv, export_report_pdf, export_report_xlsx
from reports import build_daily_report, build_period_report, parse_report_anchor
from revenue import build_revenue
from roles import (
    ROLE_EMPLOYEE,
    ROLE_OWNER,
    get_employee_or_404,
    get_org_id,
    require_company_account,
    require_owner,
    user_response,
)
from schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    AnalyticsResponse,
    DailyContactAnalyticsResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    DashboardResponse,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    ForgotPasswordRequest,
    FunnelResponse,
    LeadAttachmentResponse,
    LeadAttachmentUpdate,
    LeadCreate,
    LeadRequestCreate,
    LeadRequestReject,
    LeadRequestResponse,
    LeadImportBatchDeleteResponse,
    LeadImportBatchResponse,
    LeadImportResponse,
    LeadDiscoveryImportRequest,
    LeadDiscoveryImportResponse,
    LeadDiscoveryRequest,
    LeadDiscoveryResponse,
    PlacesUsageResponse,
    LeadPaymentCreate,
    LeadResponse,
    LeadUpdate,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PaginatedLeadResponse,
    PendingRequestCountResponse,
    PublicConfigResponse,
    RegisterRequest,
    RegisterResponse,
    ReportResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    RevenueResponse,
    StatsResponse,
    TagCreate,
    TagResponse,
    TagUpdate,
    UserResponse,
    DeleteAccountRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from security import (
    hash_password,
    validate_business_email,
    validate_company_name,
    validate_email,
    validate_employee_email,
    validate_password,
    validate_password_confirm,
    validate_username,
    verify_password,
)
from tags import get_lead_tags, sync_lead_tags, tag_response, validate_tag_ids
from utils import slugify

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="BehTech Sales Hub",
    version="2.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)
logger = logging.getLogger("behtech.api")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(intelligence_router, prefix="/api/intelligence", tags=["intelligence"])

VALID_ICONS = {
    "pen-tool", "sparkles", "scissors", "building-2", "store", "heart",
    "star", "users", "briefcase", "scissors-line-dashed", "flower-2",
    "palette", "gem", "coffee", "car", "home", "phone",
}

VALID_TAG_COLORS = {
    "amber", "orange", "blue", "purple", "slate", "red", "green", "cyan", "emerald", "indigo",
}

VALID_PRIORITIES = {"dusuk", "orta", "yuksek"}

PRIORITY_ORDER = case(
    (Lead.oncelik == "yuksek", 1),
    (Lead.oncelik == "orta", 2),
    (Lead.oncelik == "dusuk", 3),
    else_=2,
)

GENERIC_AUTH_MSG = "İşlem başarılı. E-posta adresinize talimatlar gönderildi."
GENERIC_LOGIN_MSG = "Kullanıcı adınız veya şifreniz yanlış"


def send_user_verification_email(db: Session, user: User) -> bool:
    """Send verification email. Returns True if sent, False if auto-verified."""
    if not settings.email_verification_enabled:
        user.email_verified = True
        db.commit()
        return False

    if settings.smtp_configured:
        token = generate_reset_token()
        create_verification_token(db, user.id, hash_token(token))
        try:
            send_verification_email(user.email, user.username, token)
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Doğrulama e-postası gönderilemedi. Lütfen daha sonra tekrar deneyin.",
            )
        return True

    user.email_verified = True
    db.commit()
    return False


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.middleware("http")
async def request_logging(request: Request, call_next):
    if request.url.path == "/api/health":
        return await call_next(request)

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    if settings.is_production or response.status_code >= 400:
        log_event(
            logger,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )

    return response


@app.on_event("startup")
def startup():
    setup_logging()
    settings.validate_production()
    init_db()
    logger.info("BehTech Sales Hub started env=%s", settings.app_env)


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    payload = {
        "status": "ok",
        "env": settings.app_env,
        "database": "ok",
        "version": app.version,
        "ai_enabled": settings.ai_enabled,
    }
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        log_event(logger, "health_check_failed", database="error")
        payload["status"] = "degraded"
        payload["database"] = "error"
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/api/public/config", response_model=PublicConfigResponse)
def public_config():
    return PublicConfigResponse(idle_timeout_minutes=settings.idle_timeout_minutes)


def get_category_or_404(db: Session, user_id: int, category_id: str) -> CategoryModel:
    category = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == user_id, CategoryModel.id == category_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    return category


def category_response(db: Session, user_id: int, category: CategoryModel) -> CategoryResponse:
    lead_count = (
        db.query(Lead)
        .filter(Lead.user_id == user_id, Lead.category == category.id)
        .count()
    )
    return CategoryResponse(
        id=category.id,
        label=category.label,
        icon=category.icon,
        created_at=category.created_at,
        lead_count=lead_count,
    )


def get_tag_or_404(db: Session, user_id: int, tag_id: str) -> TagModel:
    tag = (
        db.query(TagModel)
        .filter(TagModel.user_id == user_id, TagModel.id == tag_id)
        .first()
    )
    if not tag:
        raise HTTPException(status_code=404, detail="Etiket bulunamadı")
    return tag


def _lead_str(value: str | None) -> str:
    return value or ""


def lead_response(db: Session, user_id: int, lead: Lead, viewer: User | None = None) -> LeadResponse:
    tags = get_lead_tags(db, user_id, lead.id)
    hide_sensitive = viewer is not None and viewer.role == ROLE_EMPLOYEE
    return LeadResponse(
        id=lead.id,
        category=lead.category,
        isletme_adi=_lead_str(lead.isletme_adi),
        yetkili=_lead_str(lead.yetkili),
        sehir=_lead_str(lead.sehir),
        instagram=_lead_str(lead.instagram),
        whatsapp=_lead_str(lead.whatsapp),
        eposta=_lead_str(lead.eposta),
        ilk_iletisim_kanali=_lead_str(lead.ilk_iletisim_kanali),
        ilk_mesaj_tarihi=_lead_str(lead.ilk_mesaj_tarihi),
        ilk_mesaj_saati=_lead_str(lead.ilk_mesaj_saati),
        durum=_lead_str(lead.durum) or "Yeni",
        oncelik=lead.oncelik or "orta",
        takip_1=_lead_str(lead.takip_1),
        takip_2=_lead_str(lead.takip_2),
        demo_gonderildi=bool(lead.demo_gonderildi),
        demo_tarihi=_lead_str(lead.demo_tarihi),
        gorusme_tarihi=_lead_str(lead.gorusme_tarihi),
        gorusme_saati=_lead_str(lead.gorusme_saati),
        teklif="" if hide_sensitive else _lead_str(lead.teklif),
        sonuc=_lead_str(lead.sonuc),
        satis_tutari=0 if hide_sensitive else float(lead.satis_tutari or 0),
        satis_tarihi="" if hide_sensitive else _lead_str(lead.satis_tarihi),
        notlar=_lead_str(lead.notlar),
        tags=tags,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit(settings.rate_limit_login)
def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, data.username.strip().lower(), data.password)
    if not user:
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_MSG)
    require_verified_user(user)

    token, expires_in = create_access_token(
        user.id, user.username, user.token_version or 0
    )
    if data.remember_me:
        create_refresh_session(db, user.id, response)
    else:
        clear_refresh_cookie(response)

    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role or ROLE_OWNER,
        account_type=user.account_type or "company",
        expires_in=expires_in,
        idle_timeout_minutes=settings.idle_timeout_minutes,
    )


@app.post("/api/auth/refresh", response_model=LoginResponse)
@limiter.limit(settings.rate_limit_login)
def refresh_auth_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = rotate_refresh_session(db, request, response)
    if not user:
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_MSG)
    require_verified_user(user)

    token, expires_in = create_access_token(
        user.id, user.username, user.token_version or 0
    )
    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role or ROLE_OWNER,
        account_type=user.account_type or "company",
        expires_in=expires_in,
        idle_timeout_minutes=settings.idle_timeout_minutes,
    )


@app.post("/api/auth/logout", response_model=MessageResponse)
def logout_auth_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    revoke_refresh_from_request(db, request)
    clear_refresh_cookie(response)
    return MessageResponse(message="Çıkış yapıldı.")


@app.post("/api/auth/register", response_model=RegisterResponse, status_code=201)
@limiter.limit(settings.rate_limit_register)
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    username = data.username.strip().lower()
    email = data.email.strip().lower()

    if err := validate_username(username):
        raise HTTPException(status_code=400, detail=err)
    if err := validate_email(email):
        raise HTTPException(status_code=400, detail=err)
    if err := validate_password_confirm(data.password, data.password_confirm):
        raise HTTPException(status_code=400, detail=err)
    if errors := validate_password(data.password):
        raise HTTPException(status_code=400, detail=", ".join(errors))

    if data.account_type == "company":
        if err := validate_company_name(data.company_name):
            raise HTTPException(status_code=400, detail=err)
        if err := validate_business_email(email):
            raise HTTPException(status_code=400, detail=err)

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanılıyor")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(data.password),
        role=ROLE_OWNER,
        account_type=data.account_type,
        company_name=data.company_name.strip() if data.account_type == "company" else None,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    seed_user_defaults(db, user.id, data.account_type)

    verification_sent = send_user_verification_email(db, user)
    if verification_sent:
        return RegisterResponse(
            message="Hesabınız oluşturuldu. Giriş yapmadan önce e-posta adresinizi doğrulayın.",
            requires_verification=True,
            email=email,
        )

    token, expires_in = create_access_token(
        user.id, user.username, token_version=user.token_version or 0
    )
    return RegisterResponse(
        message="Hesabınız oluşturuldu.",
        requires_verification=False,
        email=email,
        access_token=token,
        username=user.username,
        role=user.role or ROLE_OWNER,
        account_type=user.account_type or "company",
        expires_in=expires_in,
    )


@app.post("/api/auth/verify-email", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_verify_email)
def verify_email(request: Request, data: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(data.token)
    record = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if record:
        user = db.query(User).filter(User.id == record.user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş doğrulama bağlantısı")

        user.email_verified = True
        record.used_at = datetime.utcnow()
        db.commit()
        return MessageResponse(message="E-posta adresiniz doğrulandı. Giriş yapabilirsiniz.")

    used_record = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.isnot(None),
        )
        .first()
    )
    if used_record:
        user = db.query(User).filter(User.id == used_record.user_id).first()
        if user and user.email_verified:
            return MessageResponse(message="E-posta adresiniz zaten doğrulandı. Giriş yapabilirsiniz.")

    raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş doğrulama bağlantısı")


@app.post("/api/auth/resend-verification", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_resend_verification)
def resend_verification(
    request: Request, data: ResendVerificationRequest, db: Session = Depends(get_db)
):
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified:
        send_user_verification_email(db, user)
    return MessageResponse(
        message="Kayıtlı ve doğrulanmamış bir hesap varsa doğrulama e-postası gönderildi."
    )


@app.post("/api/auth/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_forgot_password)
def forgot_password(request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    identifier = data.identifier.strip().lower()
    user = (
        db.query(User)
        .filter((User.username == identifier) | (User.email == identifier))
        .first()
    )

    if user and settings.smtp_configured:
        token = generate_reset_token()
        create_reset_token(db, user.id, hash_token(token))
        try:
            send_password_reset_email(user.email, user.username, token)
        except Exception:
            raise HTTPException(status_code=500, detail="E-posta gönderilemedi. Lütfen daha sonra tekrar deneyin.")

    return MessageResponse(message=GENERIC_AUTH_MSG)


@app.post("/api/auth/reset-password", response_model=MessageResponse)
@limiter.limit(settings.rate_limit_forgot_password)
def reset_password(request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)):
    if errors := validate_password(data.password):
        raise HTTPException(status_code=400, detail=", ".join(errors))

    token_hash = hash_token(data.token)
    reset_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not reset_record:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş bağlantı")

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş bağlantı")

    user.password_hash = hash_password(data.password)
    bump_token_version(user)
    revoke_all_refresh_sessions(db, user.id)
    reset_record.used_at = datetime.utcnow()
    db.commit()

    return MessageResponse(message="Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.")


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(verify_token), db: Session = Depends(get_db)):
    owner = None
    if user.role == ROLE_EMPLOYEE and user.owner_id:
        owner = db.query(User).filter(User.id == user.owner_id).first()
    return UserResponse(**user_response(user, owner))


@app.patch("/api/auth/me", response_model=UserResponse)
def update_me(
    data: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    if data.email is not None:
        new_email = str(data.email).strip().lower()
        if new_email != user.email:
            if err := validate_email(new_email):
                raise HTTPException(status_code=400, detail=err)

            if (
                db.query(User)
                .filter(User.email == new_email, User.id != user.id)
                .first()
            ):
                raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

            if user.role == ROLE_EMPLOYEE:
                owner = db.query(User).filter(User.id == user.owner_id).first()
                if owner and (err := validate_employee_email(new_email, owner.email)):
                    raise HTTPException(status_code=400, detail=err)
            elif (user.account_type or "company") == "company" and user.role == ROLE_OWNER:
                if err := validate_business_email(new_email):
                    raise HTTPException(status_code=400, detail=err)

            user.email = new_email
            if settings.email_verification_enabled and settings.smtp_configured:
                user.email_verified = False
                send_user_verification_email(db, user)
            else:
                user.email_verified = True

    if data.company_name is not None:
        if user.role != ROLE_OWNER:
            raise HTTPException(
                status_code=403,
                detail="Şirket adı yalnızca hesap sahibi tarafından güncellenebilir",
            )
        if (user.account_type or "company") != "company":
            raise HTTPException(
                status_code=400,
                detail="Bireysel hesaplarda şirket adı güncellenemez",
            )
        if err := validate_company_name(data.company_name):
            raise HTTPException(status_code=400, detail=err)
        user.company_name = data.company_name.strip()

    if data.display_name is not None:
        display_name = data.display_name.strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="Görünen ad boş olamaz")
        user.display_name = display_name

    if data.new_password:
        if not verify_password(data.current_password or "", user.password_hash):
            raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")
        if err := validate_password_confirm(data.new_password, data.new_password_confirm or ""):
            raise HTTPException(status_code=400, detail=err)
        password_errors = validate_password(data.new_password)
        if password_errors:
            raise HTTPException(status_code=400, detail=password_errors[0])
        user.password_hash = hash_password(data.new_password)
        bump_token_version(user)
        revoke_all_refresh_sessions(db, user.id)

    db.commit()
    db.refresh(user)
    owner = None
    if user.role == ROLE_EMPLOYEE and user.owner_id:
        owner = db.query(User).filter(User.id == user.owner_id).first()
    return UserResponse(**user_response(user, owner))


@app.delete("/api/auth/me", response_model=MessageResponse)
def delete_me(
    data: DeleteAccountRequest,
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    if data.confirm_username.strip().lower() != user.username:
        raise HTTPException(status_code=400, detail="Kullanıcı adı eşleşmiyor")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Şifre hatalı")

    user_id = user.id
    username = user.username
    role = user.role

    if user.role == ROLE_OWNER:
        db.query(User).filter(User.owner_id == user.id).delete(synchronize_session=False)
        delete_attachments_for_org(user_id)

    db.delete(user)
    db.commit()

    log_event(
        logger,
        "account_deleted",
        user_id=user_id,
        username=username,
        role=role,
    )
    return MessageResponse(message="Hesabınız silindi")


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(require_owner)):
    return build_dashboard(db, user.id)


@app.get("/api/funnel", response_model=FunnelResponse)
def get_funnel(db: Session = Depends(get_db), user: User = Depends(require_owner)):
    leads = db.query(Lead).filter(Lead.user_id == user.id).all()
    return build_sales_funnel(leads)


@app.get("/api/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db), user: User = Depends(require_owner)):
    return build_analytics(db, user.id)


@app.get("/api/analytics/daily-contact", response_model=DailyContactAnalyticsResponse)
def get_daily_contact_analytics(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    anchor = parse_analytics_anchor(date)
    return build_daily_contact_analytics(db, user.id, anchor)


@app.get("/api/revenue", response_model=RevenueResponse)
def get_revenue(
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(require_company_account),
):
    return build_revenue(db, user.id, year=year, month=month)


def _report_includes_revenue(user: User) -> bool:
    return (user.account_type or "company") == "company"


@app.get("/api/reports/weekly", response_model=ReportResponse)
def get_weekly_report(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD referans tarihi"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    anchor = parse_report_anchor("weekly", date, None)
    return build_period_report(db, user.id, "weekly", anchor, _report_includes_revenue(user))


@app.get("/api/reports/monthly", response_model=ReportResponse)
def get_monthly_report(
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD referans tarihi"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    anchor = parse_report_anchor("monthly", date, month)
    return build_period_report(db, user.id, "monthly", anchor, _report_includes_revenue(user))


@app.get("/api/reports/daily", response_model=ReportResponse)
def get_daily_report(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD referans tarihi"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    anchor = parse_report_anchor("daily", date, None)
    return build_daily_report(db, user.id, anchor, _report_includes_revenue(user))


@app.get("/api/reports/export")
def export_report(
    period: str = Query(..., pattern="^(weekly|monthly)$"),
    export_format: str = Query(..., alias="format", pattern="^(csv|xlsx|pdf)$"),
    date: Optional[str] = Query(default=None),
    month: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    anchor = parse_report_anchor(period, date, month)
    report = build_period_report(db, user.id, period, anchor, _report_includes_revenue(user))

    if export_format == "csv":
        content = export_report_csv(report)
        media_type = "text/csv; charset=utf-8"
        filename = f"behtech-{period}-rapor.csv"
    elif export_format == "xlsx":
        try:
            content = export_report_xlsx(report)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"behtech-{period}-rapor.xlsx"
    else:
        content = export_report_pdf(report)
        media_type = "application/pdf"
        filename = f"behtech-{period}-rapor.pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/categories", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    org_id = get_org_id(user)
    categories = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == org_id)
        .order_by(CategoryModel.label)
        .all()
    )
    return [category_response(db, org_id, cat) for cat in categories]


@app.post("/api/categories", response_model=CategoryResponse, status_code=201)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    category_id = slugify(data.id or data.label)
    if data.icon not in VALID_ICONS:
        raise HTTPException(status_code=400, detail="Geçersiz ikon")

    exists = (
        db.query(CategoryModel)
        .filter(CategoryModel.user_id == user.id, CategoryModel.id == category_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Bu kategori zaten mevcut")

    category = CategoryModel(user_id=user.id, id=category_id, label=data.label, icon=data.icon)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category_response(db, user.id, category)


@app.put("/api/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    category = get_category_or_404(db, user.id, category_id)

    if data.icon and data.icon not in VALID_ICONS:
        raise HTTPException(status_code=400, detail="Geçersiz ikon")

    new_label = data.label or category.label
    new_icon = data.icon or category.icon

    if data.id and slugify(data.id) != category_id:
        new_id = slugify(data.id)
        exists = (
            db.query(CategoryModel)
            .filter(CategoryModel.user_id == user.id, CategoryModel.id == new_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Bu kategori kimliği zaten kullanılıyor")

        db.query(Lead).filter(Lead.user_id == user.id, Lead.category == category_id).update(
            {"category": new_id}
        )
        created_at = category.created_at
        db.delete(category)
        db.flush()
        category = CategoryModel(
            user_id=user.id, id=new_id, label=new_label, icon=new_icon, created_at=created_at
        )
        db.add(category)
    else:
        category.label = new_label
        category.icon = new_icon

    db.commit()
    db.refresh(category)
    return category_response(db, user.id, category)


@app.delete("/api/categories/{category_id}")
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    category = get_category_or_404(db, user.id, category_id)
    lead_count = (
        db.query(Lead).filter(Lead.user_id == user.id, Lead.category == category_id).count()
    )

    if lead_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Bu kategoride {lead_count} kayıt var. Önce kayıtları silin veya taşıyın.",
        )

    db.delete(category)
    db.commit()
    return {"message": "Kategori silindi"}


@app.get("/api/tags", response_model=list[TagResponse])
def list_tags(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    org_id = get_org_id(user)
    tags = (
        db.query(TagModel)
        .filter(TagModel.user_id == org_id)
        .order_by(TagModel.is_system.desc(), TagModel.label.asc())
        .all()
    )
    return [tag_response(db, org_id, tag) for tag in tags]


@app.post("/api/tags", response_model=TagResponse, status_code=201)
def create_tag(
    data: TagCreate, db: Session = Depends(get_db), user: User = Depends(require_owner)
):
    if data.color not in VALID_TAG_COLORS:
        raise HTTPException(status_code=400, detail="Geçersiz etiket rengi")

    tag_id = slugify(data.id or data.label)
    if not tag_id:
        raise HTTPException(status_code=400, detail="Geçersiz etiket kimliği")

    exists = (
        db.query(TagModel)
        .filter(TagModel.user_id == user.id, TagModel.id == tag_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Bu etiket zaten mevcut")

    tag = TagModel(user_id=user.id, id=tag_id, label=data.label, color=data.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag_response(db, user.id, tag)


@app.put("/api/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: str,
    data: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    tag = get_tag_or_404(db, user.id, tag_id)

    if data.color and data.color not in VALID_TAG_COLORS:
        raise HTTPException(status_code=400, detail="Geçersiz etiket rengi")

    new_label = data.label or tag.label
    new_color = data.color or tag.color

    if data.id and slugify(data.id) != tag_id:
        if tag.is_system:
            raise HTTPException(status_code=400, detail="Sistem etiketinin kimliği değiştirilemez")

        new_id = slugify(data.id)
        conflict = (
            db.query(TagModel)
            .filter(TagModel.user_id == user.id, TagModel.id == new_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Bu etiket kimliği zaten kullanılıyor")

        db.query(LeadTag).filter(LeadTag.user_id == user.id, LeadTag.tag_id == tag_id).update(
            {"tag_id": new_id}
        )
        created_at = tag.created_at
        is_system = tag.is_system
        db.delete(tag)
        db.flush()
        tag = TagModel(
            user_id=user.id,
            id=new_id,
            label=new_label,
            color=new_color,
            is_system=is_system,
            created_at=created_at,
        )
        db.add(tag)
    else:
        tag.label = new_label
        tag.color = new_color

    db.commit()
    db.refresh(tag)
    return tag_response(db, user.id, tag)


@app.delete("/api/tags/{tag_id}")
def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    tag = get_tag_or_404(db, user.id, tag_id)

    if tag.is_system:
        raise HTTPException(status_code=400, detail="Sistem etiketleri silinemez")

    lead_count = (
        db.query(LeadTag)
        .filter(LeadTag.user_id == user.id, LeadTag.tag_id == tag_id)
        .count()
    )
    if lead_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Bu etiket {lead_count} kayıtta kullanılıyor. Önce etiketi kaldırın.",
        )

    db.delete(tag)
    db.commit()
    return {"message": "Etiket silindi"}


@app.get("/api/leads", response_model=PaginatedLeadResponse)
def list_leads(
    category: str = Query(...),
    search: Optional[str] = None,
    durum: Optional[str] = None,
    tag: Optional[str] = None,
    oncelik: Optional[str] = None,
    sehir: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.leads_page_size, ge=1, le=settings.leads_page_size_max),
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    org_id = get_org_id(user)
    get_category_or_404(db, org_id, category)

    query = db.query(Lead).filter(Lead.user_id == org_id, Lead.category == category)

    if durum:
        query = query.filter(Lead.durum == durum)

    if oncelik:
        if oncelik not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Geçersiz öncelik")
        query = query.filter(Lead.oncelik == oncelik)

    if tag:
        get_tag_or_404(db, org_id, tag)
        query = query.join(LeadTag).filter(
            LeadTag.user_id == org_id,
            LeadTag.tag_id == tag,
        )

    if sehir:
        query = query.filter(Lead.sehir.ilike(sehir.strip()))

    if search:
        term = f"%{search}%"
        query = query.filter(
            (Lead.isletme_adi.ilike(term))
            | (Lead.yetkili.ilike(term))
            | (Lead.sehir.ilike(term))
            | (Lead.notlar.ilike(term))
        )

    total = query.with_entities(Lead.id).distinct().count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages

    leads = (
        query.order_by(PRIORITY_ORDER, Lead.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedLeadResponse(
        items=[lead_response(db, org_id, lead, viewer=user) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_lead_or_404(db: Session, user_id: int, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == user_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return lead


@app.get("/api/leads/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(verify_token)):
    org_id = get_org_id(user)
    lead = get_lead_or_404(db, org_id, lead_id)
    return lead_response(db, org_id, lead, viewer=user)


@app.post("/api/leads", response_model=LeadResponse, status_code=201)
def create_lead(
    data: LeadCreate, db: Session = Depends(get_db), user: User = Depends(require_owner)
):
    get_category_or_404(db, user.id, data.category)

    if data.oncelik not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Geçersiz öncelik")

    try:
        validate_tag_ids(db, user.id, data.tag_ids)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz etiket seçimi")

    lead_fields = apply_lead_automation(data.model_dump(exclude={"tag_ids"}))
    lead = Lead(user_id=user.id, **lead_fields)
    db.add(lead)
    db.flush()
    sync_lead_tags(db, user.id, lead.id, data.tag_ids)
    record_activities(db, user.id, lead.id, activities_for_new_lead(data.model_dump()))
    emit_business_event(
        db,
        user.id,
        LEAD_CREATED,
        lead_id=lead.id,
        payload={"durum": lead.durum, "category": lead.category},
    )
    db.commit()
    db.refresh(lead)
    return lead_response(db, user.id, lead)


@app.get("/api/leads/discover/usage", response_model=PlacesUsageResponse)
def get_lead_discovery_usage(db: Session = Depends(get_db), user: User = Depends(require_owner)):
    return get_usage_summary(db, user.id)


@app.post("/api/leads/discover", response_model=LeadDiscoveryResponse)
def discover_leads_endpoint(
    data: LeadDiscoveryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    category = data.category.strip() if data.category else None
    if category:
        get_category_or_404(db, user.id, category)

    try:
        result = discover_leads(
            db,
            user.id,
            city=data.city,
            district=data.district,
            sector_keyword=data.sector_keyword,
            category=category,
            radius_meters=data.radius_meters,
            confirm_over_quota=data.confirm_over_quota,
        )
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(exc),
                "usage": exc.usage,
            },
        ) from exc
    except DiscoveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    usage = result["usage"]
    warning_message = None
    if usage.get("warning") and not usage.get("over_quota"):
        warning_message = (
            f"Uyarı: Bu ay {usage['used']}/{usage['free_quota']} ücretsiz sorgu kullanıldı."
        )
    elif usage.get("over_quota"):
        warning_message = (
            f"Bu ay ücretsiz kota aşıldı ({usage['used']}/{usage['free_quota']}). "
            "Ek sorgular ücretlidir."
        )

    log_event(
        logger,
        "leads_discovered",
        user_id=user.id,
        city=data.city.strip(),
        district=(data.district or "").strip(),
        sector=data.sector_keyword.strip(),
        found=result["total_found"],
        queries_used=result["queries_used"],
    )

    return {
        **result,
        "warning_message": warning_message,
    }


@app.post("/api/leads/discover/import", response_model=LeadDiscoveryImportResponse)
def import_discovered_leads_endpoint(
    data: LeadDiscoveryImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    category = data.category.strip()
    get_category_or_404(db, user.id, category)

    places = [item.model_dump() for item in data.places]
    result = import_discovered_leads(
        db,
        user.id,
        category=category,
        places=places,
        city=data.city,
    )
    log_event(
        logger,
        "leads_discovery_imported",
        user_id=user.id,
        category=category,
        created=result["created"],
        updated=result["updated"],
    )
    return result


@app.get("/api/leads/import/template")
def download_lead_import_template(user: User = Depends(require_owner)):
    content = build_import_template_xlsx()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="behtech-musteri-sablonu.xlsx"',
        },
    )


@app.post("/api/leads/import", response_model=LeadImportResponse)
async def import_leads(
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_category_or_404(db, user.id, category.strip())

    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Yalnızca .xlsx Excel dosyası yükleyin")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş")

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya boyutu en fazla 5 MB olabilir")

    try:
        rows = parse_leads_from_xlsx(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=400, detail="İçe aktarılacak kayıt bulunamadı")

    result = import_leads_from_rows(
        db,
        user_id=user.id,
        category=category.strip(),
        rows=rows,
        filename=file.filename or "",
    )
    log_event(
        logger,
        "leads_imported",
        user_id=user.id,
        category=category.strip(),
        created=result["created"],
        failed=result["failed"],
        batch_id=result.get("batch_id"),
    )
    return result


@app.get("/api/leads/import/batches", response_model=list[LeadImportBatchResponse])
def get_lead_import_batches(db: Session = Depends(get_db), user: User = Depends(require_owner)):
    return list_import_batches(db, user.id)


@app.delete("/api/leads/import/batches/{batch_id}", response_model=LeadImportBatchDeleteResponse)
def delete_lead_import_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    try:
        deleted = delete_import_batch(db, user.id, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="İçe aktarma kaydı bulunamadı") from exc

    log_event(logger, "import_batch_deleted", user_id=user.id, batch_id=batch_id, deleted=deleted)
    return {
        "deleted": deleted,
        "message": f"{deleted} müşteri silindi",
    }


@app.put("/api/leads/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    data: LeadUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    lead = get_lead_or_404(db, user.id, lead_id)
    if data.oncelik not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Geçersiz öncelik")

    old_durum = lead.durum
    update_data = apply_lead_automation(data.model_dump(exclude={"tag_ids"}), lead)
    sync_gorusme_activity_on_update(db, lead, update_data, user.id, lead_id)
    sync_mesaj_activity_on_update(db, lead, update_data, lead_id)
    record_activities(db, user.id, lead_id, activities_for_lead_update(lead, update_data))

    for key, value in update_data.items():
        setattr(lead, key, value)

    try:
        sync_lead_tags(db, user.id, lead_id, data.tag_ids)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz etiket seçimi")

    new_durum = update_data.get("durum", lead.durum)
    emit_stage_change_if_needed(db, user.id, lead_id, old_durum, new_durum)

    db.commit()
    db.refresh(lead)
    return lead_response(db, user.id, lead)


@app.post("/api/leads/{lead_id}/payments", response_model=LeadResponse, status_code=200)
def add_lead_payment(
    lead_id: int,
    data: LeadPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """Tekliften bağımsız alınan tutarı kasaya ekler; gelir istatistiklerinde görünür."""
    lead = get_lead_or_404(db, user.id, lead_id)
    increment = round(float(data.amount), 2)
    paid_at = (data.paid_at or "").strip()
    if paid_at:
        try:
            datetime.strptime(paid_at[:10], "%Y-%m-%d")
            paid_at = paid_at[:10]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Geçersiz ödeme tarihi") from exc
    else:
        paid_at = local_today().isoformat()

    old_amount = float(lead.satis_tutari or 0)
    new_amount = round(old_amount + increment, 2)
    lead.satis_tutari = new_amount
    if not (lead.satis_tarihi or "").strip():
        lead.satis_tarihi = paid_at

    increment_label = f"{increment:,.0f} TL".replace(",", ".")
    total_label = f"{new_amount:,.0f} TL".replace(",", ".")
    try:
        paid_dt = datetime.strptime(paid_at, "%Y-%m-%d")
    except ValueError:
        paid_dt = datetime.utcnow()
    log_activity(
        db,
        user_id=user.id,
        lead_id=lead_id,
        activity_type="satis_kaydedildi",
        title="Ödeme kaydedildi",
        description=f"{increment_label} alındı (toplam {total_label})",
        activity_date=paid_dt,
    )
    db.commit()
    db.refresh(lead)
    return lead_response(db, user.id, lead)


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(require_owner)):
    lead = get_lead_or_404(db, user.id, lead_id)
    delete_attachments_for_lead(db, user.id, lead_id)
    db.delete(lead)
    db.commit()
    return {"message": "Kayıt silindi"}


@app.get("/api/leads/{lead_id}/activities", response_model=list[ActivityResponse])
def list_activities(
    lead_id: int, db: Session = Depends(get_db), user: User = Depends(verify_token)
):
    org_id = get_org_id(user)
    lead = get_lead_or_404(db, org_id, lead_id)
    ensure_lead_activities(db, lead)
    sync_lead_mesaj_activity_date(db, lead)
    activities = (
        db.query(LeadActivity)
        .filter(LeadActivity.user_id == org_id, LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.activity_date.asc(), LeadActivity.id.asc())
        .all()
    )

    if user.role == ROLE_EMPLOYEE:
        sanitized = []
        for activity in activities:
            if activity.activity_type in {"teklif_verildi", "satis_kaydedildi"}:
                activity.description = ""
            sanitized.append(activity)
        return sanitized

    return activities


@app.post("/api/leads/{lead_id}/activities", response_model=ActivityResponse, status_code=201)
def create_activity(
    lead_id: int,
    data: ActivityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)

    if data.activity_type not in ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Geçersiz aktivite türü")

    title = data.title or ACTIVITY_TYPES[data.activity_type]
    activity = log_activity(
        db,
        user_id=user.id,
        lead_id=lead_id,
        activity_type=data.activity_type,
        title=title,
        description=data.description,
        activity_date=data.activity_date,
    )
    if data.activity_type == "teklif_verildi":
        emit_business_event(
            db,
            user.id,
            OFFER_SENT,
            lead_id=lead_id,
            payload={"activity_type": data.activity_type},
        )
    elif data.activity_type in {"gorusme_yapildi", "telefon_gorusmesi", "takip_yapildi"}:
        emit_business_event(
            db,
            user.id,
            TASK_COMPLETED,
            lead_id=lead_id,
            payload={"activity_type": data.activity_type},
        )
    db.commit()
    db.refresh(activity)
    return activity


@app.patch("/api/leads/{lead_id}/activities/{activity_id}", response_model=ActivityResponse)
def update_activity(
    lead_id: int,
    activity_id: int,
    data: ActivityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)

    activity = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.id == activity_id,
            LeadActivity.lead_id == lead_id,
            LeadActivity.user_id == user.id,
        )
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Aktivite bulunamadı")

    if data.activity_type is not None:
        if data.activity_type not in ACTIVITY_TYPES:
            raise HTTPException(status_code=400, detail="Geçersiz aktivite türü")
        activity.activity_type = data.activity_type
        activity.title = ACTIVITY_TYPES[data.activity_type]

    if data.description is not None:
        activity.description = data.description

    if data.activity_date is not None:
        activity.activity_date = data.activity_date

    db.commit()
    db.refresh(activity)
    return activity


@app.get("/api/leads/{lead_id}/attachments", response_model=list[LeadAttachmentResponse])
def list_lead_attachments(
    lead_id: int,
    status: str = Query("active", pattern="^(active|archived|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)
    attachments = list_attachments(db, user.id, lead_id, status=status)
    users = uploader_map(db, attachments)
    return [
        LeadAttachmentResponse(
            **attachment_response(
                attachment,
                users.get(attachment.uploaded_by) if attachment.uploaded_by else None,
                users.get(attachment.archived_by) if attachment.archived_by else None,
            )
        )
        for attachment in attachments
    ]


@app.post("/api/leads/{lead_id}/attachments", response_model=LeadAttachmentResponse, status_code=201)
async def upload_lead_attachment(
    lead_id: int,
    file: UploadFile = File(...),
    label: str = Form(""),
    replace_attachment_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)
    content = await read_upload_limited(file)
    original, ext = validate_upload(file, len(content))

    version_number, replaces_id, inherited_label = prepare_replacement(
        db, user.id, lead_id, replace_attachment_id, user
    )
    stored = save_attachment_file(user.id, lead_id, ext, content)
    display_label = label.strip() or inherited_label or original

    attachment = LeadAttachment(
        user_id=user.id,
        lead_id=lead_id,
        uploaded_by=user.id,
        label=display_label[:255],
        original_filename=original,
        stored_filename=stored,
        mime_type=(file.content_type or "application/octet-stream").split(";")[0].strip(),
        size_bytes=len(content),
        version_number=version_number,
        replaces_attachment_id=replaces_id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return LeadAttachmentResponse(**attachment_response(attachment, user))


@app.post(
    "/api/leads/{lead_id}/attachments/{attachment_id}/archive",
    response_model=LeadAttachmentResponse,
)
def archive_lead_attachment(
    lead_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)
    attachment = get_attachment_or_404(db, user.id, lead_id, attachment_id)
    archive_attachment(attachment, user)
    db.commit()
    db.refresh(attachment)
    return LeadAttachmentResponse(**attachment_response(attachment, None, user))


@app.get("/api/leads/{lead_id}/attachments/{attachment_id}/download")
def download_lead_attachment(
    lead_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    from urllib.parse import quote

    get_lead_or_404(db, user.id, lead_id)
    attachment = get_attachment_or_404(db, user.id, lead_id, attachment_id)
    path = stored_file_path(attachment)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    filename = attachment.original_filename
    quoted = quote(filename)
    return Response(
        content=path.read_bytes(),
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{quoted}\"; filename*=UTF-8''{quoted}",
        },
    )


@app.patch(
    "/api/leads/{lead_id}/attachments/{attachment_id}",
    response_model=LeadAttachmentResponse,
)
def update_lead_attachment(
    lead_id: int,
    attachment_id: int,
    data: LeadAttachmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)
    attachment = get_attachment_or_404(db, user.id, lead_id, attachment_id)
    attachment.label = data.label.strip()[:255]
    db.commit()
    db.refresh(attachment)
    uploader = None
    if attachment.uploaded_by:
        uploader = db.query(User).filter(User.id == attachment.uploaded_by).first()
    archiver = None
    if attachment.archived_by:
        archiver = db.query(User).filter(User.id == attachment.archived_by).first()
    return LeadAttachmentResponse(**attachment_response(attachment, uploader, archiver))


@app.delete("/api/leads/{lead_id}/attachments/{attachment_id}")
def delete_lead_attachment(
    lead_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    get_lead_or_404(db, user.id, lead_id)
    attachment = get_attachment_or_404(db, user.id, lead_id, attachment_id)
    delete_attachment_record(db, attachment)
    db.commit()
    return {"message": "Dosya silindi"}


@app.get("/api/activity-types")
def list_activity_types(user: User = Depends(verify_token)):
    return [{"id": key, "label": label} for key, label in ACTIVITY_TYPES.items()]


@app.get("/api/stats/{category}", response_model=StatsResponse)
def get_stats(category: str, db: Session = Depends(get_db), user: User = Depends(verify_token)):
    org_id = get_org_id(user)
    get_category_or_404(db, org_id, category)

    leads = db.query(Lead).filter(Lead.user_id == org_id, Lead.category == category).all()
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {"dusuk": 0, "orta": 0, "yuksek": 0}
    demo_count = 0

    cities: set[str] = set()
    for lead in leads:
        by_status[lead.durum] = by_status.get(lead.durum, 0) + 1
        priority = lead.oncelik if lead.oncelik in VALID_PRIORITIES else "orta"
        by_priority[priority] = by_priority.get(priority, 0) + 1
        if lead.demo_gonderildi:
            demo_count += 1
        if lead.sehir and lead.sehir.strip():
            cities.add(lead.sehir.strip())

    return StatsResponse(
        total=len(leads),
        by_status=by_status,
        by_priority=by_priority,
        demo_gonderildi=demo_count,
        cities=sorted(cities, key=str.casefold),
    )


@app.get("/api/employees", response_model=list[EmployeeResponse])
def list_employees(db: Session = Depends(get_db), user: User = Depends(require_company_account)):
    employees = (
        db.query(User)
        .filter(User.role == ROLE_EMPLOYEE, User.owner_id == user.id)
        .order_by(User.username.asc())
        .all()
    )
    return employees


@app.post("/api/employees", response_model=EmployeeResponse, status_code=201)
def create_employee(
    data: EmployeeCreate, db: Session = Depends(get_db), user: User = Depends(require_company_account)
):
    username = data.username.strip().lower()
    email = data.email.strip().lower()

    if err := validate_username(username):
        raise HTTPException(status_code=400, detail=err)
    if err := validate_email(email):
        raise HTTPException(status_code=400, detail=err)
    if err := validate_password_confirm(data.password, data.password_confirm):
        raise HTTPException(status_code=400, detail=err)
    if errors := validate_password(data.password):
        raise HTTPException(status_code=400, detail=", ".join(errors))
    if err := validate_employee_email(email, user.email):
        raise HTTPException(status_code=400, detail=err)

    display_name = data.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Personel adı zorunludur")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanılıyor")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    employee = User(
        username=username,
        email=email,
        display_name=display_name,
        password_hash=hash_password(data.password),
        role=ROLE_EMPLOYEE,
        owner_id=user.id,
        email_verified=False,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)

    send_user_verification_email(db, employee)
    return employee


@app.patch("/api/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_company_account),
):
    employee = get_employee_or_404(db, user.id, employee_id)
    display_name = data.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Personel adı zorunludur")
    employee.display_name = display_name
    db.commit()
    db.refresh(employee)
    return employee


@app.delete("/api/employees/{employee_id}")
def delete_employee(
    employee_id: int, db: Session = Depends(get_db), user: User = Depends(require_company_account)
):
    employee = get_employee_or_404(db, user.id, employee_id)
    if employee.id == user.id:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    db.delete(employee)
    db.commit()
    return {"message": "Personel silindi"}


@app.get("/api/lead-requests/pending-count", response_model=PendingRequestCountResponse)
def get_pending_request_count(
    db: Session = Depends(get_db), user: User = Depends(require_company_account)
):
    return PendingRequestCountResponse(count=pending_request_count(db, user.id))


@app.get("/api/lead-requests", response_model=list[LeadRequestResponse])
def list_lead_requests(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    query = db.query(LeadRequest)

    if user.role == ROLE_EMPLOYEE:
        org_id = get_org_id(user)
        query = query.filter(LeadRequest.owner_id == org_id, LeadRequest.requested_by == user.id)
    else:
        if (user.account_type or "company") != "company":
            raise HTTPException(status_code=403, detail="Bu özellik şirket hesapları içindir")
        query = query.filter(LeadRequest.owner_id == user.id)

    if status:
        query = query.filter(LeadRequest.status == status)

    requests = query.order_by(LeadRequest.created_at.desc()).all()
    return [request_response(db, item) for item in requests]


@app.post("/api/lead-requests", response_model=LeadRequestResponse, status_code=201)
def submit_lead_request(
    data: LeadRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(verify_token),
):
    if user.role != ROLE_EMPLOYEE:
        raise HTTPException(status_code=403, detail="Talep oluşturmak için personel hesabı gerekir")

    org_id = get_org_id(user)
    get_category_or_404(db, org_id, data.category)

    if data.oncelik not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Geçersiz öncelik")

    payload = data.model_dump(exclude={"tag_ids", "category", "satis_tutari", "satis_tarihi"})
    request = create_lead_request(
        db,
        owner_id=org_id,
        requested_by=user.id,
        category=data.category,
        data=payload,
        tag_ids=data.tag_ids,
    )
    return request_response(db, request)


@app.post("/api/lead-requests/{request_id}/approve", response_model=LeadResponse)
def approve_request(
    request_id: int, db: Session = Depends(get_db), user: User = Depends(require_company_account)
):
    lead = approve_lead_request(db, user, request_id)
    return lead_response(db, user.id, lead)


@app.post("/api/lead-requests/{request_id}/reject", response_model=LeadRequestResponse)
def reject_request(
    request_id: int,
    data: LeadRequestReject,
    db: Session = Depends(get_db),
    user: User = Depends(require_company_account),
):
    request = reject_lead_request(db, user, request_id, data.rejection_note)
    return request_response(db, request)
