#!/usr/bin/env python3
"""
Baba Milk - Fast AI Voice Order Agent
- Low Latency Rule-based matcher for Crate / Packet / Litre / Kg quantities
- STT: Sarvam AI (saaras:v3)
- Fast LLM fallback: Qwen (qwen/qwen3.8-27b on Groq)
- TTS: Sarvam AI (bulbul:v3, speaker: shreya)
"""

import sys
import os
import re
import json
import base64
import requests
from groq import Groq

agent_dir = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(agent_dir, ".env")

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", file_env.get("GROQ_API_KEY", ""))
SPEAKER = os.environ.get("SARVAM_SPEAKER", file_env.get("SARVAM_SPEAKER", "shreya"))
TTS_MODEL = "bulbul:v3"
LLM_MODEL = "qwen/qwen3.8-27b"

call_id = sys.argv[1] if len(sys.argv) > 1 else "test_call"
caller_num = sys.argv[2] if len(sys.argv) > 2 else "unknown"

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

# --- 2. STT: Sarvam AI (saaras:v3) ---
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

# --- 3. RULE-BASED FAST INTERCEPTOR (Instant response without waiting for LLM) ---
def fast_rule_response(text):
    t = text.lower()
    
    # Check for confirmation ("Haan", "Confirm", "Theek hai", "Bhej do")
    if any(w in t for w in ["haan", "theek hai", "confirm", "bhej do", "pack kar do", "yes"]):
        return "Aapka order confirm ho gaya hai! Delivery boy jald hi pahunch jayega. Baba Milk me call karne ke liye dhanyavaad."

    # Number word to digit mapping
    word_to_num = {
        "ek": "1", "do": "2", "teen": "3", "chaar": "4", "char": "4", "paanch": "5", "panch": "5",
        "chhah": "6", "chhe": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5"
    }
    for word, digit in word_to_num.items():
        t = re.sub(r'\b' + word + r'\b', digit, t)

    # 1. Crate rule: detects "5 crate", "2 crate doodh", "crate milk"
    crate_match = re.search(r'(\d+)\s*(crate|peti|crates)', t)
    if crate_match or "crate" in t or "peti" in t:
        qty = crate_match.group(1) if crate_match else "5"
        return f"Theek hai, {qty} crate Full Cream Milk note kar liya hai. 1 crate me 24 pouch aate hain. Kya main order confirm kar doon?"

    # 2. Litre / Packet milk rule: "2 litre", "3 packet"
    milk_match = re.search(r'(\d+)\s*(litre|l|liter|packet|pouch)?', t)
    if ("doodh" in t or "milk" in t) and milk_match:
        qty = milk_match.group(1)
        unit = "litre" if "litre" in t or "liter" in t or "l" in t else "packet"
        rate = 68 if unit == "litre" else 34
        total = int(qty) * rate
        return f"Aapka {qty} {unit} Full Cream Milk note ho gaya hai, total {total} rupaye hoga. Kya order confirm kar doon?"

    # 3. Paneer rule: "aadha kilo paneer", "500 gram paneer", "1 kg paneer"
    if "paneer" in t:
        if any(w in t for w in ["aadha", "adha", "500", "half"]):
            return "Aadha kilo Fresh Paneer note ho gaya hai, iska rate 200 rupaye hoga. Kya order confirm kar doon?"
        kg_match = re.search(r'(\d+)\s*(kg|kilo)', t)
        qty = kg_match.group(1) if kg_match else "1"
        total = int(qty) * 400
        return f"{qty} kilo Fresh Paneer note ho gaya hai, total {total} rupaye hoga. Kya order confirm kar doon?"

    # 4. Ghee rule
    if "ghee" in t:
        kg_match = re.search(r'(\d+)\s*(kg|kilo|litre)', t)
        qty = kg_match.group(1) if kg_match else "1"
        total = int(qty) * 650
        return f"{qty} kilo Desi Ghee note kar liya hai, total {total} rupaye hoga. Kya order confirm kar doon?"

    # 5. Products Inquiry / Rate list
    if any(w in t for w in ["kya milta", "rate", "bhav", "products", "list"]):
        return "Humare paas Full Cream Milk pouch, 1 litre pack, crates, fresh Paneer aur Desi Ghee uplabdh hai. Aapko kya chahiye?"

    return None

rule_reply = fast_rule_response(user_text)

# --- 4. Process Response (Rule or LLM) ---
if rule_reply:
    ai_reply = rule_reply
    print(f"[Rule Fast-Path (0ms)]: {ai_reply}")
else:
    # Fallback to Qwen on Groq for open questions
    client = Groq(api_key=GROQ_API_KEY)
    system_prompt = (
        "Aap Baba Milk ki voice assistant 'Shreya' hain. "
        "Aap natural, polite Hindi/Hinglish me baat karti hain. "
        "Products & Units: "
        "- Crate: 1 Crate me 24 pouches (Full Cream Milk) "
        "- Full Cream Milk 1 Litre: Rs 68 "
        "- Full Cream Milk 500g Pouch: Rs 34 "
        "- Fresh Paneer: Rs 400/kg "
        "- Desi Cow Ghee: Rs 650/kg. "
        "Crucial Rules: "
        "1. DHYAN SE SUNO: Agar customer 'crate' ya 'peti' bole toh use LITRE mat samjho, use 'CRATE' hi bolo! "
        "2. Javaab hamesha chhota, saaf aur 1 sentence me dein. "
        "3. Koyi markdown, asterisks ya bullet points use na karein."
    )

    messages = [{"role": "system", "content": system_prompt}] + history[-6:]

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=90
        )
        ai_reply = completion.choices[0].message.content.strip()
        ai_reply = ai_reply.replace("*", "").replace("#", "").strip()
        print(f"[Qwen LLM]: {ai_reply}")
    except Exception as e:
        print(f"[Groq LLM Exception]: {e}", file=sys.stderr)
        ai_reply = "Ji Baba Milk me aapka swagat hai. Aapko kitne crate ya litre doodh deliver karwana hai?"

history.append({"role": "assistant", "content": ai_reply})

try:
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
except Exception:
    pass

# --- 5. TTS: Sarvam AI (bulbul:v3 with Shreya voice) ---
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
        "pace": 1.08,
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
