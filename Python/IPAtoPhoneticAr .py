import sqlite3
import re
from typing import Optional, Dict, List, Tuple

DB_PATH = "/sdcard/DictionaryEnrichment/WordsMasterXX.db"

class EnglishToArabicPhonetics:
    """
    محول متقدم للنطق من الإنجليزي إلى العربي
    يدعم IPA والتحويل الذكي من الكلمات مباشرة
    """
    
    def __init__(self):
        # قواعد IPA
        self.affricates = {
            "tʃ": "تش", "dʒ": "دج",
        }
        
        self.diphthongs = {
            "əʊ": "او", "eɪ": "اي", "aɪ": "آي", "ɔɪ": "وي",
            "aʊ": "او", "oʊ": "او", "ɪə": "ير", "eə": "اير", "ʊə": "ور",
        }
        
        self.r_colored = {
            "ɑːr": "آر", "ɑr": "آر", "ɔːr": "أور", "ɔr": "أور",
            "ɜːr": "ير", "ɜr": "ير", "ɝː": "ير", "ɝ": "ير",
            "ɚ": "ر", "ər": "ر", "ɪr": "ير", "ʊr": "ور",
            "ɛr": "اير", "ær": "اير",
        }
        
        self.long_vowels = {
            "iː": "ي", "uː": "و", "ɑː": "آ", "ɔː": "أو",
            "ɜː": "ير", "æː": "آ", "ɒː": "أو", "eː": "اي",
            "oː": "او", "əː": "ير",
        }
        
        self.syllabic = {"l̩": "ل", "n̩": "ن", "m̩": "م"}
        
        self.special_consonants = {
            "ʃ": "ش", "ʒ": "ج", "θ": "ث", "ð": "ذ",
            "ŋ": "نج", "ɹ": "ر", "ɾ": "ر", "ʀ": "ر",
        }
        
        self.short_vowels = {
            "ɪ": "ي", "e": "اي", "ɛ": "اي", "æ": "آ", "a": "آ",
            "ɑ": "آ", "ʌ": "ا", "ɒ": "أ", "ɔ": "أو", "o": "او",
            "ʊ": "و", "u": "و", "i": "ي", "ɜ": "ير", "ə": "ا",
            "ɨ": "ي", "ʉ": "و", "ɘ": "ا", "ɵ": "او", "ɐ": "ا",
        }
        
        self.consonants = {
            "p": "ب", "b": "ب", "t": "ت", "d": "د", "k": "ك",
            "ɡ": "ج", "g": "ج", "f": "ف", "v": "ف", "s": "س",
            "z": "ز", "h": "ه", "ɦ": "ه", "m": "م", "n": "ن",
            "l": "ل", "ɫ": "ل", "r": "ر", "w": "و", "ʍ": "و",
            "j": "ي", "ɥ": "ي", "ʔ": "", "x": "كس", "ç": "ش",
            "ʝ": "ي", "ɣ": "ج", "χ": "خ", "ʁ": "ر",
        }
        
        # قواعد التحويل الذكي من الكلمة (مرتبة حسب الأولوية)
        self.smart_patterns = [
            # حروف صامتة في البداية (يجب معالجتها أولاً)
            (r'^ps', 'سا'),     # psychology → سايكولوجي
            (r'^pn', 'ن'),      # pneumonia
            (r'^kn', 'ن'),      # knight, know
            (r'^gn', 'ن'),      # gnome
            (r'^wr', 'ر'),      # write, wrong
            
            # نهايات شائعة
            (r'tion\b', 'شن'),
            (r'sion\b', 'جن'),
            (r'cian\b', 'شن'),
            (r'ture\b', 'تشر'),
            
            # مجموعات معقدة - الأطول أولاً
            (r'ough\b', 'او'),   # though, although
            (r'nough\b', 'ناف'), # enough
            (r'ough', 'اف'),     # tough, rough
            (r'augh', 'اوف'),    # laugh, taught
            (r'eigh', 'اي'),     # eight, weigh
            (r'igh', 'اي'),      # night, light, knight
            (r'rite\b', 'رايت'), # write
            (r'ite\b', 'ايت'),   # white, bite
            
            # حروف صامتة
            (r'mb\b', 'م'),      # climb, bomb
            (r'bt\b', 'ت'),      # debt, doubt
            (r'gh\b', ''),       # high, though
            (r'gh(?=[aeiou])', ''), # ghost → gost
            (r'gn\b', 'ن'),      # sign, design
            (r'([^c])kn', r'\1ن'), # acknowledge
            
            # مجموعات حروف متحركة ومركبة (الأطول أولاً)
            (r'tch', 'تش'),
            (r'dge\b', 'ج'),     # judge, bridge
            (r'dge', 'دج'),      # gadget
            (r'ck', 'ك'),
            (r'ph', 'ف'),
            (r'sh', 'ش'),
            (r'ch(?!o)', 'تش'),  # church, but not psychology
            (r'cho', 'كو'),      # psychology
            (r'th', 'ث'),
            (r'ng', 'نج'),
            (r'qu', 'كو'),
            
            # حروف متحركة مركبة
            (r'eau\b', 'او'),    # bureau, plateau
            (r'ieu', 'يو'),      # lieu
            (r'esign', 'يساين'), # design
            (r'ea(?=[^r])', 'ي'), # eat, sea (but not ear)
            (r'ee', 'ي'),
            (r'oo', 'و'),
            (r'ou', 'او'),
            (r'ow\b', 'او'),     # window, flow
            (r'ow', 'او'),
            (r'ai', 'اي'),
            (r'ay', 'اي'),
            (r'oi', 'وي'),
            (r'oy', 'وي'),
            (r'au', 'او'),
            (r'aw', 'او'),
            (r'ew', 'يو'),
            (r'ie\b', 'ي'),      # pie, die
            (r'ie', 'ي'),
            (r'ue\b', 'يو'),     # blue, true
            (r'ui', 'وي'),
            (r'eo', 'يو'),       # people
            
            # حروف متحركة مع R
            (r'are\b', 'اير'),   # care, share
            (r'ear\b', 'ير'),    # hear, fear
            (r'eer', 'ير'),      # beer, deer
            (r'oor', 'ور'),      # door, floor
            (r'our', 'أور'),     # four, pour
            (r'ar', 'آر'),
            (r'er\b', 'ر'),      # mother, father
            (r'ir', 'ير'),
            (r'or\b', 'ر'),      # doctor, actor
            (r'or', 'أور'),
            (r'ur', 'ير'),
            (r'air', 'اير'),
            (r'ear', 'ير'),
        ]
        
        self.single_chars = {
            'a': 'ا', 'b': 'ب', 'c': 'ك', 'd': 'د', 'e': 'ي',
            'f': 'ف', 'g': 'ج', 'h': 'ه', 'i': 'ي', 'j': 'ج',
            'k': 'ك', 'l': 'ل', 'm': 'م', 'n': 'ن', 'o': 'و',
            'p': 'ب', 'q': 'ق', 'r': 'ر', 's': 'س', 't': 'ت',
            'u': 'و', 'v': 'ف', 'w': 'و', 'x': 'كس', 'y': 'ي',
            'z': 'ز',
        }

    def clean_ipa(self, ipa: str) -> str:
        """تنظيف رموز IPA الإضافية"""
        if not ipa:
            return ""
        
        # إزالة الأقواس ومحتوياتها
        ipa = re.sub(r'\([^)]*\)', '', ipa)
        
        # رموز النبر والفواصل
        remove_chars = "ˈˌ‿/[]ˤ̆͜͡.ː̩̯ˑ"
        for char in remove_chars:
            ipa = ipa.replace(char, "")
        
        return ipa.strip()

    def from_ipa(self, ipa: str) -> str:
        """تحويل دقيق من IPA إلى نطق عربي"""
        if not ipa:
            return "غير محدد"
        
        result = self.clean_ipa(ipa)
        
        # تطبيق التحويلات بالترتيب (الأطول أولاً)
        for patterns_dict in [
            self.affricates,
            self.diphthongs,
            self.r_colored,
            self.long_vowels,
            self.syllabic,
            self.special_consonants,
            self.short_vowels,
            self.consonants,
        ]:
            for pattern, replacement in sorted(
                patterns_dict.items(), 
                key=lambda x: -len(x[0])
            ):
                result = result.replace(pattern, replacement)
        
        # تنظيف نهائي
        result = re.sub(r'[^\u0600-\u06FF]', '', result)
        result = result.strip()
        
        return result if result else "غير محدد"

    def from_word_smart(self, word: str) -> str:
        """تحويل ذكي من الكلمة الإنجليزية مباشرة"""
        if not word:
            return "غير محدد"
        
        result = word.lower().strip()
        
        # تطبيق الأنماط الصوتية بالترتيب (قبل حذف e)
        for pattern, replacement in self.smart_patterns:
            result = re.sub(pattern, replacement, result)
        
        # إزالة الحروف الصامتة في نهاية الكلمة
        result = re.sub(r'e\b', '', result)  # silent e في النهاية
        
        # تحويل الحروف المفردة المتبقية
        converted = []
        
        for i, char in enumerate(result):
            if '\u0600' <= char <= '\u06FF':  # حرف عربي بالفعل
                converted.append(char)
            else:
                arabic_char = self.single_chars.get(char, '')
                converted.append(arabic_char)
        
        result = ''.join(converted)
        
        # إزالة التكرار المفرط (أكثر من حرفين)
        result = re.sub(r'(.)\1{2,}', r'\1', result)
        
        # تنظيف نهائي
        result = result.strip()
        return result if result else "غير محدد"

    def from_word_and_ipa(self, word: str, ipa: Optional[str] = None) -> str:
        """نهج هجين: يستخدم IPA إن وُجد، وإلا يستخدم التحويل الذكي"""
        if ipa and ipa.strip():
            return self.from_ipa(ipa)
        return self.from_word_smart(word)


def test_comprehensive():
    """اختبار شامل للطرق المختلفة"""
    converter = EnglishToArabicPhonetics()
    
    test_cases = [
        # (word, ipa, expected_from_ipa, expected_from_word)
        ("manage", "ˈmænɪdʒ", "مآنيدج", "ماناج"),
        ("also", "ˈɔːl.səʊ", "أولساو", "السو"),
        ("well", "wɛl", "وايل", "ويل"),
        ("those", "ðəʊz", "ذاوز", "ثوس"),
        ("workout", "ˈwəːk.aʊt", "واكاوت", "وأوركاوت"),
        ("enumerate", "ɪˈnjuː.məˌɹeɪt", "ينيومارايت", "ينوميرات"),
        ("nation", None, None, "ناشن"),
        ("enough", None, None, "يناف"),
        ("knight", None, None, "نايت"),
        ("psychology", None, None, "سايكولوجي"),
        ("know", None, None, "ناو"),
        ("write", None, None, "رايت"),
        ("people", None, None, "بيوبل"),
        ("beautiful", None, None, "بيوتيفول"),
        ("though", None, None, "ثاو"),
        ("doubt", None, None, "داوت"),
        ("design", None, None, "ديساين"),
    ]
    
    print("=" * 100)
    print("اختبار محول النطق الشامل")
    print("=" * 100)
    print(f"{'Word':<15} {'IPA':<25} {'From IPA':<20} {'From Word':<20} {'Hybrid':<20}")
    print("-" * 100)
    
    for word, ipa, exp_ipa, exp_word in test_cases:
        from_ipa = converter.from_ipa(ipa) if ipa else "N/A"
        from_word = converter.from_word_smart(word)
        hybrid = converter.from_word_and_ipa(word, ipa)
        
        status = ""
        if exp_word and from_word == exp_word:
            status = "✓"
        elif exp_word:
            status = f"✗ (expected: {exp_word})"
        
        print(f"{word:<15} {(ipa or 'N/A'):<25} {from_ipa:<20} {from_word:<20} {hybrid:<20} {status}")
    
    print("=" * 100)


def update_database_enhanced():
    """تحديث قاعدة البيانات بالنطق العربي المحسّن"""
    converter = EnglishToArabicPhonetics()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # جلب الكلمات
    cursor.execute("""
        SELECT id, wordEn, phoneticUs 
        FROM wordsMaster
        WHERE wordEn IS NOT NULL AND wordEn != ''
    """)

    rows = cursor.fetchall()
    print(f"\n🔄 Processing {len(rows)} words...")

    updated = 0
    errors = []

    for rowid, word, phonetic_us in rows:
        try:
            # استخدام النهج الهجين
            phonetic_ar = converter.from_word_and_ipa(word, phonetic_us)
            
            cursor.execute("""
                UPDATE wordsMaster
                SET phoneticAr = ?
                WHERE id = ?
            """, (phonetic_ar, rowid))
            
            updated += 1
            
            if updated % 1000 == 0:
                print(f"  ✓ Processed {updated} words...")
                conn.commit()
                
        except Exception as e:
            errors.append((rowid, word, str(e)))

    conn.commit()
    conn.close()

    print(f"\n✅ Successfully updated {updated} rows")
    
    if errors:
        print(f"\n⚠️  {len(errors)} errors occurred:")
        for rowid, word, error in errors[:10]:
            print(f"  Row {rowid}: {word} → {error}")


if __name__ == "__main__":
    # اختبار
    test_comprehensive()
    
    # تحديث قاعدة البيانات
    print("\n")
    response = input("📊 هل تريد تحديث قاعدة البيانات؟ (y/n): ")
    if response.lower() == 'y':
        update_database_enhanced()
    else:
        print("تم الإلغاء.")