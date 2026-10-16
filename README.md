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

### 5. Make a Test Inbound Call

Pick up your personal phone, open WhatsApp, go to your business profile, and tap the **Voice Call** button:
- You will see live SIP packets in `sngrep` on your VPS.
- Asterisk will answer the call and play the welcome message!

---

## 📞 Automatic Outbound Calling & IVR Order Reminders

To trigger an automatic reminder call to a dealer (e.g., `917889142708`, `DEALER_ID=9`), play custom dealer audio, and capture DTMF keypress (1 = Order Planned, 2 = No Order Today):

### 1. Using the trigger script (Recommended)
On your server inside `sip/`:
```bash
# Syntax: ./trigger_call.sh [PHONE_NUMBER] [DEALER_ID] [OPTIONAL_CUSTOM_AUDIO_PATH]
./trigger_call.sh 917889142708 9 /var/lib/asterisk/sounds/dealers/dealer_9
```

### 2. Using Asterisk CLI directly
```bash
# If using Docker:
docker exec -it babamilk-asterisk-sip asterisk -rx "channel originate PJSIP/sip:917889142708@wa.meta.vc:5061 extension 917889142708@whatsapp-outbound variable DEALER_ID=9"

# If native Asterisk:
asterisk -rx "channel originate PJSIP/sip:917889142708@wa.meta.vc:5061 extension 917889142708@whatsapp-outbound variable DEALER_ID=9"
```

### 3. IVR DTMF Dialpad Options (Automated Feedback)
When the call connects, Asterisk executes the `[whatsapp-outbound]` dialplan:
- Plays personalized dealer audio or greeting prompt.
- Listens for DTMF keypress:
  - **Press 1:** Logs order confirmed, notifies Baba Milk backend at `POST https://menu.yarora.dev/api/calls/dtmf-response/9` (`Digits: 1`), and plays thank-you confirmation.
  - **Press 2:** Logs no order today, notifies Baba Milk backend (`Digits: 2`), and updates daily route crate allocation.
- Dashboard immediately updates in real-time via Server-Sent Events (SSE).

### 4. From your Web Dashboard / Backend (Node.js)
```javascript
const fs = require('fs');

function triggerDealerReminderCall(phone, dealerId, customAudioPath) {
  const callContent = [
    `Channel: PJSIP/sip:${phone}@wa.meta.vc:5061`,
    `CallerID: "Baba Milk" <+917889142708>`,
    `MaxRetries: 2`,
    `RetryTime: 30`,
    `WaitTime: 45`,
    `Context: whatsapp-outbound`,
    `Extension: ${phone}`,
    `Priority: 1`,
    `Set: DEALER_ID=${dealerId}`,
    customAudioPath ? `Set: AUDIO_FILE=${customAudioPath}` : '',
    `Set: BABA_API_URL=https://menu.yarora.dev`
  ].filter(Boolean).join('\n') + '\n';

  const tmp = `/tmp/call_${phone}_${Date.now()}.call`;
  const dest = `./sip/outgoing/call_${phone}_${Date.now()}.call`;
  fs.writeFileSync(tmp, callContent);
  fs.renameSync(tmp, dest); // atomic move triggers Asterisk instantly
}

// Trigger call for dealer ID 9:
triggerDealerReminderCall('917889142708', 9);
```

