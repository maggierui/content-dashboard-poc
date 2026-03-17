"""
fetch_articles.py - Build normalized article cache from source files or live pages.

Preferred sources:
    - Microsoft Learn raw markdown
    - Microsoft Support raw XML

Fallback:
    - Live HTML fetch if no matching source file is found
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from common.resolve_include_files import read_file_with_includes
from pipeline.engagement_inputs import load_unique_urls
from pipeline.url_utils import (
    extract_support_guid,
    extract_url_path,
    infer_platform,
    normalize_url,
    url_to_slug,
)

CACHE_DIR = ROOT / "data" / "cache"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ContentDashboard/1.0; "
        "+https://learn.microsoft.com)"
    )
}
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 30
GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    flags=re.IGNORECASE,
)
CONTENT_SUBPATH = Path("neutral") / "Content"


def _clean_text_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    for raw in lines:
        text = html.unescape(raw.replace("\xa0", " "))
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        if cleaned and cleaned[-1] == text:
            continue
        cleaned.append(text)

    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    return "\n".join(cleaned).strip()


def _normalize_inline_markup(text: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return text.strip()


def normalize_markdown_content(content: str) -> str:
    content = content.replace("\r\n", "\n")
    content = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|$)", "", content, flags=re.DOTALL)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    lines: list[str] = []
    in_code_block = False
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if not stripped:
            lines.append("")
            continue

        stripped = _normalize_inline_markup(stripped)
        if not stripped:
            continue

        if in_code_block:
            lines.append(stripped)
            continue
        if re.match(r"^#{1,6}\s+", stripped):
            lines.append(f"## {re.sub(r'^#{1,6}\s+', '', stripped).strip()}")
            continue
        if re.match(r"^\s*[-*+]\s+", stripped):
            lines.append(f"- {re.sub(r'^\s*[-*+]\s+', '', stripped).strip()}")
            continue
        if re.match(r"^\s*\d+[.)]\s+", stripped):
            lines.append(f"- {re.sub(r'^\s*\d+[.)]\s+', '', stripped).strip()}")
            continue
        if stripped.startswith(">"):
            lines.append(re.sub(r"^>\s*", "", stripped))
            continue
        if re.match(r"^\|?[-:\s|]+\|?$", stripped):
            continue

        lines.append(stripped)

    return _clean_text_lines(lines)


def normalize_markdown_file(path: Path) -> str:
    content = read_file_with_includes(str(path))
    if not content:
        content = path.read_text(encoding="utf-8")
    return normalize_markdown_content(content)


def normalize_xml_file(path: Path) -> str:
    parser = etree.XMLParser(recover=True, remove_comments=True)
    root = etree.fromstring(path.read_bytes(), parser=parser)

    heading_tags = {"title", "heading", "h1", "h2", "h3", "h4", "h5", "h6"}
    paragraph_tags = {
        "p",
        "para",
        "paragraph",
        "summary",
        "abstract",
        "caption",
        "note",
        "remark",
        "description",
    }
    list_tags = {"li", "listitem", "item", "step"}
    cell_tags = {"td", "th", "entry", "cell"}
    ignored_tags = {
        "script",
        "style",
        "metadata",
        "meta",
        "link",
        "links",
        "head",
        "header",
        "footer",
        "nav",
        "navigation",
    }

    lines: list[str] = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        tag = etree.QName(element).localname.lower()
        if tag in ignored_tags:
            continue

        text = " ".join(part.strip() for part in element.itertext() if part.strip())
        text = _normalize_inline_markup(text)
        if not text:
            continue

        if tag in heading_tags:
            lines.append(f"## {text}")
        elif tag in list_tags:
            lines.append(f"- {text}")
        elif tag in paragraph_tags or tag in cell_tags:
            lines.append(text)

    if not lines:
        lines = [part.strip() for part in root.itertext() if part and part.strip()]

    return _clean_text_lines(lines)


def fetch_article_text(url: str) -> str:
    """Fallback HTML extraction for cases where no source file is available."""
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup.find_all(
        ["script", "style", "nav", "header", "footer", "aside", "noscript"]
    ):
        tag.decompose()

    main_content = (
        soup.find("main")
        or soup.find(id="main-column")
        or soup.find(id="main")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_="content")
        or soup.body
    )
    if main_content is None:
        return ""

    lines: list[str] = []
    for element in main_content.descendants:
        if not getattr(element, "name", None):
            continue
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(f"## {text}")
        elif element.name == "p":
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(text)
        elif element.name == "li":
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(f"- {text}")
        elif element.name in ("th", "td"):
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(text)

    return _clean_text_lines(lines)


def load_source_map(map_path: Path | None) -> dict[str, Path]:
    if map_path is None or not map_path.exists():
        return {}

    if map_path.suffix.lower() == ".json":
        data = json.loads(map_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON source map must be an object of URL -> path")
        return {
            normalize_url(url): (
                Path(path) if Path(path).is_absolute() else map_path.parent / path
            )
            for url, path in data.items()
        }

    if map_path.suffix.lower() == ".csv":
        df = pd.read_csv(map_path)
        url_col = next((c for c in ("Url", "URL", "url") if c in df.columns), None)
        path_col = next(
            (
                c
                for c in ("Path", "FilePath", "SourcePath", "path", "file_path")
                if c in df.columns
            ),
            None,
        )
        if url_col is None or path_col is None:
            raise ValueError("CSV source map must contain URL and path columns")
        mapping: dict[str, Path] = {}
        for _, row in df.iterrows():
            url = normalize_url(row[url_col])
            raw_path = Path(str(row[path_col]))
            mapping[url] = raw_path if raw_path.is_absolute() else map_path.parent / raw_path
        return mapping

    raise ValueError(f"Unsupported source map format: {map_path}")


def _expand_content_roots(paths: list[Path] | None) -> list[Path]:
    expanded: list[Path] = []
    for raw_path in paths or []:
        path = raw_path.expanduser().resolve()
        nested_content = path / CONTENT_SUBPATH
        if nested_content.exists():
            candidates = [nested_content]
        else:
            candidates = [path]

        for candidate in candidates:
            if candidate.exists() and candidate not in expanded:
                expanded.append(candidate)
    return expanded


class SourceResolver:
    def __init__(
        self,
        learn_source_dirs: list[Path] | None,
        support_source_dirs: list[Path] | None,
        source_map: dict[str, Path],
    ) -> None:
        self.learn_source_dirs = _expand_content_roots(learn_source_dirs)
        self.support_source_dirs = _expand_content_roots(support_source_dirs)
        self.source_map = source_map
        self.learn_relative_index: dict[str, Path] = {}
        self.learn_stem_index: dict[str, list[Path]] = defaultdict(list)
        self.support_guid_index: dict[str, list[Path]] = defaultdict(list)
        self.support_stem_index: dict[str, list[Path]] = defaultdict(list)

        for learn_source_dir in self.learn_source_dirs:
            for path in learn_source_dir.rglob("*.md"):
                relative = str(path.relative_to(learn_source_dir)).replace("\\", "/").lower()
                self.learn_relative_index[relative] = path
                self.learn_stem_index[path.stem.lower()].append(path)

        for support_source_dir in self.support_source_dirs:
            for path in support_source_dir.rglob("*.ddue.xml"):
                support_stem = path.name[: -len(".ddue.xml")].lower()
                self.support_stem_index[support_stem].append(path)

            for meta_path in support_source_dir.rglob("*.ddue.xml.meta"):
                try:
                    meta_tree = etree.parse(str(meta_path))
                    guid = meta_tree.xpath('string(//*[local-name()="guid"]/@value)').strip().lower()
                except Exception:
                    continue
                if not guid:
                    continue
                xml_path = Path(str(meta_path)[:-5])
                if xml_path.exists():
                    self.support_guid_index[guid].append(xml_path)

    def resolve(self, url: str) -> Path | None:
        normalized = normalize_url(url)

        mapped = self.source_map.get(normalized)
        if mapped and mapped.exists():
            return mapped

        platform = infer_platform(normalized)
        if platform == "learn":
            return self._resolve_learn(normalized)
        if platform == "support":
            return self._resolve_support(normalized)
        return None

    def _resolve_learn(self, url: str) -> Path | None:
        if not self.learn_source_dirs:
            return None

        path = extract_url_path(url).strip("/")
        if not path:
            return None
        parts = path.split("/")
        candidates = [f"{path}.md"]
        if len(parts) > 1:
            candidates.append("/".join(parts[1:]) + ".md")
        for keep in (3, 2):
            if len(parts) >= keep:
                candidates.append("/".join(parts[-keep:]) + ".md")

        for candidate in candidates:
            direct = self.learn_relative_index.get(candidate.lower())
            if direct:
                return direct

        suffix_matches: list[Path] = []
        for candidate in candidates:
            suffix_matches.extend(
                path_obj
                for relative, path_obj in self.learn_relative_index.items()
                if relative.endswith(candidate.lower())
            )
        unique_suffixes = list(dict.fromkeys(suffix_matches))
        if len(unique_suffixes) == 1:
            return unique_suffixes[0]

        stem = parts[-1].lower()
        stem_matches = self.learn_stem_index.get(stem, [])
        if len(stem_matches) == 1:
            return stem_matches[0]

        return None

    def _resolve_support(self, url: str) -> Path | None:
        if not self.support_source_dirs:
            return None

        guid = extract_support_guid(url)
        if guid:
            guid_matches = self.support_guid_index.get(guid, [])
            if len(guid_matches) == 1:
                return guid_matches[0]

        stem = Path(extract_url_path(url)).name.lower()
        stem_matches = self.support_stem_index.get(stem, [])
        if len(stem_matches) == 1:
            return stem_matches[0]

        return None


def load_text_from_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return normalize_markdown_file(path)
    if suffix == ".xml":
        return normalize_xml_file(path)
    raise ValueError(f"Unsupported source file type: {path}")


def process_inputs(
    input_paths: list[Path],
    cache_dir: Path,
    force: bool = False,
    learn_source_dirs: list[Path] | None = None,
    support_source_dirs: list[Path] | None = None,
    source_map_path: Path | None = None,
) -> dict[str, str]:
    urls = load_unique_urls(input_paths)
    print(f"Found {len(urls)} unique URLs across {len(input_paths)} input file(s)")

    cache_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    processed = skipped = failed = 0
    source_map = load_source_map(source_map_path)
    resolver = SourceResolver(learn_source_dirs, support_source_dirs, source_map)

    for i, url in enumerate(urls, 1):
        slug = url_to_slug(url)
        cache_file = cache_dir / f"{slug}.txt"
        if cache_file.exists() and not force:
            print(f"  [{i}/{len(urls)}] CACHED   {url}")
            results[url] = str(cache_file)
            skipped += 1
            continue

        try:
            source_path = resolver.resolve(url)
            if source_path is not None:
                print(f"  [{i}/{len(urls)}] SOURCE   {url}  <- {source_path.name}")
                text = load_text_from_source(source_path)
            else:
                print(f"  [{i}/{len(urls)}] FETCH    {url}")
                text = fetch_article_text(url)

            if not text.strip():
                print(f"    Warning: empty content for {url}")
            cache_file.write_text(text, encoding="utf-8")
            results[url] = str(cache_file)
            processed += 1
        except Exception as exc:
            print(f"    Error processing {url}: {exc}")
            failed += 1
            results[url] = ""

        if i < len(urls):
            time.sleep(REQUEST_DELAY)

    print(
        f"\nDone: {processed} processed, {skipped} from cache, {failed} failed\n"
        f"Cache directory: {cache_dir}"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize article content into cache from source files or live pages"
    )
    parser.add_argument(
        "--input",
        "-i",
        nargs="+",
        required=True,
        help="One or more Power BI CSV exports",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(CACHE_DIR),
        help="Directory for cached article text files",
    )
    parser.add_argument(
        "--learn-source-dir",
        nargs="+",
        help="Directory containing raw Microsoft Learn markdown files",
    )
    parser.add_argument(
        "--support-source-dir",
        nargs="+",
        help="One or more directories containing raw Microsoft Support XML files",
    )
    parser.add_argument(
        "--source-map",
        help="Optional JSON or CSV mapping of article URL to source file path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild article cache even if files already exist",
    )
    args = parser.parse_args()

    process_inputs(
        input_paths=[Path(path) for path in args.input],
        cache_dir=Path(args.cache_dir),
        force=args.force,
        learn_source_dirs=[Path(path) for path in args.learn_source_dir] if args.learn_source_dir else None,
        support_source_dirs=[Path(path) for path in args.support_source_dir] if args.support_source_dir else None,
        source_map_path=Path(args.source_map) if args.source_map else None,
    )


if __name__ == "__main__":
    main()
