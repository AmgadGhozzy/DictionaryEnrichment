import sqlite3
import json

EMPTY_WORD_FAMILY_KEYS = {"noun", "verb", "adj", "adv"}

def is_empty_word_family(value: str) -> bool:
    """
    يعتبر wordFamily فارغ إذا:
    - JSON صالح
    - يحتوي فقط على noun / verb / adj / adv
    - كل القيم نصوص فارغة
    """
    try:
        data = json.loads(value)
        if not isinstance(data, dict):
            return False

        keys = set(data.keys())
        if keys != EMPTY_WORD_FAMILY_KEYS:
            return False

        return all(
            isinstance(v, str) and v.strip() == ""
            for v in data.values()
        )
    except Exception:
        return False


def analyze_database_gaps(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. إجمالي السجلات
    cursor.execute("SELECT COUNT(*) FROM wordsMaster")
    total_rows = cursor.fetchone()[0]

    print("=" * 60)
    print("📊 DATABASE GAP ANALYSIS REPORT")
    print(f"Total Records: {total_rows}")
    print("=" * 60)
    print(f"{'Column Name':<20} | {'Missing':<10} | {'Fill Rate':<10}")
    print("-" * 55)

    # 2. الأعمدة
    cursor.execute("PRAGMA table_info(wordsMaster)")
    columns = [col[1] for col in cursor.fetchall()]

    summary = []

    for col in columns:
        # الحالات العامة (سريعة داخل SQLite)
        cursor.execute(f"""
            SELECT COUNT(*) FROM wordsMaster
            WHERE {col} IS NULL
               OR {col} = ''
               OR {col} = '[]'
               OR {col} = '{{}}'
        """)
        missing_count = cursor.fetchone()[0]

        # معالجة خاصة لـ wordFamily
        if col == "wordFamily":
            cursor.execute("""
                SELECT wordFamily FROM wordsMaster
                WHERE wordFamily IS NOT NULL
                  AND wordFamily NOT IN ('', '{}', '[]')
            """)
            rows = cursor.fetchall()

            json_empty_count = 0
            for (value,) in rows:
                if is_empty_word_family(value):
                    json_empty_count += 1

            missing_count += json_empty_count

        fill_rate = ((total_rows - missing_count) / total_rows) * 100
        summary.append((col, missing_count, fill_rate))

        print(f"{col:<20} | {missing_count:<10} | {fill_rate:>8.1f}%")

    print("=" * 60)

    # 3. توصيات معمارية
    print("\n💡 ARCHITECT'S RECOMMENDATIONS:")

    critical = [c for c in summary if c[2] < 50]
    if critical:
        print("⚠️ Critical Gaps Found in:")
        for c in critical:
            print(f"   - {c[0]} ({c[2]:.1f}% filled)")
        print("   → Priority for next Gemini enrichment pass.")

    cefr = next((c for c in summary if c[0] == "cefrLevel"), None)
    if cefr and cefr[1] > 0:
        print(f"📌 cefrLevel missing in {cefr[1]} records.")
        print("   → Suggest heuristic or Gemini CEFR prediction.")

    wf = next((c for c in summary if c[0] == "wordFamily"), None)
    if wf:
        print(f"🧬 wordFamily quality check:")
        print(f"   → {wf[1]} records structurally empty or useless.")

    conn.close()


if __name__ == "__main__":
    DB_PATH = "/sdcard/DictionaryEnrichment/WordsMasterXX.db"
    analyze_database_gaps(DB_PATH)
