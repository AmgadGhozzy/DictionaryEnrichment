# DictionaryEnrichment

AI lexical-enrichment pipeline: raw English vocabulary → high-fidelity pedagogical JSON (header in `lexical_engine.py:1`: "Lexical Enrichment Engine v1.0 … transforming raw lexical entries into high-fidelity pedagogical knowledge objects").

## What it generates per word

Per `BatchUserPrompt.md` / `SystemPrompt.md`: exact-preserved `id`, `wordEn`, `pos`, `cefrLevel`, `arabicAr` + 6 CEFR-graded examples (A1→C2), EN definition (≤20 words, no target word), White-Arabic definition, AR mnemonic (EN words in `"double quotes"`, never `()`/`[]`), IPA with **no slashes** (`phoneticUk: null` when identical to US), Arabic transliteration.

## Layout

- `lexical_engine.py` — production engine (SQLite, `google.genai`, local/Colab envs)
- `DictionaryEnrichment.py` — threaded batch runner (ThreadPoolExecutor, Colab Drive mount)
- `finalDictEnrich.py`, `DictionaryFull.sql` — final assembly / full DB
- `oxford-3000.csv`, `oxford-5000.csv` — frequency-ranked source lists
- `BatchUserPrompt.md`, `SystemPrompt.md` — canonical prompts (source of truth for the schema)

## Run

```powershell
$env:PYTHONIOENCODING='utf-8'
python finalDictEnrich.py   # or import lexical_engine in Colab
```

Sister repo with the governed/evaluated successor: `LexicalEnrichment` (golden-set + validator contracts).
