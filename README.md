<p align="center">
  <img src="docs/assets/behtech-logo.png" alt="BehTech — Beyond The Code" width="320" />
</p>

<h1 align="center">BehTech Sales Hub</h1>

<p align="center">
  <strong>Çok kiracılı satış CRM’i, zekâ katmanı ve kontrollü AI yetenekleri</strong><br/>
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

**BehTech Sales Hub**, saha satış ve pazar araştırması ekipleri için tasarlanmış **production-grade** bir müşteri takip sistemidir. Lead’lerden müşteriye kadar huniyi, görevleri, raporları ve (isteğe bağlı) **OpenAI / Azure OpenAI** destekli AI katmanını tek panelde birleştirir.

- **Organizasyon (owner)** — tam erişim: dashboard, gelir, analizler, personel, AI operasyonları  
- **Personel (employee)** — kategori lead’leri, talep oluşturma; gelir ve owner araçları kapalı  
- **Veri izolasyonu** — tüm kayıtlar org (`user_id`) bazında ayrılır  

Canlı ortam örneği: [saleshub.behtechlabs.com](https://saleshub.behtechlabs.com)

---

## Öne çıkan özellikler

### CRM çekirdeği

| Alan | Açıklama |
|------|----------|
| Lead yönetimi | Kategori, durum, öncelik, etiketler, notlar, satış tutarı |
| Satış hunisi | Kişi → Cevap → Demo → Teklif → Satış (`funnel.py`) |
| Aktivite geçmişi | Mesaj, demo, teklif, görüşme, durum değişimi |
| Talep / onay | Personel talebi → owner onayı → kategoriye lead |
| Lead keşfi & import | Google Places tabanlı keşif, Excel içe aktarma |
| Ekler | Lead dosyaları (sunucuda `backend/uploads/`, git dışı) |
| Raporlar & analiz | Günlük / haftalık / aylık rapor, şehir-kategori-saat analizi |
| Otomasyon | Sabah / gün sonu e-posta özeti (SMTP) |
| i18n | Türkçe / İngilizce arayüz |

### Intelligence (deterministik — LLM şart değil)

| Bileşen | Ne yapar? |
|---------|-----------|
| Lead skorlama | Kural tabanlı öncelik puanı ve `action_type` |
| Öneri defteri | `IntelligenceRecommendation` kayıtları |
| Org insights | Cevap bekleyen backlog vb. |
| Şirket profili | Aylık KPI özeti, en iyi lead kaynağı |
| KPI API | `reports` + `analytics` sarmalayıcı (`compute_kpis`) |

### AI Capability Layer (Faz 0–7, feature flag)

AI **kapalı** başlayabilir; prod’da `AI_ENABLED` ve ilgili anahtarlarla açılır. Kota org başına aylık token ile sınırlanır.

| Özellik | Kısa açıklama |
|---------|----------------|
| Mesaj koçu | Lead bağlamında WhatsApp / Instagram taslağı |
| Lead özeti | Tek lead için AI özeti |
| Öncelik listesi | Owner dashboard — stabil cache (12s + session) |
| AI işleri | Batch skor, agent (read-only tool’lar), run geçmişi |
| Onay kuyruğu | Öncelik planı → onay → takip/görüşme + aktivite |
| Şirket zekâ kartı | Dashboard profil kartı |
| Günlük mail paragrafı | `AI_DAILY_EMAIL` ile otomasyon mailine AI cümlesi |
| Satış asistanı | Global chat widget + **SSE streaming** |

Detaylı faz listesi: [docs/architecture/ARCHITECTURE_FREEZE.md](./docs/architecture/ARCHITECTURE_FREEZE.md)

> **Yol haritası:** **Sales Diagnosis Engine** (deterministik teşhis + ayrı Recommendation / LLM yorum katmanı) — tasarım kilitlendi, DE-1 implementasyonu sırada. Klasik RAG / vektör arama yok; veri PostgreSQL + mevcut analitikten okunur.

---

## Teknoloji yığını

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.10+, **FastAPI**, SQLAlchemy, PostgreSQL |
| Frontend | **React 18**, TypeScript, **Vite**, Tailwind CSS |
| Auth | JWT, bcrypt, rate limiting |
| AI | OpenAI API veya Azure OpenAI |
| Deploy | systemd (`behtech-crm`), Nginx, rsync script’leri |

---

## Hızlı başlangıç (yerel)

### Gereksinimler

- Python 3.10+
- Node.js 18+
- Docker Desktop (PostgreSQL)

### Çalıştırma

```bash
chmod +x start.sh
./start.sh
```

Tarayıcı: **http://localhost:5173**

### İlk yapılandırma

1. `backend/.env.example` → `backend/.env` kopyalayın  
2. `SECRET_KEY`, `DATABASE_URL` ve (isteğe bağlı) SMTP / OpenAI alanlarını doldurun  
3. PostgreSQL: `docker compose up -d` (varsayılan port **5433**)

```env
DATABASE_URL=postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db
```

### Seed admin

| Alan | Kaynak |
|------|--------|
| Kullanıcı adı | Migration seed (ör. `behlul`) |
| Şifre | `SEED_ADMIN_PASSWORD` — **`.env` içinde, repoya commit etmeyin** |

---

## Yapılandırma (özet)

| Değişken | Açıklama |
|----------|----------|
| `AI_ENABLED` | AI katmanı master switch |
| `OPENAI_API_KEY` | Doğrudan OpenAI |
| `AI_CHAT_ENABLED` | Global satış asistanı |
| `AI_DAILY_EMAIL` | Sabah/akşam mailine AI paragrafı |
| `AI_MONTHLY_TOKEN_QUOTA` | Org aylık token kotası |
| `FOLLOWUP_REMINDER_DAYS` | Cevap bekleyen eşiği |

Tam liste: [backend/.env.example](./backend/.env.example)

---

## Proje yapısı

```
behtech_saleshub/
├── backend/
│   ├── main.py              # API girişi
│   ├── ai/                  # LLM router, chat, batch, agent
│   ├── intelligence/        # KPI, skor, insights, onay önerileri
│   ├── analytics.py         # Huniler, dönüşüm analizi
│   ├── reports.py           # Dönem raporları
│   └── dashboard.py         # Dashboard metrikleri
├── frontend/src/
│   ├── components/ai/       # Chat, öncelik, ops paneli, …
│   └── i18n/                # TR / EN
├── deploy/                  # upload-to-server, cron, nginx örnekleri
├── docs/architecture/       # Mimari notlar
└── start.sh
```

---

## API yüzeyi (seçilmiş)

| Prefix | İçerik |
|--------|--------|
| `/api/auth/*` | Giriş, kayıt, şifre sıfırlama |
| `/api/leads/*` | CRUD, aktivite, ekler |
| `/api/dashboard` | Owner dashboard verisi |
| `/api/analytics` | Analitik paket |
| `/api/reports/*` | Dönem raporları |
| `/api/intelligence/*` | KPI, insights, company-profile, action-proposals |
| `/api/ai/*` | status, chat, stream, priorities, runs |

---

## Güvenlik

- Şifreler **bcrypt**; JWT oturum; idle timeout  
- Rate limit (login / register / reset)  
- `user_id` ile çok kiracılı izolasyon  
- Prod: güçlü `SECRET_KEY`, HTTPS, CORS, `.env` asla repoda değil  
- AI: read-only bağlam; CRM yazma yalnızca onaylı action proposal hattında (sınırlı alanlar)  

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

Testler (DB gerektiren smoke test’ler dahil):

```bash
cd backend && pytest tests/ -q
```

---

## Katkı ve lisans

Bu proje [MIT License](./LICENSE) altındadır — Copyright (c) BehTech / Behlul Alar.

Sorular ve kurumsal kullanım: [BehTech Labs](https://behtechlabs.com)

---

<p align="center">
  <sub>BehTech Sales Hub — veriye dayalı satış takibi, kontrollü AI, açıklanabilir zekâ.</sub>
</p>
