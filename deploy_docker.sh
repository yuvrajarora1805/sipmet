#!/usr/bin/env bash
# ==============================================================================
# BABA MILK - 100% DOCKERIZED ASTERISK SIP & SSL SETUP
# Zero host packages required. Everything runs inside Docker containers.
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo "🥛 WhatsApp Asterisk SIP (100% Docker Mode) for VPS"
echo "=================================================================="

SIP_DOMAIN="${1:-sip.yarora.dev}"
CERT_EMAIL="${2:-yuvrajmahoney@gmail.com}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p certs recordings

echo "🔹 Domain: $SIP_DOMAIN"
echo "🔹 Email:  $CERT_EMAIL"

# 1. Obtain Let's Encrypt Certificate entirely via Docker Certbot
if [ ! -d "certs/live/$SIP_DOMAIN" ]; then
    echo "🔒 Requesting SSL Certificate using Certbot in Docker..."
    echo "Using DNS manual verification so port 80 is NEVER blocked..."
    
    docker run -it --rm \
        -v "$SCRIPT_DIR/certs:/etc/letsencrypt" \
        certbot/certbot:latest certonly \
        --manual \
        --preferred-challenges dns \
        -d "$SIP_DOMAIN" \
        --agree-tos \
        --email "$CERT_EMAIL" \
        --no-eff-email
fi

# Ensure certificate directory is accessible by Asterisk container
chmod -R 755 certs/
chmod -R 644 certs/archive/ 2>/dev/null || true
chmod -R 644 certs/live/ 2>/dev/null || true

# 2. Generate Asterisk PJSIP configuration with the domain
echo "⚙️ Configuring PJSIP with domain $SIP_DOMAIN..."
sed -e "s|{{SIP_DOMAIN}}|$SIP_DOMAIN|g" config/pjsip.conf.template > config/pjsip.conf

# 3. Start Asterisk & Certbot containers
echo "🚀 Launching Asterisk & Certbot Docker services..."
docker compose up -d

echo "=================================================================="
echo "✅ All services running in Docker!"
echo "=================================================================="
docker ps | grep -E "asterisk|certbot"
echo "=================================================================="
