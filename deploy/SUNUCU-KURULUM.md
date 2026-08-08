# Sunucuya Deploy — saleshub.behtechlabs.com

Sunucu: `root@45.141.150.48`  
Dizin: `/opt/behtech-sales-hub`  
Domain: `https://saleshub.behtechlabs.com`

---

## Tek komut (önerilen)

Lokal Mac'te proje kökünden:

```bash
chmod +x deploy/upload-to-server.sh deploy/setup-server.sh
./deploy/upload-to-server.sh
ssh root@45.141.150.48 'chmod +x /opt/behtech-sales-hub/deploy/setup-server.sh && /opt/behtech-sales-hub/deploy/setup-server.sh'
```

---

## Manuel SCP komutları (adım adım)

### 1) Lokal build

```bash
cd /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/frontend
npm run build
cd ..
```

### 2) Sunucuda dizin

```bash
ssh root@45.141.150.48 "mkdir -p /opt/behtech-sales-hub"
```

### 3) Backend (venv ve local .env hariç)

```bash
scp -r /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/backend \
  root@45.141.150.48:/opt/behtech-sales-hub/

ssh root@45.141.150.48 "rm -rf /opt/behtech-sales-hub/backend/venv"
```

### 4) Frontend build çıktısı

```bash
scp -r /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/frontend/dist \
  root@45.141.150.48:/opt/behtech-sales-hub/frontend/
```

### 5) Deploy dosyaları

```bash
scp /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/deploy/saleshub.nginx.conf \
  root@45.141.150.48:/opt/behtech-sales-hub/deploy/

scp /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/deploy/behtech-crm.service \
  root@45.141.150.48:/opt/behtech-sales-hub/deploy/

scp /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/deploy/setup-server.sh \
  root@45.141.150.48:/opt/behtech-sales-hub/deploy/
```

### 6) Sunucu .env (local SMTP korunur, URL/DB sunucuya uygun)

```bash
scp /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/backend/.env.server.example \
  root@45.141.150.48:/opt/behtech-sales-hub/backend/.env
```

### 7) Sunucuda kurulum

```bash
ssh root@45.141.150.48
chmod +x /opt/behtech-sales-hub/deploy/setup-server.sh
/opt/behtech-sales-hub/deploy/setup-server.sh
```

---

## Tek rsync (tüm proje — alternatif)

```bash
cd /Users/muhammedbehlulalar/Desktop/musteri_takip_programi/frontend && npm run build && cd ..

rsync -avz --delete \
  --exclude '.git' \
  --exclude 'backend/venv' \
  --exclude 'backend/.env' \
  --exclude 'backend/__pycache__' \
  --exclude 'frontend/node_modules' \
  --exclude 'node_modules' \
  --exclude '.cursor' \
  ./ root@45.141.150.48:/opt/behtech-sales-hub/

scp backend/.env.server.example root@45.141.150.48:/opt/behtech-sales-hub/backend/.env
```

---

## DNS (kurulumdan önce)

```
saleshub.behtechlabs.com  A  45.141.150.48
```

---

## Güncelleme (kod değişikliği sonrası)

```bash
./deploy/upload-to-server.sh
ssh root@45.141.150.48 'systemctl restart behtech-crm && systemctl reload nginx'
```

---

## Çakışma yok

| Kaynak | Değer |
|--------|--------|
| Port | `127.0.0.1:18080` (8001/8002/8003 boş) |
| DB | `behtech_crm_db` (ayrı) |
| Nginx | Yeni site: `behtech-saleshub.conf` |
| Dizin | `/opt/behtech-sales-hub` |
