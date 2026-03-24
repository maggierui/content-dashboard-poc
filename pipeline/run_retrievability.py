"""
run_retrievability.py - Generate questions per article then hit-test the Knowledge Service.

Pipeline:
  Step 2a: Generate questions per article via concurrent direct API calls (default)
           or Azure OpenAI Batch API (--batch, requires a Global Batch deployment)
  Step 2b: Save questions checkpoint -> data/scores/questions.json
  Step 2c: Query Knowledge Service for each question
  Step 2d: Calculate hit-rate score (0–100)

Usage:
    python pipeline/run_retrievability.py --input data/sample_engagement.csv
    python pipeline/run_retrievability.py --input data/sample_engagement.csv --batch
    python pipeline/run_retrievability.py --input data/sample_engagement.csv --skip-qgen
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from common.knowledge_service import process_single_question
from common.send_openai_request import create_client, send_response_request
from common.prompts import load_prompt
from common.batch import write_jsonl, send_batch, get_batch_results
from pipeline.engagement_inputs import load_unique_urls
from pipeline.url_utils import url_matches_chunk_url, url_to_slug, infer_platform

# ── Configuration ─────────────────────────────────────────────────────────────
SCORES_DIR = ROOT / "data" / "scores"
CACHE_DIR = ROOT / "data" / "cache"
QUESTIONS_FILE = SCORES_DIR / "questions.json"
OUTPUT_FILE = SCORES_DIR / "retrievability_scores.json"
TOP_K = 5
MAX_WORKERS = 10
BATCH_SIZE = 10
BATCH_DELAY = 4  # seconds between KS batches

def find_cache_file(url: str, cache_dir: Path) -> Path | None:
    slug = url_to_slug(url)
    path = cache_dir / f"{slug}.txt"
    return path if path.exists() else None


def parse_questions_from_response(response: str) -> list[str]:
    """
    Extract both concise questions and BM25 keyword queries from LLM response.
    Returns plain strings (not RetrievalQuestion objects) for simplicity.
    """
    if not response:
        return []
    extracted = []
    for line in response.splitlines():
        s = line.strip()
        if not s:
            continue
        m_num = re.match(r'^\s*\d+\.\s*(.*)$', s)
        if m_num:
            content = m_num.group(1).strip()
            if ':' in content:
                after = content.split(':', 1)[1].strip()
                if after:
                    extracted.append(after)
                    continue
            extracted.append(content)
            continue
        m_bullet = re.match(r'^[\-\u2022]\s*(.*)$', s)
        if m_bullet:
            extracted.append(m_bullet.group(1).strip())
            continue
        m_bm25 = re.match(r'^(?:BM25\b.*?:\s*)(.+)$', s, flags=re.I)
        if m_bm25:
            extracted.append(m_bm25.group(1).strip())
    return [q for q in extracted if q]

# ── Step 2a: Question generation ─────────────────────────────────────────────

def generate_questions_direct(
    urls: list[str],
    cache_dir: Path,
    max_workers: int = 5,
) -> dict[str, list[str]]:
    """Generate questions for each article using concurrent direct API calls.

    Uses ThreadPoolExecutor so multiple articles are processed in parallel
    while staying within typical Azure OpenAI rate limits.
    """
    deployment = os.environ.get("DEPLOYMENT_NAME", "gpt-5-mini")
    prompt = load_prompt("question_generator_article")
    client = create_client()
    total = len(urls)

    def _process(idx_url: tuple[int, str]) -> tuple[str, list[str]]:
        i, url = idx_url
        cache_file = find_cache_file(url, cache_dir)
        if cache_file is None:
            print(f"  [{i}/{total}] SKIP (no cache)  {url}")
            return url, []
        content = cache_file.read_text(encoding="utf-8")
        if not content.strip():
            print(f"  [{i}/{total}] SKIP (empty)     {url}")
            return url, []
        print(f"  [{i}/{total}] Gen questions: {url}")
        try:
            response = send_response_request(deployment, prompt, content, "low", client=client)
            qs = parse_questions_from_response(response)
            qs = qs[:10]  # cap at 10 (5 concise + 5 BM25)
            print(f"    -> {len(qs)} questions for {url[:60]}...")
            return url, qs
        except Exception as exc:
            print(f"    Error for {url}: {exc}")
            return url, []

    questions: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for url, qs in executor.map(_process, enumerate(urls, 1)):
            if qs:
                questions[url] = qs

    return questions


def generate_questions_batch(
    urls: list[str],
    cache_dir: Path,
) -> dict[str, list[str]]:
    """Generate questions for all articles via Azure OpenAI Batch API."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_file = SCORES_DIR / f"qgen_batch_{timestamp}.jsonl"
    SCORES_DIR.mkdir(parents=True, exist_ok=True)

    batch_deployment = os.environ.get("BATCH_DEPLOYMENT_NAME", "gpt-5-batch")
    prompt = load_prompt("question_generator_article")

    url_has_content: list[str] = []
    for url in urls:
        cache_file = find_cache_file(url, cache_dir)
        if cache_file is None or not cache_file.read_text(encoding="utf-8").strip():
            continue
        content = cache_file.read_text(encoding="utf-8")
        write_jsonl(prompt, url, batch_deployment, content, str(batch_file))
        url_has_content.append(url)

    if not batch_file.exists():
        return {}

    print(f"Submitting question-gen batch ({len(url_has_content)} articles)…")
    batch_id = send_batch(str(batch_file))
    batch_results = get_batch_results(batch_id)

    questions: dict[str, list[str]] = {}
    for url in url_has_content:
        response_text = batch_results.get(url, "")
        qs = parse_questions_from_response(response_text)
        questions[url] = qs[:10]

    return questions


# ── Step 2c: Knowledge Service queries ───────────────────────────────────────

def check_url_in_chunks(article_url: str, chunks: list[dict]) -> bool:
    """Return True if article_url's path appears in any chunk URL."""
    for chunk in chunks:
        chunk_url = chunk.get("url", "")
        if url_matches_chunk_url(article_url, chunk_url):
            return True
    return False


SMC_FILTER = "site eq 'support.microsoft.com'"


def query_ks_for_article(
    article_url: str,
    questions: list[str],
) -> dict:
    """
    Query KS for all questions of one article and compute hit-rate score.

    Each question result records 'chunks_returned' — if the KS returned 0
    chunks the call likely failed silently (rate-limit, auth error, empty
    response body).  These are counted in 'error_count' so callers can
    distinguish genuine misses from silent failures.
    """
    question_results = []
    retrieved_count = 0
    error_count = 0  # questions where KS returned 0 chunks (suspicious)

    filter_expr = SMC_FILTER if infer_platform(article_url) == "support" else None

    for question in questions:
        try:
            chunks = process_single_question(question, top_k=TOP_K, filter_expr=filter_expr)
            chunk_count = len(chunks)
            found = check_url_in_chunks(article_url, chunks)
        except Exception as exc:
            print(f"    KS exception for '{question[:60]}': {exc}")
            chunks = []
            chunk_count = 0
            found = False

        if chunk_count == 0:
            error_count += 1  # 0 chunks returned is never normal for a live KS

        question_results.append({
            "text": question,
            "retrieved": found,
            "chunks_returned": chunk_count,
        })
        if found:
            retrieved_count += 1

    total_questions = len(questions)
    score = round((retrieved_count / total_questions) * 100) if total_questions > 0 else 0

    return {
        "score": score,
        "retrieved_count": retrieved_count,
        "total_questions": total_questions,
        "error_count": error_count,   # >0 means some/all calls likely failed
        "questions": question_results,
    }


def query_all_articles_parallel(
    article_questions: dict[str, list[str]],
    max_workers: int = MAX_WORKERS,
) -> dict[str, dict]:
    """Query KS for all articles using ThreadPoolExecutor with batching."""
    items = list(article_questions.items())
    results: dict[str, dict] = {}

    print(f"Querying Knowledge Service for {len(items)} articles "
          f"({sum(len(q) for _, q in items)} total questions)…")

    for batch_start in range(0, len(items), BATCH_SIZE):
        batch = items[batch_start: batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} "
              f"(articles {batch_start + 1}–{batch_start + len(batch)})…")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(query_ks_for_article, url, qs): url
                for url, qs in batch
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                    score = results[url]["score"]
                    retrieved = results[url]["retrieved_count"]
                    total = results[url]["total_questions"]
                    errors = results[url].get("error_count", 0)
                    err_tag = f"  *** {errors} KS errors ***" if errors else ""
                    print(f"    {url[:80]}…  score={score} ({retrieved}/{total}){err_tag}")
                except Exception as exc:
                    print(f"    Error for {url}: {exc}")
                    results[url] = {
                        "score": 0,
                        "retrieved_count": 0,
                        "total_questions": len(article_questions.get(url, [])),
                        "questions": [],
                    }

        # Polite delay between batches
        if batch_start + BATCH_SIZE < len(items):
            print(f"  Sleeping {BATCH_DELAY}s…")
            time.sleep(BATCH_DELAY)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Retrievability scoring (question-gen + KS hit-rate)"
    )
    parser.add_argument("--input", "-i", nargs="+", required=True,
                        help="One or more Power BI CSV exports")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR),
                        help="Article cache directory")
    parser.add_argument("--questions-file", default=str(QUESTIONS_FILE),
                        help="Questions checkpoint JSON path")
    parser.add_argument("--output", default=str(OUTPUT_FILE),
                        help="Output JSON file path")
    parser.add_argument("--batch", action="store_true",
                        help="Use Azure OpenAI Batch API (requires a Global Batch deployment in Azure portal)")
    parser.add_argument("--skip-qgen", action="store_true",
                        help="Skip question generation (load from --questions-file)")
    parser.add_argument("--rescore-zeros", action="store_true",
                        help="Re-score any article whose saved score is 0 "
                             "(catches articles that silently failed due to KS errors)")
    args = parser.parse_args()

    urls = load_unique_urls(args.input)
    print(f"Processing {len(urls)} URLs from {len(args.input)} input file(s)")

    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir)
    questions_path = Path(args.questions_file)
    output_path = Path(args.output)

    # ── Step 2a/2b: Generate or load questions ────────────────────────────────
    if args.skip_qgen and questions_path.exists():
        with open(questions_path, encoding="utf-8") as f:
            all_questions: dict[str, list[str]] = json.load(f)
        print(f"Loaded questions for {len(all_questions)} articles from checkpoint")
    else:
        print("\n=== Step 2a: Generating questions ===")
        # Load existing checkpoint to avoid re-generating
        existing_questions: dict[str, list[str]] = {}
        if questions_path.exists():
            with open(questions_path, encoding="utf-8") as f:
                existing_questions = json.load(f)
            print(f"  {len(existing_questions)} articles already have questions")

        remaining = [u for u in urls if u not in existing_questions]
        if remaining:
            if args.batch:
                new_questions = generate_questions_batch(remaining, cache_dir)
            else:
                new_questions = generate_questions_direct(remaining, cache_dir)
            existing_questions.update(new_questions)

        all_questions = existing_questions
        questions_path.write_text(
            json.dumps(all_questions, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Saved questions checkpoint -> {questions_path}")

    # Filter to only articles that have questions
    article_questions = {
        url: qs
        for url, qs in all_questions.items()
        if qs and url in urls
    }
    print(f"\n=== Step 2c+2d: Querying Knowledge Service ===")
    print(f"  Articles with questions: {len(article_questions)}")

    # Load existing retrievability scores to allow incremental runs
    existing_scores: dict = {}
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            existing_scores = json.load(f)
        print(f"  {len(existing_scores)} articles already scored")

    def _should_score(url: str) -> bool:
        if url not in existing_scores:
            return True
        if args.rescore_zeros and existing_scores[url]["score"] == 0:
            return True
        return False

    to_score = {url: qs for url, qs in article_questions.items() if _should_score(url)}
    if args.rescore_zeros:
        zeros = sum(1 for u in article_questions if u in existing_scores
                    and existing_scores[u]["score"] == 0)
        print(f"  --rescore-zeros: {zeros} zero-score articles will be re-run")
    print(f"  Articles to score: {len(to_score)}")

    new_scores = query_all_articles_parallel(to_score)
    existing_scores.update(new_scores)

    output_path.write_text(
        json.dumps(existing_scores, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved {len(existing_scores)} retrievability scores -> {output_path}")


if __name__ == "__main__":
    main()
