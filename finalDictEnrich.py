import os
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import google.generativeai as genai # Corrected import from google.genai
from dataclasses import dataclass, asdict
import logging
from collections import deque

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PipelineConfig:
    """Central configuration for the enrichment pipeline"""

    # File paths
    system_prompt_path: str = "/content/drive/MyDrive/SystemPrompt.md"
    batch_prompt_path: str = "/content/drive/MyDrive/BatchUserPrompt.md"
    structured_output_path: str = "/content/drive/MyDrive/StructuredOutput.json"

    # Database
    db_path: str = "/content/drive/MyDrive/WordsMaster.db"
    backup_prefix: str = "backup"

    # Batch processing
    batch_size: int = 10  # Words per batch
    max_batches: Optional[int] = 1  # None = process all

    # API configuration
    model_name: str = "gemini-3-pro-preview" # Aligned with first cell's model name
    max_output_tokens: int = 81920
    temperature: float = 0.7

    # Retry logic
    max_retries: int = 3
    retry_delay: int = 5  # seconds

    # Logging
    log_dir: str = "/content/drive/MyDrive/logs"
    metrics_dir: str = "/content/drive/MyDrive/metrics"


# ============================================================================
# API KEY MANAGER
# ============================================================================

class APIKeyManager:
    """Manages API key rotation with rate limit handling"""

    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("At least one API key is required")
        self.keys = deque(api_keys)
        self.current_key = self.keys[0]
        self.key_usage = {key: 0 for key in api_keys}
        self.key_errors = {key: 0 for key in api_keys}

    def get_current_key(self) -> str:
        """Get the current active API key"""
        return self.current_key

    def rotate_key(self):
        """Rotate to the next API key"""
        self.keys.rotate(-1)
        self.current_key = self.keys[0]
        logging.info(f"Rotated to API key: {self.current_key[:8]}...")

    def mark_success(self):
        """Mark successful API call"""
        self.key_usage[self.current_key] += 1

    def mark_error(self):
        """Mark failed API call"""
        self.key_errors[self.current_key] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_calls": sum(self.key_usage.values()),
            "total_errors": sum(self.key_errors.values()),
            "keys": [{
                "key": key[:8] + "...",
                "calls": self.key_usage[key],
                "errors": self.key_errors[key]
            } for key in self.keys]
        }


# ============================================================================
# GEMINI CLIENT
# ============================================================================

class GeminiEnrichmentClient:
    """Enhanced Gemini client with structured output support"""

    def __init__(self, config: PipelineConfig, api_key_manager: APIKeyManager):
        self.config = config
        self.key_manager = api_key_manager
        self.system_prompt = self._load_file(config.system_prompt_path)
        self.batch_prompt_template = self._load_file(config.batch_prompt_path)
        self.output_schema = self._load_json(config.structured_output_path)
        self.model = None
        self._initialize_model()

    def _load_file(self, path: str) -> str:
        """Load text file content"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_json(self, path: str) -> Dict:
        """Load JSON schema"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _initialize_model(self):
        """Initialize the Gemini model with current API key"""
        genai.configure(api_key=self.key_manager.get_current_key())

        generation_config = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": self.output_schema
        }

        self.model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config=generation_config,
            system_instruction=self.system_prompt
        )

        logging.info(f"Initialized model: {self.config.model_name}")

    def enrich_batch(self, batch: List[Dict]) -> Optional[Dict]:
        """Enrich a batch of words with retry logic"""

        # Prepare minimal input (preserving required fields)
        minimal_batch = []
        for word in batch:
            minimal_batch.append({
                "id": word["id"],
                "wordEn": word["wordEn"],
                "pos": word["pos"],
                "rank": word.get("rank", 0),
                "cefrLevel": word["cefrLevel"],
                "arabicAr": word["arabicAr"]
            })

        # Create user prompt
        user_prompt = self.batch_prompt_template.replace(
            "[BATCH_PLACEHOLDER]",
            json.dumps(minimal_batch, ensure_ascii=False, indent=2)
        )

        # Retry loop
        for attempt in range(self.config.max_retries):
            try:
                logging.info(f"Attempt {attempt + 1}/{self.config.max_retries} for batch")

                response = self.model.generate_content(user_prompt)
                result = json.loads(response.text)

                self.key_manager.mark_success()
                return result

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                self.key_manager.mark_error()

                if attempt < self.config.max_retries - 1:
                    # Rotate key and retry
                    self.key_manager.rotate_key()
                    self._initialize_model()
                    time.sleep(self.config.retry_delay)
                else:
                    logging.error(f"All retries exhausted for batch")
                    return None

        return None


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Handles all database operations with intelligent merging"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def backup_database(self, backup_id: str):
        """Create a backup of the database"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_{backup_id}_{timestamp}.db"

        backup_conn = sqlite3.connect(backup_path)
        self.conn.backup(backup_conn)
        backup_conn.close()

        logging.info(f"Database backed up to: {backup_path}")
        return backup_path

    def get_words_batch(self, offset: int, limit: int) -> List[Dict]:
        """Fetch a batch of words from the database"""
        cursor = self.conn.cursor()

        query = """
            SELECT * FROM wordsMaster
            ORDER BY id
            LIMIT ? OFFSET ?
        """

        cursor.execute(query, (limit, offset))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_total_words(self) -> int:
        """Get total word count"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wordsMaster")
        return cursor.fetchone()[0]

    def save_enriched_words(self, enriched_words: List[Dict]):
        """Save enriched words with intelligent merging"""
        cursor = self.conn.cursor()

        for word in enriched_words:
            word_id = word["id"]

            # Fetch existing data
            cursor.execute("SELECT * FROM wordsMaster WHERE id = ?", (word_id,))
            existing = dict(cursor.fetchone() or {})

            if not existing:
                logging.warning(f"Word ID {word_id} not found in database")
                continue

            # Merge data intelligently
            merged = self._merge_word_data(existing, word)

            # Update database
            self._update_word(cursor, merged)

        self.conn.commit()
        logging.info(f"Saved {len(enriched_words)} enriched words")

    def _merge_word_data(self, old: Dict, new: Dict) -> Dict:
        """
        Intelligent merging logic:
        - Preserve immutable fields from old
        - If old is empty/null, use new
        - If new is empty/null, keep old
        - Improve weak data, don't discard good content
        """

        # Immutable fields (never change)
        immutable = ["id", "wordEn", "pos", "cefrLevel", "fromOxford",
                     "rank", "frequency", "category", "syllabify"]

        # Required fields (must have values)
        required = ["phoneticUs", "phoneticAr", "translit", "definitionEn",
                    "definitionAr", "usageNote", "primarySense", "semanticTags",
                    "mnemonicAr", "examples", "arabicAr"]

        merged = {}

        for key in old.keys():
            old_val = old.get(key)
            new_val = new.get(key)

            # Preserve immutable fields
            if key in immutable:
                merged[key] = old_val
                continue

            # For required fields
            if key in required:
                # If old is empty/null, use new
                if self._is_empty(old_val):
                    merged[key] = new_val
                # If new is empty/null, keep old
                elif self._is_empty(new_val):
                    merged[key] = new_val
                # Both have values - use new (improvement)
                else:
                    merged[key] = new_val

            # For optional fields
            else:
                # Prefer non-empty values
                if not self._is_empty(new_val):
                    merged[key] = new_val
                else:
                    merged[key] = new_val

        # Add any new fields from enrichment
        for key in new.keys():
            if key not in merged:
                merged[key] = new.get(key)

        return merged

    def _is_empty(self, value) -> bool:
        """Check if a value is considered empty"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False

    def _update_word(self, cursor, word: Dict):
        """Update a word record in the database"""

        # Convert complex types to JSON strings
        for key in ["examples", "collocations", "synonyms", "antonyms",
                    "relatedWords", "wordFamily", "semanticTags"]:
            if key in word and isinstance(word[key], (dict, list)):
                word[key] = json.dumps(word[key], ensure_ascii=False)

        # Build UPDATE query
        columns = [k for k in word.keys() if k != "id"]
        placeholders = ", ".join([f"{col} = ?" for col in columns])
        values = [word[col] for col in columns]
        values.append(word["id"])

        query = f"UPDATE wordsMaster SET {placeholders} WHERE id = ?"
        cursor.execute(query, values)

    def close(self):
        """Close database connection"""
        self.conn.close()


# ============================================================================
# METRICS & LOGGING
# ============================================================================

class EnrichmentMetrics:
    """Track and save enrichment metrics"""

    def __init__(self, metrics_dir: str):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.total_batches = 0
        self.successful_batches = 0
        self.failed_batches = 0
        self.total_words = 0
        self.start_time = time.time()

        self.request_log = []
        self.response_log = []

    def log_request(self, batch_num: int, batch_data: List[Dict]):
        """Log API request"""
        self.request_log.append({
            "batch": batch_num,
            "timestamp": datetime.now().isoformat(),
            "data": batch_data
        })

    def log_response(self, batch_num: int, response: Optional[Dict], success: bool):
        """Log API response"""
        self.response_log.append({
            "batch": batch_num,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "data": response
        })

        self.total_batches += 1
        if success:
            self.successful_batches += 1
            if response and "wordEntries" in response:
                self.total_words += len(response["wordEntries"])
        else:
            self.failed_batches += 1

    def save_metrics(self):
        """Save all metrics to files"""

        # Save summary
        summary = {
            "session_id": self.session_id,
            "total_batches": self.total_batches,
            "successful_batches": self.successful_batches,
            "failed_batches": self.failed_batches,
            "total_words_enriched": self.total_words,
            "duration_seconds": time.time() - self.start_time,
            "timestamp": datetime.now().isoformat()
        }

        summary_path = self.metrics_dir / f"summary_{self.session_id}.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Save request log
        requests_path = self.metrics_dir / f"requests_{self.session_id}.json"
        with open(requests_path, 'w', encoding='utf-8') as f:
            json.dump(self.request_log, f, indent=2, ensure_ascii=False)

        # Save response log
        responses_path = self.metrics_dir / f"responses_{self.session_id}.json"
        with open(responses_path, 'w', encoding='utf-8') as f:
            json.dump(self.response_log, f, indent=2, ensure_ascii=False)

        logging.info(f"Metrics saved to {self.metrics_dir}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class EnrichmentPipeline:
    """Main orchestration pipeline"""

    def __init__(self, config: PipelineConfig, api_keys: List[str]):
        self.config = config

        # Setup logging
        log_dir = Path(config.log_dir)
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"enrichment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        # Initialize components
        self.key_manager = APIKeyManager(api_keys)
        self.client = GeminiEnrichmentClient(config, self.key_manager)
        self.db = DatabaseManager(config.db_path)
        self.metrics = EnrichmentMetrics(config.metrics_dir)

        logging.info("Pipeline initialized successfully")

    def run(self):
        """Execute the enrichment pipeline"""

        try:
            # Backup database
            backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.db.backup_database(backup_id)

            # Get total words
            total_words = self.db.get_total_words()
            total_batches = (total_words + self.config.batch_size - 1) // self.config.batch_size

            if self.config.max_batches:
                total_batches = min(total_batches, self.config.max_batches)

            logging.info(f"Processing {total_batches} batches ({total_words} total words)")

            # Process batches
            for batch_num in range(total_batches):
                offset = batch_num * self.config.batch_size

                logging.info(f"\n{'='*60}")
                logging.info(f"Processing batch {batch_num + 1}/{total_batches}")
                logging.info(f"{'='*60}")

                # Fetch batch
                batch = self.db.get_words_batch(offset, self.config.batch_size)

                if not batch:
                    logging.warning(f"No data for batch {batch_num + 1}")
                    continue

                # Log request
                self.metrics.log_request(batch_num + 1, batch)

                # Enrich batch
                result = self.client.enrich_batch(batch)

                # Log response
                success = result is not None
                self.metrics.log_response(batch_num + 1, result, success)

                if success and result.get("wordEntries"):
                    # Save to database
                    self.db.save_enriched_words(result["wordEntries"])
                    logging.info(f"✓ Batch {batch_num + 1} completed successfully")
                else:
                    logging.error(f"✗ Batch {batch_num + 1} failed")

                # Rate limiting pause
                time.sleep(2)

            # Final summary
            self._print_summary()

        except Exception as e:
            logging.error(f"Pipeline error: {str(e)}", exc_info=True)

        finally:
            # Cleanup
            self.metrics.save_metrics()
            self.db.close()
            logging.info("Pipeline finished")

    def _print_summary(self):
        """Print final summary"""

        logging.info("\n" + "="*60)
        logging.info("ENRICHMENT SUMMARY")
        logging.info("="*60)

        logging.info(f"Total Batches: {self.metrics.total_batches}")
        logging.info(f"Successful: {self.metrics.successful_batches}")
        logging.info(f"Failed: {self.metrics.failed_batches}")
        logging.info(f"Words Enriched: {self.metrics.total_words}")

        duration = time.time() - self.metrics.start_time
        logging.info(f"Duration: {duration:.2f} seconds")

        # API key stats
        stats = self.key_manager.get_stats()
        logging.info(f"\nAPI Usage:")
        logging.info(f"  Total Calls: {stats['total_calls']}")
        logging.info(f"  Total Errors: {stats['total_errors']}")

        logging.info("="*60)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""

    # Configuration
    config = PipelineConfig(
        system_prompt_path="/content/drive/MyDrive/SystemPrompt.md",
        batch_prompt_path="/content/drive/MyDrive/BatchUserPrompt.md",
        structured_output_path="/content/drive/MyDrive/StructuredOutput.json",
        db_path="/content/drive/MyDrive/WordsMaster.db",
        batch_size=10,
        max_batches=1,  # Process all batches
        model_name="gemini-3-pro-preview", # Aligned with first cell's model name
        max_output_tokens=81920
    )

    # API keys from environment (comma-separated GEMINI_API_KEYS for rotation).
    # Set via .env / Colab secrets — never commit keys.
    import os
    api_keys = [
        k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()
    ]

    # Filter out None values - (this line is now technically unnecessary as keys are hardcoded)
    api_keys = [key for key in api_keys if key]

    if not api_keys:
        print("ERROR: No API keys found. Please provide valid API keys in the script.")
        return

    # Run pipeline
    pipeline = EnrichmentPipeline(config, api_keys)
    pipeline.run()


if __name__ == "__main__":
    main()