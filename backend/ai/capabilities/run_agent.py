"""Limited read-only agent (max steps, no write tools)."""

import json
import re
import time

from sqlalchemy.orm import Session

from ai.llm_client import AiNotConfiguredError, assert_llm_configured, chat_completion
from ai.run_log_redact import redact_run_step
from ai.store import append_run_step
from ai.tools import TOOL_REGISTRY, execute_tool
from ai.usage import QuotaExceededError, assert_quota_available, record_usage
from config import settings
from database import AiRun, User

MAX_AGENT_STEPS = 5

SYSTEM_PROMPT = """Sen BehTech Sales Hub satış asistanısın. Yalnızca verilen araçları kullan.
Her turda YALNIZCA tek satır JSON döndür:
{"tool":"<name>","args":{...}}  veya  {"final":"<Türkçe cevap>"}
İzinli araçlar: get_lead, list_leads, get_kpis, get_insights.
Lead/durum değiştiremez, mesaj gönderemezsin."""


def _estimated_tokens_per_step() -> int:
    return int(settings.ai_max_output_tokens) + 400


def _aggregate_usage(usage: dict) -> tuple[int, int, int]:
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or 0)
    if total <= 0:
        total = prompt + completion
    return prompt, completion, total


def _parse_agent_line(text: str) -> dict | None:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def run_agent_query(
    db: Session,
    *,
    user: User,
    org_id: int,
    run: AiRun,
    question: str,
    locale: str = "tr",
) -> tuple[str, dict]:
    assert_llm_configured()
    per_step = _estimated_tokens_per_step()
    assert_quota_available(db, org_id, estimated_tokens=per_step * MAX_AGENT_STEPS)

    started = time.perf_counter()
    tool_names = ", ".join(TOOL_REGISTRY.keys())
    context_lines = [f"Kullanıcı sorusu ({locale}): {question}", f"Araçlar: {tool_names}"]
    final_answer = ""
    step_idx = 0
    total_prompt = 0
    total_completion = 0
    total_tokens = 0

    for step_idx in range(1, MAX_AGENT_STEPS + 1):
        assert_quota_available(db, org_id, estimated_tokens=per_step)
        user_msg = "\n".join(context_lines)
        try:
            reply, usage = chat_completion(system=SYSTEM_PROMPT, user=user_msg)
        except AiNotConfiguredError:
            raise
        except QuotaExceededError:
            raise
        except Exception as exc:
            append_run_step(
                db,
                run,
                redact_run_step({"step": step_idx, "type": "llm_error", "detail": str(exc)[:200]}),
            )
            raise

        p, c, t = _aggregate_usage(usage)
        total_prompt += p
        total_completion += c
        total_tokens += t if t > 0 else max(1, (len(user_msg) + len(reply or "")) // 4)

        append_run_step(
            db,
            run,
            redact_run_step(
                {
                    "step": step_idx,
                    "type": "llm",
                    "usage": {"prompt_tokens": p, "completion_tokens": c, "total_tokens": t or None},
                    "raw": (reply or "")[:500],
                }
            ),
        )

        parsed = _parse_agent_line(reply or "")
        if not parsed:
            final_answer = (reply or "").strip()
            break

        if "final" in parsed and parsed["final"]:
            final_answer = str(parsed["final"]).strip()
            append_run_step(
                db,
                run,
                redact_run_step({"step": step_idx, "type": "final", "text": final_answer[:500]}),
            )
            break

        tool_name = parsed.get("tool")
        if not tool_name or tool_name not in TOOL_REGISTRY:
            context_lines.append(f"Asistan çıktısı geçersiz: {(reply or '')[:300]}")
            continue

        args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
        tool_result = execute_tool(db, org_id, str(tool_name), args)
        append_run_step(
            db,
            run,
            redact_run_step(
                {
                    "step": step_idx,
                    "type": "tool",
                    "tool": tool_name,
                    "args": args,
                    "result": tool_result,
                }
            ),
        )
        context_lines.append(f"Araç {tool_name} sonucu: {json.dumps(tool_result, ensure_ascii=False)[:2000]}")

    if not final_answer:
        final_answer = "Yeterli veri toplanamadı; lütfen soruyu daraltın veya dashboard KPI’larına bakın."

    if total_tokens > 0:
        record_usage(db, org_id, total_tokens)

    duration_ms = int((time.perf_counter() - started) * 1000)
    output = {"answer": final_answer, "steps_used": step_idx}
    return final_answer, {
        "output": output,
        "duration_ms": duration_ms,
        "tokens_prompt": total_prompt or None,
        "tokens_completion": total_completion or None,
        "tokens_total": total_tokens,
    }
