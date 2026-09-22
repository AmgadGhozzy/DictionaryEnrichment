import sqlite3

DB_PATH = "C:/Users/HP/Desktop/WordsMaster.db"
TABLE_NAME = "wordsMaster"
CATEGORY_COL = "pos"

def show_unique_categories():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(f"""
        SELECT DISTINCT {CATEGORY_COL}
        FROM {TABLE_NAME}
        WHERE {CATEGORY_COL} IS NOT NULL
        ORDER BY {CATEGORY_COL}
    """)

    rows = cur.fetchall()

    print("\nUnique CATEGORY values:")
    for r in rows:
        print(f"- {r[0]}")

    conn.close()

if __name__ == "__main__":
    show_unique_categories()
