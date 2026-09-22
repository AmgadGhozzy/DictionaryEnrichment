-- High-Quality Linguistic & Learning-Oriented Schema
-- Designed for Android Room + AI Enrichment Pipelines
-- One linguistic entry per (word + POS)

CREATE TABLE wordsMaster (

    -- PILLAR 1: IDENTITY & PRIORITY (The Engine)
    id INTEGER PRIMARY KEY AUTOINCREMENT,         -- Unique ID for word-state mapping and SRS tracking.
    wordEn TEXT NOT NULL,                          -- Raw English word (e.g., "Scale", "Manage").
    pos TEXT NOT NULL,                             -- Part of Speech: adj, adv, conj, det, excl, modal, noun, num, prep, pron, verb.
    cefrLevel TEXT CHECK (
        cefrLevel IN ('A1','A2','B1','B2','C1','C2')
    ),                                             -- Proficiency level: A1 to C2.
    fromOxford INTEGER NOT NULL DEFAULT 0 CHECK (
        fromOxford IN (0,1)
    ),                                             -- Flag (0/1): 1 if word is in Oxford 3000/5000 lists.
    rank INTEGER,                                  -- Global importance rank (1 to 6500+). Lower is more important.
    frequency INTEGER CHECK (
        frequency BETWEEN 1 AND 6
    ),                                             -- Normalized frequency 1-6: (1=Essential/A1, 6=Advanced/C2).
    difficultyScore INTEGER CHECK (
        difficultyScore BETWEEN 1 AND 10
    ),                                             -- Calculated 1-10: (Length + Syllables + CEFR weight). 10 is hardest.

    -- PILLAR 2: PHONETICS & SPEECH (The Sound System)
    phoneticUs TEXT,                               -- American IPA (e.g., ˈmænɪdʒ) without slashes.
    phoneticUk TEXT,                               -- British IPA. Null if identical to phoneticUs to save space use ?.let to not tshow on ui.
    phoneticAr TEXT,                               -- English pronunciation in Arabic script with full Tashkeel (e.g., مَانِيدْجْ).
    translit TEXT,                                 -- Romanized Arabic meaning (e.g., yudīr) for cross-language and unArabic learners. 
                                                   -- Must align 1:1 with arabicAr.
    syllabify TEXT,                                -- Syllable breakdown using bullet separator (e.g., man•age). Null if 1 syllable.

    -- PILLAR 3: MEANING & CONTEXT (The Semantic System)
    definitionEn TEXT NOT NULL,                    -- Simple, learner-friendly English definition for immersion learning.
    definitionAr TEXT,                             -- Conceptual Arabic explanation of meaning (not a literal translation).
    usageNote TEXT,                                -- Practical pedagogical advice: "Commonly used in spoken English instead of X."
    category TEXT,                                 -- Thematic folder: Actions & Processes, Feelings & Emotions, Food & Drink, etc.
    primarySense TEXT CHECK (
        primarySense IN (
            'Action','Process','Movement','State','Change','Relation',
            'Time','Quantity','Measure','Quality','Emotion','Idea',
            'Communication','Object','Person','Place'
        )
    ),                                             -- The Single specific "Sense Anchor" to disambiguate. NOT a topic can expand.
    semanticTags TEXT,                             -- Search hashtags for cross-discovery [e.g., "#Business", "#Finance", "#Tech", "#Health"].
    register TEXT CHECK (
        register IN ('Formal','Informal','Neutral','Archaic','Slang')
    ),                                             -- Social tone: Formal, Informal, Neutral, Archaic, Slang.
    
    -- PILLAR 4: MNEMONICS & MEMORY (The Retention System)
    mnemonicAr TEXT,                               -- A creative memory hook in White Arabic (linking sound, root, or story). 
                                                   -- Recommended for B1-C2. Vivid, short, and engaging. Avoid definitions.

    -- PILLAR 5: RELATIONAL DATA (JSON Structures)
    examples TEXT,                                 -- JSON Map by CEFR: {"A1": "text", "B2": "text"}. 
                                                   -- Rules: 1) Match CEFR 2) Use simple vocab 3) Reflect primarySense.
    collocations TEXT,                             -- JSON Array: ["manage a team", "manage a crisis", "manage to finish"].
    synonyms TEXT,                                 -- JSON Array: ["run", "handle", "administer"] (Max 5).
    antonyms TEXT,                                 -- JSON Array: ["fail", "mismanage"] (Max 3).
    relatedWords TEXT,                             -- JSON Map: {"en": ["investor", "profit"], "ar": ["مستثمر", "ربح"]}
    wordFamily TEXT,                               -- JSON Map: Derived forms ONLY. No inflections. 
                                                   -- {"noun": "management", "verb": "manage", "adj": "manageable", "adv": "managerially"}
         
    -- PILLAR 6: INTERNATIONALIZATION (Global Reach)
    arabicAr TEXT,                                 -- Primary Arabic translation (the most common meaning). 
                                                   -- Single or hyphen-separated list. Must align with translit.
    frenchFr TEXT,                                 -- French translation.
    germanDe TEXT,                                 -- German translation.
    spanishEs TEXT,                                -- Spanish translation.
    chineseZh TEXT,                                -- Chinese translation (Simplified + Pinyin).
    russianRu TEXT,                                -- Russian translation.
    portuguesePt TEXT,                             -- Portuguese translation.
    japaneseJa TEXT,                               -- Japanese translation (Kanji + Romaji).
    italianIt TEXT,                                -- Italian translation.
    turkishTr TEXT,                                -- Turkish translation.

    -- CONSTRAINTS
    UNIQUE (wordEn, pos)                           -- Ensures one linguistic entry per word-category pair.
);

-- PERFORMANCE OPTIMIZATION INDEXES
CREATE INDEX idx_words_wordEn ON wordsMaster(wordEn);
CREATE INDEX idx_words_wordEn_pos ON wordsMaster(wordEn, pos);
CREATE INDEX idx_words_rank ON wordsMaster(rank);
CREATE INDEX idx_words_arabicAr ON wordsMaster(arabicAr);