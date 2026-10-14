# 🥛 WhatsApp Business Calling with Asterisk SIP on VPS

This directory contains the production-ready Asterisk SIP configuration and deployment tools to connect your **Meta WhatsApp Cloud API Business Phone Number** to a self-hosted Asterisk PBX on your VPS.

---

## 🏗️ How the Architecture Works

1. **Meta WhatsApp Cloud API** receives an incoming call from a customer.
2. Meta initiates an encrypted **SIP over TLS** handshake to your VPS on port `5061`.
3. Meta validates your **Let's Encrypt TLS Certificate** on `sip.yourdomain.com`.
4. Voice audio is streamed directly using **WebRTC standard (DTLS-SRTP)** and the **Opus** codec over UDP ports `10000-20000`.
5. **Asterisk** answers the call, triggers the dialplan in `extensions.conf`, records the conversation, and bridges the audio into your IVR or AI Voice Assistant.

---

## 🚀 Quick Setup Instructions on your VPS

### 1. Configure DNS on Cloudflare
Add an **A Record** pointing your subdomain to your VPS IP:
* **Name**: `sip` (e.g. `sip.yourdomain.com`)
* **IPv4 Address**: `YOUR_VPS_PUBLIC_IP`
* **Proxy Status**: **DNS Only (Grey Cloud)** ⚠️ *(Must not be Orange Cloud).*

---

### 2. Copy and Run Installer on your VPS
Transfer this `sip/` directory to your VPS:

```bash
# On your local machine:
scp -r "/media/yuvraj/New Volume/xamp/htdocs/babamilk/sip" root@YOUR_VPS_IP:/root/

# SSH into your VPS:
ssh root@YOUR_VPS_IP

# Run the automated deployment script:
cd /root/sip
chmod +x deploy_vps.sh
sudo ./deploy_vps.sh
```

The script will:
- Install Asterisk 20/22, PJSIP, and Opus codec.
- Obtain a valid Let's Encrypt SSL/TLS certificate for your SIP subdomain.
- Open firewall ports (`5061/TCP`, `10000-20000/UDP`).
- Configure Asterisk and restart the service.

---

### 3. Verify Asterisk on VPS

Run these diagnostic commands inside your VPS:

```bash
# Check that TLS port 5061 is listening
asterisk -rx "pjsip show transports"

# Check the configured endpoint
asterisk -rx "pjsip show endpoints"

# Watch live SIP packets in real-time
sngrep
```

---

### 4. Fill Out the Meta WhatsApp Manager Modal

Now you can safely complete the dialog shown in your screenshot:

1. **SIP server**: `sip.yourdomain.com` *(your configured subdomain)*
2. **SIP port**: `5061`
3. **App ID**: Your Meta Developer App ID *(from developers.facebook.com/apps)*
4. **Request URI user parameters**: Leave blank
5. Click **Save**!

---

### 5. Make a Test Call

Pick up your personal phone, open WhatsApp, go to your business profile, and tap the **Voice Call** button:
- You will see live SIP packets in `sngrep` on your VPS.
- Asterisk will answer the call and play the welcome message!
