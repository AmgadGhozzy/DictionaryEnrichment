import sqlite3
import json
import time
import os
import shutil
import re
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai


# GOOGLE COLAB INTEGRATION

try:
    from google.colab import drive
    drive.mount('/content/drive')
    DRIVE_PATH = '/content/drive/MyDrive/'
    print("✓ Google Colab detected - Drive mounted")
except ImportError:
    DRIVE_PATH = ''
    print("✓ Running in local environment")


# CONFIGURATION

@dataclass
class Config:
    """Centralized configuration"""

    # API Keys from environment (comma-separated GEMINI_API_KEYS for rotation).
    # Set via .env / Colab secrets — never commit keys.
    api_keys: List[str] = field(default_factory=lambda: [
        k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()
    ])

    # Model: gemini-2.0-flash-exp (higher rate limits)
    model_name: str = "gemini-2.0-flash-exp"

    # Processing settings
    batch_size: int = 20
    delay_seconds: float = 18.0
    max_batches: Optional[int] = None
    max_retry_attempts: int = 2

    # Database paths
    drive_path: str = DRIVE_PATH
    words_db_path: str = field(init=False)
    output_db_path: str = field(init=False)
    backup_db_path: str = field(init=False)
    resume_state_path: str = field(init=False)

    # Request/Response Logging
    log_requests: bool = True
    log_responses: bool = True
    log_dir: str = field(init=False)

    # Features
    enable_parallel: bool = False
    validate_phonetics: bool = True
    enable_qa_checks: bool = True
    intelligent_improvement: bool = True

    # Languages
    languages: List[str] = field(default_factory=lambda: [
        'arabicAr', 'frenchFr', 'germanDe', 'spanishEs', 'chineseZh',
        'portuguesePt', 'russianRu', 'japaneseJa', 'koreanKo', 'italianIt',
        'turkishTr', 'hindiHi', 'urduUr', 'indonesianId', 'persianFa',
        'thaiTh', 'vietnameseVi', 'swahiliSw', 'malayMs', 'polishPl',
        'dutchNl', 'romanianRo', 'ukrainianUk', 'greekEl', 'hebrewHe',
        'bengaliBn', 'tamilTa'
    ])

    # Required fields for complete structured output
    required_fields: List[str] = field(default_factory=lambda: [
        'id', 'wordEn', 'definitionEn', 'cefrLevel', 'pos', 'frequency',
        'syllabify', 'phoneticUs', 'phoneticUk', 'phoneticAr', 'translit',
        'definitionAr', 'primarySense', 'usageNote', 'register', 'category',
        'wordFamily', 'synonyms', 'antonyms', 'examples', 'collocations',
        'relatedWords', 'arabicAr'
    ])

    def __post_init__(self):
        self.words_db_path = self.drive_path + "WordDictionary.db"
        self.output_db_path = self.drive_path + "WordDictionary.db"
        self.backup_db_path = self.drive_path + "WordDictionary_backup.db"
        self.resume_state_path = self.drive_path + "resume_state.json"
        self.log_dir = os.path.join(self.drive_path, "api_logs")

config = Config()


# METRICS TRACKING

@dataclass
class EnrichmentMetrics:
    """Track processing metrics"""
    total_words: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    api_calls: int = 0
    api_errors: int = 0
    validation_failures: Dict[str, int] = field(default_factory=dict)
    qa_issues: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_success(self):
        with self._lock:
            self.successful += 1
            self.processed += 1

    def record_failure(self):
        with self._lock:
            self.failed += 1
            self.processed += 1

    def record_api_call(self):
        with self._lock:
            self.api_calls += 1

    def record_api_error(self):
        with self._lock:
            self.api_errors += 1

    def record_validation_failure(self, reason: str):
        with self._lock:
            self.validation_failures[reason] = self.validation_failures.get(reason, 0) + 1

    def record_qa_issue(self, issue: str):
        with self._lock:
            self.qa_issues[issue] = self.qa_issues.get(issue, 0) + 1

    def progress_percentage(self) -> float:
        return (self.processed / self.total_words * 100) if self.total_words > 0 else 0.0

    def elapsed_time(self) -> str:
        return str(datetime.now() - self.start_time).split('.')[0]

    def print_progress(self):
        print(f"\r[{self.progress_percentage():.1f}%] {self.processed}/{self.total_words} | "
              f"✓{self.successful} ✗{self.failed} | API:{self.api_calls}({self.api_errors}err) | "
              f"Time:{self.elapsed_time()}", end='', flush=True)

    def print_summary(self):
        print(f"\n{'='*70}")
        print("ENRICHMENT SUMMARY")
        print(f"{'='*70}")
        print(f"Total Words:      {self.total_words}")
        print(f"Processed:        {self.processed} ({self.progress_percentage():.1f}%)")
        print(f"  ✓ Successful:   {self.successful}")
        print(f"  ✗ Failed:       {self.failed}")

        print(f"\nAPI Statistics:")
        print(f"  Calls:          {self.api_calls}")
        print(f"  Errors:         {self.api_errors}")
        print(f"  Success Rate:   {((self.api_calls-self.api_errors)/max(self.api_calls,1)*100):.1f}%")

        if self.validation_failures:
            print(f"\nValidation Issues: {sum(self.validation_failures.values())} total")
            for reason, count in sorted(self.validation_failures.items(), key=lambda x: -x[1])[:5]:
                print(f"  • {reason}: {count}")

        if self.qa_issues:
            print(f"\nQA Issues: {sum(self.qa_issues.values())} total")
            for issue, count in sorted(self.qa_issues.items(), key=lambda x: -x[1])[:5]:
                print(f"  • {issue}: {count}")

        print(f"\nElapsed Time:     {self.elapsed_time()}")
        print(f"{'='*70}")

metrics = EnrichmentMetrics()


# API KEY MANAGER

class APIKeyManager:
    """Manages API key rotation"""

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_index = 0
        self.key_usage = {i: 0 for i in range(len(api_keys))}
        self.key_failures = {i: 0 for i in range(len(api_keys))}
        self._lock = threading.Lock()

    def get_current_key(self) -> str:
        with self._lock:
            return self.api_keys[self.current_index]

    def get_current_index(self) -> int:
        with self._lock:
            return self.current_index

    def rotate_key(self) -> Tuple[str, int]:
        with self._lock:
            old_idx = self.current_index
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            new_key = self.api_keys[self.current_index]
            print(f"\n🔄 Rotating: Key#{old_idx+1} → Key#{self.current_index+1}")
            return new_key, self.current_index

    def record_success(self):
        with self._lock:
            self.key_usage[self.current_index] += 1

    def record_failure(self):
        with self._lock:
            self.key_failures[self.current_index] += 1

    def print_stats(self):
        print(f"\n{'='*70}")
        print("API KEY STATISTICS")
        print(f"{'='*70}")
        print(f"Total Keys: {len(self.api_keys)}")
        for i in range(len(self.api_keys)):
            usage = self.key_usage[i]
            failures = self.key_failures[i]
            success_rate = ((usage-failures)/usage*100) if usage > 0 else 0
            print(f"Key #{i+1}: {usage} requests ({failures} failures, {success_rate:.1f}% success)")
        print(f"{'='*70}")

api_key_manager = APIKeyManager(config.api_keys)


# DATABASE BACKUP

if os.path.exists(config.output_db_path):
    shutil.copy2(config.output_db_path, config.backup_db_path)
    print(f"✓ Backup created: {config.backup_db_path}")


# INITIALIZE GEMINI

genai.configure(api_key=api_key_manager.get_current_key())

SYSTEM_PROMPT = """You are a Senior Lexicographer and Pedagogical Content Designer for a premium English learning application.

CRITICAL ROLE:
Your output feeds a production database for mobile learning apps. Every field matters. Accuracy, pedagogy, and completeness are mandatory.

CORE PHILOSOPHY:
1. **Full Object Completion**: Return ALL fields for every word, even if input contains partial data
2. **definitionEn as Semantic Seed**: Use it to drive examples, translations, usageNote, primarySense
3. **Improve, Don't Discard**: Refine weak existing data; never blindly replace good content
4. **CEFR-Aligned Pedagogy**: Examples must match learner level precisely

OUTPUT REQUIREMENTS:
- Pure JSON only (no markdown, no explanations)
- Complete structured object per word
- NO null values (except syllabify)
- Use "" for empty strings, [] for empty arrays
- Preserve id and wordEn exactly as input
- phoneticAr MUST include full Arabic tashkeel

QUALITY STANDARD:
Output must feel "teaching-focused", not "dictionary-like". Assume users are seeing this in flashcards, quizzes, and pronunciation tools."""

BATCH_PROMPT_TEMPLATE = """Process {word_count} English vocabulary words with complete linguistic enrichment.

🎯 ENRICHMENT INSTRUCTIONS:

**For each word:**
1. **Use input data as semantic seed** (especially definitionEn if present)
2. **Improve clarity and pedagogy** of all fields
3. **Complete missing structures** (examples map, wordFamily, collocations)
4. **Normalize style** across all content
5. **Return FULL structured object** (all fields, no nulls except syllabify)

---

📋 INPUT WORDS:
{word_list}

---

🧾 REQUIRED OUTPUT STRUCTURE (per word):

{{
  "id": "integer (PRESERVE EXACTLY FROM INPUT)",
  "wordEn": "string (PRESERVE EXACTLY FROM INPUT)",
  
  "definitionEn": "Simple, learner-friendly English definition (improve if weak)",
  
  "cefrLevel": "A1|A2|B1|B2|C1|C2",
  "pos": "noun|verb|adj|adv|prep|conj|det|pron",
  "frequency": "integer 1-6 (1=most common)",
  
  "syllabify": "hy-phen-at-ed string OR null",
  "phoneticUs": "/IPA with slashes/",
  "phoneticUk": "/IPA with slashes/",
  "phoneticAr": "Arabic pronunciation WITH full tashkeel (مَثَلٌ)",
  "translit": "Arabic meaning romanized",
  
  "definitionAr": "Conceptual Arabic explanation (not literal translation)",
  
  "primarySense": "ONE semantic domain (e.g., 'Communication', 'Movement')",
  "usageNote": "Practical learner advice (when/how to use)",
  "register": "Formal|Informal|Neutral",
  "category": "Topic label (e.g., 'Business', 'Daily Life')",
  
  "wordFamily": {{
    "noun": "form or empty string",
    "verb": "form or empty string",
    "adj": "form or empty string",
    "adv": "form or empty string"
  }},
  
  "synonyms": ["max 3 common synonyms"],
  "antonyms": ["max 2 clear antonyms"],
  
  "examples": {{
    "A1": "Simple present/common structure",
    "A2": "Near future/basic past",
    "B1": "Conditionals/comparatives",
    "B2": "Complex sentences/formal tone",
    "C1": "Nuanced usage/idiomatic",
    "C2": "Academic/sophisticated context"
  }},
  
  "collocations": [
    "verb + noun",
    "adj + noun", 
    "prepositional phrase"
  ],
  
  "relatedWords": {{
    "en": ["related English terms"],
    "ar": ["مصطلحات عربية مرتبطة"]
  }},
  
  "arabicAr": "Primary Arabic translation",
  
  "frenchFr": "French translation",
  "germanDe": "German translation", 
  "spanishEs": "Spanish translation",
  "chineseZh": "Chinese translation (simplified + pinyin)",
  "russianRu": "Russian translation",
  "portuguesePt": "Portuguese translation",
  "japaneseJa": "Japanese translation (kanji + romaji)",
  "italianIt": "Italian translation",
  "turkishTr": "Turkish translation",
  "hindiHi": "Hindi translation (Devanagari + romanization)",
  "urduUr": "Urdu translation",
  "indonesianId": "Indonesian translation",
  "persianFa": "Persian translation",
  "thaiTh": "Thai translation",
  "vietnameseVi": "Vietnamese translation",
  "swahiliSw": "Swahili translation",
  "malayMs": "Malay translation",
  "polishPl": "Polish translation",
  "dutchNl": "Dutch translation",
  "romanianRo": "Romanian translation",
  "ukrainianUk": "Ukrainian translation",
  "greekEl": "Greek translation",
  "hebrewHe": "Hebrew translation",
  "bengaliBn": "Bengali translation",
  "tamilTa": "Tamil translation",
  "koreanKo": "Korean translation (Hangul + romanization)"
}}

---

🚫 CRITICAL CONSTRAINTS:

1. **NO missing fields** (every field must exist)
2. **NO null values** (except syllabify)
3. **phoneticAr MUST be pure Arabic script with tashkeel**
4. **examples MUST be CEFR-appropriate and natural**
5. **Preserve id and wordEn exactly**
6. **definitionEn drives semantic consistency**
7. **Output pure JSON array only** (no markdown, no preamble)

---

🎯 QUALITY CHECKLIST (apply to each word):
✓ definitionEn is learner-friendly and clear
✓ Examples progress naturally from A1→C2
✓ phoneticAr includes full vowel marks
✓ usageNote provides practical learning value
✓ Translations are natural, not literal
✓ wordFamily includes only real forms
✓ No hallucinated rare synonyms

---

**OUTPUT FORMAT:**
[
  {{ complete word 1 object }},
  {{ complete word 2 object }},
  ...
]
"""

GENERATION_CONFIG = genai.GenerationConfig(
    response_mime_type="application/json",
    temperature=0.1,
    top_p=0.9,
    top_k=50,
    max_output_tokens=100000
)

try:
    model = genai.GenerativeModel(
        config.model_name,
        system_instruction=SYSTEM_PROMPT,
        generation_config=GENERATION_CONFIG
    )
    print(f"✓ Model initialized: {config.model_name}")
    print(f"✓ API keys: {len(config.api_keys)} configured")
    print(f"✓ Current key: #{api_key_manager.get_current_index() + 1}")
except Exception as e:
    print(f"❌ Model initialization failed: {e}")
    exit(1)


# VALIDATION

def is_strictly_arabic_script(text: str) -> bool:
    """Validate Arabic script (no Latin characters)"""
    if not isinstance(text, str) or not text.strip():
        return False

    text = text.strip()
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))

    return arabic_chars > 0 and latin_chars == 0

def validate_structured_output(word_data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate structured output compliance.
    Returns (is_valid, issues_list)
    """
    issues = []
    
    # Critical: id and wordEn must be preserved
    if word_data.get('id') is None:
        issues.append("CRITICAL: Missing id")
        return False, issues
    
    if not word_data.get('wordEn'):
        issues.append("CRITICAL: Missing wordEn")
        return False, issues
    
    # Check required fields exist
    for field in config.required_fields:
        if field not in word_data:
            issues.append(f"Missing field: {field}")
    
    # Validate examples structure (must be CEFR map, not array)
    examples = word_data.get('examples')
    if not isinstance(examples, dict):
        issues.append("examples must be CEFR map object, not array")
    else:
        required_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        for level in required_levels:
            if level not in examples:
                issues.append(f"examples missing level: {level}")
            elif not examples[level] or not isinstance(examples[level], str):
                issues.append(f"examples[{level}] is empty or invalid")
    
    # Validate wordFamily structure
    word_family = word_data.get('wordFamily')
    if not isinstance(word_family, dict):
        issues.append("wordFamily must be object")
    else:
        for pos_key in ['noun', 'verb', 'adj', 'adv']:
            if pos_key not in word_family:
                issues.append(f"wordFamily missing: {pos_key}")
    
    # Validate relatedWords structure
    related = word_data.get('relatedWords')
    if not isinstance(related, dict):
        issues.append("relatedWords must be object")
    else:
        if 'en' not in related or 'ar' not in related:
            issues.append("relatedWords must have 'en' and 'ar' keys")
    
    # Validate phonetic formats
    for field in ['phoneticUs', 'phoneticUk']:
        value = word_data.get(field, '')
        if value and not re.match(r'^/.*/$', str(value)):
            issues.append(f"{field} must have IPA slashes")
    
    # Validate phoneticAr (must be Arabic script with tashkeel)
    phonetic_ar = word_data.get('phoneticAr', '')
    if not phonetic_ar:
        issues.append("phoneticAr is required")
    elif not is_strictly_arabic_script(phonetic_ar):
        issues.append("phoneticAr must be pure Arabic script")
    
    # Validate definitionEn exists and is substantial
    def_en = word_data.get('definitionEn', '')
    if not def_en or len(def_en.strip()) < 10:
        issues.append("definitionEn must be substantial (10+ chars)")
    
    # Record issues
    for issue in issues:
        metrics.record_validation_failure(issue)
    
    return len(issues) == 0, issues


# RESUME STATE MANAGEMENT

def save_resume_state(current_index: int, total_words: int, processed_count: int):
    """Save current progress for resume capability"""
    state = {
        'current_index': current_index,
        'total_words': total_words,
        'processed_count': processed_count,
        'timestamp': time.time()
    }
    try:
        with open(config.resume_state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"  💾 Progress saved (Word {current_index}/{total_words})")
    except Exception as e:
        print(f"  ⚠ Could not save progress: {e}")

def load_resume_state() -> Optional[Dict]:
    """Load saved progress state"""
    if os.path.exists(config.resume_state_path):
        try:
            with open(config.resume_state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            ts = state.get('timestamp', 0)
            if isinstance(ts, (int, float)):
                ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = str(ts)
            print(f"✓ Found saved progress from {ts_str}")
            return state
        except Exception as e:
            print(f"⚠ Could not load progress: {e}")
            return None
    return None

def clear_resume_state():
    """Clear resume state file"""
    if os.path.exists(config.resume_state_path):
        try:
            os.remove(config.resume_state_path)
            print("✓ Resume state cleared")
        except:
            pass


# DATABASE OPERATIONS

def load_words_from_db():
    """Load words from database"""
    if not os.path.exists(config.words_db_path):
        print(f"❌ Database not found: {config.words_db_path}")
        return []

    try:
        conn = sqlite3.connect(config.words_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM words ORDER BY rank")
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        words = [dict(zip(columns, row)) for row in rows]
        
        # Parse JSON fields
        for word in words:
            for field in ['terms', 'synonyms', 'antonyms', 'examples']:
                if word.get(field):
                    try:
                        word[field] = json.loads(word[field])
                    except:
                        pass
        
        print(f"✓ Loaded {len(words)} words from database")
        return words
    except Exception as e:
        print(f"❌ Error loading words: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_words_needing_enrichment():
    """Find words needing enrichment (all words for full object regeneration)"""
    source_words = load_words_from_db()
    if not source_words:
        return []
    
    print(f"✓ All {len(source_words)} words will be enriched (full object mode)")
    return source_words


# INPUT FORMATTER - SEMANTIC SEED APPROACH

def format_word_for_prompt(word_data: Dict) -> Dict:
    """
    Format word for API prompt.
    Preserves existing data as semantic seeds for improvement.
    """
    # Start with basic identity fields
    formatted = {
        'id': word_data.get('id'),
        'wordEn': word_data.get('englishEn') or word_data.get('wordEn'),
    }
    
    # Seed with existing definitionEn if available (CRITICAL SEMANTIC ANCHOR)
    if word_data.get('definition'):
        formatted['definitionEn_seed'] = word_data['definition']
    elif word_data.get('definitionEn'):
        formatted['definitionEn_seed'] = word_data['definitionEn']
    
    # Seed with existing examples (convert array to map if needed)
    existing_examples = word_data.get('examples', [])
    if isinstance(existing_examples, list) and len(existing_examples) == 6:
        # Convert old array format to new CEFR map
        levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        formatted['examples_seed'] = {
            levels[i]: existing_examples[i].replace(f"{levels[i]}: ", "").strip()
            for i in range(6)
        }
    elif isinstance(existing_examples, dict):
        formatted['examples_seed'] = existing_examples
    
    # Seed with existing translations
    formatted['arabicAr_seed'] = word_data.get('arabicAr', '')
    formatted['definitionAr_seed'] = word_data.get('definitionAr', '')
    
    # Seed with existing phonetics
    formatted['phoneticUs_seed'] = word_data.get('phoneticUS', '')
    formatted['phoneticUk_seed'] = word_data.get('phoneticUK', '')
    formatted['phoneticAr_seed'] = word_data.get('phoneticAR') or word_data.get('phoneticAr', '')
    
    # Seed with level
    formatted['cefrLevel_seed'] = word_data.get('level', '')
    
    # Include all other existing data as reference
    formatted['existing_data'] = {
        k: v for k, v in word_data.items()
        if v and k not in ['id', 'englishEn', 'wordEn']
    }
    
    return formatted


# RESPONSE PARSER - STRUCTURED OUTPUT

def parse_structured_response(response_text: str, batch_id: int) -> Optional[List[Dict]]:
    """
    Parse structured output response.
    With structured outputs, response should be clean JSON.
    """
    try:
        # Remove markdown fences if present (API sometimes adds them)
        clean_text = response_text.strip()
        if clean_text.startswith('```json'):
            json_match = re.search(r'```json\s*(.+?)\s*```', clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
        elif clean_text.startswith('```'):
            clean_text = re.sub(r'^```[a-z]*\s*|\s*```$', '', clean_text, flags=re.MULTILINE)
        
        # Parse JSON
        parsed = json.loads(clean_text)
        
        # Normalize to list
        if isinstance(parsed, dict):
            # Single word or wrapper object
            if 'words' in parsed:
                words = parsed['words']
            else:
                words = [parsed]
        elif isinstance(parsed, list):
            words = parsed
        else:
            raise ValueError(f"Unexpected structure type: {type(parsed)}")
        
        # Validate each word
        validated_words = []
        for idx, word_data in enumerate(words):
            is_valid, issues = validate_structured_output(word_data)
            
            if not is_valid:
                word = word_data.get('wordEn', f'word_{idx}')
                print(f"  ⚠️ Validation failed for '{word}':")
                for issue in issues[:3]:  # Show first 3 issues
                    print(f"     - {issue}")
                if len(issues) > 3:
                    print(f"     ... and {len(issues)-3} more issues")
                # Still include it for attempted save (DB layer will handle)
            
            validated_words.append(word_data)
        
        return validated_words
        
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        print(f"  Response preview: {response_text[:200]}...")
        return None
    except Exception as e:
        print(f"  ❌ Parse error: {e}")
        return None


# INTELLIGENT IMPROVEMENT LOGIC

def should_improve_field(field_name: str, old_value, new_value) -> bool:
    """
    Decide if new value is better than old value.
    Returns True if new value should replace old.
    """
    # Always preserve id and wordEn
    if field_name in ['id', 'wordEn', 'englishEn']:
        return False
    
    # If old is empty, always use new
    if not old_value or (isinstance(old_value, str) and not old_value.strip()):
        return True
    
    # If new is empty, keep old
    if not new_value or (isinstance(new_value, str) and not new_value.strip()):
        return False
    
    # Special logic for definitionEn: prefer longer, clearer version
    if field_name in ['definition', 'definitionEn']:
        old_len = len(str(old_value))
        new_len = len(str(new_value))
        # If new is substantially longer and substantial, prefer it
        if new_len > old_len * 1.3 and new_len > 20:
            return True
        # If old is very short, prefer new
        if old_len < 15 and new_len > 20:
            return True
        # Otherwise keep old (avoid degrading good definitions)
        return False
    
    # For phoneticAr: prefer one with tashkeel
    if field_name in ['phoneticAR', 'phoneticAr']:
        old_has_tashkeel = bool(re.search(r'[\u064B-\u0652]', str(old_value)))
        new_has_tashkeel = bool(re.search(r'[\u064B-\u0652]', str(new_value)))
        if new_has_tashkeel and not old_has_tashkeel:
            return True
        if old_has_tashkeel and not new_has_tashkeel:
            return False
        # Both have or don't have tashkeel: prefer valid Arabic
        if is_strictly_arabic_script(new_value) and not is_strictly_arabic_script(old_value):
            return True
        return False
    
    # For arrays: prefer longer (more complete)
    if isinstance(old_value, list) and isinstance(new_value, list):
        return len(new_value) > len(old_value)
    
    # For objects: prefer new if more complete
    if isinstance(old_value, dict) and isinstance(new_value, dict):
        old_keys = set(k for k, v in old_value.items() if v)
        new_keys = set(k for k, v in new_value.items() if v)
        return len(new_keys) > len(old_keys)
    
    # Default: prefer new (improvement mode)
    return True

def merge_with_intelligent_improvement(old_data: Dict, new_data: Dict) -> Dict:
    """
    Merge old and new data, keeping better values.
    """
    merged = new_data.copy()
    
    # Always preserve id and wordEn from old
    merged['id'] = old_data.get('id')
    merged['englishEn'] = old_data.get('englishEn') or old_data.get('wordEn')
    
    if not config.intelligent_improvement:
        return merged
    
    # For each field, decide which version to keep
    for field in old_data.keys():
        if field in ['id', 'englishEn', 'wordEn']:
            continue
        
        old_val = old_data.get(field)
        new_val = new_data.get(field)
        
        if not should_improve_field(field, old_val, new_val):
            merged[field] = old_val
    
    return merged


# DATABASE SCHEMA MAPPER

def map_to_database_schema(word_data: Dict) -> Dict:
    """
    Map structured output fields to database schema.
    Handles field name changes and structure conversions.
    """
    mapped = {}
    
    # Direct mappings
    mapped['id'] = word_data.get('id')
    mapped['englishEn'] = word_data.get('wordEn')  # Map back for DB compatibility
    mapped['arabicAr'] = word_data.get('arabicAr', '')
    mapped['level'] = word_data.get('cefrLevel', '')
    
    # Phonetics (note case sensitivity)
    mapped['phoneticUS'] = word_data.get('phoneticUs', '')
    mapped['phoneticUK'] = word_data.get('phoneticUk', '')
    mapped['phoneticAR'] = word_data.get('phoneticAr', '')  # DB uses uppercase
    mapped['translit'] = word_data.get('translit', '')
    mapped['srcTranslit'] = word_data.get('srcTranslit', '')
    
    # Core linguistic fields
    mapped['syllabify'] = word_data.get('syllabify')  # Can be null
    mapped['pos'] = word_data.get('pos', '')
    mapped['definition'] = word_data.get('definitionEn', '')  # Map to old field name
    mapped['category'] = word_data.get('category', '')
    mapped['register'] = word_data.get('register', '')
    mapped['frequency'] = word_data.get('frequency', '')
    
    # Convert examples map back to array for DB compatibility
    examples_map = word_data.get('examples', {})
    if isinstance(examples_map, dict):
        levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        mapped['examples'] = [
            f"{level}: {examples_map.get(level, '')}" 
            for level in levels
        ]
    else:
        mapped['examples'] = examples_map  # Fallback
    
    # Convert relatedWords back to terms for DB compatibility
    related_words = word_data.get('relatedWords', {})
    if isinstance(related_words, dict):
        mapped['terms'] = related_words
    else:
        mapped['terms'] = {"en": [], "ar": []}
    
    # Simple arrays
    mapped['synonyms'] = word_data.get('synonyms', [])
    mapped['antonyms'] = word_data.get('antonyms', [])
    
    # All 27 language translations
    for lang in config.languages:
        mapped[lang] = word_data.get(lang, '')
    
    # Preserve metadata
    mapped['fromOxford'] = word_data.get('fromOxford', 0)
    mapped['rank'] = word_data.get('rank', 0)
    
    return mapped


# DATABASE SAVE WITH INTELLIGENT IMPROVEMENT

def save_words_to_db_bulk(enriched_words: List[Dict]) -> Tuple[int, int]:
    """
    Save words with intelligent improvement logic.
    """
    if not enriched_words:
        return 0, 0
    
    saved_count = 0
    error_count = 0
    conn = None
    
    print(f"\nSaving {len(enriched_words)} words...")
    
    try:
        conn = sqlite3.connect(config.output_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        cursor.execute("PRAGMA table_info(words)")
        db_columns = [col[1] for col in cursor.fetchall()]
        update_columns = [col for col in db_columns if col != 'id']
        
        placeholders = ', '.join([f'"{col}" = ?' for col in update_columns])
        update_sql = f"UPDATE words SET {placeholders} WHERE id = ?"
        
        bulk_data = []
        
        for word_data in enriched_words:
            word_id = word_data.get('id')
            word = word_data.get('wordEn') or word_data.get('englishEn', 'unknown')
            
            if word_id is None:
                print(f"  ❌ Skipping '{word}': Missing ID")
                error_count += 1
                continue
            
            try:
                # Get existing data
                cursor.execute("SELECT * FROM words WHERE id = ?", (word_id,))
                existing = cursor.fetchone()
                if not existing:
                    print(f"  ❌ ID {word_id} not in database")
                    error_count += 1
                    continue
                
                existing_dict = dict(existing)
                
                # Parse JSON fields from DB
                for field in ['terms', 'synonyms', 'antonyms', 'examples']:
                    if existing_dict.get(field):
                        try:
                            existing_dict[field] = json.loads(existing_dict[field])
                        except:
                            pass
                
                # Map structured output to DB schema
                mapped_new = map_to_database_schema(word_data)
                
                # Intelligent merge
                final_data = merge_with_intelligent_improvement(existing_dict, mapped_new)
                
                # Prepare values for update
                values = []
                for col in update_columns:
                    value = final_data.get(col)
                    
                    # Serialize JSON fields
                    if col == 'terms' and isinstance(value, dict):
                        values.append(json.dumps(value, ensure_ascii=False))
                    elif col in ['synonyms', 'antonyms', 'examples'] and isinstance(value, list):
                        values.append(json.dumps(value, ensure_ascii=False))
                    elif isinstance(value, bool):
                        values.append(int(value))
                    elif value is None:
                        if col in ['synonyms', 'antonyms', 'examples']:
                            values.append(json.dumps([], ensure_ascii=False))
                        elif col == 'terms':
                            values.append(json.dumps({"en": [], "ar": []}, ensure_ascii=False))
                        elif col == 'syllabify':
                            values.append(None)
                        else:
                            values.append("")
                    else:
                        values.append(str(value) if value is not None else "")
                
                values.append(word_id)
                bulk_data.append(values)
                
            except Exception as e:
                print(f"  ❌ Error preparing '{word}': {str(e)[:100]}")
                error_count += 1
        
        # Bulk execute
        if bulk_data:
            cursor.executemany(update_sql, bulk_data)
            saved_count = cursor.rowcount
            print(f"✅ Updated {saved_count} records")
        
        conn.commit()
        
        for _ in range(saved_count):
            metrics.record_success()
        for _ in range(error_count):
            metrics.record_failure()
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Transaction failed: {str(e)[:150]}")
        error_count = len(enriched_words)
        for _ in range(error_count):
            metrics.record_failure()
    finally:
        if conn:
            conn.close()
    
    return saved_count, error_count


# API PROCESSING

def process_batch_with_retry(chat_session, batch_prompt, batch_id, max_retries=None):
    """Process batch with smart retry and key rotation"""
    if max_retries is None:
        max_retries = config.max_retry_attempts

    retry_count = 0
    key_rotated = False

    # Create log directory if it doesn't exist
    if (config.log_requests or config.log_responses) and not os.path.exists(config.log_dir):
        os.makedirs(config.log_dir, exist_ok=True)

    while retry_count <= max_retries:
        try:
            metrics.record_api_call()
            api_key_manager.record_success()

            print(f"  📤 Sending to API (Key#{api_key_manager.get_current_index()+1})...")

            # Save request to file
            if config.log_requests:
                request_filename = os.path.join(config.log_dir, f"request_batch_{batch_id}_try_{retry_count}.json")
                with open(request_filename, 'w', encoding='utf-8') as f:
                    f.write(batch_prompt)
                print(f"  💾 Request saved to {request_filename.split('/')[-1]}")

            # Send request with timeout
            response = chat_session.send_message(batch_prompt, request_options={"timeout": 600})
            response_text = response.text
            print(f"  ✓ Response received ({len(response_text)} chars)")

            # Save response to file
            if config.log_responses:
                response_filename = os.path.join(config.log_dir, f"response_batch_{batch_id}_try_{retry_count}.json")
                with open(response_filename, 'w', encoding='utf-8') as f:
                    f.write(response_text)
                print(f"  💾 Response saved to {response_filename.split('/')[-1]}")

            # Parse structured response
            words = parse_structured_response(response_text, batch_id)
            
            if words:
                print(f"  ✓ Parsed {len(words)} words")
                return words
            else:
                print(f"  ❌ Parse failed")
                retry_count += 1
                if retry_count <= max_retries:
                    time.sleep(10 * retry_count)
                continue

        except Exception as e:
            metrics.record_api_error()
            api_key_manager.record_failure()
            error_msg = str(e)

            # Rate limit - rotate key
            if '429' in error_msg or 'rate limit' in error_msg.lower() or 'quota' in error_msg.lower():
                if 'limit: 0' in error_msg:
                    print(f"  🚨 Quota exhausted on Key#{api_key_manager.get_current_index()+1}")

                    if not key_rotated and len(config.api_keys) > 1:
                        new_key, new_idx = api_key_manager.rotate_key()
                        try:
                            genai.configure(api_key=new_key)
                            global model
                            model = genai.GenerativeModel(config.model_name, system_instruction=SYSTEM_PROMPT, generation_config=GENERATION_CONFIG)
                            chat_session = model.start_chat(history=[])
                            key_rotated = True
                            retry_count += 1
                            print(f"  ✓ Rotated to Key#{new_idx+1}, retrying...")
                            time.sleep(5)
                            continue
                        except Exception as rotate_error:
                            print(f"  ❌ Rotation failed: {rotate_error}")

                    if key_rotated or len(config.api_keys) == 1:
                        print("\n🔴 ALL KEYS EXHAUSTED")
                        api_key_manager.print_stats()
                        return None

                else:
                    print(f"  🚦 Rate limit hit (likely IP-based)")

                    if not key_rotated and len(config.api_keys) > 1:
                        new_key, new_idx = api_key_manager.rotate_key()
                        try:
                            genai.configure(api_key=new_key)
                            model = genai.GenerativeModel(config.model_name, system_instruction=SYSTEM_PROMPT, generation_config=GENERATION_CONFIG)
                            chat_session = model.start_chat(history=[])
                            key_rotated = True
                        except:
                            pass

                    retry_count += 1
                    if retry_count <= max_retries:
                        wait = 25
                        print(f"  ⏳ Waiting {wait}s for IP rate limit reset...")
                        time.sleep(wait)

            # Timeout
            elif 'timeout' in error_msg.lower():
                print(f"  ⏰ Timeout")
                retry_count += 1
                if retry_count <= max_retries:
                    wait = 10 * (2 ** retry_count)
                    print(f"  ⏳ Backoff {wait}s...")
                    time.sleep(wait)

            # Other errors
            else:
                print(f"  ❌ Error: {e}")
                retry_count += 1
                if retry_count <= max_retries:
                    time.sleep(10 * retry_count)

    print(f"❌ Failed after {max_retries+1} attempts")
    return None

def process_batches_sequential(words_to_process: List[Dict], start_index: int = 0):
    """Process batches sequentially with resume capability"""
    batches = []
    for i in range(0, len(words_to_process), config.batch_size):
        if config.max_batches and len(batches) >= config.max_batches:
            break
        batches.append((words_to_process[i:i+config.batch_size], start_index + i, len(batches)+1))

    total = len(batches)
    print(f"\nProcessing {total} batches sequentially")
    print(f"Expected time: ~{total*0.5:.0f} minutes\n")

    try:
        chat_session = model.start_chat(history=[])

        for batch_data, batch_idx, batch_num in batches:
            print(f"\n{'='*70}")
            print(f"Batch {batch_num}/{total} (Words {batch_idx}-{batch_idx+len(batch_data)-1})")
            print(f"{'='*70}")

            # Format prompt
            formatted = [format_word_for_prompt(w) for w in batch_data]
            word_list = json.dumps(formatted, indent=2, ensure_ascii=False)
            prompt = BATCH_PROMPT_TEMPLATE.format(word_count=len(batch_data), word_list=word_list)

            # Process
            enriched = process_batch_with_retry(chat_session, prompt, batch_num)

            if enriched:
                saved, errors = save_words_to_db_bulk(enriched)
                print(f"✅ Batch {batch_num} complete: {saved} saved, {errors} errors")

                # Save progress after successful batch
                next_idx = batch_idx + len(batch_data)
                save_resume_state(next_idx, start_index + len(words_to_process), metrics.successful)
            else:
                print(f"✗ Batch {batch_num} failed")
                for _ in batch_data:
                    metrics.record_failure()

            metrics.print_progress()

            # Delay between batches
            if batch_num < total:
                print(f"\n⏳ Waiting {config.delay_seconds}s...")
                time.sleep(config.delay_seconds)

    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        print(f"💾 Progress saved. Resume by running script again.")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        metrics.print_summary()
        api_key_manager.print_stats()


# MAIN EXECUTION

def run_enrichment():
    """Main enrichment function with resume capability"""
    start_time = datetime.now()

    if not os.path.exists(config.words_db_path):
        print(f"❌ Database not found: {config.words_db_path}")
        return

    words_to_enrich = get_words_needing_enrichment()
    if not words_to_enrich:
        print("✓ No words to enrich!")
        clear_resume_state()
        return

    # Check for resume state (Automatic resume)
    resume_state = load_resume_state()
    start_index = 0
    total_processed_so_far = 0

    if resume_state:
        resumed_index = resume_state.get('current_index', 0)
        total_processed_so_far = resume_state.get('processed_count', 0)

        if resumed_index > 0 and resumed_index < len(words_to_enrich):
            start_index = resumed_index
            words_to_enrich = words_to_enrich[start_index:]
            metrics.successful = total_processed_so_far
            print(f"✓ Resuming automatically from word {start_index} (Already processed {total_processed_so_far})")
        else:
            clear_resume_state()

    metrics.total_words = len(words_to_enrich)
    metrics.start_time = start_time

    print(f"\n{'='*70}")
    print("STRUCTURED OUTPUT ENRICHMENT")
    print(f"{'='*70}")
    print(f"Model:        {config.model_name}")
    print(f"Mode:         Full Object Regeneration")
    print(f"Words:        {len(words_to_enrich)} (starting from word {start_index})")
    print(f"Batch size:   {config.batch_size}")
    print(f"Delay:        {config.delay_seconds}s")
    print(f"API keys:     {len(config.api_keys)}")
    print(f"Max batches:  {config.max_batches or 'Unlimited'}")
    print(f"Improvement:  {'Enabled' if config.intelligent_improvement else 'Disabled'}")
    if config.log_requests or config.log_responses:
        print(f"API Logs:     {config.log_dir}")
    print(f"{'='*70}\n")

    try:
        process_batches_sequential(words_to_enrich, start_index)
        clear_resume_state()
        print("\n🎉 Enrichment completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠ Process interrupted")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        metrics.print_summary()
        api_key_manager.print_stats()

if __name__ == "__main__":
    run_enrichment()
