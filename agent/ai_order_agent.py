#!/usr/bin/env python3
"""
Baba Milk - AI Voice Order Agent
Runs natively inside the Asterisk Docker container.
- STT: Sarvam AI (saaras:v1) - Ideal for Hindi/Hinglish speech
- LLM: Qwen (qwen/qwen3.8-27b on Groq) - Ultra-fast, fluent Hindi/English comprehension
- TTS: Sarvam AI (bulbul:v3, speaker: shreya) - Natural telephony voice
"""

import sys
import os
import json
import base64
import requests
from groq import Groq

# Determine directory paths inside container or host
agent_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(agent_dir, ".env")

# Helper to read .env file
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

# API Keys
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", file_env.get("SARVAM_API_KEY", ""))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", file_env.get("GROQ_API_KEY", ""))
SPEAKER = os.environ.get("SARVAM_SPEAKER", file_env.get("SARVAM_SPEAKER", "shreya"))
TTS_MODEL = "bulbul:v3"  # Sarvam v3 model supporting shreya
LLM_MODEL = "qwen/qwen3.8-27b"

# Arguments from Asterisk
call_id = sys.argv[1] if len(sys.argv) > 1 else "test_call"
caller_num = sys.argv[2] if len(sys.argv) > 2 else "unknown"

# Recordings directory in Asterisk container
recordings_dir = "/var/spool/asterisk/monitor"
if not os.path.exists(recordings_dir):
    recordings_dir = os.path.join(os.path.dirname(agent_dir), "recordings")
os.makedirs(recordings_dir, exist_ok=True)

input_audio = os.path.join(recordings_dir, f"in_{call_id}.wav")
output_audio = os.path.join(recordings_dir, f"reply_{call_id}.wav")
temp_audio = os.path.join(recordings_dir, f"temp_{call_id}.wav")
state_file = os.path.join(recordings_dir, f"state_{call_id}.json")

# --- 1. Load History ---
history = []
if os.path.exists(state_file):
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

# --- 2. STT: Sarvam AI (saaras:v1) ---
user_text = ""
if os.path.exists(input_audio) and os.path.getsize(input_audio) > 1000:
    try:
        url = "https://api.sarvam.ai/speech-to-text"
        headers = {"api-subscription-key": SARVAM_API_KEY}
        with open(input_audio, "rb") as f:
            files = {"file": ("audio.wav", f, "audio/wav")}
            data = {"model": "saaras:v3", "language_code": "hi-IN"}
            res = requests.post(url, headers=headers, files=files, data=data, timeout=10)
            if res.status_code == 200:
                user_text = res.json().get("transcript", "").strip()
                print(f"[Sarvam STT]: {user_text}")
            else:
                print(f"[Sarvam STT Error]: {res.status_code} {res.text}", file=sys.stderr)
    except Exception as e:
        print(f"[Sarvam STT Exception]: {e}", file=sys.stderr)

if not user_text:
    user_text = "Namaste"

history.append({"role": "user", "content": user_text})

# --- 3. Fast LLM Comprehension: Qwen (qwen/qwen3.8-27b on Groq) ---
client = Groq(api_key=GROQ_API_KEY)
system_prompt = (
    "Aap Baba Milk ki voice order assistant 'Shreya' hain. "
    "Aap natural, polite Hindi/Hinglish me baat karti hain. "
    "Baba Milk Products aur Rate: "
    "- Full Cream Cow Milk: Rs 66 per litre "
    "- Buffalo Milk: Rs 74 per litre "
    "- Desi Cow Ghee: Rs 650 per kg "
    "- Fresh Paneer: Rs 400 per kg "
    "- Fresh Dahi: Rs 80 per kg. "
    "Important rules: "
    "1. Javaab hamesha chhota, saaf aur 1-2 sentences me hi dein taaki customer phone par aasaani se sun sake. "
    "2. Kabhi bhi markdown, bullet points ya symbols jaise *, # use na karein. "
    "3. Agar customer koi item maange, toh item aur quantity confirm karein aur delivery ke baare me poochhein."
)

messages = [{"role": "system", "content": system_prompt}] + history[-6:]

try:
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.6,
        max_tokens=100
    )
    ai_reply = completion.choices[0].message.content.strip()
    ai_reply = ai_reply.replace("*", "").replace("#", "").strip()
    print(f"[Qwen LLM]: {ai_reply}")
except Exception as e:
    print(f"[Groq LLM Exception]: {e}", file=sys.stderr)
    ai_reply = "Ji Baba Milk me aapka swagat hai. Aapko kitna doodh ya paneer deliver karwana hai?"

history.append({"role": "assistant", "content": ai_reply})

try:
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
except Exception:
    pass

# --- 4. TTS: Sarvam AI (bulbul:v3 with Shreya voice) ---
try:
    tts_url = "https://api.sarvam.ai/text-to-speech"
    tts_headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }
    tts_payload = {
        "inputs": [ai_reply],
        "target_language_code": "hi-IN",
        "speaker": SPEAKER,
        "pitch": 0,
        "pace": 1.05,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": TTS_MODEL
    }
    tts_res = requests.post(tts_url, headers=tts_headers, json=tts_payload, timeout=10)
    if tts_res.status_code == 200:
        audio_b64 = tts_res.json()["audios"][0]
        with open(temp_audio, "wb") as f:
            f.write(base64.b64decode(audio_b64))

        convert_code = os.system(f"ffmpeg -y -i {temp_audio} -ar 8000 -ac 1 {output_audio} > /dev/null 2>&1")
        if convert_code != 0:
            import shutil
            shutil.copyfile(temp_audio, output_audio)
        print(f"[Sarvam TTS Shreya]: Saved {output_audio}")
    else:
        print(f"[TTS Error]: {tts_res.status_code} {tts_res.text}", file=sys.stderr)
except Exception as e:
    print(f"[TTS Exception]: {e}", file=sys.stderr)
