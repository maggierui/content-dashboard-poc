# Content Performance Dashboard

A Streamlit dashboard that enriches a Power BI engagement report with two AI-performance lenses, giving content editors a unified view of how articles perform for both human readers and AI retrieval systems.

---

## What it does

Your Power BI CSV export tells you how humans engage with articles (page views, bounce rate, click-through rate, etc.). This project adds two new signals on top of that:

| Signal | What it measures | Output |
|--------|-----------------|--------|
| **AI Readiness** | How well an article is structured for RAG retrieval — evaluated across 10 dimensions by an LLM | **High / Medium / Low** band + per-article HTML report |
| **Retrievability** | When a user asks a question this article should answer, does the Knowledge Service actually return it? | **0–100** hit-rate score |

The result is a single enriched CSV that the Streamlit app visualises in three tabs:

1. **Data Table** — Filterable, sortable table with all original columns plus the two new scores and an AI Report link column
2. **Portfolio Overview** — Charts showing distribution and a scatter plot that reveals the "high traffic but poorly retrievable" quadrant
3. **Ask the Data** — Natural-language chat interface powered by Azure OpenAI

Each scored article also gets a self-contained **HTML report** (`data/reports/{slug}.html`) with a dimension breakdown, full recommendation details (evidence / action / impact), and a direct "Open in VS Code Web" button for contributors to edit the source file.

---

## Metrics reference

### AI Readiness bands

Scored by counting LLM recommendations across 10 RAG-quality dimensions. Fewer recommendations = better-optimized content.

| Band | Total recommendations | Meaning |
|------|-----------------------|---------|
| **High** | 0–3 | Well-structured for RAG retrieval |
| **Medium** | 4–8 | Meaningful gaps; improvement recommended |
| **Low** | 9+ | Significant RAG issues; prioritize for editing |

The 10 dimensions evaluated:

| Dimension | What it checks |
|-----------|---------------|
| Heading Hierarchy | Clear H1→H2→H3 structure that helps chunkers split meaningfully |
| Chunk Autonomy | Each section makes sense in isolation, without surrounding context |
| Context Completeness | Key terms and prerequisites are explained within the article |
| Entity Normalization | Consistent naming for products, features, and concepts |
| Disambiguation | Ambiguous terms or pronouns are resolved explicitly |
| Semantic Density | Information-to-noise ratio; avoids filler |
| Structured Data Utilization | Tables and lists used where appropriate instead of prose |
| Query-Answer Alignment | Content is written to answer the questions users actually ask |
| Redundancy Efficiency | No excessive repetition that dilutes retrieval signal |
| Cross-Section Integrity | Consistent facts and no contradictions across sections |

### Retrievability score (0–100)

For each article, the pipeline generates 10 questions (5 natural-language + 5 BM25 keyword variants) and queries the Microsoft Learn Knowledge Service. The score is:

```
score = (questions_retrieved / total_questions) × 100
```

A question is "retrieved" if the article's URL path appears in any of the top-5 chunks returned by the Knowledge Service.

| Score range | Interpretation |
|-------------|---------------|
| 70–100 | Strong retrieval signal |
| 40–69 | Moderate; some questions miss |
| 0–39 | Weak; the article is frequently outcompeted |

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/maggierui/content-dashboard-poc
cd content-dashboard-poc
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Azure OpenAI endpoint and key

# 3. Drop your Power BI CSV export here:
#    data/sample_engagement.csv  (must have a "Url" column)

# 4. Run the pipeline (all steps are incremental — re-running skips already-processed articles)
python pipeline/fetch_articles.py --input data/sample_engagement.csv
python pipeline/run_ai_readiness.py --input data/sample_engagement.csv
python pipeline/run_retrievability.py --input data/sample_engagement.csv
python pipeline/merge_scores.py

# 5. Generate per-article HTML reports
python pipeline/generate_reports.py

# 6. Launch the dashboard
streamlit run app.py
```

### Re-scoring articles after pipeline changes

```bash
# Re-score all articles and overwrite existing scores (triggers LLM calls)
python pipeline/run_ai_readiness.py --input data/sample_engagement.csv --force
python pipeline/merge_scores.py
python pipeline/generate_reports.py
```

---

## Prerequisites

- Python 3.11+
- Azure OpenAI resource with a `gpt-4o-mini` (or equivalent) deployment for AI Readiness grading and chat
- Microsoft identity that can authenticate to `learn.microsoft.com` (for Knowledge Service queries — requires `az login` or managed identity)
- GitHub account with access to the target private docs repo (for "Open in VS Code Web" links in reports)

---

## Deployment

The app is deployed on [Streamlit Cloud](https://streamlit.io/cloud) from the `main` branch of `maggierui/content-dashboard-poc`. Streamlit secrets mirror the `.env` variables.

To deploy your own instance:
1. Fork the repo to a GitHub account Streamlit Cloud can access
2. Create a new app in Streamlit Cloud pointing at `app.py` on `main`
3. Add secrets in the Streamlit Cloud dashboard (Settings → Secrets) in TOML format:
   ```toml
   AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
   AZURE_OPENAI_KEY = "your-key"
   DEPLOYMENT_NAME = "gpt-4o-mini"
   ```

---

## Documentation

| File | Description |
|------|-------------|
| `docs/project-plan.md` | Architecture, file-by-file purpose, and full workflow |
| `docs/implementation_plans/content-performance-dashboard.md` | Original detailed implementation spec (historical) |
