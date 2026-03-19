"""
Content Performance Dashboard
Three-tab Streamlit app: Data Table | Portfolio Overview | Ask the Data
"""
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from pipeline.url_resolver import url_to_slug

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Content Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
ENRICHED_CSV = ROOT / "data" / "enriched_report.csv"
RETRIEVABILITY_JSON = ROOT / "data" / "scores" / "retrievability_scores.json"
REPORTS_DIR = ROOT / "data" / "reports"

BAND_COLORS = {
    "High": "#22c55e",    # green
    "Medium": "#f59e0b",  # amber
    "Low": "#ef4444",     # red
}
BAND_ORDER = ["High", "Medium", "Low"]

DEPLOYMENT_NAME = os.environ.get("DEPLOYMENT_NAME", "gpt-5-mini")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _coalesce_col(df: pd.DataFrame, primary: str, fallback: str) -> pd.Series:
    """Return primary column filled with fallback where primary is NaN.

    Used to unify LMC and SMC column name variants
    (e.g. 'BounceRate' vs 'Bounce Rate') into a single display column.
    """
    if primary in df.columns and fallback in df.columns:
        return df[primary].fillna(df[fallback])
    if primary in df.columns:
        return df[primary]
    return df[fallback] if fallback in df.columns else pd.Series([None] * len(df), index=df.index)


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    if not ENRICHED_CSV.exists():
        st.error(
            f"Enriched CSV not found at `{ENRICHED_CSV}`. "
            "Run the pipeline first:\n\n"
            "```\n"
            "python pipeline/fetch_articles.py --input data/LMC_Monthly_Engagement_Metrics.csv data/SMC_Monthly_Engagement_Metrics.csv\n"
            "python pipeline/run_ai_readiness.py --input data/LMC_Monthly_Engagement_Metrics.csv data/SMC_Monthly_Engagement_Metrics.csv\n"
            "python pipeline/run_retrievability.py --input data/LMC_Monthly_Engagement_Metrics.csv data/SMC_Monthly_Engagement_Metrics.csv\n"
            "python pipeline/merge_scores.py --input data/LMC_Monthly_Engagement_Metrics.csv data/SMC_Monthly_Engagement_Metrics.csv\n"
            "```"
        )
        st.stop()
    df = pd.read_csv(ENRICHED_CSV)

    # Backfill missing titles from cached article text files.
    # The SMC CSV omits titles for some support articles; the cache has them
    # as the first "## Heading" line from the fetched page.
    cache_dir = ROOT / "data" / "cache"
    if cache_dir.exists() and "Title" in df.columns and "Url" in df.columns:
        missing_mask = df["Title"].isna() | (df["Title"].astype(str).str.strip() == "")
        for idx in df[missing_mask].index:
            url = df.at[idx, "Url"]
            if not isinstance(url, str):
                continue
            try:
                slug = url_to_slug(url)
            except Exception:
                continue
            cache_file = cache_dir / f"{slug}.txt"
            if not cache_file.exists():
                continue
            first_line = cache_file.read_text(encoding="utf-8").split("\n")[0].strip()
            m = re.match(r"^#+\s+(.*)", first_line)
            if m:
                title = m.group(1).strip()
                df.at[idx, "Title"] = title
                if "Title_Normalized" in df.columns:
                    df.at[idx, "Title_Normalized"] = title

    # Ensure numeric types
    for col in ["Retrievability", "Retrievability_Retrieved", "Retrievability_Total",
                "AIReadiness_TotalRecs", "PageViews", "Page Views", "PageViews_Normalized"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # Fill PageViewsMoM from SMC's "PVs MoM" column (percentage string) for rows where it is missing
    if "PVs MoM" in df.columns and "PageViewsMoM" in df.columns:
        pct = (
            df["PVs MoM"].astype(str)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        df["PageViewsMoM"] = df["PageViewsMoM"].fillna(pd.to_numeric(pct, errors="coerce"))

    # Unified columns — coalesce LMC and SMC column-name variants into single display columns
    df["BounceRate_N"]       = _coalesce_col(df, "BounceRate",        "Bounce Rate")
    df["ClickthroughRate_N"] = _coalesce_col(df, "ClickThroughRate",  "Clickthrough Rate")
    df["ExitRate_N"]         = _coalesce_col(df, "ExitRate",          "Exit Rate")
    df["InteractionRate_N"]  = _coalesce_col(df, "CopyTryScrollRate", "Play Scroll Interact Rate")
    df["HelpfulRate_N"]      = _coalesce_col(df, "HelpfulRating",     "Helpful Rate")
    # "FreshNess" (capital N) is the SMC CSV's column name — not a typo
    df["Freshness_N"]        = _coalesce_col(df, "Freshness",         "FreshNess")
    df["Author_N"]           = _coalesce_col(df, "MSAuthor",          "Author")

    # Parse date column if present
    for col in df.columns:
        if "date" in col.lower() or "Date" in col:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass
    return df


@st.cache_data
def load_retrievability_detail() -> dict:
    if RETRIEVABILITY_JSON.exists():
        with open(RETRIEVABILITY_JSON, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def band_chip_html(band: str) -> str:
    color = BAND_COLORS.get(band, "#6b7280")
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:12px;font-weight:600">{band}</span>'
    )


def retrievability_bar_html(score) -> str:
    if pd.isna(score):
        return "—"
    score = int(score)
    if score >= 70:
        color = "#22c55e"
    elif score >= 40:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    bar = (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="font-weight:600;width:30px;text-align:right">{score}</span>'
        f'<div style="background:#e5e7eb;border-radius:4px;height:8px;width:80px">'
        f'<div style="background:{color};border-radius:4px;height:8px;width:{score * 0.8:.0f}px"></div>'
        f'</div></div>'
    )
    return bar


def build_context_for_chat(df: pd.DataFrame, question: str) -> str:
    """Build a context string for the LLM from the dataframe."""
    # Schema
    schema_lines = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        schema_lines.append(f"  - {col} ({dtype})")
    schema = "\n".join(schema_lines)

    # Key statistics
    stats_parts = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    for col in numeric_cols[:10]:  # limit columns
        series = df[col].dropna()
        if len(series) > 0:
            stats_parts.append(
                f"  {col}: min={series.min():.1f}, max={series.max():.1f}, "
                f"mean={series.mean():.1f}, median={series.median():.1f}"
            )
    if "AIReadiness" in df.columns:
        band_counts = df["AIReadiness"].value_counts().to_dict()
        stats_parts.append(f"  AIReadiness band counts: {band_counts}")

    stats = "\n".join(stats_parts)

    # Check if the question references a specific article title or URL
    relevant_rows = pd.DataFrame()
    q_lower = question.lower()
    title_cols = [c for c in df.columns if "title" in c.lower() or "name" in c.lower()]
    url_cols = [c for c in df.columns if "url" in c.lower()]

    for col in title_cols + url_cols:
        mask = df[col].astype(str).str.lower().str.contains(
            q_lower[:50], regex=False, na=False
        )
        if mask.any():
            relevant_rows = df[mask].head(5)
            break

    relevant_section = ""
    if not relevant_rows.empty:
        relevant_section = (
            f"\n\nRelevant rows matching query (up to 5):\n"
            f"{relevant_rows.to_string(index=False)}"
        )

    # Sample rows for general context
    sample = df.head(20).to_string(index=False)

    return (
        f"You are a data analyst assistant. Answer questions about the "
        f"content performance dataset below.\n\n"
        f"Dataset schema:\n{schema}\n\n"
        f"Key statistics:\n{stats}\n\n"
        f"Sample rows (first 20):\n{sample}"
        f"{relevant_section}\n\n"
        f"Total rows in dataset: {len(df)}"
    )


def ask_llm(context: str, question: str) -> str:
    """Send a question to Azure OpenAI using send_response_request."""
    try:
        from common.send_openai_request import send_response_request, create_client
        client = create_client()
        prompt = (
            "You are a helpful data analyst. Answer the user's question about "
            "the content performance dataset. Be concise, cite specific numbers "
            "or article names where possible. If you need to filter or aggregate "
            "data, describe your reasoning clearly."
        )
        response = send_response_request(
            DEPLOYMENT_NAME,
            f"{prompt}\n\nContext:\n{context}",
            question,
            "low",
            client=client,
        )
        return response
    except Exception as exc:
        return f"Error calling LLM: {exc}"


# ── Sidebar filters ───────────────────────────────────────────────────────────
def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("Filters")
    filtered = df.copy()

    if "Platform" in df.columns:
        platforms = sorted(df["Platform"].dropna().unique().tolist())
        if platforms:
            selected_platforms = st.sidebar.multiselect(
                "Platform (default: all sources)",
                options=platforms,
                default=platforms,
                key="platform_filter_v2",
            )
            if selected_platforms:
                filtered = filtered[filtered["Platform"].isin(selected_platforms)]

    # Date range filter (if any date column exists)
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if date_cols:
        date_col = date_cols[0]
        min_date = df[date_col].min()
        max_date = df[date_col].max()
        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input(
                "Date Range",
                value=(min_date.date(), max_date.date()),
                min_value=min_date.date(),
                max_value=max_date.date(),
            )
            if len(date_range) == 2:
                start, end = date_range
                filtered = filtered[
                    (filtered[date_col].dt.date >= start)
                    & (filtered[date_col].dt.date <= end)
                ]

    # Group filter
    group_col = "Group_Normalized" if "Group_Normalized" in df.columns else next(
        (c for c in df.columns if c.lower() in ("group", "team", "category")), None
    )
    if group_col:
        groups = sorted(df[group_col].dropna().unique().tolist())
        selected_groups = st.sidebar.multiselect(
            "Group", options=groups, default=groups
        )
        if selected_groups:
            # NaN rows (SMC articles — no group classification) always pass through;
            # they are a separate content system, not an unselected LMC group.
            filtered = filtered[
                filtered[group_col].isin(selected_groups) | filtered[group_col].isna()
            ]

    # TopicType filter
    topic_col = "TopicType_Normalized" if "TopicType_Normalized" in df.columns else next(
        (c for c in df.columns if "topic" in c.lower() or "type" in c.lower()), None
    )
    if topic_col:
        topics = sorted(df[topic_col].dropna().unique().tolist())
        selected_topics = st.sidebar.multiselect(
            "Topic Type", options=topics, default=topics
        )
        if selected_topics:
            # NaN rows pass through for the same reason as the Group filter above.
            filtered = filtered[
                filtered[topic_col].isin(selected_topics) | filtered[topic_col].isna()
            ]

    # AI Readiness filter
    if "AIReadiness" in df.columns:
        bands = [b for b in BAND_ORDER if b in df["AIReadiness"].unique()]
        bands += [b for b in df["AIReadiness"].dropna().unique() if b not in BAND_ORDER]
        selected_bands = st.sidebar.multiselect(
            "AI Readiness Band",
            options=bands,
            default=bands,
        )
        if selected_bands:
            filtered = filtered[
                filtered["AIReadiness"].isin(selected_bands)
                | filtered["AIReadiness"].isna()
            ]

    # Retrievability range
    if "Retrievability" in df.columns and df["Retrievability"].notna().any():
        retr_min = int(df["Retrievability"].dropna().min() or 0)
        retr_max = int(df["Retrievability"].dropna().max() or 100)
        if retr_min < retr_max:
            retr_range = st.sidebar.slider(
                "Retrievability Score",
                min_value=retr_min,
                max_value=retr_max,
                value=(retr_min, retr_max),
            )
            filtered = filtered[
                (filtered["Retrievability"] >= retr_range[0])
                & (filtered["Retrievability"] <= retr_range[1])
                | filtered["Retrievability"].isna()
            ]

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{len(filtered):,} articles** shown")

    return filtered


# ── Tab 1: Data Table ─────────────────────────────────────────────────────────
def render_data_table(df: pd.DataFrame) -> None:
    st.subheader(f"Articles ({len(df):,} rows)")

    # Build display dataframe
    display = df.copy()

    if "Platform" in display.columns:
        source_view = st.radio(
            "Quick source view",
            options=["All", "Learn only", "Support only", "Support with AI scores"],
            horizontal=True,
        )
        platform_series = display["Platform"].astype(str).str.lower()
        if source_view == "Learn only":
            display = display[platform_series == "learn"]
        elif source_view == "Support only":
            display = display[platform_series == "support"]
        elif source_view == "Support with AI scores":
            ai_mask = (
                display["AIReadiness"].notna()
                if "AIReadiness" in display.columns
                else pd.Series(False, index=display.index)
            )
            display = display[(platform_series == "support") & ai_mask]
        st.caption(f"Showing {len(display):,} rows for: {source_view}")

    # Sort controls
    sort_col = st.selectbox(
        "Sort by",
        options=[c for c in display.columns if c != "AIReadiness"],
        index=0,
    )
    sort_asc = st.checkbox("Ascending", value=False)
    display = display.sort_values(sort_col, ascending=sort_asc, na_position="last")

    # Add per-article AI Readiness report link column (query-param URL)
    existing_reports = {p.stem for p in REPORTS_DIR.glob("*.html")}

    def make_report_url(url):
        if pd.isna(url):
            return None
        slug = url_to_slug(str(url))
        return f"?report={slug}" if slug in existing_reports else None

    if "Url" in display.columns:
        display = display.copy()
        display["AIReadiness_Report"] = display["Url"].apply(make_report_url)

    # Curate the main table to the key fields people actually use in the UI.
    preferred_order = [
        "Date",
        "Platform",
        "ContentSource",
        "Group_Normalized",
        "TopicType_Normalized",
        "Url",
        "Title",
        # Traffic & engagement (right after Title)
        "PageViews_Normalized",
        "Visitors",
        "Freshness_N",
        "Engagement",
        "BounceRate_N",
        "ClickthroughRate_N",
        "ExitRate_N",
        "InteractionRate_N",
        "HelpfulRate_N",
        "Ratings",
        # AI scores
        "AIReadiness",
        "AIReadiness_TotalRecs",
        "AIReadiness_WeakestDim",
        "Retrievability",
        "Retrievability_Retrieved",
        "Retrievability_Total",
        "AIReadiness_Report",
        # Authorship & MoM (last)
        "Author_N",
        "PageViewsMoM",
    ]
    cols_to_show = [c for c in preferred_order if c in display.columns]

    # Use st.dataframe with column config for richer display
    col_config = {}

    if "AIReadiness" in display.columns:
        col_config["AIReadiness"] = st.column_config.TextColumn(
            "AI Readiness",
            help=(
                "Band based on total editorial recommendations across 10 RAG-readiness "
                "dimensions. High = 0–3 recs (well-optimized for AI retrieval), "
                "Medium = 4–8 recs (gaps exist), Low = 9+ recs (significant retrieval issues)."
            ),
        )
    if "AIReadiness_TotalRecs" in display.columns:
        col_config["AIReadiness_TotalRecs"] = st.column_config.NumberColumn(
            "Total Recs",
            help=(
                "Total count of improvement recommendations flagged across all 10 dimensions: "
                "heading hierarchy, chunk autonomy, context completeness, entity normalization, "
                "disambiguation, semantic density, structured data, query-answer alignment, "
                "redundancy efficiency, and cross-section integrity."
            ),
        )
    if "AIReadiness_WeakestDim" in display.columns:
        col_config["AIReadiness_WeakestDim"] = st.column_config.TextColumn(
            "Weakest Dimension",
            help=(
                "The dimension with the highest recommendation count — where improving this "
                "article will have the greatest impact on AI retrieval quality."
            ),
        )
    if "Retrievability" in display.columns:
        col_config["Retrievability"] = st.column_config.ProgressColumn(
            "Retrievability",
            help=(
                "% of test questions answered by the Knowledge Service returning this article "
                "in its top-5 chunks. Score = (retrieved / 10 questions) × 100. "
                "Blank = not yet scored."
            ),
            min_value=0,
            max_value=100,
            format="%d%%",
        )
    if "Retrievability_Retrieved" in display.columns:
        col_config["Retrievability_Retrieved"] = st.column_config.NumberColumn(
            "Retrieved",
            help=(
                "Number of test questions (out of 10) that successfully retrieved this article "
                "from the Knowledge Service."
            ),
        )
    if "Retrievability_Total" in display.columns:
        col_config["Retrievability_Total"] = st.column_config.NumberColumn(
            "Total Questions",
            help=(
                "Total test questions used (typically 10: 5 natural-language + "
                "5 BM25 keyword variants)."
            ),
        )

    if "Platform" in display.columns:
        col_config["Platform"] = st.column_config.TextColumn("Platform")
    if "ContentSource" in display.columns:
        col_config["ContentSource"] = st.column_config.TextColumn("Content Source")
    if "Group_Normalized" in display.columns:
        col_config["Group_Normalized"] = st.column_config.TextColumn("Group")
    if "TopicType_Normalized" in display.columns:
        col_config["TopicType_Normalized"] = st.column_config.TextColumn("TopicType")
    if "PageViews_Normalized" in display.columns:
        col_config["PageViews_Normalized"] = st.column_config.NumberColumn("PageViews")
    if "Freshness_N" in display.columns:
        col_config["Freshness_N"] = st.column_config.TextColumn("Freshness")
    if "BounceRate_N" in display.columns:
        col_config["BounceRate_N"] = st.column_config.TextColumn("Bounce Rate")
    if "ClickthroughRate_N" in display.columns:
        col_config["ClickthroughRate_N"] = st.column_config.TextColumn("Clickthrough Rate")
    if "ExitRate_N" in display.columns:
        col_config["ExitRate_N"] = st.column_config.TextColumn("Exit Rate")
    if "InteractionRate_N" in display.columns:
        col_config["InteractionRate_N"] = st.column_config.TextColumn(
            "Copy/Try/Scroll",
            help="CopyTryScrollRate (Learn) or Play Scroll Interact Rate (Support)",
        )
    if "HelpfulRate_N" in display.columns:
        col_config["HelpfulRate_N"] = st.column_config.TextColumn("Helpful Rate")
    if "Author_N" in display.columns:
        col_config["Author_N"] = st.column_config.TextColumn("Author")

    # Identify URL column for linking
    url_col = next(
        (c for c in display.columns if c.lower() == "url"), None
    )
    if url_col:
        col_config[url_col] = st.column_config.LinkColumn(url_col)

    if "AIReadiness_Report" in display.columns:
        col_config["AIReadiness_Report"] = st.column_config.LinkColumn(
            "AI Report",
            help=(
                "Open the full AI Readiness report for this article "
                "(opens alongside VS Code Web)"
            ),
            display_text="Report \u2197",
        )

    if "AIReadiness" in display.columns:
        ai_scored = display["Url"].loc[display["AIReadiness"].notna()].nunique()
        total = display["Url"].nunique()
        ai_pct = ai_scored / total * 100 if total > 0 else 0
        st.caption(
            f"AI Readiness scored: {ai_scored}/{total} unique articles ({ai_pct:.0f}%) "
            "— includes Microsoft Learn and Microsoft Support rows currently scored"
        )

    if "Platform" in display.columns:
        source_counts = (
            display.groupby("Platform")["Url"].nunique().sort_index().to_dict()
            if "Url" in display.columns else {}
        )
        if source_counts:
            source_summary = ", ".join(
                f"{platform}: {count}" for platform, count in source_counts.items()
            )
            st.caption(f"Showing — {source_summary}")

    if "Retrievability" in display.columns:
        scored = display["Url"].loc[display["Retrievability"].notna()].nunique()
        total = display["Url"].nunique()
        pct = scored / total * 100 if total > 0 else 0
        st.caption(
            f"Retrievability scored: {scored}/{total} unique articles ({pct:.0f}%) "
            "— blank cells = article not yet scored by the pipeline"
        )

    st.dataframe(
        display[cols_to_show],
        column_config=col_config,
        use_container_width=True,
        height=600,
        hide_index=True,
    )

    # Download button
    csv_bytes = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered CSV",
        data=csv_bytes,
        file_name="filtered_report.csv",
        mime="text/csv",
    )


# ── Tab 2: Portfolio Overview ─────────────────────────────────────────────────
def render_portfolio(df: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)

    # ── Donut: AI Readiness distribution ──────────────────────────────────────
    with col1:
        st.subheader("AI Readiness Distribution")
        if "AIReadiness" in df.columns and df["AIReadiness"].notna().any():
            band_counts = (
                df["AIReadiness"]
                .value_counts()
                .reindex(BAND_ORDER)
                .dropna()
            )
            fig = go.Figure(
                go.Pie(
                    labels=band_counts.index.tolist(),
                    values=band_counts.values.tolist(),
                    hole=0.55,
                    marker_colors=[BAND_COLORS.get(b, "#6b7280") for b in band_counts.index],
                    textinfo="label+percent",
                )
            )
            fig.update_layout(
                showlegend=True,
                margin=dict(t=20, b=20, l=20, r=20),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("AI Readiness scores not yet available.")

    # ── Histogram: Retrievability ─────────────────────────────────────────────
    with col2:
        st.subheader("Retrievability Score Distribution")
        if "Retrievability" in df.columns and df["Retrievability"].notna().any():
            fig = px.histogram(
                df.dropna(subset=["Retrievability"]),
                x="Retrievability",
                nbins=20,
                color_discrete_sequence=["#3b82f6"],
                labels={"Retrievability": "Score (0–100)"},
            )
            fig.update_layout(
                bargap=0.1,
                margin=dict(t=20, b=20, l=20, r=20),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Retrievability scores not yet available.")

    # ── Scatter: Retrievability vs PageViews ──────────────────────────────────
    st.subheader("Retrievability vs. Page Views (colored by AI Readiness)")

    pv_col = "PageViews_Normalized" if "PageViews_Normalized" in df.columns else next(
        (c for c in df.columns if "pageview" in c.lower() or "page_view" in c.lower()),
        None,
    )
    has_retr = "Retrievability" in df.columns and df["Retrievability"].notna().any()
    has_pv = pv_col and df[pv_col].notna().any()

    if has_retr and has_pv:
        scatter_df = df.dropna(subset=["Retrievability", pv_col]).copy()
        if "AIReadiness" in scatter_df.columns:
            scatter_df["AIReadiness"] = scatter_df["AIReadiness"].fillna("Unknown")
            color_col = "AIReadiness"
            color_map = {**BAND_COLORS, "Unknown": "#9ca3af"}
        else:
            color_col = None
            color_map = None

        title_col = "Title_Normalized" if "Title_Normalized" in scatter_df.columns else next(
            (c for c in scatter_df.columns if "title" in c.lower()), None
        )
        url_col = next(
            (c for c in scatter_df.columns if "url" in c.lower()), None
        )
        hover_name = title_col or url_col

        fig = px.scatter(
            scatter_df,
            x="Retrievability",
            y=pv_col,
            color=color_col,
            color_discrete_map=color_map,
            hover_name=hover_name,
            labels={
                "Retrievability": "Retrievability Score",
                pv_col: "Page Views",
            },
            category_orders={"AIReadiness": BAND_ORDER + ["Unknown"]},
        )
        # Quadrant lines
        fig.add_vline(x=40, line_dash="dash", line_color="#9ca3af", line_width=1)
        fig.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Bottom-left quadrant table: Low AI Readiness + Retrievability < 40
        st.subheader("Priority List: High Traffic + Poor AI Performance")
        st.caption(
            "Articles with **Low AI Readiness** AND **Retrievability < 40** "
            "— high editorial impact if improved"
        )
        priority_mask = (
            (scatter_df.get("AIReadiness", pd.Series(dtype=str)) == "Low")
            & (scatter_df["Retrievability"] < 40)
        )
        priority_df = scatter_df[priority_mask].sort_values(pv_col, ascending=False)
        if priority_df.empty:
            st.success("No articles in this quadrant.")
        else:
            display_cols = [c for c in [hover_name, pv_col, "Retrievability",
                                         "AIReadiness", "AIReadiness_WeakestDim"]
                            if c and c in priority_df.columns]
            st.dataframe(priority_df[display_cols], use_container_width=True)
    else:
        st.info(
            "Scatter plot requires both `Retrievability` scores and a page-views column."
        )


# ── Tab 3: Ask the Data ───────────────────────────────────────────────────────
def render_chat(df: pd.DataFrame) -> None:
    st.subheader("Ask a question about the dataset")

    example_questions = [
        "Which how-to articles have low retrievability?",
        "What's the average AI Readiness for Concepts vs how-to articles?",
        "Show me the top 10 articles by page views that have Low AI Readiness",
        "How many articles have a retrievability score below 40?",
        "Which dimension has the most recommendations overall?",
    ]

    with st.expander("Example questions"):
        for q in example_questions:
            st.markdown(f"- {q}")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render past messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input
    if user_input := st.chat_input("Ask about your content data…"):
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                context = build_context_for_chat(df, user_input)
                answer = ask_llm(context, user_input)
            st.markdown(answer)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": answer}
        )

    if st.button("Clear chat"):
        st.session_state.chat_history = []
        st.rerun()


# ── Report page ───────────────────────────────────────────────────────────────
_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def render_report_page(slug: str) -> None:
    if st.button("← Back to Dashboard"):
        st.query_params.clear()
        st.rerun()
        return

    if not _SAFE_SLUG_RE.match(slug):
        st.error("Invalid report identifier.")
        return

    report_path = (REPORTS_DIR / f"{slug}.html").resolve()
    if not str(report_path).startswith(str(REPORTS_DIR.resolve())):
        st.error("Invalid report path.")
        return

    if not report_path.exists():
        st.error(f"Report not found: `{slug}`")
        return

    html = report_path.read_text(encoding="utf-8")
    st.components.v1.html(html, height=800, scrolling=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    # Serve per-article report if ?report=<slug> is in the URL
    report_slug = st.query_params.get("report")
    if report_slug:
        render_report_page(report_slug)
        return

    st.title("Content Performance Dashboard")
    st.caption(
        "Engagement metrics enriched with AI Readiness (RAG-optimisation score) "
        "and Retrievability (Knowledge Service hit-rate)"
    )

    df_full = load_data()
    df_filtered = render_sidebar(df_full)

    tab1, tab2, tab3 = st.tabs(["Data Table", "Portfolio Overview", "Ask the Data"])

    with tab1:
        render_data_table(df_filtered)

    with tab2:
        render_portfolio(df_filtered)

    with tab3:
        render_chat(df_filtered)


if __name__ == "__main__":
    main()
