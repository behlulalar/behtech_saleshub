<p align="center">
  <img src="docs/assets/behtech-logo.png" alt="BehTech — Beyond The Code" width="320" />
</p>

<h1 align="center">BehTech Sales Hub</h1>

<p align="center">
  <strong>Multi-tenant sales CRM · Deterministic Sales Diagnosis · Human-approved AI actions · Grounded Sales Assistant</strong><br/>
  <em>Beyond The Code — BehTech Labs</em>
</p>

<p align="center">
  <a href="https://saleshub.behtechlabs.com">Live</a> ·
  <a href="./README.tr.md">Türkçe</a> ·
  <a href="./DEPLOY.md">Deploy</a> ·
  <a href="./docs/architecture/ARCHITECTURE_FREEZE.md">AI architecture</a> ·
  <a href="./LICENSE">MIT License</a>
</p>

---

## Overview

**BehTech Sales Hub** is a production CRM for field sales and market-research teams. It combines the lead pipeline, tasks, reports, revenue tracking, a rule-based sales diagnosis engine and an optional AI layer (OpenAI or Azure OpenAI) in one app.

The AI layer is built around a few rules that hold everywhere in the codebase:

- **The CRM is the source of truth.** The model reads data through tools. It never makes up offer amounts, dates, reasons or purchase chances.
- **Diagnosis logic runs without AI.** Problems are found by deterministic rules over PostgreSQL. The LLM only explains and suggests.
- **AI can suggest but not act on its own.** Every change to CRM data goes through a typed action with a policy check, owner approval and an idempotent executor.
- **Tenants are isolated on the server.** `organization_id` / `user_id` are set by the backend and never accepted from the model.
- **Off by default.** Each AI feature has its own flag and every organization has a monthly token quota.

Live: [saleshub.behtechlabs.com](https://saleshub.behtechlabs.com)

---

## Roles

| Role | Access |
|------|--------|
| **Owner (organization)** | Dashboard, revenue, analytics, staff management, Intelligence, AI operations, action approvals |
| **Employee** | Leads in assigned categories, lead requests; revenue and owner tools are hidden |

All records are scoped to the organization.

---

## CRM core

| Area | What it does |
|------|--------------|
| Lead management | Categories, status, priority, tags, notes, offer amount, attachments |
| Sales funnel | Contacted → Replied → Demo → Offer → Sale |
| Activity timeline | Messages, demos, offers, meetings, status changes |
| Payments & revenue | Payments recorded separately from offers; each payment counts in the month it was recorded; month/year filters |
| Lead requests | Employee request → owner approval → lead created in a category |
| Lead discovery & import | Google Places (New) grid search with quota tracking, Excel import |
| Reports & analytics | Period reports (XLSX / PDF export), city / category / hour-of-day breakdowns |
| Tasks & reminders | Quick tasks from existing businesses, follow-up reminders |
| Email automation | Morning and end-of-day summaries over SMTP, including that day's payments |
| Auth | JWT + HttpOnly "Remember me" refresh sessions, email verification, idle timeout, rate limiting |
| i18n | Turkish / English UI |

---

## AI & Intelligence layer

```mermaid
flowchart LR
    PG[(PostgreSQL<br/>CRM data)] --> DE[Diagnosis Engine<br/>deterministic rules]
    PG --> SC[Lead scoring<br/>rule-based]
    DE --> CASES[(Diagnosis cases<br/>+ snapshots)]
    CASES --> TREND[Trend & history]
    DE --> INT[LLM interpreter<br/>JSON-only, grounded]
    TREND --> HINT[Historical interpreter]
    INT --> MAP[Mapper + dedup]
    MAP --> ACT[ai_actions<br/>proposed]
    ACT -->|owner approves| EXE[Executor<br/>idempotent, row-locked]
    EXE --> PG
    PG --> TOOLS[Read-only CRM tools]
    TOOLS --> ASSIST[Sales Assistant<br/>tool-calling + SSE]
    REDIS[(Redis<br/>working memory)] -.-> ASSIST
```

### 1. Intelligence (deterministic, no LLM needed)

| Component | What it does |
|-----------|--------------|
| Lead scoring | Rule-based 0–100 score from priority, idle days and pipeline stage, with reasons and a suggested `action_type` |
| Recommendations | Stored `IntelligenceRecommendation` records |
| Org insights | Signals such as a growing "awaiting reply" backlog |
| Company profile | Monthly KPI snapshot, best lead source |
| KPI API | Wraps the existing reports and analytics |

### 2. Sales Diagnosis Engine (DE-3 → DE-5)

A rule engine that finds **why** sales are stalling. It uses no vector search and no classical RAG. Evidence comes straight from PostgreSQL and the analytics layer.

**Diagnosis types**

| Type | Detects |
|------|---------|
| `funnel_drop` | Conversion drops between funnel stages (daily / weekly / monthly compared with the previous period, graded by relative and absolute drop) |
| `follow_up` | Leads waiting too long without contact |
| `offer` | Offers that have gone stale without turning into a sale |

Each diagnosis includes **evidence**, **impact** (affected leads, counts), a **severity**, a **priority** and the top-priority leads behind it.

**Lifecycle and history (DE-5)**

- Diagnoses are stored as `diagnosis_cases` with `diagnosis_snapshots`, deduplicated by an observation fingerprint.
- States: `new → active → improving / worsening → resolved`, with reopen tracking.
- Trend analysis without AI: snapshot diffs, reason codes, direction, worst point, episode duration and reopen count.
- History API and UI: timeline modal, trend view, per-period drill-down.

**AI interpretation (optional)**

- `POST /api/ai/diagnosis/interpret` turns a diagnosis into a summary, "why it matters", key findings and recommended actions.
- `POST /api/ai/diagnosis/history/interpret` does the same for a diagnosis's history.
- Grounded prompt: numbers, lead names and rates may come **only** from the supplied JSON context. No invented revenue, reasons, competitors or percentages.
- JSON-only output, checked against a Pydantic schema. Invalid output is rejected, including invalid cached output.
- Low temperature (0.2), output token cap, and a result cache with a TTL (48 h by default) to control cost.

### 3. Human-in-the-loop AI actions (DE-4)

The AI can **propose** CRM changes. An owner decides whether they run.

**Flow:** DE-3 recommended actions → deterministic **mapper** → **dedup** by `(action_type, lead_id)` → `ai_actions` in `proposed` state → owner reviews, edits or cancels in the **Actions inbox** → **approve** → **execute**.

**State machine**

```
proposed → approved → executing → executed
    │          │                 └→ failed
    └──────────┴→ cancelled / expired
```

**Closed action registry**: new action types cannot be registered at runtime. Each type has a Pydantic parameter model, a risk level, a permission class and allowed roles.

| Allowed (owner confirmation required) | Risk |
|---------------------------------------|------|
| `propose_follow_up_task` | low |
| `propose_log_activity` | low |
| `propose_note_append` | low |
| `open_whatsapp_draft` (client-side `wa.me` link only, never sent by the server) | low |
| `propose_meeting_date` | medium |
| `propose_priority_change` | medium |
| `propose_status_change` | medium |

| Blocked (`NOT_ALLOWED_FOR_AI` / `ADMIN_ONLY`) |
|------------------------------------------------|
| Sending WhatsApp messages from the server, deleting leads, activities or attachments, bulk import, creating leads, recording sales, changing revenue, approving lead requests, batch rescoring |

**Safety measures:** mandatory idempotency keys, `SELECT … FOR UPDATE` row locking during execution, uniqueness checks against duplicate proposals, and a concurrency test suite.

### 4. Sales Assistant (DE-6)

A full-screen, tool-calling sales assistant that answers questions from real CRM data.

- **Persistent conversations** in PostgreSQL (`assistant_conversations`, `assistant_messages`) with sidebar, search, rename and archive.
- **SSE streaming** (`POST /api/ai/chat/stream`) with readable tool-status labels ("Searching leads…").
- **10 read-only CRM tools**:

  | Tool | Purpose |
  |------|---------|
  | `search_leads` | Fuzzy business-name search with ambiguity detection |
  | `get_lead` | Lead details |
  | `get_lead_offer` | Offer status and amount for one lead |
  | `get_lead_activities` | Activity timeline |
  | `get_sales_metrics` | Sales and funnel metrics |
  | `get_followup_candidates` | Leads that need follow-up |
  | `get_diagnoses` / `get_diagnosis` | Active diagnoses |
  | `get_pending_offers` | Every offer that has not closed yet |
  | `get_daily_sales_brief` | Ranked daily priorities |

- **Factuality rules**: every answer separates *fact* (seen in tool output), *inference* (a cautious deduction) and *unknown* (not in the CRM). Claims like "80% likely to buy" or "found the price too high" are forbidden unless the CRM contains them.
- **Pending-offer consistency**: when the user asks about pending offers across the portfolio, the backend forces a `get_pending_offers` call through `tool_choice`, so the answer never relies on memory or an older summary.
- **Entity continuity (DE-6.7)**: the conversation keeps track of the active lead. Follow-ups like "why didn't it close?" or "last activity?" stay on that lead, while broad questions ("what should I do today?") go back to portfolio tools.
- **Redis working memory (DE-6.5)**: an optional short-term cache (TTL, message and character limits). PostgreSQL stays authoritative. Redis errors never break the chat.
- **Proactive daily brief**: ranks high-severity diagnosis leads, long-idle follow-ups and stale offers.
- Answers in the user's language (Turkish / English). Tool iterations are capped at 6.

### 5. Other AI capabilities

| Capability | Description |
|------------|-------------|
| Message coach | Drafts WhatsApp / Instagram messages for a lead (intro, follow-up, demo, meeting templates) |
| Lead summary | AI summary and insights for one lead |
| Priority list | Owner dashboard priority list with a stable cache |
| AI runs | Background batch lead scoring and a limited read-only agent (max 5 steps), with run history |
| Daily email paragraph | Adds a short AI paragraph to the morning / end-of-day email. If the LLM fails, the email is sent without it |

### Privacy, cost and observability

- **PII masking**: emails and phone numbers are masked before reaching the model unless `AI_INCLUDE_PII=true`.
- **Run-log redaction**: agent step logs are cleaned of PII before they are stored.
- **Output storage is opt-in** (`AI_STORE_OUTPUT`).
- **Monthly token quota** per organization, a pre-flight token estimate, and a request rate limit (`20/minute` by default).
- `GET /api/ai/status` shows which capabilities are available and how much quota is used.
- **Provider routing**: OpenAI or Azure OpenAI for general AI. Diagnosis interpretation always uses the OpenAI API.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, **FastAPI**, SQLAlchemy 2, Pydantic 2, PostgreSQL |
| Frontend | **React 18**, TypeScript, **Vite**, Tailwind CSS, lucide-react |
| Auth | JWT (python-jose), bcrypt, HttpOnly refresh sessions, slowapi rate limiting |
| AI | OpenAI API or Azure OpenAI (`gpt-4o-mini` by default), function calling, SSE |
| Working memory | Redis (optional) |
| Integrations | Google Places API (New), SMTP (Google Workspace) |
| Exports | openpyxl (XLSX), ReportLab (PDF) |
| Deploy | Docker Compose, systemd, Nginx (Cloudflare real-IP + rate limits), scheduled backups to Google Drive (rclone) |

---

## Quick start (local)

### Requirements

- Python 3.10+
- Node.js 18+
- Docker Desktop (PostgreSQL; Redis recommended for assistant memory)

### Run

```bash
chmod +x start.sh
./start.sh
```

Open **http://localhost:5173**.

### First-time setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Fill in `SECRET_KEY`, `DATABASE_URL` and, if needed, SMTP / OpenAI / Redis / Google Places.
3. Start PostgreSQL with `docker compose up -d` (default port **5433**).

```env
DATABASE_URL=postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db
```

The seed admin is created from `SEED_ADMIN_USERNAME` / `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`. Keep these in `.env` only and never commit real values.

---

## Configuration (AI flags)

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_ENABLED` | `false` | Turns the whole AI layer on or off |
| `AI_PROVIDER` | `openai` | `openai` or `azure` |
| `OPENAI_API_KEY` / `OPENAI_CHAT_MODEL` | — / `gpt-4o-mini` | Direct OpenAI |
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT_CHAT` | — | Azure OpenAI |
| `AI_MONTHLY_TOKEN_QUOTA` | `400000` | Monthly token budget per organization |
| `AI_MAX_OUTPUT_TOKENS` / `AI_LLM_TIMEOUT_SEC` | `600` / `25` | Per-call limits |
| `AI_INCLUDE_PII` / `AI_INCLUDE_NOTES` / `AI_STORE_OUTPUT` | `false` / `true` / `false` | Data sent to or kept from the model |
| `AI_CHAT_ENABLED` | `false` | Sales Assistant |
| `AI_DAILY_EMAIL` | `false` | AI paragraph in the daily emails |
| `AI_DIAGNOSIS_INTERPRET_ENABLED` | `false` | DE-3 diagnosis interpretation |
| `AI_DIAGNOSIS_HISTORY_INTERPRET_ENABLED` | `false` | DE-5 historical interpretation |
| `AI_DE4_INTERPRET_PROPOSAL_BRIDGE_ENABLED` | `false` | Turns DE-3 recommendations into DE-4 proposals |
| `ASSISTANT_MEMORY_ENABLED` / `ASSISTANT_MEMORY_REDIS_URL` | `false` / `redis://127.0.0.1:6379/0` | Redis working memory |
| `FOLLOWUP_REMINDER_DAYS` | `3` | Days before a lead counts as awaiting follow-up |

Full list: [backend/.env.example](./backend/.env.example) and `backend/config.py`.

---

## Project structure

```
behtech_saleshub/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── database.py              # Models (CRM, AiAction, AiRun, diagnosis, assistant_*)
│   ├── config.py                # Settings / feature flags
│   ├── ai/
│   │   ├── router.py            # /api/ai/*
│   │   ├── capabilities/        # chat, chat_stream, chat_tools, diagnosis interpreters, priorities, agent, …
│   │   ├── actions/             # DE-4 registry, policies, lifecycle, mapper, dedup, executors
│   │   ├── crm_tools.py         # Read-only assistant tools
│   │   ├── entity_continuity.py # Active-lead binding
│   │   ├── assistant_memory.py  # Redis working memory
│   │   ├── snapshots/           # Lead / org snapshots + PII sanitization
│   │   ├── prompts/             # System prompts (Markdown)
│   │   └── usage.py             # Token quota accounting
│   ├── intelligence/
│   │   ├── diagnosis/           # Rules, engine, fingerprint, sync, trend, history API
│   │   ├── scoring.py
│   │   ├── insights.py
│   │   └── router.py            # /api/intelligence/*
│   ├── jobs/                    # AI batch + automation cron entry points
│   └── tests/                   # DE-1 … DE-6 and Faz 2–7 regression suites
├── frontend/src/
│   ├── components/
│   │   ├── IntelligencePage.tsx
│   │   └── ai/                  # SalesAssistantPage, diagnosis cards, DE-4 inbox, …
│   ├── api.ts
│   └── i18n/
├── deploy/                      # nginx, systemd, backups, server scripts
├── docs/architecture/           # Architecture freeze notes
├── docker-compose.yml
├── DEPLOY.md
└── start.sh
```

---

## API overview

| Prefix | Contents |
|--------|----------|
| `/api/auth/*` | Login, register, refresh / remember-me, password reset, email verification |
| `/api/leads/*` | CRUD, activities, attachments, payments |
| `/api/dashboard`, `/api/analytics`, `/api/reports/*` | Dashboard, analytics, period reports |
| `/api/intelligence/*` | KPIs, insights, company profile, diagnoses, sync, history, trend, action proposals |
| `/api/ai/*` | status, suggest-message, summarize-lead, priorities, chat / chat/stream, conversations, runs, diagnosis interpret, actions (propose / update / cancel / approve / execute) |

Health check: `GET https://saleshub.behtechlabs.com/api/health`

---

## Security

- bcrypt password hashing, JWT with HttpOnly refresh cookies, idle timeout.
- Rate limiting on login / register / reset and on AI endpoints.
- Organization isolation is enforced on the server for every query and every assistant tool.
- Assistant tools are read-only. Writes happen only through the approved DE-4 action flow.
- Financial and destructive operations are blocked for AI in the action registry.
- Production uses HTTPS, strict CORS and a strong `SECRET_KEY`, and `.env` files stay out of git.

Server setup: [DEPLOY.md](./DEPLOY.md) · [deploy/SUNUCU-KURULUM.md](./deploy/SUNUCU-KURULUM.md)

---

## Development

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Tests:

```bash
cd backend
pytest -q
# AI / diagnosis suites only
pytest tests/test_diagnosis_de*.py tests/test_de4_*.py tests/test_de5_*.py tests/test_de6_*.py -q
```

---

## License

[MIT License](./LICENSE). Copyright (c) BehTech / Behlul Alar.

Questions and business inquiries: [BehTech Labs](https://behtechlabs.com)

---

<p align="center">
  <sub>BehTech Sales Hub: data-driven sales tracking, explainable diagnosis, controlled AI.</sub>
</p>
