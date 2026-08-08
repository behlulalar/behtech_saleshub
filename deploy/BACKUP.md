# BehTech Sales Hub — Yedekleme (Google Drive)

Berber sisteminizdeki **`randevu_yedekleri`** mantığının aynısı: dump dosyası doğrudan Drive'daki klasöre gider.

## Hesap ve klasör

| | |
|---|---|
| **Google hesabı** | `behlulalar32@gmail.com` |
| **Drive klasörü** | Siz oluşturursunuz, örn. **`saleshub_yedekleri`** |
| **rclone remote adı** | `gdrive` |

Drive'da klasör yapısı (düz — alt klasör yok):

```
Google Drive (behlulalar32@gmail.com)
└── saleshub_yedekleri/
    ├── behtech_crm_20260717_030001.sql.gz    ← DB dump
    ├── behtech_crm_20260718_030001.sql.gz
    └── uploads_20260717_030002.tar.gz        ← sözleşme dosyaları (varsa)
```

Klasör adını değiştirirseniz `deploy/backup.env` içindeki `RCLONE_DEST` ile **aynı** yazın.

## Sistem bunu nereden biliyor?

1. **Hangi hesap?** → Sunucuda `rclone config` ile `behlulalar32@gmail.com` bağlanır (`gdrive` remote).
2. **Hangi klasör?** → `deploy/backup.env` → `RCLONE_DEST=saleshub_yedekleri`
3. **Script** → `gdrive:saleshub_yedekleri` yoluna `.sql.gz` ve `.tar.gz` kopyalar.

## Kurulum (sunucuda, bir kez)

```bash
ssh root@45.141.150.48
/opt/behtech-sales-hub/deploy/setup-rclone-drive.sh
rclone config
```

`rclone config` sırasında linki **Mac'inizde** açıp **behlulalar32@gmail.com** ile giriş yapın.

Drive'da (tarayıcıdan) klasör oluşturun: **`saleshub_yedekleri`**

```bash
cp /opt/behtech-sales-hub/deploy/backup.env.example /opt/behtech-sales-hub/deploy/backup.env
chmod 600 /opt/behtech-sales-hub/deploy/backup.env
mkdir -p /var/backups/behtech-crm/uploads
/opt/behtech-sales-hub/deploy/backup-all.sh
```

Kontrol:

```bash
rclone ls gdrive:saleshub_yedekleri
```

## Otomatik (cron)

```cron
0 3 * * * /opt/behtech-sales-hub/deploy/backup-all.sh >> /var/log/behtech-crm-backup.log 2>&1
```

- Sunucuda yedek **7 gün** kalır (disk dolmasın)
- Drive'da **365 gün** kalır (5 TB plan)

## backup.env özeti

```bash
RCLONE_REMOTE=gdrive
RCLONE_DEST=saleshub_yedekleri   # ← Drive'daki klasör adınız
DRIVE_RETENTION_DAYS=365
RETENTION_DAYS=7                   # sunucuda kısa tut
```

## Drive'dan geri yükleme

```bash
# En son dump'ı indir
rclone copy gdrive:saleshub_yedekleri/ /tmp/restore/ --include "*.sql.gz" --max-age 48h
gunzip -c /tmp/restore/behtech_crm_*.sql.gz | psql -h 127.0.0.1 -U behtech_crm_user -d behtech_crm
```

Dosya yedekleri için:

```bash
rclone copy gdrive:saleshub_yedekleri/ /tmp/restore/ --include "uploads_*.tar.gz" --max-age 48h
systemctl stop behtech-crm
tar -xzf /tmp/restore/uploads_*.tar.gz -C /opt/behtech-sales-hub/backend
chown -R behtech:behtech /opt/behtech-sales-hub/backend/uploads
systemctl start behtech-crm
```
