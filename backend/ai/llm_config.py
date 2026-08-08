from config import settings


def uses_openai_api() -> bool:
    return bool(settings.openai_api_key.strip())


def uses_azure_openai() -> bool:
    return bool(
        settings.azure_openai_endpoint.strip()
        and settings.azure_openai_api_key.strip()
        and settings.azure_openai_deployment_chat.strip()
    )


def ai_is_configured() -> bool:
    return uses_openai_api() or uses_azure_openai()


def provider_and_model() -> tuple[str, str]:
    if uses_openai_api():
        model = settings.openai_chat_model.strip() or "gpt-4o-mini"
        return "openai", model
    if uses_azure_openai():
        return "azure_openai", settings.azure_openai_deployment_chat.strip()
    raise RuntimeError("LLM not configured")
