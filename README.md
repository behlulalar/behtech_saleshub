# BehTech Sales Hub

Yerel veya sunucuda çalışan, çok kullanıcılı müşteri takip ve pazar araştırması sistemi.

## Özellikler

- **Çok kullanıcılı hesap sistemi** — her kullanıcı kendi verilerini görür
- **Kullanıcı adı + şifre** ile giriş (bcrypt hash)
- **Hesap oluşturma** — yeni kullanıcılar boş panelle başlar
- **Şifremi unuttum** — e-posta ile güvenli sıfırlama
- **Beni hatırla** ve **30 dk AFK otomatik çıkış**
- **Düzenlenebilir kategoriler** ve detaylı CRM alanları
- **Mobil uyumlu** minimal arayüz

## Gereksinimler

- Python 3.10+
- Node.js 18+
- Docker (PostgreSQL için)

## Kurulum ve Çalıştırma

```bash
chmod +x start.sh
./start.sh
```

Tarayıcıda: **http://localhost:5173**

### Varsayılan Admin Hesabı

| Alan | Değer |
|------|-------|
| Kullanıcı adı | `behlul` |
| Şifre | `backend/.env` içindeki `SEED_ADMIN_PASSWORD` |

## Güvenlik

- Şifreler **bcrypt** ile hashlenir (düz metin saklanmaz)
- JWT tabanlı oturum yönetimi
- Giriş, kayıt ve şifre sıfırlama için **rate limiting**
- Şifre sıfırlama token'ları hashlenir, tek kullanımlık ve süreli
- Kullanıcı enumerasyonu önlenir (şifremi unuttum her zaman aynı mesajı döner)
- HTTP güvenlik başlıkları (X-Frame-Options, X-Content-Type-Options vb.)
- Her kullanıcının verisi `user_id` ile izole edilir

### Sunucuya Yayınlarken

1. `SECRET_KEY` değerini güçlü rastgele bir anahtarla değiştirin
2. `APP_URL` ve `CORS_ORIGINS` değerlerini domain'inize ayarlayın
3. HTTPS kullanın (Nginx + Let's Encrypt önerilir)
4. Şifre sıfırlama için SMTP ayarlarını yapılandırın:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=app-password
SMTP_FROM=your@email.com
```

5. `SEED_ADMIN_PASSWORD` değerini üretim ortamında değiştirin

**Sunucuya izole deploy için:** [DEPLOY.md](./DEPLOY.md) dosyasına bakın.

## Veritabanı

PostgreSQL — `docker compose up -d` ile başlar (port **5433**).

```
DATABASE_URL=postgresql+psycopg2://crm_user:crm_pass@localhost:5433/crm_db
```

## Proje Yapısı

```
musteri_takip_programi/
├── backend/          # FastAPI + PostgreSQL
├── frontend/         # React + Vite + Tailwind
├── docker-compose.yml
├── start.sh
└── README.md
```
