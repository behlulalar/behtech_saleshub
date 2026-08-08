"""Limited read-only agent (max steps, no write tools)."""

import json
import re
import time

from sqlalchemy.orm import Session

from ai.llm_client import AiNotConfiguredError, assert_llm_configured, chat_completion
from ai.store import append_run_step
from ai.tools import TOOL_REGISTRY, execute_tool
from database import AiRun, User

MAX_AGENT_STEPS = 5

SYSTEM_PROMPT = """Sen BehTech Sales Hub satış asistanısın. Yalnızca verilen araçları kullan.
Her turda YALNIZCA tek satır JSON döndür:
{"tool":"<name>","args":{...}}  veya  {"final":"<Türkçe cevap>"}
İzinli araçlar: get_lead, list_leads, get_kpis, get_insights.
Lead/durum değiştiremez, mesaj gönderemezsin."""


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
    started = time.perf_counter()
    tool_names = ", ".join(TOOL_REGISTRY.keys())
    context_lines = [f"Kullanıcı sorusu ({locale}): {question}", f"Araçlar: {tool_names}"]
    final_answer = ""

    for step_idx in range(1, MAX_AGENT_STEPS + 1):
        user_msg = "\n".join(context_lines)
        try:
            reply, usage = chat_completion(system=SYSTEM_PROMPT, user=user_msg)
        except AiNotConfiguredError:
            raise
        except Exception as exc:
            append_run_step(
                db,
                run,
                {"step": step_idx, "type": "llm_error", "detail": str(exc)[:200]},
            )
            raise

        append_run_step(
            db,
            run,
            {
                "step": step_idx,
                "type": "llm",
                "usage": usage,
                "raw": reply[:500],
            },
        )

        parsed = _parse_agent_line(reply)
        if not parsed:
            final_answer = reply.strip()
            break

        if "final" in parsed and parsed["final"]:
            final_answer = str(parsed["final"]).strip()
            append_run_step(db, run, {"step": step_idx, "type": "final", "text": final_answer[:500]})
            break

        tool_name = parsed.get("tool")
        if not tool_name or tool_name not in TOOL_REGISTRY:
            context_lines.append(f"Asistan çıktısı geçersiz: {reply[:300]}")
            continue

        args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
        tool_result = execute_tool(db, org_id, str(tool_name), args)
        append_run_step(
            db,
            run,
            {"step": step_idx, "type": "tool", "tool": tool_name, "args": args, "result": tool_result},
        )
        context_lines.append(f"Araç {tool_name} sonucu: {json.dumps(tool_result, ensure_ascii=False)[:2000]}")

    if not final_answer:
        final_answer = "Yeterli veri toplanamadı; lütfen soruyu daraltın veya dashboard KPI’larına bakın."

    duration_ms = int((time.perf_counter() - started) * 1000)
    output = {"answer": final_answer, "steps_used": step_idx}
    return final_answer, {"output": output, "duration_ms": duration_ms, "tokens_total": None}
