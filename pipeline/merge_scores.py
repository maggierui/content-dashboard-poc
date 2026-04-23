"""
merge_scores.py - Merge Power BI CSV with AI Readiness and Retrievability scores.

Usage:
    python pipeline/merge_scores.py --input data/sample_engagement.csv
    python pipeline/merge_scores.py --input data/sample_engagement.csv --output data/enriched_report.csv
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from pipeline.engagement_inputs import load_engagement_csvs
from pipeline.url_utils import normalize_url, url_to_slug

SCORES_DIR = ROOT / "data" / "scores"
AI_READINESS_FILE = SCORES_DIR / "ai_readiness_scores.json"
RETRIEVABILITY_FILE = SCORES_DIR / "retrievability_scores.json"
DEFAULT_OUTPUT = ROOT / "data" / "enriched_report.csv"
CACHE_DIR = ROOT / "data" / "cache"
PRUNE_LOG = ROOT / "data" / "logs" / "pruned_rows.csv"
PRUNE_LOG_FIELDS = ["timestamp", "url", "reason", "platform", "date", "input_file"]


def _backfill_titles_from_cache(df: pd.DataFrame) -> int:
    """Fill empty Title values from data/cache/<slug>.txt (first '#' heading).

    Mirrors the in-memory backfill in app.py:100-123 so the pipeline persists
    whatever the cache can recover, leaving only the truly-missing rows to be
    pruned. Returns the number of rows filled.
    """
    if not CACHE_DIR.exists() or "Title" not in df.columns or "Url" not in df.columns:
        return 0

    missing_mask = df["Title"].isna() | (df["Title"].astype(str).str.strip() == "")
    filled = 0
    for idx in df[missing_mask].index:
        url = df.at[idx, "Url"]
        if not isinstance(url, str):
            continue
        try:
            slug = url_to_slug(url)
        except Exception:
            continue
        cache_file = CACHE_DIR / f"{slug}.txt"
        if not cache_file.exists():
            continue
        first_line = cache_file.read_text(encoding="utf-8").split("\n")[0].strip()
        m = re.match(r"^#+\s+(.*)", first_line)
        if m:
            title = m.group(1).strip()
            df.at[idx, "Title"] = title
            if "Title_Normalized" in df.columns:
                df.at[idx, "Title_Normalized"] = title
            filled += 1
    return filled


def _append_prune_log(rows: pd.DataFrame, reason: str) -> None:
    """Append excluded rows to data/logs/pruned_rows.csv (creates file+header if missing)."""
    if rows.empty:
        return
    PRUNE_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not PRUNE_LOG.exists()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _val(r, key, default=""):
        v = r.get(key, default)
        return "" if pd.isna(v) else v

    with PRUNE_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PRUNE_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        for _, r in rows.iterrows():
            writer.writerow({
                "timestamp": ts,
                "url": _val(r, "Url"),
                "reason": reason,
                "platform": _val(r, "Platform"),
                "date": _val(r, "Date"),
                "input_file": _val(r, "InputFile"),
            })


def _coalesce_freshness(df: pd.DataFrame) -> pd.Series:
    """LMC 'Freshness' fallback to SMC 'FreshNess' (capital N) — matches app.py:146."""
    has_l = "Freshness" in df.columns
    has_s = "FreshNess" in df.columns
    if has_l and has_s:
        return df["Freshness"].fillna(df["FreshNess"])
    if has_l:
        return df["Freshness"]
    if has_s:
        return df["FreshNess"]
    return pd.Series([None] * len(df), index=df.index)


def load_ai_readiness(path: Path) -> pd.DataFrame:
    """Load AI readiness scores and flatten into a DataFrame."""
    if not path.exists():
        print(f"Warning: AI Readiness scores not found at {path}")
        return pd.DataFrame(columns=["Url", "AIReadiness", "AIReadiness_WeakestDim",
                                     "AIReadiness_TotalRecs", "AIReadiness_ByDimension"])

    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)

    rows = []
    for url, score in data.items():
        by_dim = score.get("by_dimension", {})
        rows.append({
            "Url": url,
            "AIReadiness": score.get("band", ""),
            "AIReadiness_WeakestDim": score.get("weakest_dimension", ""),
            "AIReadiness_TotalRecs": score.get("total_recommendations", None),
            "AIReadiness_ByDimension": json.dumps(by_dim) if by_dim else None,
        })
    return pd.DataFrame(rows)


def load_retrievability(path: Path) -> pd.DataFrame:
    """Load retrievability scores into a DataFrame."""
    if not path.exists():
        print(f"Warning: Retrievability scores not found at {path}")
        return pd.DataFrame(columns=["Url", "Retrievability",
                                     "Retrievability_Retrieved", "Retrievability_Total"])

    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)

    rows = []
    for url, score in data.items():
        rows.append({
            "Url": url,
            "Retrievability": score.get("score", None),
            "Retrievability_Retrieved": score.get("retrieved_count", None),
            "Retrievability_Total": score.get("total_questions", None),
        })
    return pd.DataFrame(rows)


def build_enriched_csv(
    input_paths: list[str | Path],
    output_path: Path = DEFAULT_OUTPUT,
    ai_readiness_path: Path = AI_READINESS_FILE,
    retrievability_path: Path = RETRIEVABILITY_FILE,
) -> Path:
    """Merge engagement CSVs with scores and write enriched CSV. Returns output path."""
    df = load_engagement_csvs(input_paths)
    df["Url"] = df["Url"].map(normalize_url)

    ai_df = load_ai_readiness(ai_readiness_path)
    if not ai_df.empty:
        ai_df["Url"] = ai_df["Url"].map(normalize_url)
    retr_df = load_retrievability(retrievability_path)
    if not retr_df.empty:
        retr_df["Url"] = retr_df["Url"].map(normalize_url)

    result = df.copy()
    if not ai_df.empty:
        result = result.merge(ai_df, on="Url", how="left")
    else:
        result["AIReadiness"] = None
        result["AIReadiness_WeakestDim"] = None
        result["AIReadiness_TotalRecs"] = None

    if not retr_df.empty:
        result = result.merge(retr_df, on="Url", how="left")
    else:
        result["Retrievability"] = None
        result["Retrievability_Retrieved"] = None
        result["Retrievability_Total"] = None

    # Backfill titles from cached article text before deciding what to prune.
    filled = _backfill_titles_from_cache(result)
    if filled:
        print(f"Backfilled {filled} missing Title(s) from cache")

    # Prune rows still missing Title; record them in the audit log.
    title_missing_mask = result["Title"].isna() | (
        result["Title"].astype(str).str.strip() == ""
    )
    dropped_title = result[title_missing_mask]
    if not dropped_title.empty:
        _append_prune_log(dropped_title, "missing_title")
        print(f"Pruned {len(dropped_title)} row(s) with missing Title")
    result = result[~title_missing_mask].copy()

    # Prune rows missing Freshness (coalesced LMC Freshness / SMC FreshNess).
    freshness_series = _coalesce_freshness(result)
    freshness_missing_mask = freshness_series.isna() | (
        freshness_series.astype(str).str.strip() == ""
    )
    dropped_freshness = result[freshness_missing_mask]
    if not dropped_freshness.empty:
        _append_prune_log(dropped_freshness, "missing_freshness")
        print(f"Pruned {len(dropped_freshness)} row(s) with missing Freshness")
    result = result[~freshness_missing_mask].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge AI Readiness + Retrievability scores into the Power BI CSV"
    )
    parser.add_argument("--input", "-i", nargs="+", required=True,
                        help="One or more Power BI CSV exports")
    parser.add_argument("--ai-readiness", default=str(AI_READINESS_FILE),
                        help="AI readiness scores JSON path")
    parser.add_argument("--retrievability", default=str(RETRIEVABILITY_FILE),
                        help="Retrievability scores JSON path")
    parser.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT),
                        help="Output enriched CSV path")
    args = parser.parse_args()

    output_path = build_enriched_csv(
        input_paths=args.input,
        output_path=Path(args.output),
        ai_readiness_path=Path(args.ai_readiness),
        retrievability_path=Path(args.retrievability),
    )
    final = pd.read_csv(output_path)
    total = len(final)
    ai_scored = final["AIReadiness"].notna().sum() if "AIReadiness" in final.columns else 0
    retr_scored = final["Retrievability"].notna().sum() if "Retrievability" in final.columns else 0
    print(f"\nMerge summary:")
    print(f"  Kept rows:               {total}")
    print(f"  AI Readiness scored:     {ai_scored}/{total}")
    print(f"  Retrievability scored:   {retr_scored}/{total}")
    if ai_scored > 0:
        band_counts = final["AIReadiness"].value_counts().to_dict()
        print(f"  AI Readiness bands:      {band_counts}")
    if retr_scored > 0:
        print(f"  Retrievability mean:     {final['Retrievability'].mean():.1f}")
        print(f"  Retrievability median:   {final['Retrievability'].median():.1f}")
    print(f"\nSaved enriched report -> {output_path}")
    if PRUNE_LOG.exists():
        print(f"Prune log -> {PRUNE_LOG}")


if __name__ == "__main__":
    main()
