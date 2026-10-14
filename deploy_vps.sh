#!/usr/bin/env bash
# ==============================================================================
# BABA MILK - WHATSAPP BUSINESS CALLING ASTERISK SIP INSTALLER FOR VPS
# Target OS: Ubuntu 22.04 / 24.04 LTS or Debian 12
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo "🥛 Setting up Asterisk SIP for Meta WhatsApp Calling on VPS"
echo "=================================================================="

# Check root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script as root (sudo ./deploy_vps.sh)"
  exit 1
fi

# Variables (Passed as arguments or prompted)
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

# 1. Update system & install dependencies
echo "📦 Updating repositories and installing prerequisites..."
apt-get update -y
apt-get install -y \
    asterisk \
    asterisk-modules \
    asterisk-opus \
    asterisk-core-sounds-en-wav \
    asterisk-core-sounds-en-g722 \
    certbot \
    ufw \
    curl \
    git \
    sngrep

# 2. Configure Firewall (UFW)
echo "🛡️ Configuring Firewall rules for SIP TLS and RTP Media..."
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP for Let's Encrypt verification"
ufw allow 5061/tcp comment "SIP over TLS for Meta WhatsApp"
ufw allow 10000:20000/udp comment "RTP / SRTP Media Streams"
ufw --force enable

# 3. Obtain TLS Certificate via Certbot
echo "🔒 Requesting Let's Encrypt TLS Certificate for $SIP_DOMAIN..."
systemctl stop asterisk || true

certbot certonly --standalone \
    -d "$SIP_DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$CERT_EMAIL" \
    --preferred-challenges http

# Set permissions for Asterisk to read TLS certificates
CERT_DIR="/etc/letsencrypt/live/$SIP_DOMAIN"
chmod 755 /etc/letsencrypt/live
chmod 755 /etc/letsencrypt/archive
chmod 640 "$CERT_DIR/privkey.pem"
chown -R root:asterisk /etc/letsencrypt/archive
chown -R root:asterisk /etc/letsencrypt/live

# 4. Backup existing Asterisk configs
echo "💾 Backing up default Asterisk configs..."
mkdir -p /etc/asterisk/backup_$(date +%Y%m%d%H%M%S)
cp -r /etc/asterisk/*.conf /etc/asterisk/backup_$(date +%Y%m%d%H%M%S)/ 2>/dev/null || true

# 5. Copy customized PJSIP, Dialplan, and RTP configs
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "⚙️ Installing WhatsApp Calling configurations..."
sed -e "s|{{SIP_DOMAIN}}|$SIP_DOMAIN|g" "$SCRIPT_DIR/config/pjsip.conf.template" > /etc/asterisk/pjsip.conf
cp "$SCRIPT_DIR/config/extensions.conf" /etc/asterisk/extensions.conf
cp "$SCRIPT_DIR/config/rtp.conf" /etc/asterisk/rtp.conf
cp "$SCRIPT_DIR/config/asterisk.conf" /etc/asterisk/asterisk.conf 2>/dev/null || true

chown -R asterisk:asterisk /etc/asterisk

# 6. Start & Enable Asterisk Service
echo "🚀 Starting Asterisk Service..."
systemctl restart asterisk
systemctl enable asterisk

# 7. Certificate auto-renewal hook for Asterisk
cat <<EOF > /etc/letsencrypt/renewal-hooks/post/asterisk-reload.sh
#!/bin/bash
chown -R root:asterisk /etc/letsencrypt/archive
chown -R root:asterisk /etc/letsencrypt/live
chmod 640 /etc/letsencrypt/live/$SIP_DOMAIN/privkey.pem
asterisk -rx "module reload res_pjsip.so"
EOF
chmod +x /etc/letsencrypt/renewal-hooks/post/asterisk-reload.sh

echo "=================================================================="
echo "✅ Asterisk SIP Server Installed & Running on VPS!"
echo "=================================================================="
echo "Verify status with:"
echo "  asterisk -rx 'pjsip show transports'"
echo "  asterisk -rx 'pjsip show endpoints'"
echo "Live SIP packet trace:"
echo "  sngrep"
echo "=================================================================="
