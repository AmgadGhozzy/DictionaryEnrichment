Process the following batch of raw English vocabulary. Act as a Senior Lexicographer to transform these inputs into high-fidelity, pedagogically rich entries for the wordEntries JSON array.

1. DATA PRESERVATION & INTEGRITY

You MUST preserve the following fields exactly as provided in the input:
- id (Integer)
- wordEn (String) - Maintain exact casing.
- pos (String) - Ensure all definitions/examples match this specific part of speech.
- cefrLevel (String) - This dictates the complexity of your generated content.
- arabicAr (String) - Use this as the source of truth for the translit field.

2. ENRICHMENT WORKFLOW

A. Pedagogical Content

Examples Map: Generate exactly 6 CEFR-aligned sentences (A1, A2, B1, B2, C1, C2).
- A1/A2: Short, concrete context.
- C1/C2: Abstract, nuanced, or idiomatic context.

Definitions:
- English: Max 20 words. Simple vocabulary. Do not use the target word in the definition.
- Arabic: "White Arabic" (Podcast style) WITHOUT tashkeel. Explain the concept clearly as if talking to a friend, don't just give a synonym.

Mnemonics (mnemonicAr):
- Goal: Link the English sound/root to a familiar Arabic concept.
- USE HALF TASHKEEL - strategic diacritics only where they enhance the memory hook.
- Strict Formatting: English words must be in double quotes "". NEVER use parentheses () or brackets [] in the mnemonic.
- Example: "Venom": اربطها بكلمة "Vein" "وريد".. الـ "Venom" هو السُم اللي بيدخل في الـ "Vein" على طول.
- Return null if the mnemonic would be forced or unhelpful.

B. Linguistic Precision

Phonetics (IPA):
- NO SLASHES or brackets. (e.g., əˈtʃiːv).
- Return null for phoneticUk if it is identical to phoneticUs.

Arabic Phonetics (phoneticAr):
- Transliterate the English pronunciation into Arabic script.
- USE HALF TASHKEEL - strategic vocalization for pronunciation clarity, not full tashkeel.
- Example: schedule -> سْكِدْجول (not سكيدجول or سُكِيدُجُولْ)

Translit:
- Romanize the Arabic translation (arabicAr).
- If arabicAr is "يحقق / ينجز", return "Yuḥaqqiq / Yunjiz".

C. Semantic Logic

Primary Sense: Select the specific semantic anchor (e.g., Action, Emotion, Tool) that best fits the CEFR level provided.

Word Family: Only include derived forms (Noun/Verb/Adj/Adv). Return empty strings "" where no valid form exists.

D. Multilingual Translations

CRITICAL: ALL translation fields (frenchFr, germanDe, spanishEs, chineseZh, russianRu, portuguesePt, japaneseJa, italianIt, turkishTr) MUST be populated.

- Provide accurate, natural translations for each language.
- NEVER return null for translation fields.
- Use appropriate grammatical forms for each language.
- For Chinese: Simplified characters + Pinyin in brackets
- For Japanese: Kanji/Kana + Romaji in brackets

E. AI Confidence Score

MANDATORY: You MUST provide an aiConfidence score (0.0 to 1.0) for EACH word entry.

Scoring Guidelines:
- 0.95-1.0: Highly confident - common word, clear meaning, excellent examples
- 0.85-0.94: Confident - solid enrichment with minor uncertainties
- 0.70-0.84: Moderate - some ambiguity in usage or translations
- 0.50-0.69: Low - difficult word, limited context, or uncertain translations
- Below 0.50: Very uncertain - flag for manual review

Consider:
- Clarity of word meaning and part of speech (30%)
- Quality and naturalness of example sentences (25%)
- Accuracy of multilingual translations (25%)
- Quality of pedagogical enrichment (20%)

3. TECHNICAL OUTPUT

Return a single JSON object containing the wordEntries array.

Null Handling:
- Use JSON null ONLY for: phoneticUk (if identical to US) and mnemonicAr (if not helpful).
- Use "" for missing word family forms.
- ALL translation fields MUST have values (never null).
- Never omit a required field.

4. BATCH TO PROCESS
