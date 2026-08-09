from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str = "owner"
    account_type: str = "company"
    expires_in: int
    idle_timeout_minutes: int


class PublicConfigResponse(BaseModel):
    idle_timeout_minutes: int


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)
    account_type: Literal["individual", "company"] = "company"
    company_name: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_register(self):
        if self.password != self.password_confirm:
            raise ValueError("Şifreler eşleşmiyor")
        if self.account_type == "company" and not (self.company_name or "").strip():
            raise ValueError("Şirket adı gereklidir")
        return self


class RegisterResponse(BaseModel):
    message: str
    requires_verification: bool = False
    email: Optional[str] = None
    access_token: Optional[str] = None
    token_type: str = "bearer"
    username: Optional[str] = None
    role: Optional[str] = None
    account_type: Optional[str] = None
    expires_in: Optional[int] = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=3, description="Kullanıcı adı veya e-posta")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    username: str
    email: str
    role: str = "owner"
    account_type: str = "company"
    owner_id: int | None = None
    company_name: str | None = None
    display_name: str = ""
    email_verified: bool = False
    company_email_domains: list[str] = Field(default_factory=list)


class UpdateProfileRequest(BaseModel):
    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(default=None, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=8)
    new_password_confirm: Optional[str] = None

    @model_validator(mode="after")
    def validate_update(self):
        changing_password = any(
            [self.current_password, self.new_password, self.new_password_confirm]
        )
        if changing_password:
            if not self.current_password:
                raise ValueError("Mevcut şifre gereklidir")
            if not self.new_password:
                raise ValueError("Yeni şifre gereklidir")
            if self.new_password != (self.new_password_confirm or ""):
                raise ValueError("Şifreler eşleşmiyor")
        return self


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1)
    confirm_username: str = Field(min_length=1)


class EmployeeCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.password_confirm:
            raise ValueError("Şifreler eşleşmiyor")
        return self


class EmployeeUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)


class EmployeeResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str = ""
    email_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    icon: str = Field(default="building-2", max_length=50)


class CategoryCreate(CategoryBase):
    id: Optional[str] = Field(default=None, max_length=50)


class CategoryUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    icon: Optional[str] = Field(default=None, max_length=50)
    id: Optional[str] = Field(default=None, max_length=50)


class CategoryResponse(CategoryBase):
    id: str
    created_at: datetime
    lead_count: int = 0

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    color: str = Field(default="slate", max_length=20)


class TagCreate(TagBase):
    id: Optional[str] = Field(default=None, max_length=50)


class TagUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    color: Optional[str] = Field(default=None, max_length=20)
    id: Optional[str] = Field(default=None, max_length=50)


class TagResponse(TagBase):
    id: str
    is_system: bool = False
    created_at: datetime
    lead_count: int = 0

    class Config:
        from_attributes = True


class LeadBase(BaseModel):
    isletme_adi: str = Field(..., min_length=1)
    yetkili: str = ""
    sehir: str = ""
    instagram: str = ""
    whatsapp: str = ""
    eposta: str = ""
    ilk_iletisim_kanali: str = ""
    ilk_mesaj_tarihi: str = ""
    ilk_mesaj_saati: str = ""
    durum: str = "Yeni"
    oncelik: str = "orta"
    takip_1: str = ""
    takip_2: str = ""
    demo_gonderildi: bool = False
    demo_tarihi: str = ""
    gorusme_tarihi: str = ""
    gorusme_saati: str = ""
    teklif: str = ""
    sonuc: str = ""
    satis_tutari: float = 0
    satis_tarihi: str = ""
    notlar: str = ""


class LeadCreate(LeadBase):
    category: str
    tag_ids: list[str] = Field(default_factory=list)


class LeadUpdate(LeadBase):
    tag_ids: list[str] = Field(default_factory=list)


class LeadResponse(LeadBase):
    id: int
    category: str
    tags: list[TagResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadImportErrorItem(BaseModel):
    row: int
    isletme_adi: str = ""
    error: str


class LeadImportResponse(BaseModel):
    created: int
    failed: int
    skipped: int
    batch_id: int | None = None
    errors: list[LeadImportErrorItem] = Field(default_factory=list)


class LeadImportBatchResponse(BaseModel):
    id: int
    category: str
    filename: str
    created_count: int
    failed_count: int
    skipped_count: int
    lead_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class LeadImportBatchDeleteResponse(BaseModel):
    deleted: int
    message: str


class PlacesUsageResponse(BaseModel):
    month: str
    sku_type: str
    used: int
    free_quota: int
    remaining: int
    warning: bool
    over_quota: bool


class LeadDiscoveryRequest(BaseModel):
    city: str = Field(..., min_length=2, max_length=100)
    district: str = Field(default="", max_length=100)
    sector_keyword: str = Field(..., min_length=2, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    radius_meters: int = Field(default=5000, ge=1000, le=20000)
    confirm_over_quota: bool = False


class LeadDiscoveryResultItem(BaseModel):
    google_place_id: str
    business_name: str
    phone_number: str = ""
    phone_normalized: str = ""
    address: str = ""
    rating: float | None = None
    rating_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    already_in_crm: bool
    existing_lead_id: int | None = None
    low_digital_presence: bool = False


class LeadDiscoveryResponse(BaseModel):
    results: list[LeadDiscoveryResultItem]
    queries_used: int
    total_found: int
    mapped_category: str
    text_query: str
    usage: PlacesUsageResponse
    warning_message: str | None = None


class LeadDiscoveryImportItem(BaseModel):
    google_place_id: str
    business_name: str
    phone_number: str = ""
    address: str = ""
    rating: float | None = None
    rating_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    low_digital_presence: bool = False


class LeadDiscoveryImportRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    city: str = Field(..., min_length=2, max_length=100)
    places: list[LeadDiscoveryImportItem] = Field(..., min_length=1)


class LeadDiscoveryImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    lead_ids: list[int]


class PaginatedLeadResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    demo_gonderildi: int
    cities: list[str] = []


class DashboardItem(BaseModel):
    id: int
    isletme_adi: str
    category: str
    category_label: str
    date: str
    durum: str
    detail: str = ""


class DashboardTaskItem(DashboardItem):
    type: str
    type_label: str
    days_until: int | None = None


class ReminderItem(DashboardItem):
    last_contact_date: str
    days_waiting: int


class AutomationNotification(BaseModel):
    kind: str
    id: int
    isletme_adi: str
    category_label: str
    date: str
    durum: str
    message: str
    days_until: int | None = None
    type: str | None = None


class DailyCategoryContactStat(BaseModel):
    category: str
    category_label: str
    iletisim_sayisi: int


class DailySummarySnippet(BaseModel):
    date: str
    yeni_kayit: int
    yeni_musteri: int
    satis_sayisi: int | None = None
    toplam_gelir: float | None = None
    donusum_orani: float | None = None
    toplam_iletisim: int = 0
    kategori_iletisim: list[DailyCategoryContactStat] = Field(default_factory=list)


class FunnelStage(BaseModel):
    key: str
    label: str
    count: int
    conversion_rate: float | None = None
    overall_rate: float = 0.0


class FunnelResponse(BaseModel):
    satis_hunisi: list[FunnelStage]
    satis_donusum_orani: float


class ConversionStage(BaseModel):
    key: str
    label: str
    count: int
    asama_basari_orani: float | None = None
    onceki_asama_orani: float | None = None
    toplam_orani: float = 0.0


class CityStat(BaseModel):
    sehir: str
    toplam: int
    cevap: int
    satis: int
    cevap_orani: float
    satis_orani: float


class CategoryStat(BaseModel):
    category: str
    category_label: str
    toplam: int
    cevap: int
    satis: int
    cevap_orani: float
    satis_orani: float


class HourStat(BaseModel):
    saat: int
    saat_label: str
    mesaj_sayisi: int
    cevap_sayisi: int
    cevap_orani: float


class DayStat(BaseModel):
    gun: int
    gun_label: str
    mesaj_sayisi: int
    cevap_sayisi: int
    cevap_orani: float


class DailyContactAnalyticsResponse(BaseModel):
    date: str
    date_label: str
    toplam_iletisim: int
    kategori_bazli: list[DailyCategoryContactStat]


class AnalyticsResponse(BaseModel):
    satis_hunisi: list[FunnelStage]
    satis_donusum_orani: float
    donusum_oranlari: list[ConversionStage]
    sehir_analizi: list[CityStat]
    kategori_analizi: list[CategoryStat]
    saat_analizi: list[HourStat]
    gun_analizi: list[DayStat]


class DashboardResponse(BaseModel):
    toplam_kayit: int
    aktif_takip: int
    bugunku_gorevler: int
    bu_hafta_eklenen: int
    cevap_bekleyen_sayisi: int
    cevap_bekleyen_gun: int
    bugunku_gorevler_liste: list[DashboardTaskItem]
    son_gorusmeler: list[DashboardItem]
    yaklasan_takipler: list[DashboardTaskItem]
    son_musteriler: list[DashboardItem]
    cevap_bekleyen_liste: list[ReminderItem]
    otomasyon_bildirimleri: list[AutomationNotification] = []
    gunluk_ozet: DailySummarySnippet | None = None


class ActivityCreate(BaseModel):
    activity_type: str = Field(..., max_length=50)
    title: Optional[str] = Field(default=None, max_length=255)
    description: str = ""
    activity_date: Optional[datetime] = None


class ActivityUpdate(BaseModel):
    activity_type: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    activity_date: Optional[datetime] = None


class ActivityResponse(BaseModel):
    id: int
    lead_id: int
    activity_type: str
    title: str
    description: str
    activity_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class LeadAttachmentResponse(BaseModel):
    id: int
    lead_id: int
    label: str
    original_filename: str
    mime_type: str
    size_bytes: int
    version_number: int = 1
    replaces_attachment_id: int | None = None
    is_archived: bool = False
    archived_at: datetime | None = None
    archived_by_username: str | None = None
    uploaded_by_username: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadAttachmentUpdate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class RevenueCategoryItem(BaseModel):
    category: str
    category_label: str
    gelir: float
    satis_sayisi: int


class RevenueMonthItem(BaseModel):
    ay: str
    ay_label: str
    gelir: float


class RevenueSaleItem(BaseModel):
    id: int
    isletme_adi: str
    category: str
    category_label: str
    sehir: str
    satis_tutari: float
    satis_tarihi: str
    teklif: str


class RevenueResponse(BaseModel):
    toplam_gelir: float
    bu_ay_gelir: float
    bu_yil_gelir: float
    ortalama_satis: float
    satis_sayisi: int
    musteri_sayisi: int
    kategori_dagilimi: list[RevenueCategoryItem]
    aylik_gelir: list[RevenueMonthItem]
    son_satislar: list[RevenueSaleItem]


class LeadRequestCreate(LeadBase):
    category: str
    tag_ids: list[str] = Field(default_factory=list)


class LeadRequestReject(BaseModel):
    rejection_note: str = ""


class LeadRequestResponse(LeadBase):
    id: int
    category: str
    category_label: str
    status: str
    requested_by: int
    requested_by_username: str
    tag_ids: list[str] = Field(default_factory=list)
    rejection_note: str = ""
    reviewed_by_username: str = ""
    reviewed_at: datetime | None = None
    approved_lead_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PendingRequestCountResponse(BaseModel):
    count: int


class ReportStatusItem(BaseModel):
    durum: str
    count: int


class ReportCategoryItem(BaseModel):
    category: str
    category_label: str
    yeni_kayit: int
    musteri: int


class ReportSaleItem(BaseModel):
    isletme_adi: str
    category_label: str
    sehir: str
    satis_tutari: float
    satis_tarihi: str


class ReportPreviousPeriod(BaseModel):
    yeni_kayit: int
    yeni_musteri: int


class ReportResponse(BaseModel):
    period_type: str
    period_label: str
    period_start: str
    period_end: str
    yeni_kayit: int
    yeni_musteri: int
    donusum_orani: float | None = None
    satis_sayisi: int | None = None
    toplam_gelir: float | None = None
    ortalama_satis: float | None = None
    satis_hunisi: list[FunnelStage]
    satis_donusum_orani: float
    durum_dagilimi: list[ReportStatusItem]
    kategori_ozet: list[ReportCategoryItem]
    donem_satislar: list[ReportSaleItem] = Field(default_factory=list)
    onceki_donem: ReportPreviousPeriod


class AiStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    month: str
    tokens_used: int
    tokens_quota: int
    tokens_remaining: int
    request_count: int
    suggest_message_available: bool
    summarize_lead_available: bool = False
    priorities_available: bool = False
    batch_runs_available: bool = False
    agent_runs_available: bool = False
    daily_email_enabled: bool = False
    chat_available: bool = False


class AiChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[AiChatHistoryItem] = Field(default_factory=list, max_length=8)
    locale: str = Field(default="tr", max_length=8)


class AiChatResponse(BaseModel):
    reply: str
    run_id: int
    disclaimer: str


class SuggestMessageRequest(BaseModel):
    lead_id: int = Field(gt=0)
    template_id: str = Field(pattern="^(intro|followUp|demo|meeting)$")
    locale: str = Field(default="tr", max_length=8)


class SuggestMessageResponse(BaseModel):
    text: str
    run_id: int
    disclaimer: str


class IntelligencePeriodKpis(BaseModel):
    label: str
    start: str
    end: str
    yeni_kayit: int
    yeni_musteri: int
    donusum_orani: float | None = None
    satis_donusum_orani: float
    satis_sayisi: int | None = None
    toplam_gelir: float | None = None


class IntelligencePipelineKpis(BaseModel):
    satis_donusum_orani: float | None = None
    funnel_stage_count: int = 0


class IntelligenceKpisResponse(BaseModel):
    computed_at: str
    period_type: str
    period: IntelligencePeriodKpis
    pipeline: IntelligencePipelineKpis
    funnel_stages: list[FunnelStage] = Field(default_factory=list)


class IntelligenceInsightItem(BaseModel):
    id: int
    insight_type: str
    severity: str
    entity_type: str
    entity_id: int | None = None
    title: str
    summary: str
    evidence: dict = Field(default_factory=dict)
    source: str
    created_at: str


class IntelligenceInsightsResponse(BaseModel):
    items: list[IntelligenceInsightItem]


class DiagnosisImpact(BaseModel):
    high_priority_count: int = 0
    medium_priority_count: int = 0
    low_priority_count: int = 0
    estimated_pipeline_value: float | None = None


class DiagnosisPriorityLead(BaseModel):
    lead_id: int
    lead_name: str
    durum: str
    existing_lead_score: int
    diagnosis_modifier: int
    diagnosis_priority_score: int
    priority: str
    reason_codes: list[str] = Field(default_factory=list)
    idle_days: int | None = None
    offer_age_days: int | None = None


class DiagnosisItem(BaseModel):
    diagnosis_id: str
    type: str
    severity: str
    title: str
    description: str
    metric: str
    current_value: float | None = None
    previous_value: float | None = None
    change_percent: float | None = None
    evidence: dict = Field(default_factory=dict)
    affected_lead_count: int = 0
    detected_at: str = ""
    affected_leads_available: bool = True
    impact: DiagnosisImpact = Field(default_factory=DiagnosisImpact)
    top_priority_leads: list[DiagnosisPriorityLead] = Field(default_factory=list)


class DiagnosisListResponse(BaseModel):
    generated_at: str
    duration_ms: int = 0
    period_type: str
    anchor: str
    items: list[DiagnosisItem] = Field(default_factory=list)


class SummarizeLeadRequest(BaseModel):
    lead_id: int = Field(gt=0)
    locale: str = Field(default="tr", max_length=8)


class SummarizeLeadResponse(BaseModel):
    summary: str
    insights: list[IntelligenceInsightItem]
    run_id: int
    disclaimer: str


class PriorityRecommendationItem(BaseModel):
    lead_id: int
    isletme_adi: str
    category_label: str | None = None
    durum: str | None = None
    score: int
    priority: str
    action_type: str
    reasons: list[str] = Field(default_factory=list)
    insight_ids: list[int] = Field(default_factory=list)


class PrioritiesRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=10)
    refresh: bool = False


class PrioritiesResponse(BaseModel):
    recommendations: list[PriorityRecommendationItem]
    run_id: int
    cached: bool = False


class AiRunCreateRequest(BaseModel):
    run_type: str = Field(pattern="^(batch_score|agent)$")
    question: str | None = Field(default=None, max_length=2000)
    locale: str = Field(default="tr", max_length=8)


class AiRunCreateResponse(BaseModel):
    run_id: int
    status: str
    run_type: str


class AiRunDetailResponse(BaseModel):
    id: int
    run_type: str
    status: str
    input: dict = Field(default_factory=dict)
    output: dict | None = None
    steps: list[dict] = Field(default_factory=list)
    error_code: str | None = None
    created_at: str
    updated_at: str
    duration_ms: int | None = None


class AiRunListResponse(BaseModel):
    items: list[AiRunDetailResponse]


class ActionProposalItem(BaseModel):
    id: int
    lead_id: int | None = None
    lead_name: str | None = None
    proposed_action: str
    payload: dict = Field(default_factory=dict)
    status: str
    created_at: str


class ActionProposalListResponse(BaseModel):
    items: list[ActionProposalItem]


class ActionProposalCreateRequest(BaseModel):
    lead_id: int = Field(gt=0)


class ActionProposalResolveRequest(BaseModel):
    approve: bool


class CompanyProfileResponse(BaseModel):
    version: str = "v1"
    computed_at: str
    period_label: str | None = None
    yeni_kayit: int | None = None
    yeni_musteri: int | None = None
    satis_donusum_orani: float | None = None
    pipeline_conversion: float | None = None
    cevap_bekleyen_sayisi: int = 0
    bugunku_gorevler: int = 0
    best_lead_source: dict | None = None
    lost_or_stalled_leads: int = 0
    top_insights: list[dict] = Field(default_factory=list)
    total_leads: int = 0
