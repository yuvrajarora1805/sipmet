#!/usr/bin/env python3
"""
Generate initial Baba Milk welcome audio prompt using Sarvam AI (Shreya voice)
"""

import os
import sys
import base64
import requests

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_file = os.path.join(base_dir, "agent", ".env")

def load_env():
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

file_env = load_env()
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", file_env.get("SARVAM_API_KEY", ""))
SPEAKER = os.environ.get("SARVAM_SPEAKER", file_env.get("SARVAM_SPEAKER", "shreya"))

# Sound output directory
sounds_dir = "/var/lib/asterisk/sounds/en"
if not os.path.exists(sounds_dir):
    sounds_dir = os.path.join(base_dir, "sounds")
os.makedirs(sounds_dir, exist_ok=True)

target_wav = os.path.join(sounds_dir, "baba_welcome.wav")
temp_wav = os.path.join(sounds_dir, "temp_baba_welcome.wav")

text = "Namaste! Baba Milk me aapka swagat hai. Main Shreya hoon, bataiye aapko kya order karna hai?"

print(f"Generating welcome audio using Sarvam TTS ({SPEAKER}, bulbul:v3)...")
try:
    res = requests.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        },
        json={
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": SPEAKER,
            "pitch": 0,
            "pace": 1.05,
            "loudness": 1.5,
            "speech_sample_rate": 8000,
            "enable_preprocessing": True,
            "model": "bulbul:v3",
        },
        timeout=15,
    )
    if res.status_code == 200:
        b64 = res.json()["audios"][0]
        with open(temp_wav, "wb") as f:
            f.write(base64.b64decode(b64))

        convert_res = os.system(f"ffmpeg -y -i {temp_wav} -ar 8000 -ac 1 {target_wav} > /dev/null 2>&1")
        if convert_res != 0:
            import shutil
            shutil.copyfile(temp_wav, target_wav)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        print(f"✅ Generated {target_wav} successfully!")
    else:
        print(f"❌ Failed: {res.status_code} {res.text}")
except Exception as e:
    print(f"❌ Error: {e}")
