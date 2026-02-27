"""
verify_retrievability.py - Spot-check retrievability scoring for one article.

Loads the article's saved questions from questions.json, queries the Knowledge
Service live, and prints exactly what chunks were returned and whether the
article URL was found — so you can see whether a score of 0 is a genuine miss
or a silent KS failure.

Usage:
    # Verify a specific URL
    python pipeline/verify_retrievability.py --url "https://learn.microsoft.com/en-us/..."

    # List all zero-score articles (to pick one to verify)
    python pipeline/verify_retrievability.py --list-zeros

    # Show error summary across all saved scores
    python pipeline/verify_retrievability.py --summary
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

QUESTIONS_FILE = ROOT / "data" / "scores" / "questions.json"
SCORES_FILE = ROOT / "data" / "scores" / "retrievability_scores.json"
TOP_K = 5


def extract_url_path(url: str) -> str:
    path = re.sub(r"https?://[^/]+", "", url)
    path = path.split("?")[0].rstrip("/")
    path = re.sub(r"^/[a-z]{2}-[a-z]{2}/", "/", path)
    return path


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_summary(scores: dict) -> None:
    """Print aggregate error statistics across all saved scores."""
    total = len(scores)
    zero_score = sum(1 for s in scores.values() if s["score"] == 0)
    has_errors = sum(1 for s in scores.values() if s.get("error_count", 0) > 0)
    all_errors = sum(
        1 for s in scores.values()
        if s.get("error_count", 0) == s.get("total_questions", 0) > 0
    )

    print(f"=== Retrievability Score Summary ===")
    print(f"  Total articles scored:       {total}")
    print(f"  Score = 0:                   {zero_score} ({zero_score/total*100:.1f}%)")
    print(f"  Has any KS errors:           {has_errors}")
    print(f"  All questions KS-errored:    {all_errors}  ← these are likely false zeros")
    print()

    # Score distribution
    buckets = {"0": 0, "1-39": 0, "40-69": 0, "70-99": 0, "100": 0}
    for s in scores.values():
        sc = s["score"]
        if sc == 0:
            buckets["0"] += 1
        elif sc < 40:
            buckets["1-39"] += 1
        elif sc < 70:
            buckets["40-69"] += 1
        elif sc < 100:
            buckets["70-99"] += 1
        else:
            buckets["100"] += 1

    print("  Score distribution:")
    for band, count in buckets.items():
        bar = "█" * (count * 40 // max(total, 1))
        print(f"    {band:6s}  {bar}  {count}")


def cmd_list_zeros(scores: dict) -> None:
    """List all zero-score articles with their error count."""
    zeros = {
        url: s for url, s in scores.items() if s["score"] == 0
    }
    if not zeros:
        print("No zero-score articles found.")
        return

    print(f"Zero-score articles ({len(zeros)} total):\n")
    for url, s in zeros.items():
        errors = s.get("error_count", "?")
        total = s.get("total_questions", "?")
        likely_ks_fail = " ← likely KS failure" if errors == total else ""
        print(f"  errors={errors}/{total}{likely_ks_fail}")
        print(f"  {url}")
        print()


def cmd_verify(url: str, questions_data: dict, scores: dict) -> None:
    """Live-verify one article against the KS and compare to saved score."""
    from common.knowledge_service import process_single_question

    # Normalise URL
    url = url.rstrip("/")

    questions = questions_data.get(url)
    if not questions:
        # Try without locale
        for key in questions_data:
            if extract_url_path(key) == extract_url_path(url):
                questions = questions_data[key]
                url = key
                break

    if not questions:
        print(f"No questions found for: {url}")
        print("Run run_retrievability.py first to generate questions.")
        sys.exit(1)

    saved = scores.get(url)
    article_path = extract_url_path(url)

    print(f"=== Verifying Retrievability ===")
    print(f"URL:          {url}")
    print(f"Match path:   {article_path}")
    if saved:
        print(f"Saved score:  {saved['score']} "
              f"({saved['retrieved_count']}/{saved['total_questions']} retrieved, "
              f"errors={saved.get('error_count', 'unknown')})")
    else:
        print("Saved score:  (not yet scored)")
    print(f"Questions:    {len(questions)}")
    print()

    live_retrieved = 0
    live_errors = 0

    for i, question in enumerate(questions, 1):
        print(f"Q{i}: {question}")
        try:
            chunks = process_single_question(question, top_k=TOP_K)
        except Exception as exc:
            print(f"  ERROR: {exc}\n")
            live_errors += 1
            continue

        if not chunks:
            print(f"  KS returned 0 chunks  ← suspicious, likely a KS failure")
            live_errors += 1
            print()
            continue

        found = False
        print(f"  KS returned {len(chunks)} chunks:")
        for j, chunk in enumerate(chunks, 1):
            chunk_url = chunk.get("url", "")
            match = article_path in chunk_url
            marker = "  MATCH" if match else ""
            print(f"    [{j}] {chunk_url[:90]}{marker}")
            if match:
                found = True

        if found:
            live_retrieved += 1
            print("  RESULT: RETRIEVED")
        else:
            print("  RESULT: not retrieved")
        print()

    # Summary
    total = len(questions)
    live_score = round((live_retrieved / total) * 100) if total > 0 else 0
    print(f"=== Live Result ===")
    print(f"  Score:       {live_score} ({live_retrieved}/{total} retrieved)")
    print(f"  KS errors:   {live_errors}/{total} questions returned 0 chunks")

    if saved:
        if live_score != saved["score"]:
            print(f"  MISMATCH with saved score of {saved['score']} ← saved score is wrong")
        else:
            print(f"  Matches saved score of {saved['score']}")

    if live_errors == total:
        print()
        print("  All questions returned 0 chunks.")
        print("  This is almost certainly a KS authentication or rate-limit failure,")
        print("  not a genuine retrievability score of 0.")
        print("  Re-run with: python pipeline/run_retrievability.py "
              "--input data/sample_engagement.csv --skip-qgen --rescore-zeros")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spot-check retrievability scoring for one article"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Article URL to verify live against the KS")
    group.add_argument("--list-zeros", action="store_true",
                       help="List all zero-score articles")
    group.add_argument("--summary", action="store_true",
                       help="Show aggregate error statistics")
    args = parser.parse_args()

    scores = load_json(SCORES_FILE)

    if args.summary:
        cmd_summary(scores)
    elif args.list_zeros:
        cmd_list_zeros(scores)
    else:
        questions_data = load_json(QUESTIONS_FILE)
        cmd_verify(args.url, questions_data, scores)


if __name__ == "__main__":
    main()
