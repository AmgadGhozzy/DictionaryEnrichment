import sqlite3
import os
from datetime import datetime

DB_PATH = "/sdcard/DictionaryEnrichment/WordsMasterXX.db"

# ❗️ الكلمات المطلوب حذفها (C2 القصيرة/الخاطئة)
WORDS_TO_DELETE = ['toward','higher','growing','elected','lacking','varying',
  'unclear','morally','entitled','mentally','sexually','whereupon'
]

def remove_words_and_fix_gaps():
    if not os.path.exists(DB_PATH):
        print("❌ Error: Database not found")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("🗑️ Deleting invalid words...")

        placeholders = ",".join(["?"] * len(WORDS_TO_DELETE))
        cursor.execute(
            f"DELETE FROM wordsMaster WHERE wordEn IN ({placeholders})",
            WORDS_TO_DELETE
        )

        deleted = cursor.rowcount
        print(f"✅ Deleted {deleted} words")

        # 🔁 Reload remaining rows ordered by rank
        cursor.execute("SELECT * FROM wordsMaster ORDER BY rank ASC")
        rows = cursor.fetchall()

        columns = [col[0] for col in cursor.description]

        # 🧱 Create temp table with SAME schema
        cursor.execute("DROP TABLE IF EXISTS wordsMaster_temp")
        cursor.execute("""
            CREATE TABLE wordsMaster_temp AS
            SELECT * FROM wordsMaster WHERE 1=0
        """)

        print("🔄 Rebuilding table with continuous id & rank...")

        for new_index, row in enumerate(rows, start=1):
            record = dict(zip(columns, row))
            record["id"] = new_index
            record["rank"] = new_index

            values = [record[col] for col in columns]
            placeholders = ",".join(["?"] * len(values))

            cursor.execute(
                f"INSERT INTO wordsMaster_temp VALUES ({placeholders})",
                values
            )

        # 🔥 Replace old table
        cursor.execute("DROP TABLE wordsMaster")
        cursor.execute("ALTER TABLE wordsMaster_temp RENAME TO wordsMaster")

        conn.commit()
        print(f"📊 Final word count: {len(rows)}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error occurred: {e}")

    finally:
        conn.close()

    # 🧹 Vacuum for real cleanup
    try:
        conn_v = sqlite3.connect(DB_PATH)
        conn_v.execute("VACUUM")
        conn_v.close()
        print("🧹 VACUUM completed successfully")
    except Exception as e:
        print(f"⚠️ Vacuum failed: {e}")


if __name__ == "__main__":
    remove_words_and_fix_gaps()
