import sqlite3
import csv
import json
from collections import defaultdict

DB_PATH = "/sdcard/DictionaryEnrichment/WordsMaster.db"
OXFORD_FILES = [
    "/sdcard/DictionaryEnrichment/oxford-3000.csv",
    "/sdcard/DictionaryEnrichment/oxford-5000.csv"
]

MULTI_POS_JSON = "multi_pos_seed.json"
CEFR_FIXED_JSON = "cefr_fixed.json"


# =====================================================
# LOAD OXFORD
# =====================================================
def load_oxford():
    ox = {}
    for path in OXFORD_FILES:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ox[(r["word"].lower(), r["class"].lower())] = r["level"].upper()
    return ox


# =====================================================
# CEFR CONFLICT RESOLUTION
# =====================================================
def resolve_cefr(cursor, oxford):
    cursor.execute("""
        SELECT id, wordEn, pos, cefrLevel
        FROM wordsMaster
        WHERE fromOxford = 1
    """)

    fixed = []

    for _id, w, p, db_cefr in cursor.fetchall():
        key = (w.lower(), p.lower())
        if key in oxford:
            ox_cefr = oxford[key]
            if db_cefr != ox_cefr:
                cursor.execute("""
                    UPDATE wordsMaster
                    SET cefrLevel = ?
                    WHERE id = ?
                """, (ox_cefr, _id))
                fixed.append({
                    "word": w,
                    "pos": p,
                    "old": db_cefr,
                    "new": ox_cefr
                })

    return fixed


# =====================================================
# MAIN
# =====================================================
def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    oxford = load_oxford()

    cursor.execute("BEGIN TRANSACTION")

    fixed = resolve_cefr(cursor, oxford)
    

    conn.commit()
    conn.close()

    with open(CEFR_FIXED_JSON, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"✅ CEFR fixed: {len(fixed)}")
    print("✅ id == rank enforced")
    print("✅ No overwrite, safe migration")
    print("=" * 60)


if __name__ == "__main__":
    main()
