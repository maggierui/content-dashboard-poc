"""
run_ai_readiness.py - Grade articles across 10 RAG-readiness dimensions.

Usage:
    # Default (direct async calls, any number of articles):
    python pipeline/run_ai_readiness.py --input data/sample_engagement.csv

    # Batch mode (requires a Global Batch deployment in Azure OpenAI portal):
    python pipeline/run_ai_readiness.py --input data/sample_engagement.csv --batch

    # Re-score already-cached articles without re-fetching:
    python pipeline/run_ai_readiness.py --input data/sample_engagement.csv --cache-dir data/cache

Output: data/scores/ai_readiness_scores.json
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

# Ensure the AI-readiness grader can find its own prompts regardless of cwd
GRADER_DIR = ROOT / "project-content-improvement"
sys.path.insert(0, str(GRADER_DIR))

load_dotenv(ROOT / ".env")

from analyze_content import analyze_dimensions as analyze_dimensions_for_content, ALL_DIMENSIONS
from pipeline.engagement_inputs import load_unique_urls
from pipeline.url_utils import url_to_slug

# ── Configuration ─────────────────────────────────────────────────────────────
SCORES_DIR = ROOT / "data" / "scores"
CACHE_DIR = ROOT / "data" / "cache"
OUTPUT_FILE = SCORES_DIR / "ai_readiness_scores.json"

# Band thresholds (total recommendations across all 10 dimensions)
BAND_HIGH_MAX = 3    # 0–3   → High
BAND_MEDIUM_MAX = 8  # 4–8   → Medium
# 9+                          → Low


def assign_band(total_recs: int) -> str:
    if total_recs <= BAND_HIGH_MAX:
        return "High"
    if total_recs <= BAND_MEDIUM_MAX:
        return "Medium"
    return "Low"

def find_cache_file(url: str, cache_dir: Path) -> Path | None:
    slug = url_to_slug(url)
    path = cache_dir / f"{slug}.txt"
    return path if path.exists() else None


async def score_article(
    client,
    deployment: str,
    url: str,
    content: str,
) -> dict:
    """Run all 10 dimensions for one article, return score dict."""
    all_results = await analyze_dimensions_for_content(client, deployment, content, ALL_DIMENSIONS)

    by_dimension: dict[str, int] = {}
    recommendations_by_dimension: dict[str, list] = {}
    for dim, result in all_results.items():
        data = result.get("data") or {}
        recs = data.get("recommendations", [])
        by_dimension[dim] = len(recs)
        recommendations_by_dimension[dim] = recs

    total = sum(by_dimension.values())
    weakest = max(by_dimension, key=by_dimension.get) if by_dimension else ""

    return {
        "band": assign_band(total),
        "total_recommendations": total,
        "weakest_dimension": weakest,
        "by_dimension": by_dimension,
        "recommendations_by_dimension": recommendations_by_dimension,
    }


async def run_direct(
    urls: list[str],
    cache_dir: Path,
    existing: dict,
) -> dict:
    """Run AI Readiness grading directly (no batch API)."""
    from openai import AsyncAzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ.get("AZURE_OPENAI_KEY")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    deployment = os.environ.get("DEPLOYMENT_NAME", "gpt-5-mini")

    if api_key:
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
    else:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
        )

    results = dict(existing)
    to_process = [u for u in urls if u not in results]

    print(f"Articles to grade: {len(to_process)} "
          f"({len(results)} already scored, skipping)")

    for i, url in enumerate(to_process, 1):
        cache_file = find_cache_file(url, cache_dir)
        if cache_file is None:
            print(f"  [{i}/{len(to_process)}] SKIP (no cache)  {url}")
            continue

        content = cache_file.read_text(encoding="utf-8")
        if not content.strip():
            print(f"  [{i}/{len(to_process)}] SKIP (empty)     {url}")
            continue

        print(f"  [{i}/{len(to_process)}] Grading: {url}")
        try:
            score = await score_article(client, deployment, url, content)
            results[url] = score
            print(f"    → {score['band']} ({score['total_recommendations']} recs, "
                  f"weakest: {score['weakest_dimension']})")
        except Exception as exc:
            print(f"    Error: {exc}")

    return results


def run_batch(
    urls: list[str],
    cache_dir: Path,
    existing: dict,
) -> dict:
    """
    Submit AI Readiness grading via Azure OpenAI Batch API.
    One JSONL request per (article, dimension) pair.
    """
    import datetime
    from common.batch import write_jsonl, send_batch, get_batch_results

    # Re-import grader helpers to build messages without the async client
    sys.path.insert(0, str(ROOT / "project-content-improvement"))
    from analyze_content import create_dimension_messages, ALL_DIMENSIONS as DIMS

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_file = ROOT / "data" / "scores" / f"ai_readiness_batch_{timestamp}.jsonl"
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    batch_deployment = os.environ.get("BATCH_DEPLOYMENT_NAME", "gpt-5-batch")

    results = dict(existing)
    to_process = [u for u in urls if u not in results]
    print(f"Articles to grade (batch): {len(to_process)}")

    # Map custom_id → (url, dimension)
    id_map: dict[str, tuple[str, str]] = {}

    for url in to_process:
        cache_file = find_cache_file(url, cache_dir)
        if cache_file is None or not cache_file.read_text(encoding="utf-8").strip():
            continue
        content = cache_file.read_text(encoding="utf-8")

        for dim in DIMS:
            messages = create_dimension_messages(dim, content)
            custom_id = f"{url}|||{dim}"
            id_map[custom_id] = (url, dim)
            # Flatten messages to system/user for chat completions batch format
            system_msg = next(m["content"] for m in messages if m["role"] == "system")
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            write_jsonl(system_msg, custom_id, batch_deployment, user_msg, str(batch_file))

    if not batch_file.exists():
        print("Nothing to submit.")
        return results

    print(f"Submitting batch: {batch_file}")
    batch_id = send_batch(str(batch_file))
    batch_results = get_batch_results(batch_id)

    # Aggregate per-article
    article_dim_recs: dict[str, dict[str, int]] = {}
    for custom_id, response_text in batch_results.items():
        if "|||" not in custom_id:
            continue
        url, dim = custom_id.split("|||", 1)
        try:
            data = json.loads(response_text)
            recs = len(data.get("recommendations", []))
        except Exception:
            recs = 0
        article_dim_recs.setdefault(url, {})[dim] = recs

    for url, by_dim in article_dim_recs.items():
        total = sum(by_dim.values())
        weakest = max(by_dim, key=by_dim.get) if by_dim else ""
        results[url] = {
            "band": assign_band(total),
            "total_recommendations": total,
            "weakest_dimension": weakest,
            "by_dimension": by_dim,
        }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AI Readiness scoring on cached articles"
    )
    parser.add_argument("--input", "-i", nargs="+", required=True,
                        help="One or more Power BI CSV exports")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR),
                        help="Article cache directory")
    parser.add_argument("--output", default=str(OUTPUT_FILE),
                        help="Output JSON file path")
    parser.add_argument("--batch", action="store_true",
                        help="Use Azure OpenAI Batch API (requires a Global Batch deployment in Azure portal)")
    parser.add_argument("--force", action="store_true",
                        help="Re-score all articles even if already in the output file "
                             "(use this to populate recommendations_by_dimension in existing scores)")
    args = parser.parse_args()

    urls = load_unique_urls(args.input)
    print(f"Loaded {len(urls)} unique URLs from {len(args.input)} input file(s)")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing scores to allow incremental runs
    existing: dict = {}
    if output_path.exists() and not args.force:
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing scores from {output_path.name}")
    elif args.force:
        print("--force: ignoring existing scores, re-grading all articles")

    cache_dir = Path(args.cache_dir)

    if args.batch:
        final_scores = run_batch(urls, cache_dir, existing)
    else:
        final_scores = asyncio.run(run_direct(urls, cache_dir, existing))

    output_path.write_text(
        json.dumps(final_scores, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved {len(final_scores)} scores → {output_path}")


if __name__ == "__main__":
    main()
