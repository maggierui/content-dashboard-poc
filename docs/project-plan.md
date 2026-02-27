# Project Plan: Content Performance Dashboard

## Purpose

Content editors currently have engagement metrics (page views, bounce rate, CTR) from Power BI but no signal on how well their articles perform in AI-powered search and chat experiences. This project bridges that gap by adding two AI-performance scores to the existing report, then surfacing everything in a local Streamlit dashboard.

The pipeline is designed to be run offline — scores are computed once (or periodically re-run) and stored as JSON files. The dashboard reads from a pre-computed enriched CSV, so there is no live LLM latency during browsing.

---

## Repository structure

```
content-dashboard/
├── common/                            # Shared utilities (copied from portal-copilots-content)
│   ├── batch.py
│   ├── knowledge_service.py
│   ├── prompts.py
│   ├── resolve_include_files.py
│   ├── send_openai_request.py
│   ├── token_provider.py
│   ├── data_models/
│   │   └── retrieval_models.py
│   └── prompts/
│       └── question_generator_article.md
│
├── project-content-improvement/       # AI Readiness grader (copied from portal-copilots-content)
│   ├── analyze_content.py
│   └── prompts/
│       ├── prompt-shared-foundation.md
│       └── dimensions/               # One prompt file per RAG dimension
│
├── project-question-ks-chunk-generator/  # Question generator (copied)
│   └── main.py
│
├── pipeline/                          # New orchestration scripts
│   ├── fetch_articles.py
│   ├── run_ai_readiness.py
│   ├── run_retrievability.py
│   └── merge_scores.py
│
├── data/
│   ├── cache/      # Gitignored — scraped article text (.txt per URL)
│   └── scores/     # Gitignored — JSON score files and batch JSONL files
│
├── docs/
│   ├── project-plan.md                # This file
│   ├── progress.txt
│   └── implementation_plans/
│       └── content-performance-dashboard.md
│
├── app.py                             # Streamlit dashboard
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## File-by-file reference

### Pipeline scripts (`pipeline/`)

#### `pipeline/fetch_articles.py`
**Purpose:** Scrape and cache article text from learn.microsoft.com.

- Reads a Power BI CSV export and extracts the `Url` column
- For each URL: HTTP GET the page, parse `<main>` / `#main-column` with BeautifulSoup, strip nav/scripts/styles
- Saves clean text to `data/cache/{url_slug}.txt`
- Skips already-cached files unless `--force` is passed
- Adds a 0.5-second delay between requests

**Input:** `--input <csv>` (must have a `Url` column)
**Output:** `data/cache/` directory populated with `.txt` files

---

#### `pipeline/run_ai_readiness.py`
**Purpose:** Grade each cached article across 10 RAG-quality dimensions and assign a High/Medium/Low band.

- Loads the CSV to get the list of URLs
- For each URL, reads the cached text and calls `analyze_dimensions()` from `project-content-improvement/analyze_content.py`
- **Direct mode** (≤50 articles or no `--batch` flag): runs all 10 dimensions concurrently via `asyncio.gather`
- **Batch mode** (`--batch` or auto-triggered for >50 articles): writes one JSONL entry per (article, dimension) pair → submits to Azure OpenAI Batch API → polls until complete → parses results
- Counts `len(recommendations)` from each dimension's output and sums across all 10
- Assigns band: High (0–3), Medium (4–8), Low (9+)
- Records the `weakest_dimension` (most recommendations) for tooltip display in the dashboard
- Supports incremental runs: existing scores are loaded and skipped

**Input:** `--input <csv>`, `--cache-dir`, `--output`
**Output:** `data/scores/ai_readiness_scores.json`

Band thresholds are configurable constants at the top of the file (`BAND_HIGH_MAX`, `BAND_MEDIUM_MAX`).

---

#### `pipeline/run_retrievability.py`
**Purpose:** Measure whether the Knowledge Service retrieves each article when asked relevant questions.

Three sub-steps:

**Step 2a — Question generation**
- Calls `send_response_request()` with the `question_generator_article` prompt
- Generates 5 natural-language questions + 5 BM25 keyword queries per article
- Direct mode for ≤50 articles; batch mode for larger sets
- Saves checkpoint to `data/scores/questions.json` (re-run with `--skip-qgen` to reuse)

**Step 2b — Knowledge Service queries**
- For each (article_url, question): calls `process_single_question(question, top_k=5)` from `common/knowledge_service.py`
- Uses `ThreadPoolExecutor` (max_workers=10) in batches of 10 articles, with a 4-second delay between batches
- Checks whether the article's URL path segment appears in any of the 5 returned chunk URLs

**Step 2c — Score calculation**
- `score = (retrieved_count / total_questions) × 100` → integer 0–100
- Supports incremental runs: already-scored URLs are skipped

**Input:** `--input <csv>`, `--cache-dir`, `--questions-file`, `--output`, `--skip-qgen`
**Output:** `data/scores/questions.json` (checkpoint), `data/scores/retrievability_scores.json`

---

#### `pipeline/merge_scores.py`
**Purpose:** Join AI Readiness and Retrievability scores onto the original Power BI CSV.

- Loads the original CSV as a pandas DataFrame
- Left-joins `ai_readiness_scores.json` on the `Url` column, adding:
  - `AIReadiness` — band string (High/Medium/Low)
  - `AIReadiness_WeakestDim` — dimension name with most recommendations
  - `AIReadiness_TotalRecs` — raw recommendation count
- Left-joins `retrievability_scores.json` on the `Url` column, adding:
  - `Retrievability` — 0–100 score
  - `Retrievability_Retrieved` — number of questions retrieved
  - `Retrievability_Total` — total questions tested
- Articles not yet scored get null values (partial pipeline runs are safe)
- Normalises trailing slashes on URLs before joining to avoid mismatches

**Input:** `--input <csv>`, `--ai-readiness`, `--retrievability`, `--output`
**Output:** `data/enriched_report.csv`

---

### Dashboard (`app.py`)

**Purpose:** Three-tab Streamlit app for browsing and querying the enriched data.

**Sidebar filters** (applied across all tabs):
- Date range (if a date column exists)
- Group / Category
- Topic Type
- AI Readiness band (multi-select)
- Retrievability score range (slider)

**Tab 1 — Data Table**
- Sortable, filterable data table using `st.dataframe` with column config
- `Retrievability` column rendered as a progress bar (0–100)
- URL column rendered as clickable links
- Download button for the filtered view as CSV

**Tab 2 — Portfolio Overview**
- Donut chart: AI Readiness band distribution
- Histogram: Retrievability score distribution
- Scatter plot: Retrievability (x-axis) vs PageViews (y-axis), colored by AI Readiness band
  - Vertical dashed line at score=40 marks the low-retrievability threshold
- Priority table: articles with Low AI Readiness AND Retrievability < 40, sorted by page views

**Tab 3 — Ask the Data**
- Chat input powered by `common/send_openai_request.py` → Azure OpenAI
- Context passed to the LLM includes: full DataFrame schema, per-column statistics, band counts, and up to 5 rows matching any article title/URL mentioned in the question
- Session state preserves chat history for the duration of the browser session

---

### Shared utilities (`common/`)

| File | Purpose |
|------|---------|
| `batch.py` | Azure OpenAI Batch API helpers: write JSONL, submit job, poll status, extract results |
| `knowledge_service.py` | Call the Microsoft Learn Knowledge Service; parse chunk URLs and content |
| `send_openai_request.py` | `send_response_request()` — single synchronous call to Azure OpenAI Responses API |
| `prompts.py` | `load_prompt()` — load a `.md` prompt file by name from `common/prompts/` |
| `resolve_include_files.py` | Resolve `!INCLUDE` directives in markdown files (used by source pipeline, carried over) |
| `token_provider.py` | Thread-safe `DefaultAzureCredential` token cache for Knowledge Service bearer auth |
| `data_models/retrieval_models.py` | Dataclasses: `ArticlePerformance`, `RetrievalQuestion`, `RetrievedChunk` |
| `prompts/question_generator_article.md` | Prompt that instructs the LLM to generate 5 questions + 5 BM25 variants per article |

---

### AI Readiness grader (`project-content-improvement/`)

| File | Purpose |
|------|---------|
| `analyze_content.py` | `analyze_dimensions()` — async function that fans out 10 concurrent LLM calls, one per dimension; returns `{dimension: {data, raw_response}}` |
| `prompts/prompt-shared-foundation.md` | System prompt explaining what RAG is and how to score conservatively |
| `prompts/dimensions/dim-*.md` | One prompt per dimension defining what to look for and what format to return |

---

## End-to-end workflow

```
Power BI CSV export
        │
        ▼
[fetch_articles.py]
  HTTP scrape each URL → clean text → data/cache/{slug}.txt
        │
        ├──────────────────────────────┐
        ▼                              ▼
[run_ai_readiness.py]        [run_retrievability.py]
  LLM grades 10 dims           LLM generates 10 questions
  per article (async           per article → queries KS
  or batch API)                → checks if article retrieved
        │                              │
        ▼                              ▼
  ai_readiness_scores.json    retrievability_scores.json
        │                              │
        └──────────────┬───────────────┘
                       ▼
              [merge_scores.py]
          Left-join both score files
          onto original Power BI CSV
                       │
                       ▼
               enriched_report.csv
                       │
                       ▼
              [streamlit run app.py]
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   Data Table   Portfolio       Ask the Data
  (filterable)  Overview       (LLM chat over
                (charts)        the dataset)
```

---

## Credentials

Two distinct authentication systems are used:

| System | Credential | Used by |
|--------|-----------|---------|
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_KEY` (or `DefaultAzureCredential`) | `run_ai_readiness.py`, `run_retrievability.py` (question gen), `app.py` (chat tab) |
| Microsoft Learn Knowledge Service | `DefaultAzureCredential` scoped to `https://learn.microsoft.com/.default` | `common/knowledge_service.py` — requires `az login` with a Microsoft tenant account |

---

## Design decisions

| Decision | Rationale |
|----------|-----------|
| Band (High/Medium/Low) not numeric score | LLM only flags high-confidence issues; a raw count is more reliable than a hallucinated rating |
| Incremental pipeline runs | Large batches can fail midway; every script resumes from where it left off |
| 10 questions per article | 5 concise questions test semantic retrieval; 5 BM25 variants test keyword matching |
| Pre-computed CSV, not live scoring | Avoids LLM latency in the dashboard UI; pipeline re-runs can be scheduled overnight |
| Left join on merge | All original CSV rows are preserved even if some articles have not been scored yet |
| `ThreadPoolExecutor` for KS queries | The Knowledge Service handles concurrent requests well; parallelism cuts run time significantly |
