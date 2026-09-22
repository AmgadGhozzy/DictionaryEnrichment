import sqlite3
import csv

db_path = "WordDictionary1.db"
table_name = "words"
output_file = "output.csv"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

query = f"SELECT * FROM {table_name} LIMIT 20;"
cursor.execute(query)

# get column names
column_names = [description[0] for description in cursor.description]

rows = cursor.fetchall()

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(column_names)  # header
    writer.writerows(rows)          # data

print("Output saved to output.csv")

conn.close()
