# POC: Content Performance Dashboard with AI Readiness + Retrievability

## Context

The content team has an existing Power BI engagement report (PageViews, BounceRate, ClickThroughRate, etc.) that they export as CSV. The goal is to enrich this data with two new AI-performance lenses so editors can prioritize improvements based on both human engagement AND AI retrieval quality:

- **AI Readiness** — How well is an article structured for RAG retrieval? (using existing 10-dimension grader in `project-content-improvement/`)
- **Retrievability** — When a user asks a question this article should answer, does the Knowledge Service actually return it? (using existing question-gen + KS pipeline)

The deliverable is a **Streamlit app** with a filterable data table and a natural-language chat interface, running locally from a pre-computed enriched CSV.

---

## Important Scoring Notes

### AI Readiness is recommendation-count-based (not a numeric score)
`analyze_content.py` outputs a `recommendations[]` array per dimension — it does NOT output a numeric rating. The LLM is instructed to only flag **high-confidence issues**. Fewer recommendations = better.

**Proposed bands** (configurable constant, to be tuned after first run):
| Band | Total recommendations across 10 dims | Interpretation |
|------|--------------------------------------|----------------|
| **High** | 0–3 | Well-optimized for RAG retrieval |
| **Medium** | 4–8 | Meaningful gaps; improvement recommended |
| **Low** | 9+ | Significant RAG issues; prioritize for editing |

### Retrievability is a 0–100 hit-rate score
`calculate_scores()` awards 1 point per retrieved question (5 questions → max 5.0). Multiply × 20 → 0–100. A question is "retrieved" if the article's URL path appears in any of the top-5 Knowledge Service chunks.

---

## Project Directory: `C:\Github\content-dashboard`

Standalone folder — no dependency on the original repo after setup.

### Directory Structure

```
C:\Github\content-dashboard/
├── common/                                 # Copied from portal-copilots-content
│   ├── __init__.py
│   ├── batch.py
│   ├── knowledge_service.py
│   ├── send_openai_request.py
│   ├── prompts.py
│   ├── resolve_include_files.py
│   ├── token_provider.py
│   ├── data_models/
│   │   ├── __init__.py
│   │   └── retrieval_models.py
│   └── prompts/
│       └── question_generator_article.md
├── project-content-improvement/            # Copied from portal-copilots-content
│   ├── __init__.py
│   ├── analyze_content.py
│   └── prompts/
│       ├── prompt-shared-foundation.md
│       └── dimensions/
│           ├── dim-heading-hierarchy.md
│           ├── dim-chunk-autonomy.md
│           ├── dim-context-completeness.md
│           ├── dim-entity-normalization.md
│           ├── dim-disambiguation.md
│           ├── dim-semantic-density.md
│           ├── dim-structured-data-utilization.md
│           ├── dim-query-answer-alignment.md
│           ├── dim-redundancy-efficiency.md
│           └── dim-cross-section-integrity.md
├── project-question-ks-chunk-generator/    # Copied from portal-copilots-content
│   ├── __init__.py
│   └── main.py
├── pipeline/
│   ├── __init__.py
│   ├── fetch_articles.py           # NEW - HTML scraper
│   ├── run_ai_readiness.py         # NEW - AI Readiness grader
│   ├── run_retrievability.py       # NEW - Q-gen + KS hit-rate
│   └── merge_scores.py             # NEW - CSV enrichment
├── docs/
│   └── implementation_plans/
│       └── content-performance-dashboard.md
├── data/
│   ├── cache/                      # gitignored - article text files
│   ├── scores/                     # gitignored - JSON score files
│   └── .gitkeep
├── app.py                          # NEW - Streamlit app (3 tabs)
├── requirements.txt                # NEW
├── .env.example                    # NEW
└── .gitignore
```

---

## Pipeline Steps

### Step 0 — Data Preparation
**File:** `pipeline/fetch_articles.py`

- Input: Power BI CSV export (must have a `Url` column)
- For each URL: HTTP GET the learn.microsoft.com page, parse `<main>` / `#main-column` with BeautifulSoup, strip scripts/nav/styles → clean article text
- Cache each article as `data/cache/{url_slug}.txt` (skip re-fetch if cached)
- Output: populated `data/cache/` directory

```bash
python pipeline/fetch_articles.py --input data/sample_engagement.csv
```

---

### Step 1 — AI Readiness Pipeline
**File:** `pipeline/run_ai_readiness.py`

**Reuses:** `project-content-improvement/analyze_content.py` → `analyze_dimensions()`

**Process:**
1. For each article in cache, call `analyze_dimensions()` across all 10 dimensions
2. For **≤50 articles**: run directly via async (10 dims in parallel per article)
3. For **>50 articles**: write one JSONL request per article-dimension pair → submit to Azure OpenAI Batch API → parse results
4. Count `len(recommendations)` across all 10 dims
5. Assign band: High/Medium/Low per thresholds above
6. Record `weakest_dimension` = dimension with most recommendations

**Band thresholds (configurable in `run_ai_readiness.py`):**
```python
BAND_HIGH_MAX = 3    # 0–3   → High
BAND_MEDIUM_MAX = 8  # 4–8   → Medium
# 9+                          → Low
```

**Output:** `data/scores/ai_readiness_scores.json`
```json
{
  "https://learn.microsoft.com/...": {
    "band": "Medium",
    "total_recommendations": 6,
    "weakest_dimension": "chunk_autonomy",
    "by_dimension": { "heading_hierarchy": 1, "chunk_autonomy": 3 }
  }
}
```

```bash
python pipeline/run_ai_readiness.py --input data/sample_engagement.csv
python pipeline/run_ai_readiness.py --input data/sample_engagement.csv --batch  # for >50 articles
```

---

### Step 2 — Retrievability Pipeline
**File:** `pipeline/run_retrievability.py`

#### Step 2a: Generate questions per article
- Uses `common/prompts/question_generator_article.md` via `send_response_request()`
- For each article: generates 5 concise questions + 5 BM25 keyword queries
- >50 articles: batch API path via `common/batch.py`
- Saves checkpoint to `data/scores/questions.json`

#### Step 2b: Query Knowledge Service
- For each (article_url, question): call `process_single_question(question, top_k=5)`
- Check if `article_url`'s path segment appears in any returned chunk URL
- `ThreadPoolExecutor` (max_workers=10) with batch delays

#### Step 2c: Calculate hit-rate score
- `score = (retrieved_count / total_questions) × 100` → integer 0–100

**Output:** `data/scores/retrievability_scores.json`
```json
{
  "https://learn.microsoft.com/...": {
    "score": 60,
    "retrieved_count": 6,
    "total_questions": 10,
    "questions": [
      {"text": "How do I...", "retrieved": true},
      ...
    ]
  }
}
```

```bash
python pipeline/run_retrievability.py --input data/sample_engagement.csv
python pipeline/run_retrievability.py --input data/sample_engagement.csv --skip-qgen  # skip question gen
```

---

### Step 3 — Score Merging
**File:** `pipeline/merge_scores.py`

- Load Power BI CSV → pandas DataFrame
- Left-join AI Readiness scores on `Url` column
- Left-join Retrievability scores on `Url` column
- New columns: `AIReadiness`, `AIReadiness_WeakestDim`, `AIReadiness_TotalRecs`, `Retrievability`, `Retrievability_Retrieved`, `Retrievability_Total`
- Articles not yet scored get null values (partial runs are OK)
- Output: `data/enriched_report.csv`

```bash
python pipeline/merge_scores.py --input data/sample_engagement.csv
```

---

### Step 4 — Streamlit Dashboard
**File:** `app.py`

**Three-tab layout:**

#### Tab 1: "Data Table"
- Sidebar filters: Date range, Group, TopicType, AI Readiness band (multi-select), Retrievability range slider
- Full sortable table with all original CSV columns + 2 new score columns
- `AIReadiness`: progress-style column config with color-coded values
- `Retrievability`: progress column (0–100)
- Download button for filtered CSV export

#### Tab 2: "Portfolio Overview"
- Donut chart: AI Readiness band distribution
- Histogram: Retrievability score distribution
- Scatter plot: Retrievability (x) vs PageViews (y), colored by AI Readiness band
- Priority table: articles with Low AI Readiness AND Retrievability < 40

#### Tab 3: "Ask the Data"
- Chat interface powered by Azure OpenAI
- Context: DataFrame schema + key stats + relevant rows if article mentioned
- Example queries shown in expander
- Persistent chat history in session state

```bash
streamlit run app.py
```

---

## Run Order

```bash
# 1. Copy .env.example to .env and fill in your Azure OpenAI credentials
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Drop your Power BI CSV export into data/sample_engagement.csv

# 4. Fetch and cache article text (~5 min for 300 articles)
python pipeline/fetch_articles.py --input data/sample_engagement.csv

# 5. Run AI Readiness grading (overnight for 300 articles via batch API)
python pipeline/run_ai_readiness.py --input data/sample_engagement.csv

# 6. Run Retrievability pipeline (~1-2 hrs for 300 articles × 10 questions)
python pipeline/run_retrievability.py --input data/sample_engagement.csv

# 7. Merge all scores into enriched CSV
python pipeline/merge_scores.py --input data/sample_engagement.csv

# 8. Launch dashboard
streamlit run app.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_KEY` | Yes (or use MSI) | API key (omit to use DefaultAzureCredential) |
| `DEPLOYMENT_NAME` | No | Chat model deployment (default: `gpt-5-mini`) |
| `BATCH_DEPLOYMENT_NAME` | No | Batch model deployment (default: `gpt-5-batch`) |
| `AZURE_OPENAI_API_VERSION` | No | API version (default: `2025-04-01-preview`) |

---

## Verification Plan

1. **Unit test article fetching**: Run `fetch_articles.py` on 5 known URLs, verify cached text is non-empty and readable
2. **Spot-check AI Readiness**: Pick 3 articles (one clearly high-quality, one borderline, one known problem) — verify bands match expectation
3. **Spot-check Retrievability**: Pick an article, manually run its questions through learn.microsoft.com search, verify pipeline score matches manual test
4. **Dashboard smoke test**: Load enriched CSV in Streamlit, verify all 3 tabs render, filters work, chat responds to "Which articles have Low AI Readiness?"
5. **Chat quality check**: Ask 3 portfolio questions and 2 article-specific questions — verify responses cite actual data from the DataFrame

---

## Design Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| Recommendation count → band (not numeric score) | The LLM is instructed to only flag high-confidence issues, so count is more reliable than a hallucinated number |
| Incremental runs (skip already-scored) | Large batches can fail partway; both pipelines resume from where they left off |
| 10 questions per article (5 concise + 5 BM25) | Mirrors existing pipeline; BM25 variants improve recall on keyword-heavy queries |
| `ThreadPoolExecutor` for KS queries | KS has good throughput; parallel queries are faster than sequential |
| Pre-computed CSV → Streamlit (not live scoring) | Avoids LLM latency in the dashboard; editors can re-run overnight |
| Left-join merge | Preserves all rows from the original CSV even if some articles aren't scored yet |
