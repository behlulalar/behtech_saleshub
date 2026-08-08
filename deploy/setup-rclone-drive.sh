#!/bin/bash
# Google Drive Pro kurulumu — behlulalar32@gmail.com hesabı

set -euo pipefail

echo "=== BehTech Sales Hub — Google Drive yedek kurulumu ==="
echo ""
echo "Hesap: behlulalar32@gmail.com"
echo "Klasör: Drive'da siz oluşturursunuz (ör. saleshub_yedekleri — randevu_yedekleri gibi)"
echo ""

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone kuruluyor..."
  curl -fsSL https://rclone.org/install.sh | bash
else
  echo "rclone zaten kurulu: $(rclone version | head -1)"
fi

echo ""
echo "── Adım 1: Google hesabını bağla ──"
echo "  rclone config"
echo ""
echo "  n) New remote"
echo "  name → gdrive"
echo "  Storage → drive"
echo "  client_id → Enter (boş)"
echo "  client_secret → Enter (boş)"
echo "  scope → 1 (Full access)"
echo "  service_account_file → Enter"
echo "  Edit advanced config → n"
echo "  auto config → n   ← sunucuda tarayıcı yok"
echo "  rclone'un verdiği linki Mac'inizde açın"
echo "  behlulalar32@gmail.com ile giriş yapın, kodu sunucuya yapıştırın"
echo "  Configure as Shared Drive → n"
echo ""
echo "── Adım 2: Drive'da klasör oluştur ──"
echo "  drive.google.com → Yeni klasör → saleshub_yedekleri"
echo "  (İsterseniz farklı isim; backup.env içindeki RCLONE_DEST ile aynı olmalı)"
echo ""
echo "── Adım 3: Test ──"
echo "  rclone lsd gdrive:"
echo "  rclone lsd gdrive:saleshub_yedekleri"
echo ""
echo "── Adım 4: Ayar dosyası ──"
echo "  cp /opt/behtech-sales-hub/deploy/backup.env.example /opt/behtech-sales-hub/deploy/backup.env"
echo "  # RCLONE_DEST=saleshub_yedekleri  (Drive'daki klasör adınız)"
echo ""
echo "── Adım 5: İlk yedek ──"
echo "  /opt/behtech-sales-hub/deploy/backup-all.sh"
echo ""
echo "Drive'da göreceğiniz dosyalar (saleshub_yedekleri/ içinde):"
echo "  behtech_crm_20260717_030001.sql.gz   ← veritabanı dump"
echo "  uploads_20260717_030002.tar.gz        ← sözleşme/dosya yedekleri"
echo ""
echo "── Cron (her gece 03:00) ──"
echo "  0 3 * * * /opt/behtech-sales-hub/deploy/backup-all.sh >> /var/log/behtech-crm-backup.log 2>&1"
echo ""
