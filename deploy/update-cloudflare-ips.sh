#!/bin/bash
# Cloudflare IP listesini günceller (ayda bir cron önerilir)
set -euo pipefail

OUT="/etc/nginx/conf.d/nginx-cloudflare-realip.conf"

{
  echo "# Cloudflare gerçek IP — otomatik güncellendi: $(date -Iseconds)"
  curl -fsSL https://www.cloudflare.com/ips-v4 | sed 's/^/set_real_ip_from /; s/$/;/'
  curl -fsSL https://www.cloudflare.com/ips-v6 | sed 's/^/set_real_ip_from /; s/$/;/'
  echo "real_ip_header CF-Connecting-IP;"
  echo "real_ip_recursive on;"
} > "$OUT"

nginx -t && systemctl reload nginx
echo "Güncellendi: $OUT"
