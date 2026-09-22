import sqlite3
import json
import os
import glob
from pathlib import Path

# ================= CONFIG =================
DB_PATH = "/sdcard/DictionaryEnrichment/WordsMasterXX.db"
BASE_DIR = "/sdcard/DictionaryEnrichment"
BATCH_DIR = f"{BASE_DIR}/manual_batches"
STATE_FILE = f"{BASE_DIR}/cefr_state.json"
RESULT_DIR = "/sdcard/Download"  # Where AI Studio saves results

BATCH_SIZE = 200
os.makedirs(BATCH_DIR, exist_ok=True)

# ================= SMART FILE FINDER =================
def find_latest_result(base_name="ai_studio_code"):
    """Find the most recently modified file matching the pattern."""
    pattern = f"{RESULT_DIR}/{base_name}*.txt"
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    # Sort by modification time, newest first
    latest = max(files, key=os.path.getmtime)
    return latest

# ================= STATE ==================
def load_offset():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE, encoding="utf-8"))["offset"]
    return 0

def save_offset(offset):
    json.dump({"offset": offset}, open(STATE_FILE, "w", encoding="utf-8"))

# ================= EXPORT =================
def export_batch():
    offset = load_offset()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT wordEn, pos
        FROM wordsMaster
        WHERE cefrLevel is NULL
        ORDER BY wordEn, pos
        LIMIT ? OFFSET ?
    """, (BATCH_SIZE, offset))

    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("✅ No more batches to export.")
        return

    # Each item has "w" for word, "p" for pos, AND "i" for index verification
    batch = [{"i": offset + idx, "w": w, "p": p} for idx, (w, p) in enumerate(rows)]

    path = f"{BATCH_DIR}/batch_{offset}_{offset+len(batch)}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=2)

    print("📦 Batch exported:")
    print(path)
    print(f"📊 Offset: {offset}, Count: {len(batch)}")
    print("🔄 Processing words with fromOxford = 0 (includes words with existing cefrLevel)")
    print("➡️ Paste this file into Gemini AI Studio for processing with Structured Outputs.")

# ================= IMPORT =================
def import_result(result_path=None):
    # Smart auto-detect - always use latest file
    if not result_path:
        result_path = find_latest_result()
        if result_path:
            print(f"🔍 Using latest result file:\n{result_path}")
        else:
            print("❌ No result files found matching pattern 'ai_studio_code*.txt'")
            return

    if not os.path.exists(result_path):
        print(f"❌ File not found: {result_path}")
        return

    try:
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        print("⚠️ The file may be corrupted. Please check the file content.")
        return

    if "items" in data:
        items = data["items"]
    else:
        items = data  # fallback if raw JSON array

    if not isinstance(items, list):
        print("❌ Invalid format: Expected a list of items")
        return

    offset = load_offset()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT wordEn, pos
        FROM wordsMaster
        WHERE cefrLevel is NULL
        ORDER BY wordEn, pos
        LIMIT ? OFFSET ?
    """, (len(items), offset))

    rows = cur.fetchall()

    if len(rows) != len(items):
        conn.close()
        print(f"❌ SIZE MISMATCH!")
        print(f"   Result file has: {len(items)} items")
        print(f"   Database expects: {len(rows)} items")
        print(f"   Current offset: {offset}")
        print("\n⚠️ IMPORT ABORTED - No changes made to database")
        print("💡 This usually means:")
        print("   - Wrong result file (from a different batch)")
        print("   - Corrupted/incomplete AI response")
        print("   - Database was modified elsewhere")
        return

    # CRITICAL: Validate that words/pos match exactly
    mismatches = []
    for i, (item, (db_word, db_pos)) in enumerate(zip(items, rows)):
        if not isinstance(item, dict):
            conn.close()
            print(f"❌ Item {i} is not a valid object")
            print("⚠️ IMPORT ABORTED - No changes made")
            return
        
        # Check if word matches (POS is optional since AI Studio may not return it)
        item_word = item.get("w")
        item_pos = item.get("p")  # May be None if AI Studio doesn't return it
        
        # Word must match
        if item_word != db_word:
            mismatches.append({
                "index": i,
                "expected": f"{db_word} ({db_pos})",
                "got": f"{item_word} ({item_pos})"
            })
        
        # Check for index verification if available
        if "i" in item and item["i"] != offset + i:
            conn.close()
            print(f"❌ BATCH INDEX MISMATCH at item {i}")
            print(f"   Expected index: {offset + i}")
            print(f"   Got index: {item['i']}")
            print("\n⚠️ This result is from a DIFFERENT batch!")
            print("⚠️ IMPORT ABORTED - No changes made")
            return
        
        if "cefr" not in item and "error" not in item:
            conn.close()
            print(f"❌ Item {i} missing both 'cefr' and 'error' fields")
            print(f"   Word: {db_word}, POS: {db_pos}")
            print("⚠️ IMPORT ABORTED - No changes made")
            return
    
    # If we found word/pos mismatches, abort
    if mismatches:
        conn.close()
        print(f"❌ WORD/POS MISMATCH DETECTED!")
        print(f"   Found {len(mismatches)} mismatches")
        print("\n🚨 This result file contains DIFFERENT words than expected!")
        print("   First 5 mismatches:")
        for mm in mismatches[:5]:
            print(f"   [{mm['index']}] Expected: {mm['expected']}, Got: {mm['got']}")
        print("\n⚠️ IMPORT ABORTED - No changes made to database")
        print("💡 Make sure you're importing the correct result file for this batch")
        return

    # All validations passed, proceed with update
    for (word, pos), item in zip(rows, items):
        # Handle INVALID_POS
        cefr_value = None
        if "cefr" in item:
            cefr_value = item["cefr"]
        elif "error" in item and item["error"] == "INVALID_POS":
            cefr_value = "INVALID_POS"

        cur.execute("""
            UPDATE wordsMaster
            SET cefrLevel = ?
            WHERE wordEn = ? AND pos = ?
        """, (cefr_value, word, pos))

    conn.commit()
    conn.close()

    save_offset(offset + len(items))
    print(f"✅ Batch imported successfully. New offset: {offset + len(items)}")
    
    # Archive the processed file
    archive_dir = f"{BASE_DIR}/processed_results"
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = f"{archive_dir}/{Path(result_path).name}"
    try:
        os.rename(result_path, archive_path)
        print(f"📁 Result file archived to: {archive_path}")
    except:
        print(f"⚠️ Could not archive file (file may be in use)")

# ================= CLI ====================
if __name__ == "__main__":
    while True:
        print("\n" + "=" * 50)
        
        # Check for pending results
        latest = find_latest_result()
        if latest:
            print("📥 Found result file - attempting import...")
            import_result()
        else:
            print("ℹ️ No result files found")
        
        print("=" * 50)
        
        # Ask about exporting next batch
        print("\n📤 Export next batch?")
        choice = input("(y/n): ").strip().lower()
        
        if choice == 'y':
            export_batch()
            print("\n⏳ Waiting for you to process this batch in AI Studio...")
            print("   1. Copy the batch file content")
            print("   2. Paste into Gemini AI Studio")
            print("   3. Download the result as 'ai_studio_code.txt'")
            print("   4. Press ENTER when ready to continue")
            input()
        else:
            print("✅ Done. Run the script again when you have results.")
            break