<p align="center">
  <img src="docs/assets/behtech-logo.png" alt="BehTech — Beyond The Code" width="320" />
</p>

<h1 align="center">BehTech Sales Hub</h1>

<p align="center">
  <strong>Çok kiracılı satış CRM'i · Deterministik Satış Teşhisi · İnsan onaylı AI aksiyonları · Veriye dayalı Satış Asistanı</strong><br/>
  <em>Beyond The Code — BehTech Labs</em>
</p>

<p align="center">
  <a href="https://saleshub.behtechlabs.com">Canlı</a> ·
  <a href="./README.md">English</a> ·
  <a href="./DEPLOY.md">Deploy</a> ·
  <a href="./docs/architecture/ARCHITECTURE_FREEZE.md">AI mimarisi</a> ·
  <a href="./LICENSE">MIT Lisansı</a>
</p>

---

## Genel bakış

**BehTech Sales Hub**, saha satış ve pazar araştırması ekipleri için geliştirilmiş, canlıda çalışan bir CRM'dir. Lead hunisini, görevleri, raporları, gelir takibini, kural tabanlı bir satış teşhis motorunu ve isteğe bağlı bir AI katmanını (OpenAI veya Azure OpenAI) tek uygulamada birleştirir.

AI katmanı, kod tabanının her yerinde geçerli olan birkaç kurala dayanır:

- **Gerçeğin kaynağı CRM'dir.** Model veriyi araçlar üzerinden okur. Teklif tutarı, tarih, sebep veya satın alma ihtimali uydurmaz.
- **Teşhis mantığı AI olmadan çalışır.** Sorunları PostgreSQL üzerinde çalışan deterministik kurallar bulur. LLM yalnızca açıklar ve öneri verir.
- **AI öneri verir, kendi başına işlem yapmaz.** CRM verisindeki her değişiklik; tipli bir aksiyon, politika kontrolü, owner onayı ve idempotent bir executor üzerinden geçer.
- **Kiracılar sunucu tarafında ayrılır.** `organization_id` / `user_id` backend tarafından belirlenir, modelden asla alınmaz.
- **Varsayılan olarak kapalıdır.** Her AI özelliğinin kendi flag'i vardır ve her organizasyonun aylık token kotası bulunur.

Canlı ortam: [saleshub.behtechlabs.com](https://saleshub.behtechlabs.com)

---

## Roller

| Rol | Erişim |
|-----|--------|
| **Owner (organizasyon)** | Dashboard, gelir, analizler, personel yönetimi, Intelligence, AI operasyonları, aksiyon onayları |
| **Personel (employee)** | Atandığı kategorilerdeki lead'ler, lead talepleri; gelir ve owner araçları gizlidir |

Tüm kayıtlar organizasyon bazında ayrılır.

---

## CRM çekirdeği

| Alan | Ne yapar? |
|------|-----------|
| Lead yönetimi | Kategori, durum, öncelik, etiketler, notlar, teklif tutarı, ekler |
| Satış hunisi | Kişi → Cevap → Demo → Teklif → Satış |
| Aktivite geçmişi | Mesaj, demo, teklif, görüşme, durum değişimi |
| Tahsilat ve gelir | Tahsilatlar tekliften ayrı tutulur; her tahsilat kaydedildiği aya yazılır; ay/yıl filtreleri |
| Lead talepleri | Personel talebi → owner onayı → kategoride lead oluşturma |
| Lead keşfi ve içe aktarma | Kota takipli Google Places (New) grid araması, Excel içe aktarma |
| Raporlar ve analiz | Dönem raporları (XLSX / PDF dışa aktarma), şehir / kategori / saat bazlı kırılımlar |
| Görevler ve hatırlatmalar | Kayıtlı işletmelerden hızlı görev, takip hatırlatmaları |
| E-posta otomasyonu | SMTP ile sabah ve gün sonu özetleri (o günün tahsilatları dahil) |
| Kimlik doğrulama | JWT + HttpOnly "Beni hatırla" refresh oturumları, e-posta doğrulama, boşta kalma zaman aşımı, rate limit |
| i18n | Türkçe / İngilizce arayüz |

---

## AI ve Intelligence katmanı

```mermaid
flowchart LR
    PG[(PostgreSQL<br/>CRM verisi)] --> DE[Teşhis Motoru<br/>deterministik kurallar]
    PG --> SC[Lead skorlama<br/>kural tabanlı]
    DE --> CASES[(Teşhis kayıtları<br/>+ snapshot'lar)]
    CASES --> TREND[Trend ve geçmiş]
    DE --> INT[LLM yorumlayıcı<br/>yalnızca JSON, veriye bağlı]
    TREND --> HINT[Geçmiş yorumlayıcı]
    INT --> MAP[Eşleyici + tekilleştirme]
    MAP --> ACT[ai_actions<br/>önerildi]
    ACT -->|owner onaylar| EXE[Executor<br/>idempotent, satır kilitli]
    EXE --> PG
    PG --> TOOLS[Salt okunur CRM araçları]
    TOOLS --> ASSIST[Satış Asistanı<br/>tool-calling + SSE]
    REDIS[(Redis<br/>çalışma belleği)] -.-> ASSIST
```

### 1. Intelligence (deterministik, LLM gerekmez)

| Bileşen | Ne yapar? |
|---------|-----------|
| Lead skorlama | Öncelik, boşta geçen gün ve huni aşamasından kural tabanlı 0–100 puan; gerekçeler ve önerilen `action_type` ile |
| Öneriler | Kalıcı `IntelligenceRecommendation` kayıtları |
| Org insights | Büyüyen "cevap bekleyen" birikimi gibi sinyaller |
| Şirket profili | Aylık KPI özeti, en iyi lead kaynağı |
| KPI API | Mevcut rapor ve analitiği sarmalar |

### 2. Satış Teşhis Motoru (DE-3 → DE-5)

Satışların **neden** tıkandığını bulan kural motoru. Vektör arama veya klasik RAG kullanmaz. Kanıtlar doğrudan PostgreSQL'den ve analitik katmanından gelir.

**Teşhis türleri**

| Tür | Tespit eder |
|-----|-------------|
| `funnel_drop` | Huni aşamaları arasındaki dönüşüm düşüşleri (günlük / haftalık / aylık, önceki dönemle karşılaştırılır, göreli ve mutlak düşüşe göre derecelendirilir) |
| `follow_up` | Uzun süredir iletişim kurulmamış lead'ler |
| `offer` | Satışa dönüşmeden bekleyen eski teklifler |

Her teşhis **kanıt**, **etki** (etkilenen lead'ler, sayılar), **şiddet**, **öncelik** ve arkasındaki en öncelikli lead'leri içerir.

**Yaşam döngüsü ve geçmiş (DE-5)**

- Teşhisler `diagnosis_cases` ve `diagnosis_snapshots` olarak saklanır; gözlem parmak iziyle tekilleştirilir.
- Durumlar: `new → active → improving / worsening → resolved`; yeniden açılmalar da takip edilir.
- AI gerektirmeyen trend analizi: snapshot farkları, sebep kodları, yön, en kötü nokta, dönem süresi ve yeniden açılma sayısı.
- Geçmiş API'si ve arayüzü: zaman çizelgesi modalı, trend görünümü, dönem bazlı detay.

**AI yorumu (isteğe bağlı)**

- `POST /api/ai/diagnosis/interpret` bir teşhisi özet, "neden önemli", temel bulgular ve önerilen aksiyonlara dönüştürür.
- `POST /api/ai/diagnosis/history/interpret` aynısını teşhisin geçmişi için yapar.
- Veriye bağlı prompt: sayılar, lead adları ve oranlar **yalnızca** verilen JSON bağlamından alınabilir. Uydurma gelir, sebep, rakip veya yüzde yok.
- Yalnızca JSON çıktı, Pydantic şemasıyla doğrulanır. Geçersiz çıktı reddedilir; önbellekteki geçersiz çıktı da.
- Maliyeti kontrol etmek için düşük sıcaklık (0.2), çıktı token sınırı ve süreli sonuç önbelleği (varsayılan 48 saat).

### 3. İnsan onaylı AI aksiyonları (DE-4)

AI, CRM değişiklikleri **önerebilir**. Çalışıp çalışmayacağına owner karar verir.

**Akış:** DE-3 önerilen aksiyonları → deterministik **eşleyici** → `(action_type, lead_id)` bazında **tekilleştirme** → `proposed` durumunda `ai_actions` → owner **Aksiyon kutusunda** inceler, düzenler veya iptal eder → **onay** → **çalıştırma**.

**Durum makinesi**

```
proposed → approved → executing → executed
    │          │                 └→ failed
    └──────────┴→ cancelled / expired
```

**Kapalı aksiyon kaydı**: çalışma anında yeni aksiyon türü eklenemez. Her türün bir Pydantic parametre modeli, risk seviyesi, izin sınıfı ve izinli rolleri vardır.

| İzinli (owner onayı gerekir) | Risk |
|------------------------------|------|
| `propose_follow_up_task` | düşük |
| `propose_log_activity` | düşük |
| `propose_note_append` | düşük |
| `open_whatsapp_draft` (yalnızca istemci tarafı `wa.me` linki, sunucu mesaj göndermez) | düşük |
| `propose_meeting_date` | orta |
| `propose_priority_change` | orta |
| `propose_status_change` | orta |

| Engelli (`NOT_ALLOWED_FOR_AI` / `ADMIN_ONLY`) |
|------------------------------------------------|
| Sunucudan WhatsApp mesajı gönderme, lead / aktivite / ek silme, toplu içe aktarma, lead oluşturma, satış kaydetme, gelir değiştirme, lead talebi onaylama, toplu yeniden skorlama |

**Güvenlik önlemleri:** zorunlu idempotency anahtarları, çalıştırma sırasında `SELECT … FOR UPDATE` satır kilidi, mükerrer önerilere karşı benzersizlik kontrolleri ve eşzamanlılık test paketi.

### 4. Satış Asistanı (DE-6)

Soruları gerçek CRM verisiyle yanıtlayan, tam ekran, tool-calling yapan satış asistanı.

- **Kalıcı sohbetler** PostgreSQL'de (`assistant_conversations`, `assistant_messages`); kenar çubuğu, arama, yeniden adlandırma ve arşiv.
- **SSE streaming** (`POST /api/ai/chat/stream`), okunabilir araç durumlarıyla ("Lead'ler aranıyor…").
- **10 salt okunur CRM aracı**:

  | Araç | Amaç |
  |------|------|
  | `search_leads` | Belirsizlik tespitli, esnek işletme adı araması |
  | `get_lead` | Lead detayları |
  | `get_lead_offer` | Tek lead'in teklif durumu ve tutarı |
  | `get_lead_activities` | Aktivite geçmişi |
  | `get_sales_metrics` | Satış ve huni metrikleri |
  | `get_followup_candidates` | Takip gereken lead'ler |
  | `get_diagnoses` / `get_diagnosis` | Aktif teşhisler |
  | `get_pending_offers` | Henüz kapanmamış tüm teklifler |
  | `get_daily_sales_brief` | Sıralanmış günlük öncelikler |

- **Doğruluk kuralları**: her cevap *gerçek* (araç çıktısında görülen), *çıkarım* (temkinli yorum) ve *bilinmeyen* (CRM'de olmayan) bilgiyi ayırır. "%80 alır" veya "fiyatı yüksek buldu" gibi iddialar CRM'de karşılığı yoksa yasaktır.
- **Bekleyen teklif tutarlılığı**: kullanıcı portföydeki bekleyen teklifleri sorduğunda backend `tool_choice` ile `get_pending_offers` çağrısını zorunlu kılar; cevap hafızaya veya eski bir özete dayanmaz.
- **Varlık sürekliliği (DE-6.7)**: sohbet aktif lead'i takip eder. "Neden kapanmadı?" veya "son aktivite?" gibi devam soruları aynı lead üzerinde kalır; "bugün ne yapmalıyım?" gibi genel sorular portföy araçlarına döner.
- **Redis çalışma belleği (DE-6.5)**: isteğe bağlı kısa süreli önbellek (TTL, mesaj ve karakter sınırlı). Asıl kaynak PostgreSQL'dir. Redis hataları sohbeti asla bozmaz.
- **Proaktif günlük brief**: yüksek şiddetli teşhis lead'lerini, uzun süredir takip edilmeyenleri ve eski teklifleri sıralar.
- Kullanıcının dilinde (Türkçe / İngilizce) yanıt verir. Araç turu sayısı 6 ile sınırlıdır.

### 5. Diğer AI özellikleri

| Özellik | Açıklama |
|---------|----------|
| Mesaj koçu | Lead için WhatsApp / Instagram mesaj taslağı (tanışma, takip, demo, görüşme şablonları) |
| Lead özeti | Tek lead için AI özeti ve içgörüler |
| Öncelik listesi | Owner dashboard'unda stabil önbellekli öncelik listesi |
| AI işleri | Arka planda toplu lead skorlama ve sınırlı salt okunur agent (en fazla 5 adım), iş geçmişiyle |
| Günlük mail paragrafı | Sabah / gün sonu mailine kısa AI paragrafı ekler. LLM hata verirse mail paragrafsız gönderilir |

### Gizlilik, maliyet ve izlenebilirlik

- **Kişisel veri maskeleme**: `AI_INCLUDE_PII=true` değilse e-posta ve telefonlar modele gitmeden maskelenir.
- **İş logu temizleme**: agent adım logları saklanmadan önce kişisel verilerden arındırılır.
- **Çıktı saklama isteğe bağlıdır** (`AI_STORE_OUTPUT`).
- Organizasyon başına **aylık token kotası**, istek öncesi token tahmini ve istek hız sınırı (varsayılan `20/dakika`).
- `GET /api/ai/status` hangi özelliklerin kullanılabilir olduğunu ve kota kullanımını gösterir.
- **Sağlayıcı yönlendirme**: genel AI için OpenAI veya Azure OpenAI. Teşhis yorumu her zaman OpenAI API kullanır.

---

## Teknoloji yığını

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.10+, **FastAPI**, SQLAlchemy 2, Pydantic 2, PostgreSQL |
| Frontend | **React 18**, TypeScript, **Vite**, Tailwind CSS, lucide-react |
| Kimlik doğrulama | JWT (python-jose), bcrypt, HttpOnly refresh oturumları, slowapi rate limit |
| AI | OpenAI API veya Azure OpenAI (varsayılan `gpt-4o-mini`), function calling, SSE |
| Çalışma belleği | Redis (isteğe bağlı) |
| Entegrasyonlar | Google Places API (New), SMTP (Google Workspace) |
| Dışa aktarma | openpyxl (XLSX), ReportLab (PDF) |
| Deploy | Docker Compose, systemd, Nginx (Cloudflare real-IP + rate limit), Google Drive'a zamanlanmış yedekleme (rclone) |

---

## Hızlı başlangıç (yerel)

### Gereksinimler

- Python 3.10+
- Node.js 18+
- Docker Desktop (PostgreSQL; asistan belleği için Redis önerilir)

### Çalıştırma

```bash
chmod +x start.sh
./start.sh
```

Tarayıcı: **http://localhost:5173**

### İlk yapılandırma

1. `backend/.env.example` dosyasını `backend/.env` olarak kopyalayın.
2. `SECRET_KEY`, `DATABASE_URL` ve gerekirse SMTP / OpenAI / Redis / Google Places alanlarını doldurun.
3. PostgreSQL'i `docker compose up -d` ile başlatın (varsayılan port **5433**).

```env
DATABASE_URL=postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db
```

Seed admin `SEED_ADMIN_USERNAME` / `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` değerlerinden oluşturulur. Bunları yalnızca `.env` içinde tutun, gerçek değerleri asla commit etmeyin.

---

## Yapılandırma (AI flag'leri)

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `AI_ENABLED` | `false` | Tüm AI katmanını açar / kapatır |
| `AI_PROVIDER` | `openai` | `openai` veya `azure` |
| `OPENAI_API_KEY` / `OPENAI_CHAT_MODEL` | — / `gpt-4o-mini` | Doğrudan OpenAI |
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_DEPLOYMENT_CHAT` | — | Azure OpenAI |
| `AI_MONTHLY_TOKEN_QUOTA` | `400000` | Organizasyon başına aylık token bütçesi |
| `AI_MAX_OUTPUT_TOKENS` / `AI_LLM_TIMEOUT_SEC` | `600` / `25` | Çağrı başına sınırlar |
| `AI_INCLUDE_PII` / `AI_INCLUDE_NOTES` / `AI_STORE_OUTPUT` | `false` / `true` / `false` | Modele gönderilen veya saklanan veri |
| `AI_CHAT_ENABLED` | `false` | Satış Asistanı |
| `AI_DAILY_EMAIL` | `false` | Günlük maillerde AI paragrafı |
| `AI_DIAGNOSIS_INTERPRET_ENABLED` | `false` | DE-3 teşhis yorumu |
| `AI_DIAGNOSIS_HISTORY_INTERPRET_ENABLED` | `false` | DE-5 geçmiş yorumu |
| `AI_DE4_INTERPRET_PROPOSAL_BRIDGE_ENABLED` | `false` | DE-3 önerilerini DE-4 aksiyon önerilerine çevirir |
| `ASSISTANT_MEMORY_ENABLED` / `ASSISTANT_MEMORY_REDIS_URL` | `false` / `redis://127.0.0.1:6379/0` | Redis çalışma belleği |
| `FOLLOWUP_REMINDER_DAYS` | `3` | Bir lead'in takip bekliyor sayılması için gereken gün |

Tam liste: [backend/.env.example](./backend/.env.example) ve `backend/config.py`.

---

## Proje yapısı

```
behtech_saleshub/
├── backend/
│   ├── main.py                  # FastAPI girişi
│   ├── database.py              # Modeller (CRM, AiAction, AiRun, diagnosis, assistant_*)
│   ├── config.py                # Ayarlar / feature flag'ler
│   ├── ai/
│   │   ├── router.py            # /api/ai/*
│   │   ├── capabilities/        # chat, chat_stream, chat_tools, teşhis yorumlayıcıları, priorities, agent, …
│   │   ├── actions/             # DE-4 registry, politikalar, yaşam döngüsü, eşleyici, tekilleştirme, executor'lar
│   │   ├── crm_tools.py         # Asistanın salt okunur araçları
│   │   ├── entity_continuity.py # Aktif lead bağlama
│   │   ├── assistant_memory.py  # Redis çalışma belleği
│   │   ├── snapshots/           # Lead / org snapshot'ları + kişisel veri temizleme
│   │   ├── prompts/             # Sistem prompt'ları (Markdown)
│   │   └── usage.py             # Token kotası takibi
│   ├── intelligence/
│   │   ├── diagnosis/           # Kurallar, motor, parmak izi, sync, trend, geçmiş API'si
│   │   ├── scoring.py
│   │   ├── insights.py
│   │   └── router.py            # /api/intelligence/*
│   ├── jobs/                    # AI batch + otomasyon cron girişleri
│   └── tests/                   # DE-1 … DE-6 ve Faz 2–7 regresyon testleri
├── frontend/src/
│   ├── components/
│   │   ├── IntelligencePage.tsx
│   │   └── ai/                  # SalesAssistantPage, teşhis kartları, DE-4 kutusu, …
│   ├── api.ts
│   └── i18n/
├── deploy/                      # nginx, systemd, yedekleme, sunucu script'leri
├── docs/architecture/           # Mimari freeze notları
├── docker-compose.yml
├── DEPLOY.md
└── start.sh
```

---

## API özeti

| Prefix | İçerik |
|--------|--------|
| `/api/auth/*` | Giriş, kayıt, refresh / beni hatırla, şifre sıfırlama, e-posta doğrulama |
| `/api/leads/*` | CRUD, aktiviteler, ekler, tahsilatlar |
| `/api/dashboard`, `/api/analytics`, `/api/reports/*` | Dashboard, analitik, dönem raporları |
| `/api/intelligence/*` | KPI, insights, şirket profili, teşhisler, sync, geçmiş, trend, aksiyon önerileri |
| `/api/ai/*` | status, suggest-message, summarize-lead, priorities, chat / chat/stream, conversations, runs, teşhis yorumu, aksiyonlar (propose / update / cancel / approve / execute) |

Sağlık kontrolü: `GET https://saleshub.behtechlabs.com/api/health`

---

## Güvenlik

- bcrypt ile şifre hash'leme, HttpOnly refresh cookie'li JWT, boşta kalma zaman aşımı.
- Giriş / kayıt / sıfırlama ve AI uç noktalarında rate limit.
- Organizasyon izolasyonu her sorguda ve her asistan aracında sunucu tarafında uygulanır.
- Asistan araçları salt okunurdur. Yazma işlemleri yalnızca onaylı DE-4 aksiyon akışıyla yapılır.
- Finansal ve yıkıcı işlemler aksiyon kaydında AI'a kapalıdır.
- Canlıda HTTPS, sıkı CORS ve güçlü `SECRET_KEY` kullanılır; `.env` dosyaları git'e girmez.

Sunucu kurulumu: [DEPLOY.md](./DEPLOY.md) · [deploy/SUNUCU-KURULUM.md](./deploy/SUNUCU-KURULUM.md)

---

## Geliştirme

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Testler:

```bash
cd backend
pytest -q
# Yalnızca AI / teşhis testleri
pytest tests/test_diagnosis_de*.py tests/test_de4_*.py tests/test_de5_*.py tests/test_de6_*.py -q
```

---

## Lisans

[MIT Lisansı](./LICENSE). Copyright (c) BehTech / Behlul Alar.

Sorular ve kurumsal kullanım: [BehTech Labs](https://behtechlabs.com)

---

<p align="center">
  <sub>BehTech Sales Hub: veriye dayalı satış takibi, açıklanabilir teşhis, kontrollü AI.</sub>
</p>
