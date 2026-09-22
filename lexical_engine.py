"""
Lexical Enrichment Engine v1.0
==============================
A production-grade AI enrichment pipeline for transforming raw lexical entries
into high-fidelity pedagogical knowledge objects.
"""

import os
import sys
import json
import sqlite3
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from collections import deque
from enum import Enum

# External Dependency Check
try:
    import google.genai as genai
    from google.api_core import retry
except ImportError:
    print("CRITICAL ERROR: 'google-genai' library not found.")
    print("Please install it with: pip install google-genai")
    sys.exit(1)


# ============================================================================
# 1. CONFIGURATION & ENVIRONMENT
# ============================================================================

class EnvType(Enum):
    LOCAL = "local"
    COLAB = "colab"

@dataclass
class PathConfig:
    db_path: str
    log_dir: str
    system_prompt_path: str
    user_prompt_path: str
    schema_path: str

class Config:
    # API keys from environment (comma-separated GEMINI_API_KEYS for rotation).
    # Set via .env / Colab secrets — never commit keys.
    API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
    MODEL_NAME = "gemini-3-pro-preview"
    TEMPERATURE = 1.0
    MAX_OUTPUT_TOKENS = 81920
    BATCH_SIZE = 5
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    QA_THRESHOLD = 0.8 

    @staticmethod
    def detect_env() -> EnvType:
        if "google.colab" in sys.modules:
            return EnvType.COLAB
        return EnvType.LOCAL

    @classmethod
    def get_paths(cls) -> PathConfig:
        env = cls.detect_env()
        if env == EnvType.COLAB:
            base_dir = "/content/drive/MyDrive/LexicalEngine" # Update if needed
            db_path = "/content/drive/MyDrive/LexicalEngine/WordsMaster.db"
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "WordsMaster.db")
            
        return PathConfig(
            db_path=db_path,
            log_dir=os.path.join(base_dir, "logs"),
            system_prompt_path=os.path.join(base_dir, "SystemPrompt.md"),
            user_prompt_path=os.path.join(base_dir, "BatchUserPrompt.md"),
            schema_path=os.path.join(base_dir, "StructuredOutput.json")
        )

# ============================================================================
# 2. DOMAIN MODELS (FULL SPEC)
# ============================================================================

@dataclass
class SystemMeta:
    enriched: bool = False
    enrichmentVersion: str = "v1.0"
    lastEnrichedAt: Optional[str] = None
    qualityStatus: str = "raw" 
    confidenceScore: float = 0.0
    aiConfidence: float = 0.0
    systemConfidence: float = 0.0
    qaFlags: List[str] = field(default_factory=list)
    retryCount: int = 0

@dataclass
class WordEntry:
    # --- Identifiers & Immutable from DB ---
    id: int
    wordEn: str
    pos: str
    cefrLevel: str
    fromOxford: int = 0
    rank: int = 0
    frequency: float = 0.0
    category: Optional[str] = None # DB value wins if present
    syllabify: Optional[str] = None
    
    # --- Pedagogical & Calculated ---
    difficultyScore: Optional[str] = None # nullable, use old if null
    
    phoneticUs: Optional[str] = None
    phoneticUk: Optional[str] = None
    phoneticAr: Optional[str] = None # Half tashkeel
    translit: Optional[str] = None   # Romanized arabicAr
    
    definitionEn: Optional[str] = None
    definitionAr: Optional[str] = None
    usageNote: Optional[str] = None
    
    primarySense: Optional[str] = None
    semanticTags: List[str] = field(default_factory=list)
    register: Optional[str] = None
    mnemonicAr: Optional[str] = None
    
    # --- Complex Structures ---
    examples: Dict[str, str] = field(default_factory=dict) # A1-C2 map
    collocations: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    relatedWords: Dict[str, List[str]] = field(default_factory=dict) # {en: [], ar: []}
    wordFamily: Dict[str, str] = field(default_factory=dict) # {noun: "", verb: "", ...}
    
    # --- Translations ---
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
    
    # --- Meta ---
    systemMeta: SystemMeta = field(default_factory=SystemMeta)

    def to_dict(self):
        return asdict(self)

# ============================================================================
# 3. PROMPT ENGINEERING & GEMINI CLIENT
# ============================================================================

class GeminiClient:
    def __init__(self, api_keys: List[str], paths: PathConfig):
        self.api_keys = deque(api_keys)
        self.current_key = self.api_keys[0]
        self.paths = paths
        self.system_prompt = self._load_file(paths.system_prompt_path)
        self.user_prompt_template = self._load_file(paths.user_prompt_path)
        self.output_schema = self._load_json(paths.schema_path)
        self.client = None
        self.model = None
        self._init_client()
        
    def _load_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.read()
        except Exception as e:
            logging.error(f"Failed to load file {path}: {e}")
            return ""

    def _load_json(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load JSON {path}: {e}")
            return {}

    def _init_client(self):
        """Initialize the new google.genai client"""
        self.client = genai.Client(api_key=self.current_key)
        
        # Create generation config
        self.generation_config = {
            "temperature": Config.TEMPERATURE,
            "max_output_tokens": Config.MAX_OUTPUT_TOKENS,
            "response_mime_type": "application/json"
        }
        
        # Note: response_schema is handled differently in the new API
        # You may need to adjust this based on the actual google.genai API

    def rotate_key(self):
        if len(self.api_keys) > 1:
            self.api_keys.rotate(-1)
            self.current_key = self.api_keys[0]
            self._init_client()
            logging.warning(f"Rotate API Key to: ...{self.current_key[-4:]}")

    def generate(self, batch_data: List[Dict]) -> List[Dict]:
        """
        Enrich a batch of words using the new google.genai API.
        """
        user_prompt = self.user_prompt_template.replace("{{BATCH_JSON}}", 
                                                         json.dumps(batch_data, ensure_ascii=False, indent=2))
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                # Use the new API format
                response = self.client.models.generate_content(
                    model=Config.MODEL_NAME,
                    contents=user_prompt,
                    config={
                        "system_instruction": self.system_prompt,
                        **self.generation_config
                    }
                )
                
                # Parse response
                result_text = response.text
                result = json.loads(result_text)
                
                # Extract batch array
                if isinstance(result, dict) and "batch" in result:
                    return result["batch"]
                elif isinstance(result, list):
                    return result
                else:
                    logging.error(f"Unexpected response format: {type(result)}")
                    return []
                    
            except Exception as e:
                logging.error(f"API Error (Attempt {attempt+1}): {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    self.rotate_key()
                time.sleep(Config.RETRY_DELAY * (attempt + 1))
        
        return []

# ============================================================================
# 4. QA & CONFLICT RESOLUTION
# ============================================================================

class QARulesEngine:
    @staticmethod
    def validate(enriched: Dict) -> Dict:
        flags = []
        
        # 1. Required Fields
        required = ["definitionEn", "definitionAr", "arabicAr", "phoneticUs"]
        for field in required:
            if not enriched.get(field):
                flags.append(f"missing_{field}")
        
        # 2. CEFR Examples
        cefr_level = enriched.get("cefrLevel", "").upper()
        examples = enriched.get("examples", {})
        if cefr_level and cefr_level not in examples:
            flags.append("no_cefr_example")
        
        # 3. Translations Consistency
        main_ar = enriched.get("arabicAr", "")
        related_ar = enriched.get("relatedWords", {}).get("ar", [])
        if main_ar and main_ar in related_ar:
            flags.append("redundant_translation")
        
        # 4. AI Confidence
        ai_conf = enriched.get("aiConfidence", 0.0)
        if ai_conf < Config.QA_THRESHOLD:
            flags.append("low_confidence")
        
        passed = len(flags) == 0
        system_conf = 1.0 if passed else max(0.3, 1.0 - (len(flags) * 0.15))
        
        return {
            "passed": passed,
            "flags": flags,
            "systemConfidence": system_conf
        }

class ConflictResolutionEngine:
    @staticmethod
    def merge(raw: Dict, enriched: Dict) -> WordEntry:
        """
        Merge DB seed + AI enriched data.
        Rules:
          1. IDs (id, wordEn, pos, cefrLevel) -> DB immutable
          2. Metadata (category, fromOxford, rank, frequency, syllabify) -> DB wins
          3. AI Fields -> AI wins (overwrite)
        """
        
        # 1. Immutable IDs from DB
        # ------------------------
        merged_ids = {
            "id": raw["id"],
            "wordEn": raw["wordEn"],
            "pos": raw["pos"],
            "cefrLevel": raw["cefrLevel"]
        }
        
        # 2. Metadata (DB Wins)
        # ---------------------
        metadata_fields = ["category", "fromOxford", "rank", "frequency", "syllabify"]
        for k in metadata_fields:
            # DB value first, then AI, then None
            merged_ids[k] = raw.get(k) or enriched.get(k)
        
        # Special: difficultyScore logic
        # If AI gives null or empty string, keep old DB value
        diff_score = enriched.get("difficultyScore")
        if not diff_score or diff_score == "":
            diff_score = raw.get("difficultyScore")
        # Enforce valid range or string format if needed
        merged_ids["difficultyScore"] = diff_score

        # 3. AI Fields (Must Get / Overwrite)
        # -----------------------------------
        ai_fields = [
            "phoneticUs", "phoneticUk", "phoneticAr", "translit",
            "definitionEn", "definitionAr", "usageNote",
            "primarySense", "semanticTags", "register", "mnemonicAr",
            "examples", "collocations", "synonyms", "antonyms",
            "relatedWords", "wordFamily", "arabicAr",
            
            # Languages
            "frenchFr", "germanDe", "spanishEs", "chineseZh", 
            "russianRu", "portuguesePt", "japaneseJa", "italianIt", "turkishTr"
        ]
        
        for k in ai_fields:
            # If AI returns explicit null (None), check if we want to keep old?
            # User said "must get for all" -> implies AI overrides.
            val = enriched.get(k)
            # Special case: phoneticUk can be nullable if == US.
            merged_ids[k] = val

        # 4. Meta & Confidence
        # --------------------
        # Extract aiConfidence directly from the Gemini JSON response.
        ai_conf = float(enriched.get("aiConfidence", 0.85)) 

        
        # Build Object
        return WordEntry(
            **merged_ids,
            systemMeta=SystemMeta(
                enriched=True,
                qualityStatus="enriched", # Will be updated by Pipeline decision
                aiConfidence=ai_conf
            )
        )

# ============================================================================
# 5. DATA INFRASTRUCTURE (SQLITE)
# ============================================================================

class DAO:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def _ensure_tables(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # 1. Core Table Check
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wordsMaster'")
            if not cursor.fetchone():
                return
            
            # 2. Column Migration
            cursor.execute("PRAGMA table_info(wordsMaster)")
            existing = {row[1] for row in cursor.fetchall()}
            
            # New Unified Schema
            required = {
                # Identifiers
                "fromOxford": "INTEGER DEFAULT 0",
                "rank": "INTEGER DEFAULT 0",
                "frequency": "REAL DEFAULT 0.0",
                # Linguistics
                "phoneticUs": "TEXT", "phoneticUk": "TEXT", "phoneticAr": "TEXT", "translit": "TEXT",
                "difficultyScore": "TEXT", "syllabify": "TEXT",
                # Definitions / Pedagogy
                "definitionEn": "TEXT", "definitionAr": "TEXT", "usageNote": "TEXT",
                "category": "TEXT", "primarySense": "TEXT", "register": "TEXT",
                "mnemonicAr": "TEXT", 
                # Complex JSONs
                "semanticTags": "TEXT", "examples": "TEXT", "collocations": "TEXT",
                "synonyms": "TEXT", "antonyms": "TEXT", "relatedWords": "TEXT", "wordFamily": "TEXT",
                # Languages
                "frenchFr": "TEXT", "germanDe": "TEXT", "spanishEs": "TEXT", 
                "chineseZh": "TEXT", "russianRu": "TEXT", "portuguesePt": "TEXT",
                "japaneseJa": "TEXT", "italianIt": "TEXT", "turkishTr": "TEXT",
                # Meta
                "enriched": "INTEGER DEFAULT 0", "qualityStatus": "TEXT", 
                "aiConfidence": "REAL", "systemConfidence": "REAL", "confidenceScore": "REAL",
                "qaFlags": "TEXT", "retryCount": "INTEGER"
            }
            
            for col, dtype in required.items():
                if col not in existing:
                    logging.info(f"Adding column {col}")
                    try: cursor.execute(f"ALTER TABLE wordsMaster ADD COLUMN {col} {dtype}")
                    except: pass
            
            conn.commit()
        finally:
            conn.close()

    def fetch_batch(self, batch_size: int) -> List[Dict]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wordsMaster WHERE enriched = 0 LIMIT ?", (batch_size,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_word(self, word: WordEntry):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        data = word.to_dict()
        meta = data.pop("systemMeta")
        data.update(asdict(meta)) # Flatten meta
        
        # Serialize JSON fields
        json_cols = ["examples", "collocations", "synonyms", "antonyms", 
                     "relatedWords", "wordFamily", "semanticTags", "qaFlags"]
        for k in json_cols:
            if isinstance(data.get(k), (dict, list)):
                data[k] = json.dumps(data[k], ensure_ascii=False)
        
        # Dynamic Update
        keys = [k for k in data.keys() if k != "id"]
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        values = [data[k] for k in keys] + [data["id"]]
        
        try:
            cursor.execute(f"UPDATE wordsMaster SET {set_clause} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

# ============================================================================
# MAIN
# ============================================================================

class Pipeline:
    def __init__(self, dry_run: bool):
        self.paths = Config.get_paths()
        self.dao = DAO(self.paths.db_path)
        self.gemini = GeminiClient(Config.API_KEYS, self.paths)
        self.dry_run = dry_run
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    def run(self):
        print(f"--- LEXICAL ENGINE v1.0 ({'DRY RUN' if self.dry_run else 'LIVE'}) ---")
        
        while True:
            batch = self.dao.fetch_batch(Config.BATCH_SIZE)
            if not batch:
                print("No pending words.")
                break
                
            print(f"Batch: {[w['wordEn'] for w in batch]}")
            
            # Prep input (Send FULL data as requested, excluding system noise)
            system_cols = {"enriched", "systemMeta", "qaFlags", "retryCount", 
                          "aiConfidence", "systemConfidence", "qualityStatus", 
                          "enrichmentVersion", "lastEnrichedAt", "confidenceScore"}
            
            ai_input = []
            for w in batch:
                # Convert row to dict and filter system columns
                full_record = dict(w)
                clean_seed = {k: v for k, v in full_record.items() 
                             if k not in system_cols and v is not None and v != ""}
                ai_input.append(clean_seed)

            if self.dry_run:
                print(f"[DRY RUN] AI Input Payload (Seed Data):")
                print(json.dumps(ai_input, indent=2, ensure_ascii=False))
                
            enriched_results = self.gemini.generate(ai_input)
            
            for raw in batch:
                enriched = next((e for e in enriched_results if e.get("id") == raw["id"]), None)
                if not enriched:
                    print(f"Skipped {raw['wordEn']} (AI missing)")
                    continue
                    
                # QA & Confidence
                qa = QARulesEngine.validate(enriched)
                
                # Merge
                final_word = ConflictResolutionEngine.merge(raw, enriched)
                
                # Update System Meta
                final_word.systemMeta.systemConfidence = qa["systemConfidence"]
                final_word.systemMeta.confidenceScore = (final_word.systemMeta.aiConfidence * 0.6) + (qa["systemConfidence"] * 0.4)
                final_word.systemMeta.qaFlags = qa["flags"]
                final_word.systemMeta.qualityStatus = "passed_qa" if qa["passed"] else "failed_qa"

                if self.dry_run:
                    print(f"  > Enriched: {final_word.wordEn} (Conf: {final_word.systemMeta.confidenceScore:.2f}) - Status: {final_word.systemMeta.qualityStatus}")
                else:
                    self.dao.save_word(final_word)
                    print(f"  > Saved: {final_word.wordEn}")

if __name__ == "__main__":
    # Get user input for dry run mode
    print("=" * 60)
    print("LEXICAL ENRICHMENT ENGINE v1.0")
    print("=" * 60)
    print("\nMode Selection:")
    print("  1. DRY RUN - Preview AI inputs/outputs without saving to database")
    print("  2. LIVE - Process and save enriched data to database")
    print()
    
    while True:
        choice = input("Select mode (1 for DRY RUN, 2 for LIVE): ").strip()
        if choice == "1":
            dry_run = True
            break
        elif choice == "2":
            dry_run = False
            confirm = input("\n⚠️  WARNING: This will modify your database. Continue? (yes/no): ").strip().lower()
            if confirm == "yes":
                break
            else:
                print("Cancelled.")
                sys.exit(0)
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    print()
    Pipeline(dry_run).run()