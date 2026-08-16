# Architecture freeze — AI & Intelligence layers

## AI Capability Layer (Faz 0–7)

| Faz | Scope | Status |
|-----|--------|--------|
| 0–1 | AI router, quota, message coach, OpenAI | Done |
| 2 | Lead summary, owner priorities, stable cache | Done |
| 3 | Runs, batch score, agent tools, action proposals (queue v1) | Done |
| 4 | Company intelligence profile, daily email paragraph | Done |
| 5 | Global sales assistant chat (`POST /api/ai/chat`) | Done |
| 6 | Proposal approval → CRM side effects (takip/görüşme + activity + open lead) | Done |
| 7 | Sales chat SSE streaming (`POST /api/ai/chat/stream`) | Done |

## Sales Diagnosis & Assistant (DE-3 → DE-6)

| Epic | Scope | Status |
|------|--------|--------|
| **DE-3** | Deterministic diagnosis engine + optional LLM interpret | Done |
| **DE-4** | Executable `ai_actions` lifecycle, proposal bridge, duplicate hardening, inbox UX | Done |
| **DE-5** | Diagnosis cases/snapshots, sync, history API/UI, trend, historical interpret | Done |
| **DE-6** | Persistent Sales Assistant, CRM tools, Redis working memory, entity continuity, pending-offer consistency, full-screen UI | Done |

## Design constraints (still in force)

- No classical RAG / vector search for CRM truth
- Diagnosis evidence comes from PostgreSQL + analytics rules
- Assistant CRM tools are **read-only**
- Critical amounts (offers) must come from tools, not model invention
- `organization_id` / `user_id` are server-controlled
- Optional later: richer agent write tools (only with audit + approval)

See also: root [README.md](../../README.md)
