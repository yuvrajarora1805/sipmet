#!/usr/bin/env python3
"""
Baba Milk - Fast AI Voice Order Agent
- Built using full product list from Baba Milk catalog
- Zero Price Disclosure (as requested)
- High-speed Rule-based matching for Crates, Pouches, Litres, Kg, Cups, Buckets
- Fast LLM fallback (Qwen) for general questions
- STT: Sarvam AI (saaras:v3)
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

# --- 3. RULE-BASED FAST INTERCEPTOR (NO PRICE DISCLOSURE) ---
def fast_rule_response(text):
    t = text.lower()

    # Rule 0: Order Confirmation ("Haan", "Confirm", "Theek hai", "Bhej do", "Pack kar do")
    if any(w in t for w in ["haan", "theek hai", "confirm", "bhej do", "pack kar do", "yes", "sahi hai", "done"]):
        return "Aapka order confirm ho gaya hai! Delivery boy jald hi deliver kar dega. Baba Milk me call karne ke liye shukriya."

    # Convert spoken Hindi & English numbers to digits
    word_to_num = {
        "ek": "1", "do": "2", "teen": "3", "chaar": "4", "char": "4", "paanch": "5", "panch": "5",
        "chhah": "6", "chhe": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
        "gyarah": "11", "barah": "12", "pandrah": "15", "bees": "20", "pachees": "25",
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
        "seven": "7", "eight": "8", "nine": "9", "ten": "10"
    }
    for word, digit in word_to_num.items():
        t = re.sub(r'\b' + word + r'\b', digit, t)

    # Quantity extractor helper
    def extract_qty(default=1):
        m = re.search(r'(\d+)', t)
        return int(m.group(1)) if m else default

    # List of known products
    has_product = any(w in t for w in [
        "doodh", "milk", "paneer", "dahi", "curd", "ghee", "makkhan", "butter",
        "lassi", "chaach", "chhach", "khoa", "mawa", "barfi", "kulfi", "rabri",
        "crate", "peti"
    ])

    # If user specifies ONLY quantity without product (e.g. "5 kilo", "2 packet", "10 litre")
    if not has_product:
        qty_unit_match = re.search(r'(\d+)\s*(kilo|kg|litre|liter|l|packet|pack|pouch|piece|drum|bucket|barfi)', t)
        if qty_unit_match:
            q = qty_unit_match.group(1)
            u = qty_unit_match.group(2)
            return f"Aapko {q} {u} kis cheez ka chahiye? Jaise Paneer, Dahi, Doodh ya Ghee?"

    # 1. CRATE / PETI MATCHING (Milk, Curd, Chaach, etc.)
    if "crate" in t or "peti" in t or "crates" in t:
        qty = extract_qty(5)
        item = "Milk"
        if "fcm" in t or "full cream" in t:
            item = "Full Cream Milk"
        elif "std" in t or "standard" in t:
            item = "Standardized Milk"
        elif "dtm" in t or "double toned" in t:
            item = "Double Toned Milk"
        elif "curd" in t or "dahi" in t:
            item = "Dahi"
        elif "lassi" in t or "chaach" in t:
            item = "Lassi"
        return f"Theek hai, {qty} crate {item} note kar liya hai. Kya main order confirm kar doon?"

    # 2. FRESH MILK (Full Cream, Toned, Double Toned, Cow Milk, Standardized)
    if any(w in t for w in ["doodh", "milk"]):
        qty = extract_qty(1)
        if "cow" in t or "gai" in t:
            prod = "Cow Milk"
        elif "toned" in t or "dtm" in t:
            prod = "Toned Milk"
        elif "standard" in t or "std" in t:
            prod = "Standardized Milk"
        else:
            prod = "Full Cream Milk"

        unit = "litre" if any(u in t for u in ["litre", "liter", "l"]) else "packet"
        return f"Aapka {qty} {unit} {prod} note kar liya hai. Kya order confirm kar doon?"

    # 3. PANEER (Fresh Paneer: 100g pack, 200g pack, 1kg block, 5kg tub)
    if "paneer" in t:
        # Check pack size: 100g, 200g, or 1kg block
        is_100g = bool(re.search(r'\b(100|sau)\s*(g|gm|gram|gms)?\b', t))
        is_200g = bool(re.search(r'\b(200|dosau|do\s*sau)\s*(g|gm|gram|gms)?\b', t))
        is_1kg = bool(re.search(r'\b(1|ek)\s*(kg|kilo)\b', t))

        # Check for count / quantity (e.g., "6 quantity", "6 pack", "6 block", "6 piece", "ke 6")
        count_match = re.search(r'(\d+)\s*(quantity|count|pack|packet|pouch|piece|pcs|block|tikiya|box)', t)
        if not count_match:
            count_match = re.search(r'(quantity|count|pack|packet|pouch|piece|pcs|block|tikiya|box)\s*(\d+)', t)
        if not count_match:
            count_match = re.search(r'(?:ki|ke|ka)\s*(\d+)', t)

        count = None
        if count_match:
            count = count_match.group(1) if count_match.group(1).isdigit() else count_match.group(2)

        # 1kg Block Paneer (SKU: P-1)
        if is_1kg:
            if count and count != "1":
                return f"1 kilo Fresh Paneer ke {count} packet note kar liye hain. Kya main order confirm kar doon?"
            else:
                # Customer said "1kg paneer" -> Ask how many packets/quantity!
                return "1 kilo Fresh Paneer ke kitne packet karne hain?"

        # 100g / 200g Packets
        if is_100g or is_200g:
            size_name = "100 gram" if is_100g else "200 gram"
            if count:
                return f"{size_name} Fresh Paneer ke {count} packet note kar liye hain. Kya main order confirm kar doon?"
            else:
                return f"{size_name} Fresh Paneer ke kitne packet chahiye aapko?"

        if any(w in t for w in ["aadha", "adha", "500", "half"]):
            if count and count != "1":
                return f"Aadha kilo Fresh Paneer ke {count} packet note kar liye hain. Kya order confirm kar doon?"
            return "Aadha kilo Fresh Paneer note kar liya hai. Kya order confirm kar doon?"

        if "tub" in t or ("5" in t and "kilo" in t):
            if count and count != "1":
                return f"5 kilo Fresh Paneer tub ke {count} unit note kar liye hain. Kya order confirm kar doon?"
            return "5 kilo Fresh Paneer tub note kar liya hai. Kya order confirm kar doon?"

        # Default Kg / Packet matcher
        kg_match = re.search(r'(\d+)\s*(kg|kilo)', t)
        if kg_match:
            qty = kg_match.group(1)
            return f"{qty} kilo Fresh Paneer note kar liya hai. Kya order confirm kar doon?"

        pkt_match = re.search(r'(\d+)\s*(packet|pack|quantity)', t)
        if pkt_match:
            qty = pkt_match.group(1)
            return f"Fresh Paneer ke {qty} packet note kar liye hain. Kya order confirm kar doon?"

        return "Aapko kitna paneer chahiye? Humare paas 100 gram, 200 gram aur 1 kilo block uplabdh hai."

    # 4. DAHI / CURD (Matka Dahi, Toned Dahi, Bulk Drum)
    if "dahi" in t or "curd" in t:
        qty = extract_qty(1)
        if "matka" in t:
            return f"{qty} Matka Dahi pot note kar liya hai. Kya order confirm kar doon?"
        if "bucket" in t or "balti" in t or "5" in t:
            return f"{qty} bucket Dahi note kar liya hai. Kya order confirm kar doon?"
        if "drum" in t or "15" in t:
            return f"{qty} commercial Dahi drum note kar liya hai. Kya order confirm kar doon?"
        return f"{qty} packet Dahi note kar liya hai. Kya order confirm kar doon?"

    # 5. GHEE (Pure Desi Ghee Jar 1L)
    if "ghee" in t:
        qty = extract_qty(1)
        return f"{qty} jar Pure Desi Ghee note kar liya hai. Kya order confirm kar doon?"

    # 6. BUTTER / MAKKHAN (White Makkhan, Table Butter 500g)
    if "makkhan" in t or "butter" in t:
        qty = extract_qty(1)
        b_type = "White Makkhan" if "white" in t or "safed" in t or "makkhan" in t else "Table Butter"
        return f"{qty} pack {b_type} note kar liya hai. Kya order confirm kar doon?"

    # 7. LASSI / BUTTERMILK / CHAACH
    if any(w in t for w in ["lassi", "chaach", "chhach", "buttermilk"]):
        qty = extract_qty(1)
        l_type = "Sweet Lassi" if "meethi" in t or "sweet" in t else ("Chaach" if "chaach" in t else "Plain Lassi")
        return f"{qty} packet {l_type} note kar liya hai. Kya order confirm kar doon?"

    # 8. KHOA / SWEETS / KULFI / RABRI
    if any(w in t for w in ["khoa", "mawa", "barfi", "kulfi", "rabri"]):
        qty = extract_qty(1)
        s_type = "Khoa" if "khoa" in t or "mawa" in t else ("Barfi" if "barfi" in t else ("Kulfi" if "kulfi" in t else "Rabri"))
        return f"{qty} {s_type} note kar liya hai. Kya order confirm kar doon?"

    # 9. PRODUCTS INQUIRY / CATALOG QUESTION
    if any(w in t for w in ["kya milta", "menu", "products", "list", "kya kya", "item"]):
        return "Humare paas Fresh Milk crates, Dahi, Paneer, Desi Ghee, Butter, Lassi aur Khoa uplabdh hain. Aapko kya chahiye?"

    return None

rule_reply = fast_rule_response(user_text)

# --- 4. Process Response (Rule or LLM) ---
if rule_reply:
    ai_reply = rule_reply
    print(f"[Rule Fast-Path (0ms)]: {ai_reply}")
else:
    # Fallback to Qwen for open questions
    client = Groq(api_key=GROQ_API_KEY)
    system_prompt = (
        "Aap Baba Milk ki voice order assistant 'Shreya' hain. "
        "Aap natural, polite Hindi/Hinglish me baat karti hain. "
        "Products Catalog: Fresh Milk (Crates, Litres, Pouches), Paneer (100g, 200g, 1kg, 5kg), "
        "Dahi (Pouch, Matka Dahi, 5kg Bucket, 15kg Drum), Desi Ghee, White Makkhan, Table Butter, "
        "Lassi, Chaach, Fresh Khoa, Barfi, Rabri, Matka Kulfi. "
        "CRITICAL RULES: "
        "1. DO NOT ASK FOR NAME OR ADDRESS! Customer already registered hai, unka name aur address phone number se automatically fetch ho jata hai. Name ya address kabhi mat poocho! "
        "2. DO NOT MENTION ANY PRICES OR RATES! Prices nahi batane hain. Sirf item aur quantity confirm karke poochna hai. "
        "3. Agar customer sirf quantity bole (jaise '5 kilo', '2 packet') bina item bataye, toh hamesha poocho: 'Aapko kis cheez ka chahiye? Jaise Paneer, Doodh ya Dahi?' "
        "4. Agar customer 'crate' ya 'peti' bole toh use LITRE mat bolo, use CRATE hi bolo! "
        "5. Javaab hamesha chhota, saaf aur 1 sentence me dein. "
        "6. Koyi markdown, asterisks ya bullet points use na karein."
    )

    messages = [{"role": "system", "content": system_prompt}] + history[-6:]

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=80
        )
        ai_reply = completion.choices[0].message.content.strip()
        ai_reply = ai_reply.replace("*", "").replace("#", "").strip()
        print(f"[Qwen LLM]: {ai_reply}")
    except Exception as e:
        print(f"[Groq LLM Exception]: {e}", file=sys.stderr)
        ai_reply = "Ji Baba Milk me aapka swagat hai. Bataiye aapko kitne crate doodh ya paneer deliver karwana hai?"

history.append({"role": "assistant", "content": ai_reply})

try:
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
except Exception:
    pass

# Phonetic cleaner for Hindi TTS (fixes "2-shunya-shunya" -> "do sau")
def clean_for_hindi_tts(text):
    # Fix 100 and 200 gram pronunciations
    text = re.sub(r'\b100\s*(?:gram|gm|g)\b', 'ek sau gram', text, flags=re.IGNORECASE)
    text = re.sub(r'\b200\s*(?:gram|gm|g)\b', 'do sau gram', text, flags=re.IGNORECASE)
    text = re.sub(r'\b500\s*(?:gram|gm|g)\b', 'aadha kilo', text, flags=re.IGNORECASE)

    # Replace standalone digits with natural Hindi words
    num_map = {
        r'\b1\b': 'ek', r'\b2\b': 'do', r'\b3\b': 'teen', r'\b4\b': 'chaar', r'\b5\b': 'paanch',
        r'\b6\b': 'chhe', r'\b7\b': 'saat', r'\b8\b': 'aath', r'\b9\b': 'nau', r'\b10\b': 'das',
        r'\b15\b': 'pandrah', r'\b20\b': 'bees', r'\b24\b': 'chaubees', r'\b25\b': 'pachees'
    }
    for pattern, rep in num_map.items():
        text = re.sub(pattern, rep, text)

    return text

# --- 5. TTS: Sarvam AI (bulbul:v3 with Shreya voice) ---
try:
    tts_speech_text = clean_for_hindi_tts(ai_reply)
    print(f"[TTS Phonetic Text]: {tts_speech_text}")

    tts_url = "https://api.sarvam.ai/text-to-speech"
    tts_headers = {
        "Content-Type": "application/json",
        "api-subscription-key": SARVAM_API_KEY
    }
    tts_payload = {
        "inputs": [tts_speech_text],
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
