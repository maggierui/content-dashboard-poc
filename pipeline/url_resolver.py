"""
url_resolver.py - Map Learn article URLs to GitHub/VS Code Web URLs.

Uses config/repo_url_map.json for longest-prefix matching.
"""
import json
from pathlib import Path

LEARN_BASE = "https://learn.microsoft.com/en-us/"


def url_to_slug(url: str) -> str:
    """Convert a Learn article URL to a filesystem-safe slug (used for report filenames)."""
    path = url.rstrip("/")
    if path.startswith(LEARN_BASE):
        path = path[len(LEARN_BASE):]
    return path.replace("/", "_")


def resolve_github_urls(learn_url: str, map_path: Path) -> dict:
    """
    Given a Learn article URL, return GitHub edit and VS Code Web URLs.

    Returns a dict with:
      - github_edit_url: https://github.com/{org}/{repo}/edit/{branch}/{path}.md
      - vscode_url:      https://github.dev/{org}/{repo}/blob/{branch}/{path}.md
      - fallback_url:    original Learn URL (used when no repo mapping found)
      - matched:         True if a repo mapping was found
    """
    fallback = {"github_edit_url": None, "vscode_url": None,
                "fallback_url": learn_url, "matched": False}

    if not map_path.exists():
        return fallback

    with open(map_path, encoding="utf-8") as f:
        repo_map: dict = json.load(f)

    # Strip Learn base prefix and trailing slash
    url = learn_url.rstrip("/")
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
        "fallback_url": learn_url,
        "matched": True,
    }
