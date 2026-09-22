"""
Lexical Enrichment Engine v1.0 - API Airforce Edition (Fixed)
==============================================================
Fixed: Key rotation, single word batches, response logging, loop prevention
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

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Install with: pip install requests")
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
    response_log_path: str

class Config:
    # API Airforce Configuration with multiple keys
    API_KEYS = [
        "sk-air-5RwRZe49hCIRYZO9qYUniPHDB92MOBBUZsYhS7DUwPIOlxZSsAbsRhTLASBT4POv",
        "sk-air-8xQmc65TC2jUAonMhyQQQVRD776HDs5YxGmPO2512Ju9pMaWwX8sqMAMtcCELO6A",
    ]
    API_URL = "https://api.airforce/v1/chat/completions"
    MODEL_NAME = "gemini-3-pro"
    TEMPERATURE = 0.7
    MAX_TOKENS = 16000
    
    BATCH_SIZE = 1  # Changed to 1 word per batch
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    QA_THRESHOLD = 0.8
    
    # Rate limiting: 1 request per minute per key
    RATE_LIMIT_DELAY = 60  # seconds between requests for same key

    @staticmethod
    def detect_env() -> EnvType:
        if "google.colab" in sys.modules:
            return EnvType.COLAB
        return EnvType.LOCAL

    @classmethod
    def get_paths(cls) -> PathConfig:
        env = cls.detect_env()
        if env == EnvType.COLAB:
            base_dir = "/content/drive/MyDrive/LexicalEngine"
            db_path = "/content/drive/MyDrive/LexicalEngine/WordsMaster.db"
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "WordsMaster.db")
            
        return PathConfig(
            db_path=db_path,
            log_dir=os.path.join(base_dir, "logs"),
            system_prompt_path=os.path.join(base_dir, "SystemPrompt.md"),
            user_prompt_path=os.path.join(base_dir, "BatchUserPrompt.md"),
            schema_path=os.path.join(base_dir, "StructuredOutput.json"),
            response_log_path=os.path.join(base_dir, "api_responses.jsonl")
        )

# ============================================================================
# 2. DOMAIN MODELS
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
# 3. API AIRFORCE CLIENT WITH KEY ROTATION
# ============================================================================

class AirforceClient:
    def __init__(self, paths: PathConfig):
        self.paths = paths
        self.api_url = Config.API_URL
        self.api_keys = deque(Config.API_KEYS)
        self.current_key_index = 0
        self.last_request_times = {i: 0 for i in range(len(Config.API_KEYS))}
        
        self.system_prompt = self._load_file(paths.system_prompt_path)
        self.user_prompt_template = self._load_file(paths.user_prompt_path)
        self.output_schema = self._load_json(paths.schema_path)
        
        # Add function calling instruction
        self.system_prompt += """

CRITICAL INSTRUCTION:
You MUST use the 'enrich_words' function/tool to return your response. 
This is a REQUIRED structured output format. Do NOT return plain text.
Always call the enrich_words function with the complete enriched word entries data.
"""
        
    def _load_file(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f: 
                return f.read()
        except Exception as e:
            logging.error(f"Failed to load file {path}: {e}")
            return ""

    def _load_json(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load JSON {path}: {e}")
            return {}

    def _get_next_key(self) -> tuple:
        """Get next available key respecting rate limits"""
        current_time = time.time()
        
        # Try all keys
        for i in range(len(Config.API_KEYS)):
            key_index = (self.current_key_index + i) % len(Config.API_KEYS)
            time_since_last = current_time - self.last_request_times[key_index]
            
            if time_since_last >= Config.RATE_LIMIT_DELAY:
                self.current_key_index = key_index
                return Config.API_KEYS[key_index], key_index
        
        # If all keys are rate-limited, wait for the oldest one
        oldest_key = min(self.last_request_times.items(), key=lambda x: x[1])
        key_index = oldest_key[0]
        wait_time = Config.RATE_LIMIT_DELAY - (current_time - oldest_key[1])
        
        if wait_time > 0:
            logging.info(f"⏳ Rate limit: waiting {wait_time:.1f}s for key #{key_index+1}")
            time.sleep(wait_time)
        
        self.current_key_index = key_index
        return Config.API_KEYS[key_index], key_index

    def _log_response(self, request_data: dict, response_data: dict, success: bool):
        """Log API responses for debugging"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "request": {
                "model": request_data.get("model"),
                "batch_size": len(request_data.get("messages", [{}])[-1].get("content", "[]")),
            },
            "response": response_data
        }
        
        try:
            with open(self.paths.response_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.warning(f"Failed to log response: {e}")

    def _create_function_definition(self) -> Dict:
        """Convert schema to OpenAI function format"""
        return {
            "type": "function",
            "function": {
                "name": "enrich_words",
                "description": "Submit enriched word entries with complete pedagogical data",
                "parameters": self.output_schema
            }
        }

    def _extract_response(self, result: dict) -> List[Dict]:
        """Extract word entries from various response formats"""
        
        # Try tool_calls first (OpenAI function calling format)
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            
            # Check for tool_calls
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                for tool_call in tool_calls:
                    if tool_call.get("type") == "function":
                        function_data = tool_call.get("function", {})
                        if function_data.get("name") == "enrich_words":
                            arguments = function_data.get("arguments", "{}")
                            
                            if isinstance(arguments, str):
                                parsed = json.loads(arguments)
                            else:
                                parsed = arguments
                            
                            if "wordEntries" in parsed:
                                return parsed["wordEntries"]
            
            # Fallback: check content
            content = message.get("content", "")
            if content:
                try:
                    # Remove markdown code blocks if present
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    parsed = json.loads(content)
                    
                    if "wordEntries" in parsed:
                        return parsed["wordEntries"]
                    elif isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                    logging.error(f"Content: {content[:200]}...")
        
        return []

    def generate(self, batch_data: List[Dict]) -> List[Dict]:
        """Generate enriched data with key rotation"""
        user_prompt = self.user_prompt_template.replace(
            "{{BATCH_JSON}}", 
            json.dumps(batch_data, ensure_ascii=False, indent=2)
        )
        
        tools = [self._create_function_definition()]
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                # Get next available key
                api_key, key_index = self._get_next_key()
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": Config.MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "tools": tools,
                    "tool_choice": {"type": "function", "function": {"name": "enrich_words"}},
                    "temperature": Config.TEMPERATURE,
                    "max_tokens": Config.MAX_TOKENS,
                    "stream": False
                }
                
                logging.info(f"🔄 Request (Key #{key_index+1}, Attempt {attempt+1}/{Config.MAX_RETRIES})")
                
                # Mark request time BEFORE making request
                self.last_request_times[key_index] = time.time()
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Log the response
                self._log_response(payload, result, True)
                
                # Extract word entries
                word_entries = self._extract_response(result)
                
                if word_entries:
                    logging.info(f"✅ Success: {len(word_entries)} entries extracted")
                    return word_entries
                else:
                    logging.warning(f"⚠️ No word entries found in response")
                    # Log raw response for debugging
                    logging.debug(f"Raw response: {json.dumps(result, indent=2)[:500]}...")
                    
            except requests.exceptions.HTTPError as e:
                logging.error(f"❌ HTTP Error: {e}")
                if e.response.status_code == 429:
                    logging.warning(f"Rate limited on key #{key_index+1}, rotating...")
                    self.current_key_index = (key_index + 1) % len(Config.API_KEYS)
                self._log_response(payload, {"error": str(e)}, False)
                
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                self._log_response(payload if 'payload' in locals() else {}, {"error": str(e)}, False)
            
            if attempt < Config.MAX_RETRIES - 1:
                wait = Config.RETRY_DELAY * (attempt + 1)
                logging.info(f"⏳ Waiting {wait}s before retry...")
                time.sleep(wait)
        
        logging.error("❌ All retry attempts failed")
        return []

# ============================================================================
# 4. QA & CONFLICT RESOLUTION
# ============================================================================

class QARulesEngine:
    @staticmethod
    def validate(enriched: Dict) -> Dict:
        flags = []
        required = ["definitionEn", "definitionAr", "arabicAr", "phoneticUs"]
        for field in required:
            if not enriched.get(field):
                flags.append(f"missing_{field}")
        
        cefr_level = enriched.get("cefrLevel", "").upper()
        examples = enriched.get("examples", {})
        if cefr_level and cefr_level not in examples:
            flags.append("no_cefr_example")
        
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
        merged_ids = {
            "id": raw["id"],
            "wordEn": raw["wordEn"],
            "pos": raw["pos"],
            "cefrLevel": raw["cefrLevel"]
        }
        
        metadata_fields = ["category", "fromOxford", "rank", "frequency", "syllabify"]
        for k in metadata_fields:
            merged_ids[k] = raw.get(k) or enriched.get(k)
        
        diff_score = enriched.get("difficultyScore")
        if not diff_score:
            diff_score = raw.get("difficultyScore")
        merged_ids["difficultyScore"] = diff_score

        ai_fields = [
            "phoneticUs", "phoneticUk", "phoneticAr", "translit",
            "definitionEn", "definitionAr", "usageNote",
            "primarySense", "semanticTags", "register", "mnemonicAr",
            "examples", "collocations", "synonyms", "antonyms",
            "relatedWords", "wordFamily", "arabicAr",
            "frenchFr", "germanDe", "spanishEs", "chineseZh", 
            "russianRu", "portuguesePt", "japaneseJa", "italianIt", "turkishTr"
        ]
        
        for k in ai_fields:
            merged_ids[k] = enriched.get(k)

        ai_conf = float(enriched.get("aiConfidence", 0.85))
        
        return WordEntry(
            **merged_ids,
            systemMeta=SystemMeta(
                enriched=True,
                qualityStatus="enriched",
                aiConfidence=ai_conf
            )
        )

# ============================================================================
# 5. DATA INFRASTRUCTURE
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
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wordsMaster'")
            if not cursor.fetchone():
                return
            
            cursor.execute("PRAGMA table_info(wordsMaster)")
            existing = {row[1] for row in cursor.fetchall()}
            
            required = {
                "fromOxford": "INTEGER DEFAULT 0",
                "rank": "INTEGER DEFAULT 0",
                "frequency": "REAL DEFAULT 0.0",
                "phoneticUs": "TEXT", "phoneticUk": "TEXT", "phoneticAr": "TEXT", "translit": "TEXT",
                "difficultyScore": "TEXT", "syllabify": "TEXT",
                "definitionEn": "TEXT", "definitionAr": "TEXT", "usageNote": "TEXT",
                "category": "TEXT", "primarySense": "TEXT", "register": "TEXT",
                "mnemonicAr": "TEXT", 
                "semanticTags": "TEXT", "examples": "TEXT", "collocations": "TEXT",
                "synonyms": "TEXT", "antonyms": "TEXT", "relatedWords": "TEXT", "wordFamily": "TEXT",
                "frenchFr": "TEXT", "germanDe": "TEXT", "spanishEs": "TEXT", 
                "chineseZh": "TEXT", "russianRu": "TEXT", "portuguesePt": "TEXT",
                "japaneseJa": "TEXT", "italianIt": "TEXT", "turkishTr": "TEXT",
                "enriched": "INTEGER DEFAULT 0", "qualityStatus": "TEXT", 
                "aiConfidence": "REAL", "systemConfidence": "REAL", "confidenceScore": "REAL",
                "qaFlags": "TEXT", "retryCount": "INTEGER"
            }
            
            for col, dtype in required.items():
                if col not in existing:
                    logging.info(f"Adding column {col}")
                    try: 
                        cursor.execute(f"ALTER TABLE wordsMaster ADD COLUMN {col} {dtype}")
                    except: 
                        pass
            
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
        data.update(asdict(meta))
        
        json_cols = ["examples", "collocations", "synonyms", "antonyms", 
                     "relatedWords", "wordFamily", "semanticTags", "qaFlags"]
        for k in json_cols:
            if isinstance(data.get(k), (dict, list)):
                data[k] = json.dumps(data[k], ensure_ascii=False)
        
        keys = [k for k in data.keys() if k != "id"]
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        values = [data[k] for k in keys] + [data["id"]]
        
        try:
            cursor.execute(f"UPDATE wordsMaster SET {set_clause} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

# ============================================================================
# 6. MAIN PIPELINE
# ============================================================================

class Pipeline:
    def __init__(self, dry_run: bool):
        self.paths = Config.get_paths()
        self.dao = DAO(self.paths.db_path)
        self.client = AirforceClient(self.paths)
        self.dry_run = dry_run
        self.processed_ids = set()  # Track processed IDs to prevent loops
        
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

    def run(self):
        mode = "DRY RUN 🧪" if self.dry_run else "LIVE MODE 🚀"
        print(f"\n{'='*60}")
        print(f"   LEXICAL ENGINE v1.0 - API AIRFORCE EDITION")
        print(f"   Mode: {mode}")
        print(f"   Batch Size: {Config.BATCH_SIZE} word(s)")
        print(f"   API Keys: {len(Config.API_KEYS)}")
        print(f"{'='*60}\n")
        
        total_processed = 0
        batch_num = 0
        
        while True:
            batch = self.dao.fetch_batch(Config.BATCH_SIZE)
            if not batch:
                print(f"\n✅ Processing complete! Total words: {total_processed}")
                break
            
            # Check for loop (same IDs appearing again)
            batch_ids = {w['id'] for w in batch}
            if batch_ids & self.processed_ids:
                print(f"\n⚠️ LOOP DETECTED: Skipping already processed IDs: {batch_ids & self.processed_ids}")
                break
                
            batch_num += 1
            words = [w['wordEn'] for w in batch]
            print(f"\n📦 Batch #{batch_num}: {words}")
            
            # Prep input
            system_cols = {
                "enriched", "systemMeta", "qaFlags", "retryCount", 
                "aiConfidence", "systemConfidence", "qualityStatus", 
                "enrichmentVersion", "lastEnrichedAt", "confidenceScore"
            }
            
            ai_input = []
            for w in batch:
                full_record = dict(w)
                clean_seed = {
                    k: v for k, v in full_record.items() 
                    if k not in system_cols and v is not None and v != ""
                }
                ai_input.append(clean_seed)

            if self.dry_run:
                print(f"\n[DRY RUN] 📤 AI Input:")
                print(json.dumps(ai_input, indent=2, ensure_ascii=False))
                
            enriched_results = self.client.generate(ai_input)
            
            if not enriched_results:
                print("⚠️  No results from API - skipping batch")
                # Mark as processed to avoid loop
                self.processed_ids.update(batch_ids)
                continue
            
            for raw in batch:
                enriched = next((e for e in enriched_results if e.get("id") == raw["id"]), None)
                if not enriched:
                    print(f"  ⚠️  Skipped {raw['wordEn']} (AI missing)")
                    continue
                    
                qa = QARulesEngine.validate(enriched)
                final_word = ConflictResolutionEngine.merge(raw, enriched)
                
                final_word.systemMeta.systemConfidence = qa["systemConfidence"]
                final_word.systemMeta.confidenceScore = (
                    final_word.systemMeta.aiConfidence * 0.6 + 
                    qa["systemConfidence"] * 0.4
                )
                final_word.systemMeta.qaFlags = qa["flags"]
                final_word.systemMeta.qualityStatus = "passed_qa" if qa["passed"] else "failed_qa"

                if self.dry_run:
                    status_icon = "✅" if qa["passed"] else "⚠️"
                    print(f"  {status_icon} {final_word.wordEn}: Conf={final_word.systemMeta.confidenceScore:.2f} | {final_word.systemMeta.qualityStatus}")
                    if qa["flags"]:
                        print(f"     Flags: {', '.join(qa['flags'])}")
                else:
                    self.dao.save_word(final_word)
                    status_icon = "✅" if qa["passed"] else "⚠️"
                    print(f"  {status_icon} Saved: {final_word.wordEn}")
                
                total_processed += 1
                self.processed_ids.add(raw["id"])

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  LEXICAL ENRICHMENT ENGINE v1.0")
    print("  API Airforce Edition - FIXED")
    print("="*60)
    print("\nاختر الوضع / Select Mode:")
    print("  1️⃣  DRY RUN - معاينة بدون حفظ / Preview without saving")
    print("  2️⃣  LIVE - معالجة وحفظ / Process and save to database")
    print()
    
    while True:
        choice = input("اختيارك / Your choice (1 or 2): ").strip()
        if choice == "1":
            dry_run = True
            print("\n🧪 Starting in DRY RUN mode...\n")
            break
        elif choice == "2":
            dry_run = False
            confirm = input("\n⚠️  تحذير: سيتم تعديل قاعدة البيانات. متأكد؟ / WARNING: Database will be modified. Sure? (yes/no): ").strip().lower()
            if confirm in ["yes", "نعم", "y"]:
                print("\n🚀 Starting in LIVE mode...\n")
                break
            else:
                print("❌ Cancelled.")
                sys.exit(0)
        else:
            print("⚠️  اختيار خاطئ / Invalid choice. Please enter 1 or 2.")
    
    Pipeline(dry_run).run()