import sqlite3
import json
import os
import shutil
from datetime import datetime

# ==================== CONFIGURATION ====================
OLD_DB_PATH = "/storage/emulated/0/DictionaryEnrichment/WordsMaster.db"
NEW_DB_PATH = "/storage/emulated/0/DictionaryEnrichment/WordsMaster_v2.db"
BACKUP_PATH = "/storage/emulated/0/DictionaryEnrichment/backups/"

# ==================== SCHEMA CREATION ====================
def create_new_schema(conn):
    """إنشاء الـ schema الجديد"""
    cursor = conn.cursor()
    
    # Drop table if exists
    cursor.execute("DROP TABLE IF EXISTS wordsMaster")
    
    # Create new table with enhanced schema
    cursor.execute("""
        CREATE TABLE wordsMaster (
            -- PILLAR 1: IDENTITY & PRIORITY
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordEn TEXT NOT NULL,
            pos TEXT NOT NULL,
            cefrLevel TEXT CHECK (cefrLevel IN ('A1','A2','B1','B2','C1','C2')),
            fromOxford INTEGER NOT NULL DEFAULT 0 CHECK (fromOxford IN (0,1)),
            rank INTEGER,
            frequency INTEGER CHECK (frequency BETWEEN 1 AND 6),
            difficultyScore INTEGER CHECK (difficultyScore BETWEEN 1 AND 10),

            -- PILLAR 2: PHONETICS & SPEECH
            phoneticUs TEXT,
            phoneticUk TEXT,
            phoneticAr TEXT,
            translit TEXT,
            syllabify TEXT,

            -- PILLAR 3: MEANING & CONTEXT
            definitionEn TEXT NOT NULL,
            definitionAr TEXT,
            usageNote TEXT,
            category TEXT,
            primarySense TEXT CHECK (
                primarySense IN (
                    'Action','Process','Movement','State','Change','Relation',
                    'Time','Quantity','Measure','Quality','Emotion','Idea',
                    'Communication','Object','Person','Place'
                )
            ),
            semanticTags TEXT,
            register TEXT CHECK (register IN ('Formal','Informal','Neutral','Archaic','Slang')),
            
            -- PILLAR 4: MNEMONICS & MEMORY
            mnemonicAr TEXT,

            -- PILLAR 5: RELATIONAL DATA
            examples TEXT,
            collocations TEXT,
            synonyms TEXT,
            antonyms TEXT,
            relatedWords TEXT,
            wordFamily TEXT,
            
            -- PILLAR 6: INTERNATIONALIZATION
            arabicAr TEXT,
            frenchFr TEXT,
            germanDe TEXT,
            spanishEs TEXT,
            chineseZh TEXT,
            russianRu TEXT,
            portuguesePt TEXT,
            japaneseJa TEXT,
            italianIt TEXT,
            turkishTr TEXT,

            -- TEMPORARY: Migration tracking
            addedFromOxford INTEGER DEFAULT 0,

            -- CONSTRAINTS
            UNIQUE (wordEn, pos)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX idx_words_wordEn ON wordsMaster(wordEn)")
    cursor.execute("CREATE INDEX idx_words_wordEn_pos ON wordsMaster(wordEn, pos)")
    cursor.execute("CREATE INDEX idx_words_rank ON wordsMaster(rank)")
    cursor.execute("CREATE INDEX idx_words_arabicAr ON wordsMaster(arabicAr)")
    
    conn.commit()
    print("✅ تم إنشاء الـ schema الجديد بنجاح!")

# ==================== DATA TRANSFORMATION ====================
def validate_json_field(field_value):
    """التحقق من صحة JSON field وإصلاحه"""
    if not field_value or field_value == 'null':
        return None
    
    try:
        # محاولة parse
        parsed = json.loads(field_value)
        # إعادة التحويل للتأكد من الصيغة
        return json.dumps(parsed, ensure_ascii=False)
    except:
        # إذا فشل، نحاول إصلاح بسيط
        try:
            # إزالة backslashes زائدة
            fixed = field_value.replace('\\"', '"').replace('\\', '')
            parsed = json.loads(fixed)
            return json.dumps(parsed, ensure_ascii=False)
        except:
            return None

def transform_row(old_row):
    """تحويل صف من القديم للجديد - بدون تعديل frequency أو difficultyScore"""
    (old_id, wordEn, rank, fromOxford, cefrLevel, pos, syllabify,
     phoneticUs, phoneticUk, phoneticAr, translit, definitionEn,
     definitionAr, primarySense, usageNote, register, category,
     frequency_old, wordFamily, synonyms, antonyms, examples,
     collocations, relatedWords, arabicAr, frenchFr, germanDe,
     spanishEs, chineseZh, russianRu, portuguesePt, japaneseJa,
     italianIt, turkishTr, addedFromOxford) = old_row
    
    # نسخ frequency كما هو من القاعدة القديمة (بدون تحويل)
    frequency = frequency_old
    
    # تعيين difficultyScore = 5 مؤقتاً (سيتم تحديثه لاحقاً)
    difficultyScore = 5
    
    # تنظيف JSON fields
    examples = validate_json_field(examples)
    collocations = validate_json_field(collocations)
    synonyms = validate_json_field(synonyms)
    antonyms = validate_json_field(antonyms)
    relatedWords = validate_json_field(relatedWords)
    wordFamily = validate_json_field(wordFamily)
    
    # Default for required fields
    if not definitionEn:
        definitionEn = f"[TO BE ENRICHED: {wordEn}]"
    
    return {
        'wordEn': wordEn,
        'pos': pos,
        'cefrLevel': cefrLevel,
        'fromOxford': fromOxford or 0,
        'rank': rank,
        'frequency': frequency,
        'difficultyScore': difficultyScore,
        'phoneticUs': phoneticUs,
        'phoneticUk': phoneticUk,
        'phoneticAr': phoneticAr,
        'translit': translit,
        'syllabify': syllabify,
        'definitionEn': definitionEn,
        'definitionAr': definitionAr,
        'usageNote': usageNote,
        'category': category,
        'primarySense': primarySense,
        'semanticTags': None,
        'register': register,
        'mnemonicAr': None,
        'examples': examples,
        'collocations': collocations,
        'synonyms': synonyms,
        'antonyms': antonyms,
        'relatedWords': relatedWords,
        'wordFamily': wordFamily,
        'arabicAr': arabicAr,
        'frenchFr': frenchFr,
        'germanDe': germanDe,
        'spanishEs': spanishEs,
        'chineseZh': chineseZh,
        'russianRu': russianRu,
        'portuguesePt': portuguesePt,
        'japaneseJa': japaneseJa,
        'italianIt': italianIt,
        'turkishTr': turkishTr,
        'addedFromOxford': addedFromOxford or 0
    }

# ==================== MIGRATION PROCESS ====================
def migrate_data():
    """عملية الـ migration الرئيسية"""
    
    # 1. Backup القاعدة القديمة
    print("\n" + "=" * 70)
    print("📦 STEP 1: Backup")
    print("=" * 70)
    
    if not os.path.exists(BACKUP_PATH):
        os.makedirs(BACKUP_PATH)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_PATH}WordsMaster_backup_{timestamp}.db"
    shutil.copy2(OLD_DB_PATH, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    # 2. إنشاء قاعدة البيانات الجديدة
    print("\n" + "=" * 70)
    print("🏗️  STEP 2: Create New Schema")
    print("=" * 70)
    
    new_conn = sqlite3.connect(NEW_DB_PATH)
    create_new_schema(new_conn)
    
    # 3. قراءة البيانات من القديمة
    print("\n" + "=" * 70)
    print("📥 STEP 3: Load Old Data")
    print("=" * 70)
    
    old_conn = sqlite3.connect(OLD_DB_PATH)
    old_cursor = old_conn.cursor()
    
    old_cursor.execute("""
        SELECT id, wordEn, rank, fromOxford, cefrLevel, pos, syllabify,
               phoneticUs, phoneticUk, phoneticAr, translit, definitionEn,
               definitionAr, primarySense, usageNote, register, category,
               frequency, wordFamily, synonyms, antonyms, examples,
               collocations, relatedWords, arabicAr, frenchFr, germanDe,
               spanishEs, chineseZh, russianRu, portuguesePt, japaneseJa,
               italianIt, turkishTr, addedFromOxford
        FROM wordsMaster
        ORDER BY rank
    """)
    
    old_rows = old_cursor.fetchall()
    total_rows = len(old_rows)
    print(f"✅ تم تحميل {total_rows} صف من القاعدة القديمة")
    
    # 4. تحويل وإدخال البيانات
    print("\n" + "=" * 70)
    print("🔄 STEP 4: Transform & Insert Data")
    print("=" * 70)
    
    new_cursor = new_conn.cursor()
    
    stats = {
        'total': total_rows,
        'success': 0,
        'skipped': 0,
        'errors': [],
        'frequency_distribution': {}
    }
    
    for i, old_row in enumerate(old_rows, 1):
        try:
            new_data = transform_row(old_row)
            
            # تتبع توزيع frequency
            freq = new_data['frequency']
            stats['frequency_distribution'][freq] = stats['frequency_distribution'].get(freq, 0) + 1
            
            # Insert into new database
            new_cursor.execute("""
                INSERT INTO wordsMaster (
                    wordEn, pos, cefrLevel, fromOxford, rank, frequency, difficultyScore,
                    phoneticUs, phoneticUk, phoneticAr, translit, syllabify,
                    definitionEn, definitionAr, usageNote, category, primarySense,
                    semanticTags, register, mnemonicAr,
                    examples, collocations, synonyms, antonyms, relatedWords, wordFamily,
                    arabicAr, frenchFr, germanDe, spanishEs, chineseZh,
                    russianRu, portuguesePt, japaneseJa, italianIt, turkishTr,
                    addedFromOxford
                ) VALUES (
                    :wordEn, :pos, :cefrLevel, :fromOxford, :rank, :frequency, :difficultyScore,
                    :phoneticUs, :phoneticUk, :phoneticAr, :translit, :syllabify,
                    :definitionEn, :definitionAr, :usageNote, :category, :primarySense,
                    :semanticTags, :register, :mnemonicAr,
                    :examples, :collocations, :synonyms, :antonyms, :relatedWords, :wordFamily,
                    :arabicAr, :frenchFr, :germanDe, :spanishEs, :chineseZh,
                    :russianRu, :portuguesePt, :japaneseJa, :italianIt, :turkishTr,
                    :addedFromOxford
                )
            """, new_data)
            
            stats['success'] += 1
            
            if i % 500 == 0:
                new_conn.commit()
                print(f"   ✓ تم معالجة {i}/{total_rows} صف...")
        
        except sqlite3.IntegrityError as e:
            stats['skipped'] += 1
            stats['errors'].append({
                'row': i,
                'word': old_row[1],
                'error': str(e)
            })
        
        except Exception as e:
            stats['errors'].append({
                'row': i,
                'word': old_row[1],
                'error': str(e)
            })
    
    new_conn.commit()
    
    # 5. عرض الإحصائيات
    print("\n" + "=" * 70)
    print("📊 STEP 5: Migration Statistics")
    print("=" * 70)
    
    print(f"\n✅ Migration Summary:")
    print(f"   • Total rows: {stats['total']}")
    print(f"   • Successfully migrated: {stats['success']}")
    print(f"   • Skipped (duplicates): {stats['skipped']}")
    print(f"   • Errors: {len(stats['errors'])}")
    
    print(f"\n📊 Frequency Distribution:")
    for freq in sorted(stats['frequency_distribution'].keys()):
        count = stats['frequency_distribution'][freq]
        percentage = (count / stats['success']) * 100
        bar = '█' * int(percentage / 2)
        freq_label = freq if freq is not None else 'NULL'
        print(f"   Freq {freq_label}: {count:5d} كلمة ({percentage:5.2f}%) {bar}")
    
    if stats['errors']:
        print(f"\n⚠️  Errors (first 10):")
        for err in stats['errors'][:10]:
            print(f"   • Row {err['row']} ({err['word']}): {err['error']}")
    
    # 6. Verification
    print("\n" + "=" * 70)
    print("🔍 STEP 6: Verification")
    print("=" * 70)
    
    new_cursor.execute("SELECT COUNT(*) FROM wordsMaster")
    new_count = new_cursor.fetchone()[0]
    
    new_cursor.execute("SELECT COUNT(*) FROM wordsMaster WHERE addedFromOxford = 1")
    oxford_added = new_cursor.fetchone()[0]
    
    new_cursor.execute("SELECT COUNT(*) FROM wordsMaster WHERE frequency = 6")
    freq_6_count = new_cursor.fetchone()[0]
    
    print(f"✅ New database contains {new_count} words")
    print(f"   • Added from Oxford: {oxford_added}")
    print(f"   • Original words: {new_count - oxford_added}")
    print(f"   • Words with frequency = 6: {freq_6_count}")
    
    # Close connections
    old_conn.close()
    new_conn.close()
    
    print("\n" + "=" * 70)
    print("🎉 Migration Completed Successfully!")
    print("=" * 70)
    print(f"\n📁 Files:")
    print(f"   • Old DB: {OLD_DB_PATH}")
    print(f"   • New DB: {NEW_DB_PATH}")
    print(f"   • Backup: {backup_file}")
    print(f"\n⚠️  Note: difficultyScore set to 5 temporarily.")
    print(f"   Run the difficulty score update script to calculate proper values.")

# ==================== MAIN EXECUTION ====================
def main():
    print("=" * 70)
    print("🚀 DATABASE MIGRATION: Old Schema → New Enhanced Schema")
    print("=" * 70)
    
    # Check if old database exists
    if not os.path.exists(OLD_DB_PATH):
        print(f"❌ Error: Old database not found at {OLD_DB_PATH}")
        return
    
    # Check if new database already exists
    if os.path.exists(NEW_DB_PATH):
        print(f"\n⚠️  Warning: New database already exists at {NEW_DB_PATH}")
        overwrite = input("Do you want to overwrite it? (yes/no): ")
        if overwrite.lower() != 'yes':
            print("❌ Migration cancelled.")
            return
        os.remove(NEW_DB_PATH)
    
    # Confirmation
    print(f"\n📋 Migration Plan:")
    print(f"   • Source: {OLD_DB_PATH}")
    print(f"   • Destination: {NEW_DB_PATH}")
    print(f"   • Backup folder: {BACKUP_PATH}")
    
    confirmation = input("\n⚠️  Start migration? (yes/no): ")
    
    if confirmation.lower() == 'yes':
        try:
            migrate_data()
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n⏸️  Migration cancelled.")

if __name__ == "__main__":
    main()