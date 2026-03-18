# Spec: "How It Works" PowerPoint Presentation

**Date:** 2026-03-18
**Output:** `docs/content-dashboard-how-it-works.pptx`
**Generator:** `docs/create_how_it_works_presentation.py`
**Style:** Matches existing `create_presentation.py` — Segoe UI, Microsoft blue/green/orange palette, blank slide layout, header bar + footer bar pattern.

---

## Slide Outline

### Slide 1 — Title
- Dark blue full-bleed background
- Title: "Content Performance Dashboard: How It Works"
- Subtitle: "Pipeline architecture, scoring methodology, and content ingestion comparison"
- No footer timer

### Slide 2 — The Problem
- Header: "Two gaps in content intelligence"
- Left panel: Human engagement (Power BI — page views, bounce rate, CTR) ✓ known
- Right panel: AI engagement (Copilot retrieval, Knowledge Service ranking) ✗ unknown
- Call-out: "When a user asks Copilot a question, does our article show up? We don't know."

### Slide 3 — System Architecture
- Header: "End-to-end pipeline"
- Linear flow diagram: Power BI CSV → Content Cache → AI Readiness Scorer → Retrievability Scorer → Enriched CSV → Streamlit Dashboard
- Color assignments: Power BI CSV = LIGHT_GRAY; Content Cache = BLUE_MID (note below); AI Readiness Scorer = ORANGE; Retrievability Scorer = GREEN; Enriched CSV = LIGHT_GRAY; Streamlit Dashboard = GREEN
- Brief label under each box describing its role
- Note under Content Cache box: "3 ingestion methods — see Stage 1" (teaser for Slide 4)

### Slide 4 — Stage 1: Content Ingestion
- Header: "Stage 1: Fetching and caching article content"
- Preamble sentence at top: "Three ingestion methods have been tested — each gives the LLM a different view of the same article."
- Three columns for the three methods:
  - Method A: HTML crawl → BeautifulSoup extraction → normalized plain text (links, images, code removed)
  - Method B: Local .md files → normalize_markdown_content() — headings flattened to ##, links/images stripped
  - Method C: Local .md files → raw markdown — YAML front matter stripped, original H1–H6, [links](url), `code`, | tables |, blockquotes all preserved
- Comparison table rows: Source | Heading levels | Links/tables | Coverage
  - A: HTML crawl | flattened | stripped | 273 articles
  - B: Local .md  | flattened to ## | stripped | 273 articles
  - C: Local .md  | H1–H6 preserved | preserved | 155 articles
- Slide 4 is motivation (why three methods exist); Slides 8–9 are the results comparison

### Slide 5 — Stage 2: AI Readiness Scoring
- Header: "Stage 2: AI Readiness — is this article well-structured for AI?"
- Left: 10 dimensions (use the same ordered list as `create_presentation.py` Appendix A slide):
  1. Heading Hierarchy — Clear H1→H2→H3 structure for meaningful chunking
  2. Chunk Autonomy — Each section makes sense without surrounding context
  3. Context Completeness — Key terms and prerequisites explained within the article
  4. Entity Normalization — Consistent naming for products, features, concepts
  5. Disambiguation — Ambiguous terms and pronouns resolved explicitly
  6. Semantic Density — High information-to-noise ratio; no filler
  7. Structured Data Utilization — Tables and lists used instead of dense prose
  8. Query-Answer Alignment — Content answers the questions users actually ask
  9. Redundancy Efficiency — No copy-paste repetition that dilutes retrieval signal
  10. Cross-Section Integrity — No contradictions or inconsistent facts across sections
- Right: How scoring works — 10 concurrent LLM calls → recommendation count per dimension → total → band assignment
- Band thresholds: High (0–3 recs), Medium (4–8 recs), Low (9+ recs)
- Font size 10–11pt for dimension list; validate against Appendix A slide in existing script

### Slide 6 — Stage 3: Retrievability Scoring
- Header: "Stage 3: Retrievability — does AI actually surface this article?"
- Four-step flow: Question generation → KS query → Hit detection → Score
- Formula highlight at bottom: Score = (hits / 10) × 100
- Score ranges: 70–100 Strong, 40–69 Moderate, 0–39 Weak

### Slide 7 — Stage 4: Dashboard Output
- Header: "Stage 4: What the pipeline produces"
- Three output views described:
  1. Data table — all Power BI columns + AI Readiness band + Retrievability score + Report link
  2. Portfolio scatter — Retrievability (x) vs PageViews (y), colored by AI Readiness band; priority table
  3. Per-article HTML report — dimension bar chart, recommendation cards (Evidence/Action/Impact)

### Slide 8 — Why Three Ingestion Methods (motivation)
- Header: "Hypothesis: does richer markdown structure improve LLM assessment?"
- This slide covers the WHY — motivation for running three methods
- Left: what the LLM uses to score (content fed into the prompt)
- Centre: hypothesis — "Preserving heading hierarchy, live links, and table structure gives the LLM richer signals → fewer spurious recommendations"
- Right: how we tested — ran same scoring pipeline with each of the three caches
- Transition line at bottom: "273 articles scored with A and B; 155 with C (matched local .md files)"

### Slide 9 — Method A vs B vs C: What the LLM Sees (mechanics)
- Header: "What each method feeds to the LLM"
- This slide covers the HOW — mechanical detail of what content the LLM actually receives
- Side-by-side cards (one per method), each showing a short excerpt-style example of the same hypothetical section rendered in that method's format:
  - Method A: "Introduction\nCopilot is an AI tool. See also Configuration." (plain text, no structure)
  - Method B: "## Introduction\nCopilot is an AI tool. See also Configuration." (flattened heading, no links)
  - Method C: "# Introduction\nCopilot is an [AI tool](url). See also [Configuration](url).\n| Feature | Status |\n|---------|--------|\n| Chat | GA |" (full structure)
- Key insight call-out box: "B and C use the same source files — score differences are purely structural"

### Slide 10 — Score Comparison Results
- Header: "Score comparison: does structure preservation change results?"
- Two sub-sections:
  - Top: Summary stats table (avg total recs per method, band change counts)
  - Bottom: Note that B→C top-10 and per-dimension structural impact data populate once Method C scoring is complete
- Placeholder text if scores not yet available: "Run pipeline/run_ai_readiness.py with --cache-dir data/cache_raw_md"

---

## Implementation Notes

- Single Python script: `docs/create_how_it_works_presentation.py`
- Copy palette constants and helper functions verbatim from `create_presentation.py` — do NOT import from it, as that script executes Presentation() and prs.save() at module scope (side-effect import would generate the demo deck)
- Helpers to copy: `rgb()`, `add_rect()`, `add_textbox()`, `add_bullet_para()`, `header_bar()`, `footer_bar()`, and all palette constants (BLUE_DARK, BLUE_MID, GREEN, ORANGE, WHITE, LIGHT_GRAY, MID_GRAY, DARK_GRAY)
- Loads Method A scores from git: `OLD_COMMIT = "36245ff"` (HTML-based, Method A)
- Loads Method B scores from git: `NEW_COMMIT = "20bcc2f"` (norm-markdown, Method B)
- Loads Method C data from `data/scores/ai_readiness_scores_raw_md.json` if it exists; otherwise show placeholder
- Saves to `docs/content-dashboard-how-it-works.pptx`
- Script is standalone: `python docs/create_how_it_works_presentation.py`
- Placeholder command for Slide 10: `python pipeline/run_ai_readiness.py --input data/LMC_Monthly_Engagement_Metrics.csv --cache-dir data/cache_raw_md --output data/scores/ai_readiness_scores_raw_md.json`
