import sqlite3

DB_PATH = "/storage/emulated/0/DictionaryEnrichment/WordsMasterXX.db"

def estimate_syllables(word):
    """
    تقدير محسّن لعدد المقاطع باستخدام قواعد أفضل
    """
    if not word:
        return 1
    
    word = word.lower()
    word_len = len(word)
    
    # حروف العلة
    vowels = "aeiouy"
    syllable_count = 0
    previous_was_vowel = False
    
    # عد مجموعات حروف العلة
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not previous_was_vowel:
            syllable_count += 1
        previous_was_vowel = is_vowel
    
    # تعديل للحالات الخاصة
    # كلمات تنتهي بـ e صامتة
    if word.endswith('e') and syllable_count > 1:
        syllable_count -= 1
    
    # كلمات تنتهي بـ le مع حرف ساكن قبلها
    if word_len >= 3 and word.endswith('le') and word[-3] not in vowels:
        syllable_count += 1
    
    # الحد الأدنى مقطع واحد
    return max(1, syllable_count)


def calculate_difficulty_score(word, syllables, cefr_level, frequency):
    """
    حساب difficultyScore (1-10) - النسخة المحسّنة v3
    
    التحسينات الجديدة:
    - تقدير أفضل للمقاطع
    - معالجة الكلمات بدون cefrLevel
    - ضبط أفضل لـ frequency=2
    """
    
    # ==================== الخطوة 1: تحديد عدد المقاطع ====================
    
    if syllables:
        syllable_count = len(syllables.split('•'))
    else:
        syllable_count = estimate_syllables(word)
    
    word_len = len(word) if word else 4
    
    # ==================== الخطوة 2: النقاط الأساسية ====================
    
    if frequency is not None:
        FREQUENCY_BASE = {
            1: 0.3,   # كلمات شائعة جداً (the, a, is)
            2: 2.2,   # كلمات شائعة (be, have, do) - رفعناها قليلاً
            3: 4.2,   # كلمات متوسطة الشيوع
            4: 6.2,   # كلمات أقل شيوعاً - رفعناها قليلاً
            5: 8.0,   # كلمات نادرة
            6: 9.0    # كلمات نادرة جداً
        }
        base_score = FREQUENCY_BASE.get(frequency, 5.0)
    
    elif cefr_level:
        CEFR_BASE = {
            'A1': 2.0,
            'A2': 3.5,
            'B1': 5.5,
            'B2': 7.0,
            'C1': 8.5,
            'C2': 9.5
        }
        base_score = CEFR_BASE.get(cefr_level, 5.0)
    
    else:
        # كلمات بدون cefrLevel - نستخدم تقدير حسب الطول والمقاطع
        if word_len <= 4 and syllable_count <= 1:
            base_score = 3.0
        elif word_len <= 6 and syllable_count <= 2:
            base_score = 5.0
        else:
            base_score = 6.5
    
    # ==================== الخطوة 3: تعديل المقاطع ====================
    
    if syllable_count == 1:
        syllable_modifier = -1.2   # خففناه قليلاً
    elif syllable_count == 2:
        syllable_modifier = -0.1   # خففناه
    elif syllable_count == 3:
        syllable_modifier = 0.5
    elif syllable_count == 4:
        syllable_modifier = 1.3
    else:
        syllable_modifier = 2.0
    
    # ==================== الخطوة 4: تعديل الطول ====================
    
    if word_len <= 2:
        length_modifier = -1.0
    elif word_len <= 4:
        length_modifier = -0.2
    elif word_len <= 7:
        length_modifier = 0
    elif word_len <= 10:
        length_modifier = 0.4
    else:
        length_modifier = 0.9
    
    # ==================== الخطوة 5: تعديلات خاصة ====================
    
    # كلمات frequency=1 سهلة جداً
    if frequency == 1:
        return 1
    
    # كلمات frequency=6 مع 3+ مقاطع صعبة جداً
    if frequency == 6 and syllable_count >= 3:
        return 10
    
    # كلمات frequency=5 طويلة وصعبة
    if frequency == 5 and syllable_count >= 4:
        return 10
    
    # ==================== الحساب النهائي ====================
    
    final_score = base_score + syllable_modifier + length_modifier
    normalized_score = max(1, min(10, round(final_score)))
    
    return int(normalized_score)


def test_difficulty_scores():
    """اختبار الدالة المحسّنة v3"""
    
    test_cases = [
        # (word, syllables, cefr, frequency, expected)
        ("a", None, "A1", 1, "1"),
        ("I", None, "A1", 1, "1"),
        ("the", None, "A1", 1, "1"),
        ("is", None, "A1", 1, "1"),
        ("and", None, "A1", 1, "1"),
        
        ("be", None, "A1", 2, "1"),
        ("have", None, "A1", 2, "2"),      # ← المشكلة هنا
        ("which", None, "A1", 2, "2"),
        
        ("should", None, "A1", 3, "3-4"),
        ("between", "be•tween", "A1", 3, "4"),
        ("information", "in•for•ma•tion", "A1", 3, "6-7"),
        
        ("consider", "con•sid•er", "A2", 4, "6-7"),
        ("development", "de•vel•op•ment", "B1", 4, "7-8"),
        
        ("circumstance", "cir•cum•stance", "B2", 5, "9"),
        ("characteristic", "char•ac•ter•is•tic", "B2", 5, "10"),
        
        ("solicitor", "so•lic•i•tor", "C1", 6, "10"),
        
        # اختبار كلمات بدون cefrLevel
        ("test", None, None, 4, "5-6"),
        ("example", None, None, 4, "6-7"),
        ("programming", None, None, 5, "8-9"),
    ]
    
    print("=" * 90)
    print("🧪 اختبار الدالة المحسّنة v3")
    print("=" * 90)
    print(f"{'Word':<18} {'CEFR':<6} {'Freq':<6} {'Syll':<6} {'Score':<6} {'Expected':<10} {'Status'}")
    print("-" * 90)
    
    correct = 0
    total = len(test_cases)
    
    for word, syllables, cefr, freq, expected in test_cases:
        score = calculate_difficulty_score(word, syllables, cefr, freq)
        
        if syllables:
            syll_count = len(syllables.split('•'))
        else:
            syll_count = estimate_syllables(word)
        
        freq_str = str(freq) if freq is not None else '-'
        cefr_str = cefr if cefr else '-'
        
        if '-' in expected:
            min_exp, max_exp = map(int, expected.split('-'))
            is_correct = min_exp <= score <= max_exp
        else:
            is_correct = score == int(expected)
        
        status = "✅" if is_correct else "❌"
        if is_correct:
            correct += 1
        
        print(f"{word:<18} {cefr_str:<6} {freq_str:<6} {syll_count:<6} {score:<6} {expected:<10} {status}")
    
    print("=" * 90)
    print(f"\n📊 النتيجة: {correct}/{total} ({(correct/total)*100:.1f}%)")
    
    # اختبار إضافي للتقدير
    print("\n" + "=" * 90)
    print("🔍 اختبار تقدير المقاطع:")
    print("=" * 90)
    
    estimation_tests = [
        ("be", 1),
        ("have", 1),  # have = 1 مقطع فعلياً
        ("which", 1),
        ("should", 1),
        ("between", 2),
        ("information", 4),
        ("consider", 3),
        ("development", 4),
    ]
    
    for word, expected in estimation_tests:
        estimated = estimate_syllables(word)
        status = "✅" if estimated == expected else f"❌ (توقع: {expected})"
        print(f"   {word:<15} → {estimated} مقطع {status}")


def update_all_difficulty_scores():
    """تحديث جميع قيم difficultyScore"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "=" * 90)
    print("🔄 تحديث مستويات الصعوبة (v3)")
    print("=" * 90)
    
    cursor.execute("""
        SELECT id, wordEn, syllabify, cefrLevel, frequency, difficultyScore
        FROM wordsMaster
        ORDER BY id
    """)
    
    rows = cursor.fetchall()
    total = len(rows)
    
    stats = {
        'updated': 0,
        'unchanged': 0,
        'distribution_before': {},
        'distribution_after': {},
        'by_frequency': {},
        'no_cefr': 0,
        'syllable_estimates': 0
    }
    
    for row in rows:
        old_score = row[5]
        stats['distribution_before'][old_score] = stats['distribution_before'].get(old_score, 0) + 1
    
    print(f"\n📊 توزيع الصعوبة قبل التحديث:")
    for score in sorted(stats['distribution_before'].keys()):
        count = stats['distribution_before'][score]
        percentage = (count / total) * 100
        print(f"   Score {score:2d}: {count:5d} كلمة ({percentage:5.2f}%)")
    
    print(f"\n🔄 جاري تحديث {total} كلمة...")
    
    updates = []
    for row in rows:
        id_val, word, syllables, cefr, frequency, old_score = row
        
        if not syllables:
            stats['syllable_estimates'] += 1
        if not cefr:
            stats['no_cefr'] += 1
        
        new_score = calculate_difficulty_score(word, syllables, cefr, frequency)
        
        if new_score != old_score:
            updates.append((new_score, id_val))
            stats['updated'] += 1
        else:
            stats['unchanged'] += 1
        
        stats['distribution_after'][new_score] = stats['distribution_after'].get(new_score, 0) + 1
        
        if frequency:
            if frequency not in stats['by_frequency']:
                stats['by_frequency'][frequency] = {}
            stats['by_frequency'][frequency][new_score] = stats['by_frequency'][frequency].get(new_score, 0) + 1
    
    if updates:
        cursor.executemany("""
            UPDATE wordsMaster 
            SET difficultyScore = ? 
            WHERE id = ?
        """, updates)
        conn.commit()
    
    print(f"\n✅ تم تحديث {stats['updated']} كلمة")
    print(f"   • غير متغيرة: {stats['unchanged']}")
    print(f"   • كلمات بدون syllabify: {stats['syllable_estimates']}")
    print(f"   • كلمات بدون cefrLevel: {stats['no_cefr']}")
    
    print(f"\n📊 توزيع الصعوبة بعد التحديث:")
    for score in sorted(stats['distribution_after'].keys()):
        count = stats['distribution_after'][score]
        percentage = (count / total) * 100
        bar = '█' * int(percentage / 2)
        print(f"   Score {score:2d}: {count:5d} كلمة ({percentage:5.2f}%) {bar}")
    
    print(f"\n📊 توزيع الصعوبة حسب Frequency:")
    for freq in sorted(stats['by_frequency'].keys()):
        freq_data = stats['by_frequency'][freq]
        total_freq = sum(freq_data.values())
        print(f"\n   Frequency {freq} ({total_freq} كلمة):")
        for score in sorted(freq_data.keys()):
            count = freq_data[score]
            pct = (count / total_freq) * 100
            print(f"      Score {score:2d}: {count:4d} ({pct:5.1f}%)")
    
    print(f"\n📝 أمثلة على الكلمات:")
    
    for freq in [1, 2, 3, 4, 5, 6]:
        cursor.execute("""
            SELECT wordEn, cefrLevel, syllabify, difficultyScore
            FROM wordsMaster
            WHERE frequency = ?
            LIMIT 5
        """, (freq,))
        
        examples = cursor.fetchall()
        if examples:
            print(f"\n   Frequency {freq}:")
            for word, cefr, syll, score in examples:
                if syll:
                    syll_count = len(syll.split('•'))
                    syll_info = f"{syll_count}م"
                else:
                    est_syll = estimate_syllables(word)
                    syll_info = f"~{est_syll}م"
                
                cefr_str = cefr if cefr else 'NULL'
                print(f"      • {word:<16} CEFR:{cefr_str:<4} Score:{score:2d} ({syll_info})")
    
    conn.close()
    
    print("\n" + "=" * 90)
    print("🎉 اكتمل التحديث بنجاح!")
    print("=" * 90)


if __name__ == "__main__":
    print("تشغيل الاختبار أولاً...")
    test_difficulty_scores()
    
    print("\n" + "=" * 90)
    choice = input("\nهل تريد تطبيق التحديث على القاعدة؟ (yes/no): ")
    
    if choice.lower() == 'yes':
        update_all_difficulty_scores()
    else:
        print("\n⏸️  تم إلغاء التحديث.")