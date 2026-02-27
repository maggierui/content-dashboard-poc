"""
Content Performance Dashboard
Three-tab Streamlit app: Data Table | Portfolio Overview | Ask the Data
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

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

BAND_COLORS = {
    "High": "#22c55e",    # green
    "Medium": "#f59e0b",  # amber
    "Low": "#ef4444",     # red
}
BAND_ORDER = ["High", "Medium", "Low"]

DEPLOYMENT_NAME = os.environ.get("DEPLOYMENT_NAME", "gpt-5-mini")


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    if not ENRICHED_CSV.exists():
        st.error(
            f"Enriched CSV not found at `{ENRICHED_CSV}`. "
            "Run the pipeline first:\n\n"
            "```\n"
            "python pipeline/fetch_articles.py --input data/sample_engagement.csv\n"
            "python pipeline/run_ai_readiness.py --input data/sample_engagement.csv\n"
            "python pipeline/run_retrievability.py --input data/sample_engagement.csv\n"
            "python pipeline/merge_scores.py --input data/sample_engagement.csv\n"
            "```"
        )
        st.stop()
    df = pd.read_csv(ENRICHED_CSV)
    # Ensure numeric types
    for col in ["Retrievability", "Retrievability_Retrieved", "Retrievability_Total",
                "AIReadiness_TotalRecs"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
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
    group_col = next(
        (c for c in df.columns if c.lower() in ("group", "team", "category")), None
    )
    if group_col:
        groups = sorted(df[group_col].dropna().unique().tolist())
        selected_groups = st.sidebar.multiselect(
            "Group", options=groups, default=groups
        )
        if selected_groups:
            filtered = filtered[filtered[group_col].isin(selected_groups)]

    # TopicType filter
    topic_col = next(
        (c for c in df.columns if "topic" in c.lower() or "type" in c.lower()), None
    )
    if topic_col:
        topics = sorted(df[topic_col].dropna().unique().tolist())
        selected_topics = st.sidebar.multiselect(
            "Topic Type", options=topics, default=topics
        )
        if selected_topics:
            filtered = filtered[filtered[topic_col].isin(selected_topics)]

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
    if "Retrievability" in df.columns:
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

    # Sort controls
    sort_col = st.selectbox(
        "Sort by",
        options=[c for c in df.columns if c != "AIReadiness"],
        index=0,
    )
    sort_asc = st.checkbox("Ascending", value=False)
    display = display.sort_values(sort_col, ascending=sort_asc, na_position="last")

    # Render with styled columns
    # We render as markdown table for rich formatting
    cols_to_show = [c for c in display.columns
                    if c not in ("AIReadiness_WeakestDim", "AIReadiness_TotalRecs",
                                 "Retrievability_Retrieved", "Retrievability_Total")]

    # Use st.dataframe with column config for richer display
    col_config = {}

    if "AIReadiness" in display.columns:
        col_config["AIReadiness"] = st.column_config.TextColumn(
            "AI Readiness",
            help="High = well-optimized, Medium = gaps exist, Low = significant issues",
        )
    if "AIReadiness_WeakestDim" in display.columns:
        col_config["AIReadiness_WeakestDim"] = st.column_config.TextColumn(
            "Weakest Dimension",
            help="Dimension with most recommendations",
        )
    if "Retrievability" in display.columns:
        col_config["Retrievability"] = st.column_config.ProgressColumn(
            "Retrievability",
            help="% of generated questions retrieved by Knowledge Service",
            min_value=0,
            max_value=100,
            format="%d%%",
        )

    # Identify URL column for linking
    url_col = next(
        (c for c in display.columns if "url" in c.lower()), None
    )
    if url_col:
        col_config[url_col] = st.column_config.LinkColumn(url_col)

    st.dataframe(
        display,
        column_config=col_config,
        use_container_width=True,
        height=600,
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

    pv_col = next(
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

        title_col = next(
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
            "Scatter plot requires both `Retrievability` scores and a `PageViews` column."
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


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
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
