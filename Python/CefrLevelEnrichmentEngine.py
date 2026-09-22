
# =====================================================
# CEFR ENRICHMENT PIPELINE — FINAL ARCHITECTURE
# SAFE + RESUMABLE + BACKUP + DEBUG + TOKEN OPTIMIZED
# Model: gemini-3-flash-preview
# SDK: google.genai (OFFICIAL)
# =====================================================

!pip install -q google-genai

import sqlite3
import json
import time
import os
import shutil
from datetime import datetime
from google.colab import drive
from google import genai
from google.genai import types

# ------------------ MOUNT DRIVE ----------------------
drive.mount("/content/drive")

# ------------------ CONFIG ---------------------------
DB_PATH = "/content/drive/MyDrive/DictionaryEnrichment/WordsMaster.db"
BACKUP_DIR = "/content/drive/MyDrive/DictionaryEnrichment/backups"
STATE_FILE = "/content/drive/MyDrive/DictionaryEnrichment/cefr_resume_state.json"
BAD_RESPONSE_FILE = "/content/drive/MyDrive/DictionaryEnrichment/bad_response.json"

BATCH_SIZE = 100
# API key from environment / Colab secrets — never commit keys.
try:
    from google.colab import userdata
    API_KEY = userdata.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
except ImportError:
    API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ------------------ BACKUP (ONCE) --------------------
os.makedirs(BACKUP_DIR, exist_ok=True)

if not os.path.exists(STATE_FILE):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/WordsMaster_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"🛡️ Backup created: {backup_path}")
else:
    print("↩️ Resume detected — backup skipped")

# ------------------ GEMINI CLIENT --------------------
client = genai.Client(api_key=API_KEY)

# ------------------ SYSTEM PROMPT --------------------
SYSTEM_PROMPT = """
You are an expert English lexicographer and CEFR classification specialist.

Task:
Assign the most accurate CEFR level (A1–C2) for each English word using:
- The given English word
- Its part of speech (implicitly provided in input context)

Context:
- These words are NOT part of Oxford 3000 or Oxford 5000.
- Classify based on learner frequency, common usage, and CEFR descriptors.

Rules:
- Each item represents one (word + POS) entry.
- Use the POS for reasoning, but DO NOT return it.
- Assign CEFR for the most common learner-relevant sense.
- Do NOT explain.
- Do NOT add, remove, or reorder items.
- Output MUST strictly follow the JSON response schema.

Authoritative references:
- https://www.oxfordlearnersdictionaries.com
- https://www.coe.int/en/web/common-european-framework-reference-languages
"""

# ------------------ RESPONSE SCHEMA ------------------
RESPONSE_SCHEMA = {
    "type": "object",
    "description": "Compressed CEFR classification output.",
    "properties": {
        "items": {
            "type": "array",
            "description": "CEFR results in the same order as input.",
            "items": {
                "type": "object",
                "properties": {
                    "w": {
                        "type": "string",
                        "description": "English word exactly as provided."
                    },
                    "c": {
                        "type": "string",
                        "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                        "description": "Assigned CEFR level."
                    }
                },
                "required": ["w", "c"]
            }
        }
    },
    "required": ["items"]
}

# ------------------ GENERATION CONFIG ----------------
GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.0,
    top_p=0.95,
    top_k=40,
    max_output_tokens=100000,
    response_mime_type="application/json",
    response_schema=RESPONSE_SCHEMA
)

# ------------------ UTIL: PRETTY PRINT --------------
def pretty_print(title, data, limit=2000):
    print(f"\n{'='*20} {title} {'='*20}")
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    print(text[:limit])
    if len(text) > limit:
        print("... [TRUNCATED]")

# ------------------ RESUME STATE ---------------------
def load_offset():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("offset", 0)
    return 0

def save_offset(offset):
    with open(STATE_FILE, "w") as f:
        json.dump({"offset": offset}, f)

# ------------------ FETCH BATCH ----------------------
def fetch_batch(offset):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT wordEn, pos
        FROM wordsMaster
        WHERE cefrLevel IS NULL
          AND fromOxford = 0
        ORDER BY wordEn, pos
        LIMIT ? OFFSET ?
    """, (BATCH_SIZE, offset))

    rows = cur.fetchall()
    conn.close()
    return [{"w": w, "p": p} for w, p in rows]

# ------------------ GEMINI CALL ----------------------
def classify_cefr(batch):
    # Gemini sees POS, but will not return it
    request_payload = SYSTEM_PROMPT + "\n\nInput:\n" + json.dumps(batch, ensure_ascii=False)

    pretty_print("REQUEST (Batch Sent)", batch)

    contents = [
        types.Content(
            role="user",
            parts=[{"text": request_payload}]
        )
    ]

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=contents,
        config=GENERATION_CONFIG
    )

    raw_text = response.text
    pretty_print("RAW RESPONSE (Gemini)", raw_text)

    try:
        parsed = json.loads(raw_text)
        return parsed["items"]

    except json.JSONDecodeError as e:
        print("❌ JSON PARSE ERROR:", e)
        with open(BAD_RESPONSE_FILE, "w", encoding="utf-8") as f:
            f.write(raw_text)
        raise RuntimeError("Malformed JSON from Gemini. Saved for inspection.")

# ------------------ UPDATE DB ------------------------
def update_db(batch, items):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for input_item, result_item in zip(batch, items):
        cur.execute("""
            UPDATE wordsMaster
            SET cefrLevel = ?
            WHERE wordEn = ? AND pos = ?
        """, (
            result_item["c"],
            input_item["w"],
            input_item["p"]
        ))

    conn.commit()
    conn.close()

# ------------------ MAIN LOOP ------------------------
offset = load_offset()
print(f"▶ Resuming from offset: {offset}")

while True:
    batch = fetch_batch(offset)
    if not batch:
        print("✅ All CEFR gaps filled successfully.")
        break

    print(f"🔄 Processing batch {offset} → {offset + len(batch)}")

    try:
        results = classify_cefr(batch)
        update_db(batch, results)
        offset += BATCH_SIZE
        save_offset(offset)
        time.sleep(1)

    except Exception as e:
        print("⏸️ PIPELINE STOPPED SAFELY")
        print("Reason:", e)
        print("Progress saved — you can resume safely.")
        break