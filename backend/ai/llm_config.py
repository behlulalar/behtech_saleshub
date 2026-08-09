from config import settings


def uses_openai_api() -> bool:
    return bool(settings.openai_api_key.strip())


def uses_azure_openai() -> bool:
    return bool(
        settings.azure_openai_endpoint.strip()
        and settings.azure_openai_api_key.strip()
        and settings.azure_openai_deployment_chat.strip()
    )


def normalized_ai_provider() -> str:
    return (settings.ai_provider or "openai").strip().lower()


def ai_is_configured() -> bool:
    if normalized_ai_provider() == "azure":
        return uses_azure_openai() or uses_openai_api()
    return uses_openai_api() or uses_azure_openai()


def provider_and_model() -> tuple[str, str]:
    if normalized_ai_provider() == "azure" and uses_azure_openai():
        return "azure_openai", settings.azure_openai_deployment_chat.strip()
    if uses_openai_api():
        model = settings.openai_chat_model.strip() or "gpt-4o-mini"
        return "openai", model
    if uses_azure_openai():
        return "azure_openai", settings.azure_openai_deployment_chat.strip()
    raise RuntimeError("LLM not configured")


def diagnosis_openai_available() -> bool:
    """DE-3 may call OpenAI only when key is present (never Azure)."""
    return uses_openai_api()


def diagnosis_provider_and_model() -> tuple[str, str]:
    """
    DE-3 diagnosis interpret: always OpenAI API + OPENAI_API_KEY.
    Azure credentials are ignored for this capability.
    """
    if not diagnosis_openai_available():
        raise RuntimeError("DE-3 requires OpenAI (OPENAI_API_KEY)")
    override = settings.ai_diagnosis_model.strip()
    model = override or settings.openai_chat_model.strip() or "gpt-4o-mini"
    return "openai", model
