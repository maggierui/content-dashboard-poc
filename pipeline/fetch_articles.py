"""
fetch_articles.py - Fetch and cache article text from learn.microsoft.com

Usage:
    python pipeline/fetch_articles.py --input data/sample_engagement.csv
    python pipeline/fetch_articles.py --input data/sample_engagement.csv --url-col Url
    python pipeline/fetch_articles.py --input data/sample_engagement.csv --force  # re-fetch all
"""
import argparse
import hashlib
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

CACHE_DIR = ROOT / "data" / "cache"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ContentDashboard/1.0; "
        "+https://learn.microsoft.com)"
    )
}
REQUEST_DELAY = 0.5   # seconds between requests to be polite
REQUEST_TIMEOUT = 30  # seconds


def url_to_slug(url: str) -> str:
    """Convert a URL to a safe filename slug."""
    # Remove scheme and normalise separators
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    # Truncate + append short hash to avoid collisions on long paths
    short_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{slug[:160]}_{short_hash}"


def fetch_article_text(url: str) -> str:
    """
    Fetch a learn.microsoft.com page and return clean article text.
    Parses <main> or #main-column; strips nav/scripts/styles.
    """
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                               "aside", "noscript"]):
        tag.decompose()

    # Try to find the main article content in priority order
    main_content = (
        soup.find("main")
        or soup.find(id="main-column")
        or soup.find(id="main")
        or soup.find(class_="content")
        or soup.body
    )

    if main_content is None:
        return ""

    # Extract text with reasonable spacing
    lines = []
    for element in main_content.descendants:
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lines.append(f"\n## {element.get_text(strip=True)}\n")
        elif element.name == "p":
            text = element.get_text(strip=True)
            if text:
                lines.append(text)
        elif element.name in ("li",):
            text = element.get_text(strip=True)
            if text:
                lines.append(f"- {text}")
        elif element.name in ("th", "td"):
            text = element.get_text(strip=True)
            if text:
                lines.append(text)

    return "\n".join(lines).strip()


def process_csv(
    csv_path: Path,
    url_col: str,
    cache_dir: Path,
    force: bool = False,
) -> dict[str, str]:
    """
    Read the Power BI CSV and fetch/cache article text for each URL.

    Returns a mapping of {url: cache_file_path}.
    """
    df = pd.read_csv(csv_path)
    if url_col not in df.columns:
        raise ValueError(
            f"Column '{url_col}' not found in CSV. "
            f"Available columns: {list(df.columns)}"
        )

    urls = df[url_col].dropna().unique().tolist()
    print(f"Found {len(urls)} unique URLs in {csv_path.name}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    fetched = skipped = failed = 0

    for i, url in enumerate(urls, 1):
        slug = url_to_slug(url)
        cache_file = cache_dir / f"{slug}.txt"

        if cache_file.exists() and not force:
            print(f"  [{i}/{len(urls)}] CACHED  {url}")
            results[url] = str(cache_file)
            skipped += 1
            continue

        try:
            print(f"  [{i}/{len(urls)}] FETCH   {url}")
            text = fetch_article_text(url)
            if not text.strip():
                print(f"    Warning: empty content for {url}")
            cache_file.write_text(text, encoding="utf-8")
            results[url] = str(cache_file)
            fetched += 1
        except Exception as exc:
            print(f"    Error fetching {url}: {exc}")
            failed += 1
            results[url] = ""

        # Polite delay between requests
        if i < len(urls):
            time.sleep(REQUEST_DELAY)

    print(
        f"\nDone: {fetched} fetched, {skipped} from cache, {failed} failed\n"
        f"Cache directory: {cache_dir}"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch and cache article text from learn.microsoft.com"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to Power BI CSV export (must have a URL column)",
    )
    parser.add_argument(
        "--url-col",
        default="Url",
        help="Name of the URL column in the CSV (default: Url)",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(CACHE_DIR),
        help="Directory for cached article text files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch articles even if already cached",
    )
    args = parser.parse_args()

    process_csv(
        csv_path=Path(args.input),
        url_col=args.url_col,
        cache_dir=Path(args.cache_dir),
        force=args.force,
    )


if __name__ == "__main__":
    main()
