YOUR TASK
Process the following batch of raw English vocabulary and transform each entry into a complete, pedagogically rich word object for the wordEntries JSON array.

You are acting as a Senior Lexicographer with expertise in:
Linguistic analysis (phonetics, morphology, semantics)
CEFR-aligned pedagogy (A1-C2 curriculum design)
Cross-linguistic transfer (English ↔ Arabic)
Multilingual lexicography (10 languages)

WORKFLOW OVERVIEW

Step 1: DATA PRESERVATION ✅
CRITICAL: The following fields are immutable — preserve them exactly as provided:

| Field | Type | Rule |
|-------|------|------|
| id | Integer | Unique identifier - NEVER change |
| wordEn | String | Exact spelling & casing - NEVER modify |
| pos | String | Part of speech - All examples MUST match this |
| cefrLevel | String | Proficiency level - Dictates content complexity |

Additional metadata to preserve (if present):
fromOxford (Integer) - Oxford 3000/5000 indicator
rank (Integer) - Frequency ranking
frequency (Float) - Corpus frequency
category (String) - Only override if clearly incorrect
syllabify (String) - Syllable breakdown

Step 2: LINGUISTIC ENRICHMENT 🎯

A. Phonetic Transcription

phoneticUs (American IPA)
Format: Plain IPA symbols
CRITICAL: NO slashes / or brackets [ ]
Example: ✅ əˈtʃiːv | ❌ /əˈtʃiːv/
Required: NEVER null or empty

phoneticUk (British IPA)
Format: Plain IPA symbols (no slashes/brackets)
Rule: Return null if identical to phoneticUs
Example:
  schedule: US≠UK → Provide both
  cat: US=UK → Return null for UK

phoneticAr (Arabic Phonetic Guide)
Purpose: Help Arabic speakers pronounce the English word
Method: Transliterate English pronunciation into Arabic script
MANDATORY: Include full tashkeel (vocalization marks)
Examples:
  achieve → أَتْشِيفْ (NOT أتشيف)
  schedule → سْكِدْجُول (NOT سكيدجول)
  venom → فِنُمْ (NOT فينوم)

translit (Arabic Translation Romanization)
Purpose: Romanize the Arabic translation (from arabicAr field)
NOT: Romanization of the English word
Method: Standard Arabic romanization with diacritics
Rule: If arabicAr has multiple translations separated by /, provide corresponding romanizations
Examples:
  arabicAr: "يحقق" → translit: "yuḥaqqiq"
  arabicAr: "يحقق / ينجز" → translit: "yuḥaqqiq / yunjiz"

B. Definitions & Explanations

definitionEn (English Definition)
Length: Maximum 20 words
Vocabulary: Use high-frequency words (top 1000 list)
Rule: Do NOT use the target word in its own definition
Style: Clear, simple, learner-friendly
Example:
  ✅ achieve → "To successfully complete or reach a goal through effort"
  ❌ achieve → "The act of achieving something" (circular)

definitionAr (Arabic Conceptual Explanation)
Style: "White Arabic" (فصحى بيضاء) - accessible to MSA and dialect speakers
Approach: Explain the concept, not just a synonym
Tone: Conversational, podcast-style explanation
Example:
  ✅ schedule → "خطة أو جدول زمني بيحدد المواعيد والأنشطة اللي هتعملها في وقت معين"
  ❌ schedule → "جدول" (too brief, not explanatory)

usageNote (Pedagogical Guidance)
Explain nuances, restrictions, or common mistakes
Provide collocation guidance
Clarify differences from similar words
Example:
  high vs tall: "Use 'high' for mountains, buildings. Use 'tall' for people, trees."
  achieve: "Collocates with abstract goals (achieve success/dreams). For concrete tasks, use 'complete' or 'finish'."

C. Difficulty Assessment

difficultyScore (Learning Difficulty: 1-10)
Rate based on:
Concreteness (abstract = higher)
Spelling complexity (irregular = higher)
Frequency (rare = higher)
Semantic nuance (polysemy = higher)

Scale:
1-2: Basic concrete (cat, red, eat, go)
3-4: Everyday words (table, run, happy)
5-6: Abstract/professional (achieve, schedule, maintain)
7-8: Complex/technical (phenomenon, synthesize)
9-10: Rare/highly nuanced (epistemology, paradigmatic)

Step 3: PEDAGOGICAL CONTENT 📚

A. CEFR-Scaled Example Sentences

Generate EXACTLY 6 sentences (one per level: A1, A2, B1, B2, C1, C2)

Requirements:
Use the word in context matching its pos (part of speech)
Scale linguistic complexity with CEFR level
Ensure cultural neutrality and universal relatability
Keep within appropriate length for each level

Level Guidelines:

| Level | Complexity | Length | Example |
|-------|-----------|--------|---------|
| A1 | Simple present, SVO | 5-8 words | "She achieves her goal." |
| A2 | Past/future, basic description | 6-10 words | "He achieved success last year." |
| B1 | Compound sentence, everyday context | 10-15 words | "The team achieved excellent results through consistent effort." |
| B2 | Complex structure, professional context | 12-18 words | "Despite facing challenges, the project achieved its objectives ahead of schedule." |
| C1 | Nuanced, idiomatic, implied meanings | 15-20 words | "The research achieved groundbreaking insights that challenged existing frameworks." |
| C2 | Literary, academic, sophisticated | 18-25 words | "His work achieved a synthesis of disparate traditions, transcending conventional boundaries." |

B. Creative Memory Hooks

mnemonicAr (Arabic Mnemonic)

Goal: Create a vivid association between English sound/spelling and meaning

Method:
Link English sound or root to Arabic concept
Use wordplay, visual imagery, or phonetic similarity
Keep simple and conversational

CRITICAL FORMATTING:
English words MUST be in double quotes ""
NEVER use parentheses () or brackets []
Use .. or - for separation

Examples:

✅ CORRECT:
venom → اربطها بكلمة "Vein" "وريد".. الـ "Venom" هو السُم اللي بيدخل في الـ "Vein" على طول
evaluate → في نصها كلمة "Value".. إنت بتعمل إيه؟ بتحدد القيمة
schedule → اسمع الكلمة.. فيها "School".. في المدرسة دايماً فيه "Schedule" جدول

❌ WRONG:
venom → اربطها بكلمة Vein (وريد) ← Missing quotes, has parentheses
evaluate → (تحتوي على Value) ← Has parentheses

Null Rule: Return null if:
No natural mnemonic exists
Association feels forced
Would confuse rather than help

Step 4: SEMANTIC ANALYSIS 🧭

A. Classification

category (Thematic Folder)
Assign to ONE theme:
Travel & Movement
Work & Business
Health & Body
Food & Cooking
Emotions & States
Education & Learning
Technology & Science
Relationships & Social
Nature & Environment
Time & Schedules

primarySense (Semantic Anchor)
Choose ONE from enum:
Action, Process, Movement, State, Condition, Change, Relation
Time, Event, Quantity, Measure, Quality, Attribute, Emotion
Concept, Communication, Object, Tool, Person, Place

Usage: Disambiguates polysemy
bank (building) → Place
bank (riverside) → Relation

semanticTags (Searchable Hashtags)
Provide 3-5 specific tags:
Format: ["#Finance", "#Money", "#Banking"]
Enable cross-category connections

register (Social Context)
Choose ONE: Formal, Informal, Neutral, Archaic, Slang

B. Morphological Family

wordFamily (Derived Forms)
Provide only derived forms (not inflections):

{
  "noun": "achievement",  // or "" if none
  "verb": "achieve",
  "adj": "achievable",
  "adv": ""              // empty string if none
}

Rules:
❌ Do NOT include inflections (achieving, achieved)
✅ DO include forms with different meanings
Use "" for non-existent forms
Gerunds only if distinct nouns (e.g., swimming as sport)

C. Related Vocabulary

collocations (Natural Pairings)
List 3-5 high-frequency combinations:
Example: ["achieve success", "achieve a goal", "achieve results"]

synonyms (Similar Words)
Up to 5 common alternatives:
Example: ["accomplish", "attain", "reach", "realize"]

antonyms (Opposites)
Up to 3 clear opposites:
Example: ["fail", "forfeit", "lose"]
Use [] if none exist

relatedWords (Semantic Field)
{
  "en": ["success", "goal", "effort", "result"],
  "ar": ["نجاح", "هدف", "جهد", "نتيجة"]
}
Arabic list must match English list 1:1

Step 5: MULTILINGUAL TRANSLATIONS 🌍

A. Standard Languages
Provide most common equivalent:
frenchFr: Standard French
germanDe: Standard German
spanishEs: Spanish (Latin American preferred)
russianRu: Standard Russian
portuguesePt: Portuguese (Brazilian preferred)
italianIt: Standard Italian
turkishTr: Standard Turkish

B. Special Romanization Formats

chineseZh (Simplified + Pinyin)
Format: 汉字 (Pīnyīn)
Example: 你好 (Nǐ hǎo), 实现 (shíxiàn)

japaneseJa (Kanji/Kana + Romaji)
Format: 漢字 (Romaji)
Example: 猫 (Neko), 達成する (tassei suru)

C. Primary Arabic Translation

arabicAr (Main Arabic Translation)
Provide most common translation
Separate multiple meanings with  / 
Example: يحقق / ينجز
This is the source for translit

Step 6: QUALITY CONTROL ✅

aiConfidence (Self-Assessment: 0.0-1.0)
Rate your certainty:
0.9-1.0: Highly confident (common word, clear data)
0.7-0.9: Confident (standard usage)
0.5-0.7: Moderate (some ambiguity)
0.3-0.5: Low (rare word, uncertain)
0.0-0.3: Very uncertain (incomplete/guess)

Pre-Submission Checklist:
All required fields present
Immutable fields unchanged (id, wordEn, pos, cefrLevel)
phoneticUs provided (never empty)
phoneticAr has full tashkeel
translit romanizes arabicAr (not English)
examples has exactly 6 entries
definitionEn under 20 words
mnemonicAr uses double quotes (no parentheses)
arabicAr translation provided
aiConfidence reflects actual certainty

NULL HANDLING RULES

| Scenario | Use |
|----------|-----|
| phoneticUk same as US | null (JSON null) |
| No good mnemonic | null (JSON null) |
| Missing word family form | "" (empty string) |
| No antonyms | [] (empty array) |

NEVER write the string "null" — use actual JSON null.

OUTPUT FORMAT REQUIREMENT

YOU MUST CALL THE enrich_words FUNCTION

Your response MUST be a function call with this structure:
{
  "wordEntries": [
    {
      "id": 1,
      "wordEn": "achieve",
      "pos": "verb",
      "cefrLevel": "B1",
      "difficultyScore": "5",
      "phoneticUs": "əˈtʃiːv",
      "phoneticUk": null,
      "phoneticAr": "أَتْشِيفْ",
      "translit": "yuḥaqqiq",
      "definitionEn": "To successfully complete or reach a goal through effort",
      "definitionAr": "إنجاز هدف أو غاية بعد جهد وعمل",
      "usageNote": "Collocates with abstract goals. For concrete tasks, use 'complete'.",
      "category": "Work & Success",
      "primarySense": "Action",
      "semanticTags": ["#Success", "#Goals", "#Achievement"],
      "register": "Neutral",
      "mnemonicAr": "الكلمة تبدأ بـ \"A\" زي \"أنجز\".. والـ \"achieve\" معناها الإنجاز",
      "examples": {
        "A1": "She achieves her goal.",
        "A2": "He achieved success last year.",
        "B1": "The team achieved excellent results through hard work.",
        "B2": "Despite facing challenges, they achieved their objectives.",
        "C1": "The research achieved groundbreaking insights into the phenomenon.",
        "C2": "His work achieved a synthesis of disparate theoretical frameworks."
      },
      "collocations": ["achieve success", "achieve a goal", "achieve results"],
      "synonyms": ["accomplish", "attain", "reach", "realize"],
      "antonyms": ["fail", "forfeit"],
      "relatedWords": {
        "en": ["success", "goal", "accomplishment", "effort"],
        "ar": ["نجاح", "هدف", "إنجاز", "جهد"]
      },
      "wordFamily": {
        "noun": "achievement",
        "verb": "achieve",
        "adj": "achievable",
        "adv": ""
      },
      "arabicAr": "يحقق / ينجز",
      "frenchFr": "réaliser",
      "germanDe": "erreichen",
      "spanishEs": "lograr",
      "chineseZh": "实现 (shíxiàn)",
      "russianRu": "достигать",
      "portuguesePt": "alcançar",
      "japaneseJa": "達成する (tassei suru)",
      "italianIt": "raggiungere",
      "turkishTr": "başarmak",
      "aiConfidence": 0.95
    }
  ]
}

BATCH DATA TO PROCESS

{{BATCH_JSON}}

Begin enrichment now. Call the enrich_words function with your complete response.