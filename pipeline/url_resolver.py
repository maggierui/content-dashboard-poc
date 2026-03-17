"""
url_resolver.py - Map Learn article URLs to GitHub/VS Code Web URLs.

Uses config/repo_url_map.json for longest-prefix matching.
"""
import json
from pathlib import Path

from pipeline.url_utils import infer_platform, normalize_url, url_to_slug

LEARN_BASE = "https://learn.microsoft.com/en-us/"

def load_repo_map(map_path: Path) -> dict:
    """Load the repo URL map from disk. Returns {} if file does not exist."""
    if not map_path.exists():
        return {}
    with open(map_path, encoding="utf-8") as f:
        return json.load(f)


def resolve_github_urls(article_url: str, repo_map: dict) -> dict:
    """
    Given a Learn article URL and a pre-loaded repo map, return GitHub/VS Code URLs.

    repo_map should be the dict returned by load_repo_map().

    Returns a dict with:
      - github_edit_url: https://github.com/{org}/{repo}/edit/{branch}/{path}.md
      - vscode_url:      https://github.dev/{org}/{repo}/blob/{branch}/{path}.md
      - fallback_url:    original Learn URL (used when no repo mapping found)
      - matched:         True if a repo mapping was found
    """
    normalized_url = normalize_url(article_url)
    fallback = {"github_edit_url": None, "vscode_url": None,
                "fallback_url": normalized_url, "matched": False}

    # Strip Learn base prefix and trailing slash
    url = normalized_url.rstrip("/")
    if infer_platform(url) != "learn":
        return fallback
    if url.startswith(LEARN_BASE):
        path = url[len(LEARN_BASE):]
    else:
        return fallback

    # Longest-prefix match
    best_prefix = ""
    best_entry = None
    for prefix, entry in repo_map.items():
        if path.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_entry = entry

    if best_entry is None:
        return fallback

    org = best_entry["org"]
    repo = best_entry["repo"]
    branch = best_entry["branch"]

    return {
        "github_edit_url": f"https://github.com/{org}/{repo}/edit/{branch}/{path}.md",
        "vscode_url": f"https://github.dev/{org}/{repo}/blob/{branch}/{path}.md",
        "fallback_url": normalized_url,
        "matched": True,
    }
