from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse


GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    flags=re.IGNORECASE,
)
LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}-[a-z]{2}$", flags=re.IGNORECASE)


def normalize_url(url: str | None) -> str:
    if url is None:
        return ""
    raw = str(url).strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")

    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.lower(),
        query="",
        fragment="",
    )
    return urlunparse(normalized).rstrip("/")


def infer_platform(url: str | None) -> str:
    host = urlparse(normalize_url(url)).netloc.lower()
    if host == "learn.microsoft.com":
        return "learn"
    if host == "support.microsoft.com":
        return "support"
    return "unknown"


def extract_url_path(url: str | None) -> str:
    path = urlparse(normalize_url(url)).path or ""
    parts = [part for part in path.split("/") if part]
    if parts and LOCALE_SEGMENT_RE.match(parts[0]):
        parts = parts[1:]
    return "/" + "/".join(parts) if parts else ""


def extract_support_guid(url: str | None) -> str:
    match = GUID_RE.search(normalize_url(url))
    return match.group(0).lower() if match else ""


def url_to_slug(url: str) -> str:
    normalized = normalize_url(url)
    slug = re.sub(r"https?://", "", normalized)
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    short_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:160]}_{short_hash}"


def url_matches_chunk_url(article_url: str, chunk_url: str) -> bool:
    normalized_article = normalize_url(article_url)
    normalized_chunk = normalize_url(chunk_url)
    if not normalized_article or not normalized_chunk:
        return False

    if normalized_article == normalized_chunk:
        return True

    support_guid = extract_support_guid(normalized_article)
    if support_guid and support_guid in normalized_chunk.lower():
        return True

    article_path = extract_url_path(normalized_article)
    chunk_path = extract_url_path(normalized_chunk)
    if not article_path or not chunk_path:
        return False

    return (
        article_path == chunk_path
        or article_path in chunk_path
        or chunk_path in article_path
    )
