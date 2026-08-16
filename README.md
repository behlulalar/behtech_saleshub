<p align="center">
  <img src="docs/assets/behtech-logo.png" alt="BehTech — Beyond The Code" width="320" />
</p>

<h1 align="center">BehTech Sales Hub</h1>

<p align="center">
  <strong>Çok kiracılı satış CRM’i · Sales Diagnosis · kontrollü AI aksiyonları · Sales Assistant</strong><br/>
  <em>Beyond The Code — BehTech Labs</em>
</p>

<p align="center">
  <a href="https://saleshub.behtechlabs.com">Production</a> ·
  <a href="./DEPLOY.md">Deploy</a> ·
  <a href="./docs/architecture/ARCHITECTURE_FREEZE.md">AI mimarisi</a> ·
  <a href="./LICENSE">MIT License</a>
</p>

---

## Genel bakış

**BehTech Sales Hub**, saha satış ve pazar araştırması ekipleri için tasarlanmış **production-grade** bir müşteri takip sistemidir. Lead hunisi, görevler, raporlar, deterministik satış teşhisi ve (isteğe bağlı) **OpenAI / Azure OpenAI** destekli AI katmanını tek panelde birleştirir.

- **Organizasyon (owner)** — dashboard, gelir, analizler, personel, Intelligence / AI operasyonları  
- **Personel (employee)** — kategori lead’leri, talep oluşturma; gelir ve owner araçları kapalı  
- **Veri izolasyonu** — tüm kayıtlar org (`user_id` / `organization_id`) bazında ayrılır  
- **CRM gerçeği** — asistan teklif tutarı gibi kritik bilgileri uydurmaz; CRM tool’larından okur  

Canlı ortam: [saleshub.behtechlabs.com](https://saleshub.behtechlabs.com)

---

## Öne çıkan özellikler

### CRM çekirdeği

| Alan | Açıklama |
|------|----------|
| Lead yönetimi | Kategori, durum, öncelik, etiketler, notlar, satış / teklif tutarı |
| Satış hunisi | Kişi → Cevap → Demo → Teklif → Satış |
| Aktivite geçmişi | Mesaj, demo, teklif, görüşme, durum değişimi |
| Talep / onay | Personel talebi → owner onayı → kategoriye lead |
| Lead keşfi & import | Google Places tabanlı keşif, Excel içe aktarma |
| Ekler | Lead dosyaları (`backend/uploads/`, git dışı) |
| Raporlar & analiz | Dönem raporları, şehir / kategori / saat analizi |
| Görevler | Kayıtlı işletmelerden hızlı görev seçimi |
| Otomasyon | Sabah / gün sonu e-posta özeti (SMTP) |
| Auth | JWT + HttpOnly **Remember Me** refresh session |
| i18n | Türkçe / İngilizce arayüz |

### Intelligence (deterministik — LLM şart değil)

| Bileşen | Ne yapar? |
|---------|-----------|
| Lead skorlama | Kural tabanlı öncelik puanı ve `action_type` |
| Öneri defteri | `IntelligenceRecommendation` kayıtları |
| Org insights | Cevap bekleyen backlog vb. |
| Şirket profili | Aylık KPI özeti, en iyi lead kaynağı |
| KPI API | `reports` + `analytics` sarmalayıcı |

### Sales Diagnosis Engine (DE-3 → DE-5)

Deterministik teşhis motoru; LLM opsiyonel yorum katmanıdır. Klasik RAG / vektör arama yok — veri PostgreSQL + mevcut analitikten okunur.

| Katman | Durum | Özet |
|--------|-------|------|
| **DE-3** | Done | Teşhis kuralları, evidence, impact, öncelik, AI yorum (`diagnosis/interpret`) |
| **DE-4** | Done | Teşhis → `ai_actions` köprüsü; propose / update / cancel / approve / execute; duplicate hardening |
| **DE-5** | Done | `diagnosis_cases` / `diagnosis_snapshots`, sync, history API/UI, deterministik trend, historical AI yorum |

UI: **Intelligence** → teşhis kartları, history modal, trend, aksiyon kutusu.

### AI Capability Layer (Faz 0–7 + DE-6)

AI **kapalı** başlayabilir; prod’da `AI_ENABLED` ve ilgili anahtarlarla açılır. Kota org başına aylık token ile sınırlanır.

| Özellik | Kısa açıklama |
|---------|----------------|
| Mesaj koçu | Lead bağlamında WhatsApp / Instagram taslağı |
| Lead özeti | Tek lead için AI özeti |
| Öncelik listesi | Owner dashboard — stabil cache |
| AI işleri | Batch skor, agent (read-only tool’lar), run geçmişi |
| Günlük mail paragrafı | `AI_DAILY_EMAIL` ile otomasyon mailine AI cümlesi |
| **Sales Assistant (DE-6)** | Tam ekran asistan: kalıcı sohbet, CRM tool’ları, Redis working memory, entity continuity, bekleyen teklif tutarlılığı |

#### Sales Assistant (DE-6) — özet

- PostgreSQL sohbet kalıcılığı (`assistant_conversations` / `assistant_messages`)
- Read-only CRM tool’ları: lead arama, teklif, aktivite, bekleyen teklifler, günlük brief
- Redis working memory (TTL’li kısa bağlam; PG kaynak gerçeği)
- Konuşma içi **entity continuity** (aktif lead takip; portföy soruları yanlış scope’lanmaz)
- Portfolio “bekleyen teklifler” → `get_pending_offers` (model uydurmaz)
- Full-screen UI: sidebar, arama, arşiv, streaming, insan okunur tool status

Detaylı faz listesi: [docs/architecture/ARCHITECTURE_FREEZE.md](./docs/architecture/ARCHITECTURE_FREEZE.md)

---

## Teknoloji yığını

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.10+, **FastAPI**, SQLAlchemy, PostgreSQL |
| Frontend | **React 18**, TypeScript, **Vite**, Tailwind CSS |
| Auth | JWT, bcrypt, HttpOnly refresh sessions, rate limiting |
| AI | OpenAI API veya Azure OpenAI |
| Working memory | **Redis** (asistan kısa bağlamı; opsiyonel flag) |
| Deploy | systemd (`behtech-crm`), Nginx, rsync (`deploy/upload-to-server.sh`) |

---

## Hızlı başlangıç (yerel)

### Gereksinimler

- Python 3.10+
- Node.js 18+
- Docker Desktop (PostgreSQL; Redis önerilir — asistan memory için)

### Çalıştırma

```bash
chmod +x start.sh
./start.sh
```

Tarayıcı: **http://localhost:5173**

### İlk yapılandırma

1. `backend/.env.example` → `backend/.env` kopyalayın  
2. `SECRET_KEY`, `DATABASE_URL` ve (isteğe bağlı) SMTP / OpenAI / Redis alanlarını doldurun  
3. PostgreSQL: `docker compose up -d` (varsayılan port **5433**)

```env
DATABASE_URL=postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db
```

### Seed admin

| Alan | Kaynak |
|------|--------|
| Kullanıcı adı | Migration seed (ör. `SEED_ADMIN_USERNAME`) |
| Şifre | `SEED_ADMIN_PASSWORD` — **yalnızca `.env` içinde, repoya commit etmeyin** |

---

## Yapılandırma (özet)

| Değişken | Açıklama |
|----------|----------|
| `AI_ENABLED` | AI katmanı master switch |
| `OPENAI_API_KEY` | Doğrudan OpenAI |
| `AI_CHAT_ENABLED` | Sales Assistant |
| `AI_DAILY_EMAIL` | Sabah/akşam mailine AI paragrafı |
| `AI_MONTHLY_TOKEN_QUOTA` | Org aylık token kotası |
| `AI_DIAGNOSIS_INTERPRET_ENABLED` | DE-3 teşhis yorumu |
| `AI_DE4_INTERPRET_PROPOSAL_BRIDGE_ENABLED` | DE-3 → DE-4 aksiyon köprüsü |
| `ASSISTANT_MEMORY_ENABLED` | Redis working memory |
| `ASSISTANT_MEMORY_REDIS_URL` | örn. `redis://127.0.0.1:6379/0` |
| `FOLLOWUP_REMINDER_DAYS` | Cevap bekleyen eşiği |

Tam liste: [backend/.env.example](./backend/.env.example) ve `backend/config.py`

---

## Proje yapısı

```
behtech_saleshub/
├── backend/
│   ├── main.py                 # FastAPI girişi
│   ├── database.py             # Modeller (CRM, AiAction, diagnosis, assistant_*)
│   ├── config.py               # Settings / feature flags
│   ├── ai/
│   │   ├── router.py           # /api/ai/* (chat, stream, conversations, status, …)
│   │   ├── capabilities/       # chat, stream, diagnose interpret, priorities, …
│   │   ├── actions/            # DE-4 lifecycle (propose → execute)
│   │   ├── crm_tools.py        # Asistan read-only CRM tool’ları
│   │   ├── entity_continuity.py
│   │   ├── conversations_store.py
│   │   └── assistant_memory.py # Redis working memory
│   ├── intelligence/
│   │   ├── diagnosis/          # DE-3 motor + DE-5 sync/history/trend
│   │   ├── scoring.py
│   │   ├── insights.py
│   │   └── router.py           # /api/intelligence/*
│   ├── tests/                  # DE-3 … DE-6 regression suite’leri
│   └── .env.example
├── frontend/src/
│   ├── components/
│   │   ├── IntelligencePage.tsx
│   │   └── ai/                 # SalesAssistantPage, teşhis, DE-4 inbox, …
│   ├── api.ts
│   └── i18n/
├── deploy/                     # upload-to-server, nginx, backup, systemd
├── docs/
│   ├── architecture/           # Mimari freeze notları
│   └── assets/
├── docker-compose.yml
├── DEPLOY.md
└── start.sh
```

---

## API yüzeyi (seçilmiş)

| Prefix | İçerik |
|--------|--------|
| `/api/auth/*` | Giriş, kayıt, refresh / remember-me, şifre sıfırlama |
| `/api/leads/*` | CRUD, aktivite, ekler |
| `/api/dashboard` | Owner dashboard verisi |
| `/api/analytics` | Analitik paket |
| `/api/reports/*` | Dönem raporları |
| `/api/intelligence/*` | KPI, insights, company-profile, diagnoses, sync, history, action-proposals |
| `/api/ai/*` | status, chat/stream, conversations, priorities, runs, diagnosis interpret, DE-4 actions |

Production health: `GET https://saleshub.behtechlabs.com/api/health`

---

## Güvenlik

- Şifreler **bcrypt**; JWT + HttpOnly refresh; idle timeout  
- Rate limit (login / register / reset)  
- Org izolasyonu; asistan `organization_id` / `user_id` sunucu tarafında zorlanır  
- Prod: güçlü `SECRET_KEY`, HTTPS, CORS, `.env` asla repoda değil  
- AI asistan: CRM tool’ları **read-only**; yazma yalnızca onaylı DE-4 action hattında  
- Model teklif tutarı uyduramaz — CRM tool sonucu zorunlu  

Sunucu kurulumu: [DEPLOY.md](./DEPLOY.md) · [deploy/SUNUCU-KURULUM.md](./deploy/SUNUCU-KURULUM.md)

---

## Geliştirme

```bash
# Backend (venv)
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Testler (DE-3 … DE-6 dahil):

```bash
cd backend
pytest tests/test_diagnosis_de3.py tests/test_de4_*.py tests/test_de5_*.py tests/test_de6_*.py -q
```

---

## Katkı ve lisans

Bu proje [MIT License](./LICENSE) altındadır — Copyright (c) BehTech / Behlul Alar.

Sorular ve kurumsal kullanım: [BehTech Labs](https://behtechlabs.com)

---

<p align="center">
  <sub>BehTech Sales Hub — veriye dayalı satış takibi, açıklanabilir teşhis, kontrollü AI.</sub>
</p>
