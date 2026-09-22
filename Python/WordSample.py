import sqlite3
import json
import os

# =========================
# CONFIG
# =========================

DB_PATH = "/sdcard/DictionaryEnrichment/WordsMasterXX.db"
TABLE_NAME = "wordsMaster"

SAMPLE_SIZE = 20
OUTPUT_FILE = "/sdcard/DictionaryEnrichment/sample_words.json"


# =========================
# MAIN FUNCTION
# =========================

def export_random_words_to_json():
    if not os.path.isfile(DB_PATH):
        print("❌ Database not found")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT *
        FROM {TABLE_NAME}
        ORDER BY RANDOM()
        LIMIT ?
    """, (SAMPLE_SIZE,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No data found")
        return

    # Convert rows to list of dicts
    data = [dict(row) for row in rows]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("✅ JSON file created successfully")
    print(f"📄 File: {OUTPUT_FILE}")
    print(f"🔢 Words exported: {len(data)}")


# =========================
# RUNp
0# =========================

if __name__ == "__main__":
    export_random_words_to_json()
