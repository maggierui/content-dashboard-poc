"""
merge_scores.py - Merge Power BI CSV with AI Readiness and Retrievability scores.

Usage:
    python pipeline/merge_scores.py --input data/sample_engagement.csv
    python pipeline/merge_scores.py --input data/sample_engagement.csv --output data/enriched_report.csv
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

SCORES_DIR = ROOT / "data" / "scores"
AI_READINESS_FILE = SCORES_DIR / "ai_readiness_scores.json"
RETRIEVABILITY_FILE = SCORES_DIR / "retrievability_scores.json"
DEFAULT_OUTPUT = ROOT / "data" / "enriched_report.csv"


def load_ai_readiness(path: Path) -> pd.DataFrame:
    """Load AI readiness scores and flatten into a DataFrame."""
    if not path.exists():
        print(f"Warning: AI Readiness scores not found at {path}")
        return pd.DataFrame(columns=["Url", "AIReadiness", "AIReadiness_WeakestDim",
                                     "AIReadiness_TotalRecs"])

    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)

    rows = []
    for url, score in data.items():
        rows.append({
            "Url": url,
            "AIReadiness": score.get("band", ""),
            "AIReadiness_WeakestDim": score.get("weakest_dimension", ""),
            "AIReadiness_TotalRecs": score.get("total_recommendations", None),
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge AI Readiness + Retrievability scores into the Power BI CSV"
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to Power BI CSV export")
    parser.add_argument("--url-col", default="Url",
                        help="URL column name in the CSV (default: Url)")
    parser.add_argument("--ai-readiness", default=str(AI_READINESS_FILE),
                        help="AI readiness scores JSON path")
    parser.add_argument("--retrievability", default=str(RETRIEVABILITY_FILE),
                        help="Retrievability scores JSON path")
    parser.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT),
                        help="Output enriched CSV path")
    args = parser.parse_args()

    # Load the main engagement CSV
    df = pd.read_csv(args.input)
    if args.url_col not in df.columns:
        print(f"Error: column '{args.url_col}' not found. "
              f"Columns: {list(df.columns)}")
        sys.exit(1)
    print(f"Loaded {len(df)} rows from {args.input}")

    # Normalise URL column to strip trailing slashes for consistent joins
    df[args.url_col] = df[args.url_col].str.rstrip("/")

    # Load scores
    ai_df = load_ai_readiness(Path(args.ai_readiness))
    if not ai_df.empty:
        ai_df["Url"] = ai_df["Url"].str.rstrip("/")
    retr_df = load_retrievability(Path(args.retrievability))
    if not retr_df.empty:
        retr_df["Url"] = retr_df["Url"].str.rstrip("/")

    # Merge on URL (left join to keep all rows from the original CSV)
    result = df.copy()

    if not ai_df.empty:
        result = result.merge(
            ai_df.rename(columns={"Url": args.url_col}),
            on=args.url_col,
            how="left",
        )
    else:
        result["AIReadiness"] = None
        result["AIReadiness_WeakestDim"] = None
        result["AIReadiness_TotalRecs"] = None

    if not retr_df.empty:
        result = result.merge(
            retr_df.rename(columns={"Url": args.url_col}),
            on=args.url_col,
            how="left",
        )
    else:
        result["Retrievability"] = None
        result["Retrievability_Retrieved"] = None
        result["Retrievability_Total"] = None

    # Summary
    total = len(result)
    ai_scored = result["AIReadiness"].notna().sum()
    retr_scored = result["Retrievability"].notna().sum()
    print(f"\nMerge summary:")
    print(f"  Total rows:              {total}")
    print(f"  AI Readiness scored:     {ai_scored}/{total}")
    print(f"  Retrievability scored:   {retr_scored}/{total}")
    if ai_scored > 0:
        band_counts = result["AIReadiness"].value_counts().to_dict()
        print(f"  AI Readiness bands:      {band_counts}")
    if retr_scored > 0:
        print(f"  Retrievability mean:     {result['Retrievability'].mean():.1f}")
        print(f"  Retrievability median:   {result['Retrievability'].median():.1f}")

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"\nSaved enriched report → {output_path}")


if __name__ == "__main__":
    main()
