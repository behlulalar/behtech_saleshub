# BehTech Sales Hub — Sunucuya İzole Deploy Rehberi

Bu rehber, uygulamayı **mevcut sunucudaki diğer sistemlerle çakışmadan** çalıştırmanız içindir.

## İzolasyon stratejisi (özet)

| Katman | Nasıl izole edilir |
|--------|-------------------|
| Docker project | `behtech-sales-hub` (ayrı compose projesi) |
| Container isimleri | `behtech_crm_*` (benzersiz) |
| Network | `behtech_crm_net` (sadece bu uygulama) |
| Volume | `behtech_crm_pgdata` (ayrı PostgreSQL verisi) |
| PostgreSQL portu | **Host'a açılmaz** (5432/5433 çakışması yok) |
| Uygulama portu | Sadece `127.0.0.1:18080` (değiştirilebilir) |
| Dış erişim | Mevcut **host Nginx** → subdomain proxy |
| Kod dizini | Örn. `/opt/behtech-sales-hub` (ayrı klasör) |

```text
Internet
   │
   ▼
[Sunucu Nginx]  ← zaten çalışan diğer siteler burada kalır
   │  saleshub.behtechlabs.com → 127.0.0.1:18080
   ▼
[behtech_crm_web] ──► [behtech_crm_backend] ──► [behtech_crm_postgres]
     (docker)              (docker)                  (docker, iç ağ)
```

---

## 1) Sunucuda ön kontrol (çakışma taraması)

Sunucuya SSH ile bağlanın:

```bash
# Kullanılan portlar
sudo ss -tlnp

# Çalışan container'lar
docker ps --format 'table {{.Names}}\t{{.Ports}}'

# 18080 boş mu? (farklı port istiyorsanız .env'de APP_HOST_PORT değiştirin)
sudo ss -tlnp | grep 18080 || echo "18080 uygun görünüyor"
```

**Çakışma riski olanlar (bu projede kullanılmaz / izole edilir):**
- `8000`, `5173` → production'da host'ta dinlenmez
- `5432`, `5433` → PostgreSQL host'a bind edilmez
- Genel `nginx` / `80` / `443` → paylaşılır ama **yeni server block** ile sadece subdomain eklenir

---

## 2) Projeyi sunucuya alın

Önerilen dizin:

```bash
sudo mkdir -p /opt/behtech-sales-hub
sudo chown $USER:$USER /opt/behtech-sales-hub
cd /opt/behtech-sales-hub
```

### Seçenek A — Git ile

```bash
git clone <repo-url> .
```

### Seçenek B — rsync ile (lokalden)

```bash
rsync -avz --exclude node_modules --exclude backend/venv --exclude .git \
  ./ user@SUNUCU_IP:/opt/behtech-sales-hub/
```

---

## 3) Production ortam dosyası

```bash
cd /opt/behtech-sales-hub
cp deploy/.env.production.example deploy/.env.production
nano deploy/.env.production
```

**Mutlaka değiştirin:**
- `POSTGRES_PASSWORD`
- `SECRET_KEY` (uzun rastgele)
- `SEED_ADMIN_PASSWORD`
- `APP_URL` → `https://saleshub.behtechlabs.com` (kendi subdomain'iniz)
- `CORS_ORIGINS` → aynı domain
- SMTP bilgileri

Port çakışması varsa:

```env
APP_HOST_PORT=18081
```

---

## 4) Deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Kontrol:

```bash
docker ps --filter name=behtech_crm
curl -I http://127.0.0.1:18080
```

Beklenen: `HTTP/1.1 200 OK`

---

## 5) Host Nginx'e subdomain ekleyin

Mevcut Nginx yapılandırmanıza **yeni site** olarak ekleyin (diğer `server` bloklarına dokunmayın).

```bash
sudo cp deploy/host-nginx.example.conf /etc/nginx/sites-available/behtech-crm.conf
sudo ln -s /etc/nginx/sites-available/behtech-crm.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

SSL:

```bash
sudo certbot --nginx -d saleshub.behtechlabs.com
```

DNS'te `saleshub.behtechlabs.com` A kaydını sunucu IP'nize yönlendirin.

---

## 6) Güncelleme (yeni sürüm push)

```bash
cd /opt/behtech-sales-hub
git pull   # veya rsync
./deploy/deploy.sh
```

Veritabanı volume'u (`behtech_crm_pgdata`) korunur; veri silinmez.

---

## 7) Yedekleme (kritik sistem)

```bash
# PostgreSQL dump
docker exec behtech_crm_postgres pg_dump -U behtech_crm_user behtech_crm_db > backup_$(date +%F).sql

# .env yedeği (güvenli yerde saklayın)
cp deploy/.env.production ~/backups/behtech-crm-env-$(date +%F)
```

---

## 8) Sorun giderme

| Belirti | Olası neden | Çözüm |
|---------|-------------|--------|
| 502 Bad Gateway | Web container down | `docker logs behtech_crm_web` |
| API hata | Backend DB bağlanamıyor | `docker logs behtech_crm_backend` |
| Port çakışması | 18080 dolu | `APP_HOST_PORT` değiştir + nginx proxy güncelle |
| CORS hatası | `CORS_ORIGINS` yanlış | `.env.production` domain ile eşleştir |
| Mail gitmiyor | SMTP / App Password | `backend/.env` değil, `deploy/.env.production` |

Loglar:

```bash
docker logs -f behtech_crm_backend
docker logs -f behtech_crm_web
docker logs -f behtech_crm_postgres
```

---

## 9) Bu sistemin diğerlerinden ayrı kalma garantisi

- **Ayrı PostgreSQL instance** (paylaşımlı DB yok)
- **Ayrı Docker network** (diğer container'larla trafik karışmaz)
- **Host'ta tek açık port**: loopback `127.0.0.1:APP_HOST_PORT`
- **Ayrı subdomain** ile routing
- **Ayrı volume** ile kalıcı veri
- `start.sh` production'da kullanılmaz (dev içindir; port 8000/5173 kill etmez)

---

## Hızlı checklist

- [ ] `deploy/.env.production` oluşturuldu ve şifreler değiştirildi
- [ ] `APP_HOST_PORT` sunucuda boş
- [ ] `./deploy/deploy.sh` başarılı
- [ ] `curl http://127.0.0.1:PORT` 200 dönüyor
- [ ] Nginx subdomain proxy eklendi
- [ ] SSL aktif
- [ ] DNS A kaydı doğru
- [ ] İlk giriş + mail doğrulama test edildi
