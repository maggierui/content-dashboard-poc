from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.url_utils import infer_platform, normalize_url


URL_CANDIDATES = ("Url", "URL", "url")
TITLE_CANDIDATES = ("Title", "Name")
PAGE_VIEWS_CANDIDATES = ("PageViews", "Page Views")
TOPIC_CANDIDATES = ("TopicType", "Content Type")
GROUP_CANDIDATES = ("Group", "Team", "Category")


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _parse_numeric(series: pd.Series) -> pd.Series:
    text = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    text = text.where(~series.isna(), None)
    return pd.to_numeric(text, errors="coerce")


def _normalize_frame(df: pd.DataFrame, input_path: Path) -> pd.DataFrame:
    columns = df.columns.tolist()
    url_col = _pick_column(columns, URL_CANDIDATES)
    if url_col is None:
        raise ValueError(
            f"No URL column found in {input_path}. Available columns: {columns}"
        )

    title_col = _pick_column(columns, TITLE_CANDIDATES)
    pageviews_col = _pick_column(columns, PAGE_VIEWS_CANDIDATES)
    topic_col = _pick_column(columns, TOPIC_CANDIDATES)
    group_col = _pick_column(columns, GROUP_CANDIDATES)

    result = df.copy()
    result["Url"] = result[url_col].map(
        lambda value: normalize_url(value) if pd.notna(value) else None
    )
    result["Title_Normalized"] = (
        result[title_col] if title_col else pd.Series([None] * len(result))
    )
    result["PageViews_Normalized"] = (
        _parse_numeric(result[pageviews_col])
        if pageviews_col
        else pd.Series([pd.NA] * len(result), dtype="Float64")
    )
    result["TopicType_Normalized"] = (
        result[topic_col] if topic_col else pd.Series([None] * len(result))
    )
    result["Group_Normalized"] = (
        result[group_col] if group_col else pd.Series([None] * len(result))
    )
    result["Platform"] = result["Url"].map(infer_platform)
    result["ContentSource"] = result["Platform"].map(
        {
            "learn": "Microsoft Learn",
            "support": "Microsoft Support",
        }
    ).fillna("Unknown")
    result["SourceFileType"] = result["Platform"].map(
        {
            "learn": "markdown",
            "support": "xml",
        }
    ).fillna("unknown")
    result["InputFile"] = input_path.name
    return result


def load_engagement_csvs(input_paths: list[str | Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for raw_path in input_paths:
        path = Path(raw_path)
        df = pd.read_csv(path)
        frames.append(_normalize_frame(df, path))

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


def load_unique_urls(input_paths: list[str | Path]) -> list[str]:
    df = load_engagement_csvs(input_paths)
    if "Url" not in df.columns:
        return []
    return df["Url"].dropna().drop_duplicates().tolist()
