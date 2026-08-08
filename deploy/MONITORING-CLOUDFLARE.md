# Faz 3 — Cloudflare + UptimeRobot Kurulumu

**Site:** `https://saleshub.behtechlabs.com`  
**Sunucu IP:** `45.141.150.48`  
**Health endpoint:** `https://saleshub.behtechlabs.com/api/health`

---

## Bölüm 1 — Cloudflare DNS

### 1.1 Site ekle
1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Add a site**
2. Domain: `behtechlabs.com`
3. Plan: **Free**

### 1.2 Nameserver değiştir (Squarespace)
Cloudflare size 2 nameserver verir (ör. `ada.ns.cloudflare.com`).

Squarespace → **Domains** → **behtechlabs.com** → **DNS / Nameservers**  
Squarespace nameserver'ları → Cloudflare nameserver'ları ile değiştir.

> Yayılma 1–24 saat sürebilir. Cloudflare dashboard'da "Active" olunca devam edin.

### 1.3 DNS kayıtları (Cloudflare DNS sekmesi)

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `saleshub` | `45.141.150.48` | **Proxied** (turuncu bulut) |
| TXT | `saleshub` | `google-site-verification=...` | DNS only (gri) — Search Console için |
| TXT | `@` veya `google._domainkey` | Mevcut e-posta DKIM kayıtları | DNS only |

**Önemli:** `saleshub` A kaydı **turuncu bulut (Proxied)** olmalı — DDoS koruması ve CDN için.

### 1.4 SSL/TLS ayarı
Cloudflare → **SSL/TLS** → Overview:

| Ayar | Değer |
|------|--------|
| Encryption mode | **Full (strict)** |

Sunucuda zaten Let's Encrypt sertifikası var; Full (strict) doğru mod.

### 1.5 Güvenlik (önerilen)
Cloudflare → **Security** → **Settings**:

- **Security Level:** Medium
- **Bot Fight Mode:** On (Free plan)
- **Browser Integrity Check:** On

Cloudflare → **Speed** → **Optimization**:
- Auto Minify: CSS, JS (isteğe bağlı)

### 1.6 Sunucuda Cloudflare gerçek IP
SSH ile sunucuda (bir kez):

```bash
cp /opt/behtech-sales-hub/deploy/nginx-cloudflare-realip.conf /etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

Aylık güncelleme (isteğe bağlı cron):
```bash
chmod +x /opt/behtech-sales-hub/deploy/update-cloudflare-ips.sh
# 0 4 1 * * /opt/behtech-sales-hub/deploy/update-cloudflare-ips.sh
```

---

## Bölüm 2 — UptimeRobot

### 2.1 HTTP(S) monitor ekle
1. [uptimerobot.com](https://uptimerobot.com) → **Add New Monitor**

| Alan | Değer |
|------|--------|
| Monitor Type | **HTTP(s)** |
| Friendly Name | `BehTech Sales Hub` |
| URL | `https://saleshub.behtechlabs.com/api/health` |
| Monitoring Interval | **5 minutes** (Free) |
| Monitor Timeout | 30 seconds |

### 2.2 Keyword monitoring (önerilen)
Aynı monitor'de veya ikinci monitor:

| Alan | Değer |
|------|--------|
| Keyword Type | **Keyword Exists** |
| Keyword | `"status":"ok"` |

Health endpoint DB sorunu varsa `"status":"degraded"` döner → UptimeRobot alarm verir.

### 2.3 İkinci monitor — ana sayfa
| Alan | Değer |
|------|--------|
| URL | `https://saleshub.behtechlabs.com/` |
| Keyword | `BehTech Sales Hub` veya `Sales Hub` |

### 2.4 Bildirimler
**My Settings** → **Alert Contacts**:
- E-posta (behlulalar32@gmail.com)
- İsterseniz Telegram / Slack entegrasyonu

Her monitor'e alert contact bağlayın.

---

## Bölüm 3 — Kontrol listesi

Deploy sonrası terminalden:

```bash
# Health (200 + database ok)
curl -s https://saleshub.behtechlabs.com/api/health | jq .

# Beklenen:
# { "status": "ok", "env": "production", "database": "ok", "version": "2.0.0" }

# Cloudflare üzerinden mi geliyor?
curl -sI https://saleshub.behtechlabs.com/ | grep -i cf-ray
# cf-ray header varsa Cloudflare aktif
```

---

## Bölüm 4 — Sorun giderme

| Sorun | Çözüm |
|-------|--------|
| 522 Error (Cloudflare) | Sunucuda `systemctl status behtech-crm` — backend çökmüş |
| 525 SSL handshake | Cloudflare SSL → Full (strict), sunucuda certbot kontrol |
| Health 503 | PostgreSQL down — `systemctl status postgresql` |
| UptimeRobot false alarm | Keyword'ü `"database":"ok"` olarak daraltın |
| Search Console TXT kayboldu | Cloudflare DNS'e TXT kaydını tekrar ekleyin (DNS only) |

---

## Özet sıra

1. Cloudflare'e site ekle → nameserver değiştir  
2. A kaydı `saleshub` → `45.141.150.48` (Proxied)  
3. SSL: Full (strict)  
4. Sunucuda `nginx-cloudflare-realip.conf`  
5. UptimeRobot → `/api/health` + keyword `"status":"ok"`  
6. Alert contact bağla
