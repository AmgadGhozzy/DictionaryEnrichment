"""
Manual Lexical Enrichment Engine v3.0
=====================================
✨ NEW: Cross-Platform Support (PC & Android)
✨ Auto-detect platform and paths
✨ Auto-detect pending batch and offset
"""

import os
import sys
import json
import sqlite3
import glob
import shutil
import platform
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

# ============================================================================
# 1. PLATFORM DETECTION & AUTO-CONFIGURATION
# ============================================================================

class PlatformDetector:
    """Auto-detect platform and configure paths."""
    
    @staticmethod
    def detect_platform() -> str:
        """Detect if running on Android or PC."""
        # Check for Android-specific paths
        if os.path.exists("/sdcard"):
            return "android"
        # Check Windows environment
        elif platform.system() == "Windows":
            return "windows"
        # Check Linux/Mac
        elif platform.system() in ["Linux", "Darwin"]:
            return "unix"
        else:
            return "windows"  # Default to Windows
    
    @staticmethod
    def get_base_paths(detected_platform: str) -> Dict[str, str]:
        """Get platform-specific base paths."""
        
        if detected_platform == "android":
            return {
                "base_dir": "/sdcard/DictionaryEnrichment/Manual",
                "result_dir": "/sdcard/Download",
                "db_search_paths": [
                    "/sdcard/DictionaryEnrichment/Manual/WordsMaster.db",
                    "/sdcard/WordsMaster.db",
                    "/sdcard/DictionaryEnrichment/WordsMaster.db"
                ]
            }
        
        else:  # Windows/PC
            home = Path.home()
            downloads = home / "Downloads"
            desktop = home / "Desktop"
            
            # PC paths from your request
            pc_paths = {
                "base_dir": str(desktop / "DictionaryEnrichment" / "Manual"),
                "result_dir": str(downloads),
                "db_search_paths": [
                    str(desktop / "DictionaryEnrichment" / "Manual" / "WordsMaster.db"),
                    str(downloads / "WordsMaster.db"),
                    str(desktop / "WordsMaster.db"),
                    str(home / "Documents" / "WordsMaster.db")
                ]
            }
            
            return pc_paths

class Config:
    """Dynamic configuration based on platform."""
    
    BATCH_SIZE = 40
    
    QA_THRESHOLD = 0.8
    
    # Platform detection
    PLATFORM = PlatformDetector.detect_platform()
    PATHS = PlatformDetector.get_base_paths(PLATFORM)
    
    # Dynamic paths
    BASE_DIR = PATHS["base_dir"]
    RESULT_DIR = PATHS["result_dir"]
    DB_PATH = None  # Will be auto-detected
    
    BATCH_DIR = f"{BASE_DIR}/batches"
    STATE_FILE = f"{BASE_DIR}/enrichment_state.json"
    BATCH_PROMPT_PATH = f"{BASE_DIR}/BatchUserPrompt.md"
    
    # Result file patterns
    RESULT_PATTERNS = [
        "ai_studio_code*.txt",
        "gemini_result*.txt",
        "enrichment_result*.txt",
        "claude_result*.txt"
    ]
    
    @classmethod
    def auto_detect_database(cls) -> Optional[str]:
        """Auto-detect database file."""
        print(f"🔍 Searching for database...")
        
        # Search in predefined paths
        for db_path in cls.PATHS["db_search_paths"]:
            if os.path.exists(db_path):
                print(f"   ✅ Found: {db_path}")
                return db_path
        
        # Search in common locations
        search_dirs = [
            cls.BASE_DIR,
            cls.RESULT_DIR,
            str(Path.home()),
            str(Path.home() / "Documents"),
            str(Path.home() / "Desktop")
        ]
        
        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                for root, dirs, files in os.walk(search_dir):
                    for file in files:
                        if file == "WordsMaster.db":
                            db_path = os.path.join(root, file)
                            print(f"   ✅ Found: {db_path}")
                            return db_path
        
        print(f"   ❌ Database not found!")
        return None
    
    @classmethod
    def setup_dirs(cls):
        """Create necessary directories."""
        os.makedirs(cls.BASE_DIR, exist_ok=True)
        os.makedirs(cls.BATCH_DIR, exist_ok=True)
        os.makedirs(f"{cls.BASE_DIR}/processed_results", exist_ok=True)
        os.makedirs(f"{cls.BASE_DIR}/processed_batches", exist_ok=True)
        
        print(f"\n📁 Platform: {cls.PLATFORM.upper()}")
        print(f"📂 Base Directory: {cls.BASE_DIR}")
        print(f"📥 Result Directory: {cls.RESULT_DIR}")
    
    @classmethod
    def initialize(cls):
        """Initialize configuration."""
        cls.setup_dirs()
        cls.DB_PATH = cls.auto_detect_database()
        return cls.DB_PATH is not None

# ============================================================================
# 2. DOMAIN MODELS
# ============================================================================

@dataclass
class SystemMeta:
    enriched: bool = False
    enrichmentVersion: str = "v3.0"
    lastEnrichedAt: Optional[str] = None
    qualityStatus: str = "raw"
    confidenceScore: float = 0.0
    aiConfidence: float = 0.0
    systemConfidence: float = 0.0
    qaFlags: List[str] = field(default_factory=list)
    retryCount: int = 0

@dataclass
class WordEntry:
    id: int
    wordEn: str
    pos: str
    cefrLevel: str
    fromOxford: int = 0
    rank: int = 0
    frequency: float = 0.0
    category: Optional[str] = None
    syllabify: Optional[str] = None
    difficultyScore: Optional[str] = None
    phoneticUs: Optional[str] = None
    phoneticUk: Optional[str] = None
    phoneticAr: Optional[str] = None
    translit: Optional[str] = None
    definitionEn: Optional[str] = None
    definitionAr: Optional[str] = None
    usageNote: Optional[str] = None
    primarySense: Optional[str] = None
    semanticTags: List[str] = field(default_factory=list)
    register: Optional[str] = None
    mnemonicAr: Optional[str] = None
    examples: Dict[str, str] = field(default_factory=dict)
    collocations: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    relatedWords: Dict[str, List[str]] = field(default_factory=dict)
    wordFamily: Dict[str, str] = field(default_factory=dict)
    arabicAr: Optional[str] = None
    frenchFr: Optional[str] = None
    germanDe: Optional[str] = None
    spanishEs: Optional[str] = None
    chineseZh: Optional[str] = None
    russianRu: Optional[str] = None
    portuguesePt: Optional[str] = None
    japaneseJa: Optional[str] = None
    italianIt: Optional[str] = None
    turkishTr: Optional[str] = None
    systemMeta: SystemMeta = field(default_factory=SystemMeta)
    
    def to_dict(self):
        return asdict(self)

# ============================================================================
# 3. QA & CONFLICT RESOLUTION
# ============================================================================

class QARulesEngine:
    @staticmethod
    def validate(enriched: Dict) -> Dict:
        flags = []
        
        required = ["definitionEn", "definitionAr", "arabicAr", "phoneticUs", "aiConfidence"]
        for field_name in required:
            if not enriched.get(field_name):
                flags.append(f"missing_{field_name}")
        
        translation_fields = [
            "frenchFr", "germanDe", "spanishEs", "chineseZh",
            "russianRu", "portuguesePt", "japaneseJa", "italianIt", "turkishTr"
        ]
        for field_name in translation_fields:
            value = enriched.get(field_name)
            if not value or value == "":
                flags.append(f"missing_translation_{field_name}")
        
        ai_conf = enriched.get("aiConfidence", 0.0)
        if not isinstance(ai_conf, (int, float)) or ai_conf < 0.0 or ai_conf > 1.0:
            flags.append("invalid_ai_confidence")
        
        cefr_level = enriched.get("cefrLevel", "").upper()
        examples = enriched.get("examples", {})
        if cefr_level and cefr_level not in examples:
            flags.append("no_cefr_example")
        
        main_ar = enriched.get("arabicAr", "")
        related_ar = enriched.get("relatedWords", {}).get("ar", [])
        if main_ar and main_ar in related_ar:
            flags.append("redundant_translation")
        
        definition_ar = enriched.get("definitionAr", "")
        if definition_ar and any(c in definition_ar for c in "ًٌٍَُِّْ"):
            flags.append("info_tashkeel_in_definition")
        
        passed = len([f for f in flags if not f.startswith("info_")]) == 0
        critical_flags = [f for f in flags if not f.startswith("info_")]
        system_conf = 1.0 if passed else max(0.3, 1.0 - (len(critical_flags) * 0.15))
        
        return {
            "passed": passed,
            "flags": flags,
            "systemConfidence": system_conf
        }

class ConflictResolutionEngine:
    @staticmethod
    def merge(raw: Dict, enriched: Dict) -> WordEntry:
        merged = {
            "id": raw["id"],
            "wordEn": raw["wordEn"],
            "pos": raw["pos"],
            "cefrLevel": raw["cefrLevel"]
        }
        
        metadata_fields = ["category", "fromOxford", "rank", "frequency", "syllabify"]
        for k in metadata_fields:
            merged[k] = raw.get(k) or enriched.get(k)
        
        diff_score = enriched.get("difficultyScore")
        if diff_score is not None:
            diff_score = str(diff_score)
        if not diff_score or diff_score == "":
            diff_score = raw.get("difficultyScore")
        merged["difficultyScore"] = diff_score
        
        ai_fields = [
            "phoneticUs", "phoneticUk", "phoneticAr", "translit",
            "definitionEn", "definitionAr", "usageNote",
            "primarySense", "register", "mnemonicAr", "arabicAr",
            "frenchFr", "germanDe", "spanishEs", "chineseZh",
            "russianRu", "portuguesePt", "japaneseJa", "italianIt", "turkishTr"
        ]
        
        for k in ai_fields:
            merged[k] = enriched.get(k)
        
        list_fields = ["semanticTags", "collocations", "synonyms", "antonyms"]
        for k in list_fields:
            val = enriched.get(k)
            merged[k] = val if isinstance(val, list) else []
        
        examples = enriched.get("examples")
        merged["examples"] = examples if isinstance(examples, dict) else {}
        
        related = enriched.get("relatedWords")
        if isinstance(related, dict):
            merged["relatedWords"] = related
        else:
            merged["relatedWords"] = {"en": [], "ar": []}
        
        word_family = enriched.get("wordFamily")
        if isinstance(word_family, dict):
            merged["wordFamily"] = word_family
        else:
            merged["wordFamily"] = {"noun": "", "verb": "", "adj": "", "adv": ""}
        
        ai_conf = float(enriched.get("aiConfidence", 0.85))
        
        return WordEntry(
            **merged,
            systemMeta=SystemMeta(
                enriched=True,
                qualityStatus="enriched",
                aiConfidence=ai_conf,
                lastEnrichedAt=datetime.now().isoformat()
            )
        )

# ============================================================================
# 4. DATABASE ACCESS OBJECT (DAO)
# ============================================================================

class DAO:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def count_pending(self) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM wordsMaster 
            WHERE enriched = 0 OR enriched IS NULL
        """)
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def fetch_pending_batch(self, offset: int, limit: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM wordsMaster 
            WHERE enriched = 0 OR enriched IS NULL
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Fields to exclude from batch export (to reduce JSON size)
        exclude_fields = {
            'frenchFr', 'germanDe', 'spanishEs', 'chineseZh', 'russianRu',
            'portuguesePt', 'japaneseJa', 'italianIt', 'turkishTr',
            'fromOxford', 'addedFromOxford', 'enriched', 'enrichmentVersion',
            'lastEnrichedAt', 'qualityStatus', 'confidenceScore',
            'aiConfidence', 'systemConfidence', 'qaFlags'
        }
        
        # Convert rows to dict and remove excluded fields
        batch = []
        for row in rows:
            word_dict = dict(row)
            # Remove excluded fields
            word_dict = {k: v for k, v in word_dict.items() if k not in exclude_fields}
            batch.append(word_dict)
        
        return batch
    
    def save_word(self, word: WordEntry):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        meta = word.systemMeta
        
        update_sql = """
        UPDATE wordsMaster SET
            phoneticUs = ?, phoneticUk = ?, phoneticAr = ?, translit = ?,
            definitionEn = ?, definitionAr = ?, usageNote = ?,
            primarySense = ?, semanticTags = ?, register = ?, mnemonicAr = ?,
            examples = ?, collocations = ?, synonyms = ?, antonyms = ?,
            relatedWords = ?, wordFamily = ?,
            arabicAr = ?, frenchFr = ?, germanDe = ?, spanishEs = ?,
            chineseZh = ?, russianRu = ?, portuguesePt = ?, japaneseJa = ?,
            italianIt = ?, turkishTr = ?,
            enriched = ?, enrichmentVersion = ?, lastEnrichedAt = ?,
            qualityStatus = ?, confidenceScore = ?, aiConfidence = ?,
            systemConfidence = ?, qaFlags = ?
        WHERE id = ?
        """
        
        cursor.execute(update_sql, (
            word.phoneticUs, word.phoneticUk, word.phoneticAr, word.translit,
            word.definitionEn, word.definitionAr, word.usageNote,
            word.primarySense, json.dumps(word.semanticTags, ensure_ascii=False),
            word.register, word.mnemonicAr,
            json.dumps(word.examples, ensure_ascii=False),
            json.dumps(word.collocations, ensure_ascii=False),
            json.dumps(word.synonyms, ensure_ascii=False),
            json.dumps(word.antonyms, ensure_ascii=False),
            json.dumps(word.relatedWords, ensure_ascii=False),
            json.dumps(word.wordFamily, ensure_ascii=False),
            word.arabicAr, word.frenchFr, word.germanDe, word.spanishEs,
            word.chineseZh, word.russianRu, word.portuguesePt, word.japaneseJa,
            word.italianIt, word.turkishTr,
            1, meta.enrichmentVersion, meta.lastEnrichedAt,
            meta.qualityStatus, meta.confidenceScore, meta.aiConfidence,
            meta.systemConfidence, json.dumps(meta.qaFlags),
            word.id
        ))
        
        conn.commit()
        conn.close()

# ============================================================================
# 5. STATE MANAGER WITH AUTO-DETECTION
# ============================================================================

class StateManager:
    """Enhanced state manager with auto-detection."""
    
    def __init__(self):
        self.offset = 0
        self.pending_batch_file = None
        self.pending_batch_ids = []
        self.load()
        self.auto_detect_pending()
    
    def load(self):
        """Load state from file."""
        if os.path.exists(Config.STATE_FILE):
            try:
                with open(Config.STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.offset = data.get('offset', 0)
                    self.pending_batch_file = data.get('pending_batch_file')
                    self.pending_batch_ids = data.get('pending_batch_ids', [])
                    print(f"✅ State loaded: offset={self.offset}")
            except Exception as e:
                print(f"⚠️  Failed to load state: {e}")
    
    def save(self):
        """Save state to file."""
        try:
            with open(Config.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'offset': self.offset,
                    'pending_batch_file': self.pending_batch_file,
                    'pending_batch_ids': self.pending_batch_ids
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Failed to save state: {e}")
    
    def auto_detect_pending(self):
        """Auto-detect pending batch file and IDs."""
        if self.pending_batch_file and os.path.exists(self.pending_batch_file):
            print(f"✅ Pending batch detected: {Path(self.pending_batch_file).name}")
            return
        
        # Search for latest batch file
        batch_files = glob.glob(f"{Config.BATCH_DIR}/batch_*.txt")
        if batch_files:
            latest_batch = max(batch_files, key=os.path.getctime)
            
            # Try to extract IDs from file
            try:
                with open(latest_batch, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for ID pattern in the file
                    import re
                    ids = re.findall(r'"id":\s*(\d+)', content)
                    if ids:
                        self.pending_batch_file = latest_batch
                        self.pending_batch_ids = [int(id_str) for id_str in ids]
                        self.save()
                        print(f"🔍 Auto-detected pending batch: {Path(latest_batch).name}")
                        print(f"   Found {len(self.pending_batch_ids)} IDs")
            except Exception as e:
                print(f"⚠️  Could not read batch file: {e}")
    
    def clear_pending(self):
        """Clear pending batch."""
        self.pending_batch_file = None
        self.pending_batch_ids = []
        self.save()

# ============================================================================
# 6. BATCH EXPORT
# ============================================================================

def export_batch(dao: DAO, state: StateManager) -> bool:
    """Export next batch."""
    
    if state.pending_batch_file and os.path.exists(state.pending_batch_file):
        print(f"\n⚠️  Active batch exists: {Path(state.pending_batch_file).name}")
        confirm = input("   Create new batch anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            return False
    
    pending = dao.count_pending()
    if pending == 0:
        print("\n🎉 No pending words! All enriched!")
        return False
    
    batch = dao.fetch_pending_batch(state.offset, Config.BATCH_SIZE)
    if not batch:
        print("\n❌ No words fetched")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_file = f"{Config.BATCH_DIR}/batch_{timestamp}_{len(batch)}words.txt"
    
    prompt_template = ""
    if os.path.exists(Config.BATCH_PROMPT_PATH):
        with open(Config.BATCH_PROMPT_PATH, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    
    # Compact JSON (single line, no indentation) to reduce file size
    batch_json = json.dumps(batch, ensure_ascii=False, separators=(',', ':'))
    
    full_content = f"{prompt_template}\n\n{batch_json}" if prompt_template else batch_json
    
    with open(batch_file, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    state.pending_batch_file = batch_file
    state.pending_batch_ids = [w['id'] for w in batch]
    state.save()
    
    print(f"\n{'='*60}")
    print(f"✅ BATCH EXPORTED")
    print(f"{'='*60}")
    print(f"📄 File: {Path(batch_file).name}")
    print(f"📊 Words: {len(batch)}")
    print(f"🆔 IDs: {state.pending_batch_ids}")
    print(f"📂 Location: {batch_file}")
    print(f"{'='*60}")
    
    return True

# ============================================================================
# 7. RESULT FILE DETECTION
# ============================================================================

def find_latest_result() -> Optional[str]:
    """Find latest result file using multiple patterns."""
    all_results = []
    
    for pattern in Config.RESULT_PATTERNS:
        results = glob.glob(f"{Config.RESULT_DIR}/{pattern}")
        all_results.extend(results)
    
    if not all_results:
        return None
    
    latest = max(all_results, key=os.path.getctime)
    return latest

def archive_result_file(file_path: str):
    """Archive result file."""
    archive_dir = f"{Config.BASE_DIR}/processed_results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path(file_path).name
    archive_path = f"{archive_dir}/{timestamp}_{filename}"
    
    try:
        shutil.copy2(file_path, archive_path)
        os.remove(file_path)
        print(f"   📦 Archived result")
    except Exception as e:
        print(f"   ⚠️  Archive failed: {e}")

def archive_batch_file(file_path: str):
    """Archive batch file."""
    archive_dir = f"{Config.BASE_DIR}/processed_batches"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path(file_path).name
    archive_path = f"{archive_dir}/{timestamp}_{filename}"
    
    try:
        shutil.copy2(file_path, archive_path)
        print(f"   📦 Archived batch")
    except Exception as e:
        print(f"   ⚠️  Archive failed: {e}")

# ============================================================================
# 8. RESULT IMPORT
# ============================================================================

def import_result(dao: DAO, state: StateManager, result_path: str) -> bool:
    """Import enrichment result."""
    
    print(f"\n📥 Importing: {Path(result_path).name}")
    
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        return False
    
    # Try to parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if not json_match:
            json_match = re.search(r'```\s*(\{.*?\})\s*```', content, re.DOTALL)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except:
                print("❌ Invalid JSON format")
                return False
        else:
            print("❌ No JSON found in file")
            return False
    
    # Extract wordEntries array
    if isinstance(data, dict) and "wordEntries" in data:
        items = data["wordEntries"]
    elif isinstance(data, dict) and "batch" in data:
        items = data["batch"]
    elif isinstance(data, list):
        items = data
    else:
        print("❌ Invalid format: Expected 'wordEntries' array or list")
        return False
    
    if not items:
        print("❌ Empty result")
        return False
    
    print(f"📊 Found {len(items)} word entries")
    
    # Get IDs and validate
    result_ids = [item.get("id") for item in items]
    
    if state.pending_batch_ids:
        if set(result_ids) != set(state.pending_batch_ids):
            print(f"\n⚠️  ID MISMATCH WARNING")
            print(f"   Expected: {state.pending_batch_ids}")
            print(f"   Got: {result_ids}")
            confirm = input("   Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                return False
    
    # Fetch original records
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    raw_records = {}
    for item_id in result_ids:
        cursor.execute("SELECT * FROM wordsMaster WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            raw_records[item_id] = dict(row)
    conn.close()
    
    # Process each word
    success_count = 0
    fail_count = 0
    
    print(f"\n🔄 Processing {len(items)} words...\n")
    
    for enriched in items:
        word_id = enriched.get("id")
        
        if word_id not in raw_records:
            print(f"   ⚠️  ID {word_id} not found in DB - skipping")
            fail_count += 1
            continue
        
        raw = raw_records[word_id]
        qa = QARulesEngine.validate(enriched)
        final_word = ConflictResolutionEngine.merge(raw, enriched)
        
        final_word.systemMeta.systemConfidence = qa["systemConfidence"]
        final_word.systemMeta.confidenceScore = (
            final_word.systemMeta.aiConfidence * 0.6 +
            qa["systemConfidence"] * 0.4
        )
        final_word.systemMeta.qaFlags = qa["flags"]
        final_word.systemMeta.qualityStatus = "passed_qa" if qa["passed"] else "failed_qa"
        
        try:
            dao.save_word(final_word)
            status = "✅" if qa["passed"] else "⚠️ "
            print(f"   {status} {final_word.wordEn:15s} | AI: {final_word.systemMeta.aiConfidence:.2f} | Final: {final_word.systemMeta.confidenceScore:.2f}")
            
            if qa["flags"]:
                flags_str = ', '.join(qa['flags'][:3])
                if len(qa['flags']) > 3:
                    flags_str += f" (+{len(qa['flags'])-3} more)"
                print(f"      ⚠️  Flags: {flags_str}")
            
            success_count += 1
        except Exception as e:
            print(f"   ❌ {enriched.get('wordEn')}: {e}")
            fail_count += 1
    
    print(f"\n{'='*60}")
    print("📊 IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {fail_count}")
    
    # Archive files if successful
    if success_count > 0:
        print(f"\n🗂️  Archiving files...")
        archive_result_file(result_path)
        
        if state.pending_batch_file and os.path.exists(state.pending_batch_file):
            archive_batch_file(state.pending_batch_file)
            try:
                os.remove(state.pending_batch_file)
                print(f"   🗑️  Deleted batch file")
            except:
                pass
        
        state.pending_batch_file = None
        state.pending_batch_ids = []
        state.offset += success_count
        state.save()
        
        print(f"   ✅ Cleanup complete!")
    
    print(f"{'='*60}")
    
    return success_count > 0

# ============================================================================
# 9. MAIN CLI
# ============================================================================

def show_status(dao: DAO, state: StateManager):
    """Display current status."""
    pending = dao.count_pending()
    
    print(f"\n{'='*60}")
    print(f"📊 ENRICHMENT STATUS")
    print(f"{'='*60}")
    print(f"💻 Platform: {Config.PLATFORM.upper()}")
    print(f"📁 Database: {Path(Config.DB_PATH).name}")
    print(f"📊 Pending Words: {pending}")
    print(f"📏 Batch Size: {Config.BATCH_SIZE}")
    print(f"📈 Total Processed: {state.offset}")
    
    if state.pending_batch_file:
        if os.path.exists(state.pending_batch_file):
            print(f"\n🔄 Active Batch:")
            print(f"   📄 File: {Path(state.pending_batch_file).name}")
            print(f"   🆔 IDs: {len(state.pending_batch_ids)} words")
        else:
            print(f"\n⚠️  Batch file missing, clearing state...")
            state.clear_pending()
    
    result = find_latest_result()
    if result:
        print(f"\n📥 Result Ready: {Path(result).name}")
    
    print(f"{'='*60}")

def main():
    print(f"\n{'='*60}")
    print("MANUAL LEXICAL ENRICHMENT ENGINE v3.0")
    print("✨ Cross-Platform Edition (PC & Android)")
    print(f"{'='*60}")
    
    # Initialize configuration
    if not Config.initialize():
        print("\n❌ Failed to initialize. Database not found!")
        print("\n💡 Make sure WordsMaster.db is in one of these locations:")
        for path in Config.PATHS["db_search_paths"]:
            print(f"   • {path}")
        return
    
    print("\nCommands:")
    print("  [ENTER] - Import result & auto-extract next batch")
    print("  e - Export new batch")
    print("  s - Show status")
    print("  q - Quit")
    print(f"{'='*60}")
    
    dao = DAO(Config.DB_PATH)
    state = StateManager()
    
    while True:
        show_status(dao, state)
        
        # Check for result file BEFORE input
        result_path = find_latest_result()
        
        if result_path:
            print(f"\n💡 Result file detected! Press ENTER to import.")
        
        print()
        choice = input("▶ Command [ENTER/e/s/q]: ").strip().lower()
        
        if choice == 'q':
            print("\n👋 Goodbye!")
            break
        
        elif choice == 'e':
            export_batch(dao, state)
        
        elif choice == 's':
            continue
        
        elif choice == '':
            # ========== ENTER KEY PRESSED ==========
            
            # Re-check for result file (in case it appeared)
            result_path = find_latest_result()
            
            if result_path:
                # === STEP 1: IMPORT ===
                print("\n" + "="*60)
                print("📥 STEP 1: IMPORTING RESULT...")
                print("="*60)
                
                import_success = import_result(dao, state, result_path)
                
                # === STEP 2: AUTO-EXTRACT (if import succeeded) ===
                if import_success:
                    print("\n" + "="*60)
                    print("🔄 STEP 2: AUTO-EXTRACTING NEXT BATCH...")
                    print("="*60)
                    
                    pending = dao.count_pending()
                    if pending > 0:
                        export_success = export_batch(dao, state)
                        if export_success:
                            print("\n✅ Ready for next cycle!")
                    else:
                        print("\n🎉 ALL WORDS ENRICHED! Congratulations!")
                else:
                    print("\n⚠️ Import failed - not extracting next batch")
            else:
                print("\n❌ No result file found!")
                print(f"   Looking for patterns:")
                for pattern in Config.RESULT_PATTERNS:
                    print(f"      • {pattern}")
                print(f"   In folder: {Config.RESULT_DIR}")
                print("\n   → Press 'e' to export a batch first")
        
        else:
            print(f"\n❓ Unknown command: '{choice}'")
            print("   Use: ENTER, e, s, or q")

if __name__ == "__main__":
    main()