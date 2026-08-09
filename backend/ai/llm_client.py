from collections.abc import Iterator

import httpx
from openai import AzureOpenAI, OpenAI

from ai.llm_config import (
    diagnosis_provider_and_model,
    provider_and_model,
    uses_azure_openai,
    uses_openai_api,
)
from config import settings


class AiNotConfiguredError(RuntimeError):
    pass


class DiagnosisOpenAiRequiredError(AiNotConfiguredError):
    """DE-3 interpret requires direct OpenAI API; Azure is not used."""


def assert_llm_configured() -> None:
    if not settings.ai_enabled:
        raise AiNotConfiguredError("AI disabled")
    if not uses_openai_api() and not uses_azure_openai():
        raise AiNotConfiguredError("OpenAI or Azure OpenAI not configured")


def assert_diagnosis_openai_configured() -> None:
    if not settings.ai_enabled:
        raise AiNotConfiguredError("AI disabled")
    if not uses_openai_api():
        raise DiagnosisOpenAiRequiredError(
            "Teşhis yorumu için OpenAI gerekli (OPENAI_API_KEY). Azure bu özellikte kullanılmaz."
        )


def chat_completion(*, system: str, user: str) -> tuple[str, dict]:
    assert_llm_configured()
    _provider, model = provider_and_model()
    timeout = settings.ai_llm_timeout_sec
    http_client = httpx.Client(timeout=timeout)

    if uses_openai_api():
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=timeout,
            http_client=http_client,
        )
    else:
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version="2024-08-01-preview",
            azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
            timeout=timeout,
            http_client=http_client,
        )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=settings.ai_max_output_tokens,
        temperature=0.7,
    )
    choice = response.choices[0].message.content or ""
    usage_obj = response.usage
    usage = {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", None) if usage_obj else None,
        "completion_tokens": getattr(usage_obj, "completion_tokens", None) if usage_obj else None,
        "total_tokens": getattr(usage_obj, "total_tokens", None) if usage_obj else None,
    }
    return choice, usage


def chat_completion_messages(*, messages: list[dict]) -> tuple[str, dict]:
    assert_llm_configured()
    _provider, model = provider_and_model()
    timeout = settings.ai_llm_timeout_sec
    http_client = httpx.Client(timeout=timeout)

    if uses_openai_api():
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=timeout,
            http_client=http_client,
        )
    else:
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version="2024-08-01-preview",
            azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
            timeout=timeout,
            http_client=http_client,
        )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=settings.ai_max_output_tokens,
        temperature=0.5,
    )
    choice = response.choices[0].message.content or ""
    usage_obj = response.usage
    usage = {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", None) if usage_obj else None,
        "completion_tokens": getattr(usage_obj, "completion_tokens", None) if usage_obj else None,
        "total_tokens": getattr(usage_obj, "total_tokens", None) if usage_obj else None,
    }
    return choice, usage


def _openai_client():
    timeout = settings.ai_llm_timeout_sec
    http_client = httpx.Client(timeout=timeout)
    if uses_openai_api():
        return OpenAI(
            api_key=settings.openai_api_key,
            timeout=timeout,
            http_client=http_client,
        )
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version="2024-08-01-preview",
        azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
        timeout=timeout,
        http_client=http_client,
    )


def _openai_direct_client() -> OpenAI:
    """DE-3 only: direct OpenAI API (never AzureOpenAI)."""
    timeout = settings.ai_llm_timeout_sec
    http_client = httpx.Client(timeout=timeout)
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=timeout,
        http_client=http_client,
    )


def stream_chat_completion_messages(
    *,
    messages: list[dict],
    usage_out: dict | None = None,
) -> Iterator[str]:
    assert_llm_configured()
    _provider, model = provider_and_model()
    client = _openai_client()
    create_kwargs: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": settings.ai_max_output_tokens,
        "temperature": 0.5,
        "stream": True,
    }
    if uses_openai_api():
        create_kwargs["stream_options"] = {"include_usage": True}
    stream = client.chat.completions.create(**create_kwargs)
    for chunk in stream:
        usage_obj = getattr(chunk, "usage", None)
        if usage_obj and usage_out is not None:
            usage_out["prompt_tokens"] = getattr(usage_obj, "prompt_tokens", None)
            usage_out["completion_tokens"] = getattr(usage_obj, "completion_tokens", None)
            usage_out["total_tokens"] = getattr(usage_obj, "total_tokens", None)
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def strip_llm_json_content(text: str) -> str:
    """Remove optional markdown fences from model output before JSON parse."""
    s = (text or "").strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _usage_from_response(response) -> dict:
    usage_obj = response.usage
    return {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", None) if usage_obj else None,
        "completion_tokens": getattr(usage_obj, "completion_tokens", None) if usage_obj else None,
        "total_tokens": getattr(usage_obj, "total_tokens", None) if usage_obj else None,
    }


def chat_completion_structured(
    *,
    system: str,
    user: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> tuple[str, dict]:
    """
    Chat completion with JSON object response (DE-3 diagnosis interpret).
    Always uses direct OpenAI API; never AzureOpenAI.
    Does not alter existing chat_completion / chat_completion_messages behavior.
    """
    assert_diagnosis_openai_configured()
    _provider, resolved_model = diagnosis_provider_and_model()
    assert _provider == "openai"
    resolved_model = model or resolved_model
    temp = settings.ai_diagnosis_interpret_temperature if temperature is None else temperature
    max_out = settings.ai_diagnosis_interpret_max_output_tokens if max_tokens is None else max_tokens

    client = _openai_direct_client()
    create_kwargs: dict = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_out,
        "temperature": temp,
        "response_format": {"type": "json_object"},
    }
    response = client.chat.completions.create(**create_kwargs)
    choice_obj = response.choices[0]
    choice = choice_obj.message.content or ""
    usage = _usage_from_response(response)
    usage["finish_reason"] = getattr(choice_obj, "finish_reason", None)
    return strip_llm_json_content(choice), usage
