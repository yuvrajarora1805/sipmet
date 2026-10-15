#!/usr/bin/env bash
# ==============================================================================
# BABA MILK - DOCKERIZED ASTERISK SIP INSTALLER FOR VPS
# Safe for servers already running Docker apps (Finance App, Postfix, etc.)
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo "🥛 Setting up WhatsApp Asterisk SIP (Docker Mode) on VPS"
echo "=================================================================="

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script as root (sudo ./deploy_docker.sh)"
  exit 1
fi

SIP_DOMAIN="${1:-}"
CERT_EMAIL="${2:-}"

if [ -z "$SIP_DOMAIN" ]; then
  read -rp "Enter your SIP Subdomain (e.g. sip.yourdomain.com): " SIP_DOMAIN
fi

if [ -z "$CERT_EMAIL" ]; then
  read -rp "Enter your email for Let's Encrypt SSL: " CERT_EMAIL
fi

echo "🔹 Target Domain: $SIP_DOMAIN"
echo "🔹 Admin Email:   $CERT_EMAIL"

# 1. Install certbot if not present
which certbot >/dev/null 2>&1 || (apt-get update && apt-get install -y certbot)

# 2. Open firewall for SIP TLS and RTP
echo "🛡️ Opening firewall ports 5061/TCP and 10000-20000/UDP..."
if which ufw >/dev/null 2>&1; then
    ufw allow 5061/tcp comment "SIP over TLS for Meta WhatsApp"
    ufw allow 10000:20000/udp comment "RTP / SRTP Media Streams"
fi

# 3. Obtain TLS certificate (using standalone challenge or existing webserver)
echo "🔒 Checking Let's Encrypt TLS Certificate for $SIP_DOMAIN..."
if [ ! -d "/etc/letsencrypt/live/$SIP_DOMAIN" ]; then
    certbot certonly --standalone \
        -d "$SIP_DOMAIN" \
        --non-interactive \
        --agree-tos \
        --email "$CERT_EMAIL" \
        --preferred-challenges http
fi

# Ensure certificate directory is readable
chmod 755 /etc/letsencrypt/live
chmod 755 /etc/letsencrypt/archive
chmod 644 "/etc/letsencrypt/live/$SIP_DOMAIN/privkey.pem"

# 4. Generate pjsip.conf from template
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$SCRIPT_DIR/recordings"
sed -e "s|{{SIP_DOMAIN}}|$SIP_DOMAIN|g" "$SCRIPT_DIR/config/pjsip.conf.template" > "$SCRIPT_DIR/config/pjsip.conf"

# 5. Launch Asterisk container
echo "🚀 Starting Asterisk Docker container..."
cd "$SCRIPT_DIR"
docker compose up -d

echo "=================================================================="
echo "✅ Asterisk SIP Container is Up & Running alongside your other apps!"
echo "=================================================================="
echo "Diagnostic checks:"
echo "  docker exec -it babamilk-asterisk-sip asterisk -rx 'pjsip show transports'"
echo "  docker exec -it babamilk-asterisk-sip asterisk -rx 'pjsip show endpoints'"
echo "=================================================================="
