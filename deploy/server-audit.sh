#!/bin/bash
# BehTech Sales Hub — sunucu envanter / çakışma analizi
# Kullanım: chmod +x deploy/server-audit.sh && ./deploy/server-audit.sh
# Çıktıyı kaydetmek için: ./deploy/server-audit.sh | tee server-audit-$(date +%F).txt

set -u

REPORT_TIME="$(date -Iseconds 2>/dev/null || date)"
HOSTNAME_VAL="$(hostname 2>/dev/null || echo unknown)"
OS_VAL="$(uname -a 2>/dev/null || echo unknown)"

section() {
  echo ""
  echo "================================================================"
  echo " $1"
  echo "================================================================"
}

cmd_or_skip() {
  local label="$1"
  shift
  echo ""
  echo "--- $label ---"
  if command -v "$1" &>/dev/null; then
    "$@" 2>&1 || echo "[komut hata kodu: $?]"
  else
    echo "[atlandı: $1 bulunamadı]"
  fi
}

echo "BehTech Sales Hub — Sunucu Denetim Raporu"
echo "Zaman   : $REPORT_TIME"
echo "Host    : $HOSTNAME_VAL"
echo "Sistem  : $OS_VAL"

section "1) DISK & DIZINLER (/opt, /var/www, /home)"
cmd_or_skip "Disk kullanımı" df -h
echo ""
echo "--- /opt içeriği ---"
ls -la /opt 2>/dev/null || echo "[/opt yok veya erişim yok]"
echo ""
echo "--- /var/www içeriği ---"
ls -la /var/www 2>/dev/null || echo "[/var/www yok veya erişim yok]"
echo ""
echo "--- /home kullanıcı dizinleri ---"
ls -la /home 2>/dev/null || echo "[/home erişim yok]"

section "2) DINLENEN PORTLAR (çakışma riski)"
if command -v ss &>/dev/null; then
  echo "--- ss -tulpn (TCP/UDP) ---"
  ss -tulpn 2>&1 || sudo ss -tulpn 2>&1
elif command -v netstat &>/dev/null; then
  netstat -tulpn 2>&1 || sudo netstat -tulpn 2>&1
else
  echo "[ss/netstat bulunamadı]"
fi

section "3) DOCKER"
cmd_or_skip "Docker sürüm" docker --version
echo ""
echo "--- Çalışan container'lar ---"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>&1 || echo "[docker ps başarısız]"
echo ""
echo "--- Tüm container'lar ---"
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>&1 || true
echo ""
echo "--- Docker compose projeleri ---"
docker compose ls 2>&1 || docker-compose ls 2>&1 || echo "[compose ls yok]"
echo ""
echo "--- Docker network'ler ---"
docker network ls 2>&1 || true
echo ""
echo "--- Docker volume'ler ---"
docker volume ls 2>&1 || true

section "4) SYSTEMD SERVISLERI (web, db, app)"
for pattern in nginx apache2 httpd caddy traefik postgres mysql mariadb redis docker pm2 node python gunicorn uvicorn; do
  if command -v systemctl &>/dev/null; then
    matches="$(systemctl list-units --type=service --all 2>/dev/null | grep -i "$pattern" || true)"
    if [ -n "$matches" ]; then
      echo ""
      echo "--- systemctl | grep -i $pattern ---"
      echo "$matches"
    fi
  fi
done

section "5) NGINX / APACHE YAPILANDIRMASI"
if command -v nginx &>/dev/null; then
  echo "--- nginx -v ---"
  nginx -v 2>&1
  echo ""
  echo "--- nginx -T (server_name + listen + proxy_pass) ---"
  nginx -T 2>/dev/null | grep -E '^\s*(server_name|listen|proxy_pass|root)\s' || sudo nginx -T 2>/dev/null | grep -E '^\s*(server_name|listen|proxy_pass|root)\s' || echo "[nginx -T erişilemedi — sudo gerekebilir]"
  echo ""
  echo "--- sites-enabled ---"
  ls -la /etc/nginx/sites-enabled 2>/dev/null || true
fi

if command -v apache2 &>/dev/null || command -v httpd &>/dev/null; then
  cmd_or_skip "apache servis durumu" systemctl status apache2 --no-pager
fi

section "6) VERITABANLARI (host üzerinde)"
cmd_or_skip "PostgreSQL servis" systemctl status postgresql --no-pager
cmd_or_skip "MySQL/MariaDB servis" systemctl status mysql --no-pager
cmd_or_skip "Redis servis" systemctl status redis --no-pager

section "7) PM2 / NODE / PYTHON SURECLERI"
cmd_or_skip "PM2 list" pm2 list
echo ""
echo "--- node süreçleri ---"
pgrep -af node 2>/dev/null || echo "[node süreci yok]"
echo ""
echo "--- python/uvicorn/gunicorn süreçleri ---"
pgrep -af 'uvicorn|gunicorn|python' 2>/dev/null | head -30 || echo "[python app süreci yok]"

section "8) KRITIK PORT KONTROLU (BehTech CRM için)"
check_port() {
  local port="$1"
  if command -v ss &>/dev/null; then
    result="$(ss -tlnp 2>/dev/null | grep ":${port} " || true)"
  else
    result="$(netstat -tlnp 2>/dev/null | grep ":${port} " || true)"
  fi
  if [ -n "$result" ]; then
    echo "DOLU  : $port -> $result"
  else
    echo "BOS   : $port"
  fi
}

for port in 80 443 3000 3306 5432 5433 8000 8080 5173 18080 18081; do
  check_port "$port"
done

section "9) BEHTECH CRM ONERILEN KAYNAKLAR (rezerve isimler)"
echo "Önerilen compose project : behtech-sales-hub"
echo "Önerilen container'lar   : behtech_crm_postgres, behtech_crm_backend, behtech_crm_web"
echo "Önerilen network         : behtech_crm_net"
echo "Önerilen volume          : behtech_crm_pgdata"
echo "Önerilen host port       : 127.0.0.1:18080 (veya boş bir port)"
echo ""
echo "--- Mevcut isim çakışması kontrolü ---"
docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E 'behtech|crm' || echo "behtech/crm isimli container yok"
docker network ls --format '{{.Name}}' 2>/dev/null | grep -E 'behtech|crm' || echo "behtech/crm network yok"
docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E 'behtech|crm' || echo "behtech/crm volume yok"

section "10) FIREWALL (varsa)"
cmd_or_skip "ufw status" ufw status verbose
cmd_or_skip "firewalld" firewall-cmd --list-all

echo ""
echo "================================================================"
echo " Rapor tamamlandı: $REPORT_TIME"
echo " Bu çıktıyı paylaşın; deploy planı buna göre netleştirilir."
echo "================================================================"
