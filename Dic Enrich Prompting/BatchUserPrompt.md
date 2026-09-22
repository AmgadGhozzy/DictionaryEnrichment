Process the following batch of raw English vocabulary. Act as a Senior Lexicographer to transform these inputs into high-fidelity, pedagogically rich entries for the wordEntries JSON array.

1. DATA PRESERVATION & INTEGRITY
You MUST preserve the following fields exactly as provided in the input:
id (Integer)
wordEn (String) - Maintain exact casing.
pos (String) - Ensure all definitions/examples match this specific part of speech.
cefrLevel (String) - This dictates the complexity of your generated content.
arabicAr (String) - Use this as the source of truth for the translit field.

2. ENRICHMENT WORKFLOW

A. Pedagogical Content
Examples Map: Generate exactly 6 CEFR-aligned sentences (A1, A2, B1, B2, C1, C2).
    A1/A2: Short, concrete context.
    C1/C2: Abstract, nuanced, or idiomatic context.
Definitions:
    English: Max 20 words. Simple vocabulary. Do not use the target word in the definition.
    Arabic: "White Arabic" (Podcast style). Explain the concept clearly, don't just give a synonym.
Mnemonics (mnemonicAr):
    Goal: Link the English sound/root to a familiar Arabic concept.
    Strict Formatting: English words must be in double quotes "". NEVER use parentheses () or brackets [] in the mnemonic.
    Example: "Venom": اربطها بكلمة "Vein" (وريد).. الـ "Venom" هو السُم اللي بيدخل في الـ "Vein" على طول.

B. Linguistic Precision
Phonetics (IPA):
    NO SLASHES or brackets. (e.g., əˈtʃiːv).
    Return null for phoneticUk if it is identical to phoneticUs.
Arabic Phonetics (phoneticAr):
    Transliterate the English pronunciation into Arabic script.
    MUST USE FULL TASHKEEL (e.g., سْكِدْجُول not سكيدجول).
Translit:
    Romanize the Arabic translation (arabicAr).
    If arabicAr is "يحقق / ينجز", return "Yuḥaqqiq / Yunjiz".

C. Semantic Logic
Primary Sense: Select the specific semantic anchor (e.g., Action, Emotion, Tool) that best fits the CEFR level provided.
Word Family: Only include derived forms (Noun/Verb/Adj/Adv). Return empty strings "" where no valid form exists.

3. TECHNICAL OUTPUT
Return a single JSON object containing the wordEntries array.
Null Handling:** Use JSON null for missing optional data. Use "" for missing string fields. Never omit a required field.

4. BATCH TO PROCESS

{{BATCH_JSON}}
