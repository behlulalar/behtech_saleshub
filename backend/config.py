from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_SECRET_KEYS = frozenset({
    "degistirin-bunu-guclu-bir-anahtar-ile",
    "crm-gizli-anahtar-degistirin-2026-guclu-bir-deger",
    "change-me",
    "secret",
})

WEAK_ADMIN_PASSWORDS = frozenset({
    "MuhammeD''123",
    "admin",
    "password",
    "12345678",
})


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "degistirin-bunu-guclu-bir-anahtar-ile"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    remember_me_expire_days: int = 30
    idle_timeout_minutes: int = 30
    leads_page_size: int = 50
    leads_page_size_max: int = 100

    database_url: str = "postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_url: str = "http://localhost:5173"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "BehTech Sales Hub"
    smtp_reply_to: str = ""
    smtp_align_from_user: bool = True

    password_reset_expire_minutes: int = 60
    email_verification_expire_hours: int = 48
    email_verification_enabled: bool = False
    rate_limit_login: str = "10/minute"
    rate_limit_register: str = "5/hour"
    rate_limit_forgot_password: str = "3/hour"
    rate_limit_verify_email: str = "30/hour"
    rate_limit_resend_verification: str = "5/hour"

    seed_admin_username: str = "behlul"
    seed_admin_email: str = "behlul@local.crm"
    seed_admin_password: str = "MuhammeD''123"
    followup_reminder_days: int = 3
    diagnosis_engine_enabled: bool = True
    meeting_reminder_days: int = 3
    automation_email_enabled: bool = True
    company_email_domains: str = "behtechlabs.com"

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 15
    allowed_upload_extensions: str = ".pdf,.png,.jpg,.jpeg,.doc,.docx"
    allowed_upload_mime_types: str = (
        "application/pdf,"
        "image/png,"
        "image/jpeg,"
        "application/msword,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    google_places_api_key: str = ""
    places_free_quota_monthly: int = 1000
    places_quota_warning: int = 800
    places_grid_cell_meters: int = 2500
    places_max_grid_cells: int = 9
    places_low_rating_count_threshold: int = 10
    places_rescan_hours: int = 24

    ai_enabled: bool = False
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_chat: str = ""
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    ai_monthly_token_quota: int = 200_000
    ai_max_output_tokens: int = 600
    ai_llm_timeout_sec: int = 25
    ai_include_pii: bool = False
    ai_include_notes: bool = True
    ai_store_output: bool = False
    ai_rate_limit: str = "20/minute"
    ai_daily_email: bool = False
    ai_chat_enabled: bool = False
    ai_provider: str = "openai"
    """Primary LLM vendor for general AI features (openai|azure). DE-3 interpret always uses OpenAI API only."""
    # DE-3: AI Diagnosis Interpreter (POST /api/ai/diagnosis/interpret)
    ai_diagnosis_interpret_enabled: bool = False
    ai_diagnosis_model: str = ""
    """OpenAI model id for diagnosis interpret; empty uses openai_chat_model. Azure: deployment name override if set."""
    ai_diagnosis_interpret_cache_ttl_hours: int = 48
    ai_diagnosis_interpret_max_output_tokens: int = 450
    ai_diagnosis_interpret_temperature: float = 0.2
    ai_diagnosis_interpret_estimated_tokens: int = 1200
    ai_de4_interpret_proposal_bridge_enabled: bool = False
    # DE-5.1-C: Historical diagnosis interpretation (POST /api/ai/diagnosis/history/interpret)
    ai_diagnosis_history_interpret_enabled: bool = False
    ai_diagnosis_history_interpret_cache_ttl_hours: int = 48
    ai_diagnosis_history_interpret_estimated_tokens: int = 1400

    # DE-6.5 — optional Redis working memory (default OFF; PG remains authoritative)
    assistant_memory_enabled: bool = False
    assistant_memory_redis_url: str = "redis://127.0.0.1:6379/0"
    assistant_memory_ttl_seconds: int = 86400
    assistant_memory_max_messages: int = 12
    assistant_memory_max_chars: int = 14000
    assistant_memory_socket_timeout_sec: float = 0.5

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    def validate_production(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []

        if self.secret_key in WEAK_SECRET_KEYS or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be at least 32 characters and not a default placeholder")

        if self.seed_admin_password in WEAK_ADMIN_PASSWORDS:
            errors.append("SEED_ADMIN_PASSWORD must be changed from the default value")

        if "localhost" in self.app_url or "127.0.0.1" in self.app_url:
            errors.append("APP_URL must use the production domain (not localhost)")

        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origin_list):
            errors.append("CORS_ORIGINS must not include localhost in production")

        if self.email_verification_enabled and not self.smtp_configured:
            errors.append("SMTP must be configured when EMAIL_VERIFICATION_ENABLED=true")

        if errors:
            raise RuntimeError(
                "Production configuration errors:\n- " + "\n- ".join(errors)
            )


settings = Settings()
