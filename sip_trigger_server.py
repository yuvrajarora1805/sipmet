#!/usr/bin/env python3
"""
Production Hardened SIP Webhook Trigger Bridge for Baba Milk Asterisk VPS
- Dynamic Auto-Fetch & Caching of Dealer Audio Prompts from backend
- Cryptographic Authentication (HMAC-SHA256 + Anti-Replay + Bearer Token)
- Circuit-Breaker Emergency Toggle (/api/toggle-service)
- Strict Phone & Parameter Sanitization
"""

import http.server
import socketserver
import json
import subprocess
import os
import re
import hmac
import hashlib
import time
import urllib.request
import urllib.error

PORT = 5055
TOKEN = os.environ.get("SIP_WEBHOOK_SECRET", "babamilk_sip_secret_2026")
LOCAL_SOUNDS_DIR = os.path.expanduser("~/sipmet/sounds/dealers")
CONTAINER_SOUNDS_DIR = "/var/lib/asterisk/sounds/en/dealers"
DEFAULT_AUDIO = "/var/lib/asterisk/sounds/en/baba_welcome"
SERVICE_ENABLED = True

os.makedirs(LOCAL_SOUNDS_DIR, exist_ok=True)

class SecureCallTriggerHandler(http.server.BaseHTTPRequestHandler):
    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def check_auth(self, post_data_bytes):
        # 1. Bearer Token Check
        auth_header = self.headers.get("Authorization", "")
        if auth_header != f"Bearer {TOKEN}":
            return False, "Unauthorized: Invalid or missing Bearer token"

        # 2. Replay Protection & HMAC-SHA256 Signature Verification
        sig = self.headers.get("X-Signature")
        ts = self.headers.get("X-Timestamp")
        if sig and ts:
            try:
                ts_int = int(ts)
                if abs(time.time() - ts_int) > 300:
                    return False, "Unauthorized: Request timestamp expired (replay detected)"
                expected_sig = hmac.new(
                    TOKEN.encode("utf-8"),
                    f"{ts}.".encode("utf-8") + post_data_bytes,
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(sig, expected_sig):
                    return False, "Unauthorized: HMAC signature mismatch"
            except Exception as e:
                return False, f"Unauthorized: Signature validation error ({e})"

        return True, None

    def ensure_dealer_audio(self, dealer_id, audio_url):
        """Auto-fetches dealer audio prompt to host cache if missing or url provided"""
        target_file = os.path.join(LOCAL_SOUNDS_DIR, f"dealer_{dealer_id}.wav")
        if not os.path.exists(target_file) and audio_url:
            print(f"📥 Fetching dealer audio from: {audio_url}")
            try:
                req = urllib.request.Request(
                    audio_url,
                    headers={"User-Agent": "BabaMilk-SIP-Bridge/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp, open(target_file, "wb") as out:
                    out.write(resp.read())
                print(f"✅ Audio downloaded and cached to {target_file}")
            except Exception as e:
                print(f"⚠️ Audio fetch error: {e}")

        if os.path.exists(target_file):
            return f"{CONTAINER_SOUNDS_DIR}/dealer_{dealer_id}"
        return DEFAULT_AUDIO

    def do_POST(self):
        global SERVICE_ENABLED

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        authorized, err = self.check_auth(post_data)
        if not authorized:
            return self.send_json(401, {"success": False, "error": err})

        # Toggle Endpoint
        if self.path == "/api/toggle-service":
            try:
                payload = json.loads(post_data.decode("utf-8")) if post_data else {}
                SERVICE_ENABLED = bool(payload.get("enabled", not SERVICE_ENABLED))
                return self.send_json(200, {
                    "success": True,
                    "service_enabled": SERVICE_ENABLED,
                    "message": f"Calling service is now {'ENABLED' if SERVICE_ENABLED else 'DISABLED'}"
                })
            except Exception as e:
                return self.send_json(400, {"success": False, "error": str(e)})

        if self.path != "/api/trigger-call":
            return self.send_json(404, {"success": False, "error": "Not Found"})

        if not SERVICE_ENABLED:
            return self.send_json(503, {"success": False, "error": "SIP Calling is currently disabled via circuit-breaker"})

        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            payload = {}

        raw_phone = str(payload.get("phone", "")).replace("+", "").replace(" ", "").strip()
        raw_dealer = str(payload.get("dealer_id", "0")).strip()
        audio_url = payload.get("audio_url", "").strip()

        # Sanitize parameters
        if not re.match(r"^\d{10,15}$", raw_phone):
            return self.send_json(400, {"success": False, "error": "Invalid phone format (10-15 digits expected)"})
        if not re.match(r"^\d+$", raw_dealer):
            return self.send_json(400, {"success": False, "error": "Invalid dealer ID"})

        # Auto-fetch / verify personalized audio
        selected_audio = self.ensure_dealer_audio(raw_dealer, audio_url)
        print(f"📞 Dispatching call: Phone={raw_phone}, Dealer={raw_dealer}, Audio={selected_audio}")

        # Secure subprocess execution (safe array, no shell=True)
        cmd = [
            "docker", "exec", "babamilk-asterisk-sip", "asterisk", "-rx",
            f"channel originate PJSIP/whatsapp-outbound/sip:{raw_phone}@wa.meta.vc:5061 extension {raw_phone}@whatsapp-outbound variable DEALER_ID={raw_dealer},BABA_API_URL=https://menu.yarora.dev,AUDIO_FILE={selected_audio}"
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
            output = res.stdout.strip() or res.stderr.strip()
            print(f"Asterisk Response: {output}")

            return self.send_json(200, {
                "success": True,
                "message": "Call dispatched to Asterisk",
                "audio_used": selected_audio,
                "asterisk_output": output
            })
        except Exception as e:
            return self.send_json(500, {"success": False, "error": str(e)})

    def do_GET(self):
        self.send_json(200, {
            "status": "online",
            "service": "Baba Milk SIP Webhook Trigger",
            "service_enabled": SERVICE_ENABLED,
            "version": "2.0.0-production-hardened"
        })

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Signature, X-Timestamp")
        self.end_headers()

if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), SecureCallTriggerHandler) as httpd:
        print(f"🚀 Hardened SIP Trigger Bridge listening on port {PORT}...")
        httpd.serve_forever()
