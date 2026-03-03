"""
generate_reports.py - Generate self-contained per-article AI Readiness HTML reports.

Reads data/scores/ai_readiness_scores.json and config/repo_url_map.json,
outputs one HTML file per article to data/reports/{slug}.html.

Usage:
    # Generate all reports
    python pipeline/generate_reports.py

    # Generate for one article
    python pipeline/generate_reports.py --url https://learn.microsoft.com/en-us/...
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from pipeline.url_resolver import resolve_github_urls, url_to_slug

SCORES_FILE = ROOT / "data" / "scores" / "ai_readiness_scores.json"
MAP_FILE = ROOT / "config" / "repo_url_map.json"
REPORTS_DIR = ROOT / "data" / "reports"

BAND_COLORS = {
    "High": "#22c55e",
    "Medium": "#f59e0b",
    "Low": "#ef4444",
}

BAND_ICONS = {
    "High": "●",
    "Medium": "◑",
    "Low": "●",
}

DIMENSION_LABELS = {
    "heading_hierarchy": "Heading Hierarchy",
    "chunk_autonomy": "Chunk Autonomy",
    "context_completeness": "Context Completeness",
    "entity_normalization": "Entity Normalization",
    "disambiguation": "Disambiguation",
    "semantic_density": "Semantic Density",
    "structured_data_utilization": "Structured Data",
    "query_answer_alignment": "Query-Answer Alignment",
    "redundancy_efficiency": "Redundancy Efficiency",
    "cross_section_integrity": "Cross-Section Integrity",
}

DIMENSION_ORDER = list(DIMENSION_LABELS.keys())



def bar_html(count: int, max_count: int, is_weakest: bool) -> str:
    bar_color = "#ef4444" if is_weakest else "#3b82f6"
    bar_width = int((count / max(max_count, 1)) * 200)
    weakest_badge = (
        ' <span style="font-size:11px;background:#fef2f2;color:#ef4444;'
        'padding:1px 6px;border-radius:10px;font-weight:600">WEAKEST</span>'
        if is_weakest else ""
    )
    return (
        f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
        f'<div style="background:#e5e7eb;border-radius:3px;height:14px;width:200px;flex-shrink:0">'
        f'<div style="background:{bar_color};border-radius:3px;height:14px;width:{bar_width}px"></div>'
        f'</div>'
        f'<span style="font-size:13px;color:#374151">{count} rec{"s" if count != 1 else ""}</span>'
        f'{weakest_badge}'
        f'</div>'
    )


def _rec_card_html(dim_key: str, recs: list) -> str:
    """Render one dimension's recommendation list as an HTML card."""
    if not recs:
        return ""
    label = DIMENSION_LABELS.get(dim_key, dim_key)
    items = []
    for rec in recs:
        evidence = rec.get("evidence", "")
        action = rec.get("action", "")
        impact = rec.get("impact", "")
        item = (
            f'<div style="margin:8px 0 8px 12px;font-size:13px">'
            + (f'<div><span style="color:#6b7280;font-weight:600">Evidence:</span> '
               f'<em>{evidence}</em></div>' if evidence else "")
            + (f'<div style="margin-top:4px"><span style="color:#374151;font-weight:600">Action:</span> '
               f'{action}</div>' if action else "")
            + (f'<div style="margin-top:4px"><span style="color:#6b7280">Impact:</span> '
               f'{impact}</div>' if impact else "")
            + '</div>'
        )
        items.append(item)
    return (
        f'<div style="margin:12px 0;border-left:3px solid #3b82f6;padding-left:12px">'
        f'<div style="font-weight:600;font-size:14px;color:#1e40af">{label}</div>'
        + "\n".join(items)
        + '</div>'
    )


def generate_report(url: str, score: dict) -> str:
    band = score.get("band", "Unknown")
    total = score.get("total_recommendations", 0)
    weakest = score.get("weakest_dimension", "")
    by_dimension = score.get("by_dimension", {})
    recs_by_dim = score.get("recommendations_by_dimension", {})
    has_full_recs = bool(recs_by_dim)

    band_color = BAND_COLORS.get(band, "#6b7280")
    band_icon = BAND_ICONS.get(band, "●")

    urls = resolve_github_urls(url, MAP_FILE)
    vscode_url = urls["vscode_url"]
    learn_url = url

    # Primary action button
    if vscode_url:
        primary_btn = (
            f'<a href="{vscode_url}" target="_blank" style="'
            f'display:inline-block;background:#0066b8;color:white;padding:8px 16px;'
            f'border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;margin-right:8px">'
            f'Open in VS Code Web &#x2197;</a>'
        )
    else:
        primary_btn = ""

    secondary_btn = (
        f'<a href="{learn_url}" target="_blank" style="'
        f'display:inline-block;background:#f3f4f6;color:#374151;padding:8px 16px;'
        f'border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;'
        f'border:1px solid #d1d5db">'
        f'View on Learn &#x2197;</a>'
    )

    # Dimension rows
    max_count = max(by_dimension.values()) if by_dimension else 1
    dim_rows = []
    for key in DIMENSION_ORDER:
        count = by_dimension.get(key, 0)
        label = DIMENSION_LABELS.get(key, key)
        is_weakest = key == weakest
        row = (
            f'<tr>'
            f'<td style="padding:6px 12px 6px 0;font-size:13px;color:#374151;'
            f'white-space:nowrap;font-weight:{"600" if is_weakest else "400"}">{label}</td>'
            f'<td style="padding:6px 0">{bar_html(count, max_count, is_weakest)}</td>'
            f'</tr>'
        )
        dim_rows.append(row)
    dim_table = "\n".join(dim_rows)

    # Band threshold legend
    threshold_note = (
        "<p style='font-size:12px;color:#6b7280;margin:8px 0 0'>"
        "Thresholds: High = 0&#8211;3 recs &nbsp;|&nbsp; Medium = 4&#8211;8 recs"
        " &nbsp;|&nbsp; Low = 9+ recs"
        "</p>"
    )

    # Recommendations section — full text if available, else upgrade prompt
    if has_full_recs:
        rec_cards = []
        # Sort: weakest dimension first, then by count descending
        sorted_dims = sorted(
            DIMENSION_ORDER,
            key=lambda d: (0 if d == weakest else 1, -by_dimension.get(d, 0))
        )
        for dim_key in sorted_dims:
            recs = recs_by_dim.get(dim_key, [])
            if recs:
                rec_cards.append(_rec_card_html(dim_key, recs))
        recs_section = (
            "<h2>Recommendations</h2>"
            + ("\n".join(rec_cards) if rec_cards else
               "<p style='color:#6b7280;font-size:13px'>No recommendations for this article.</p>")
        )
    else:
        recs_section = (
            "<div style='background:#fef9c3;border:1px solid #fde047;border-radius:6px;"
            "padding:10px 14px;margin-top:16px;font-size:13px;color:#713f12'>"
            "<strong>Note:</strong> Full recommendation details (evidence, action, impact) "
            "are not stored in the current score cache. Re-run the AI Readiness pipeline "
            "to populate per-recommendation details here."
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Readiness Report</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 24px; background: #f9fafb; color: #111827; }}
  .card {{ background: white; border-radius: 10px; padding: 24px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 16px; font-weight: 600; color: #6b7280; margin: 0 0 4px; }}
  .url {{ font-size: 12px; color: #9ca3af; word-break: break-all; margin: 0 0 16px; }}
  .band-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }}
  .band-chip {{ padding: 4px 12px; border-radius: 20px; color: white;
               font-weight: 700; font-size: 16px; }}
  .total {{ font-size: 14px; color: #6b7280; }}
  .actions {{ margin: 16px 0; }}
  h2 {{ font-size: 14px; font-weight: 600; color: #374151; margin: 20px 0 8px;
        border-top: 1px solid #e5e7eb; padding-top: 16px; }}
  table {{ border-collapse: collapse; width: 100%; }}
</style>
</head>
<body>
<div class="card">
  <h1>AI Readiness Report</h1>
  <p class="url">{url}</p>

  <div class="band-row">
    <span class="band-chip" style="background:{band_color}">{band_icon} {band}</span>
    <span class="total">{total} total recommendation{"s" if total != 1 else ""}</span>
  </div>

  <div class="actions">
    {primary_btn}
    {secondary_btn}
  </div>

  <h2>Dimension Breakdown</h2>
  <table>
    {dim_table}
  </table>
  {threshold_note}
  {recs_section}
</div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-article AI Readiness HTML reports")
    parser.add_argument("--url", help="Generate report for a single URL only")
    parser.add_argument("--scores", default=str(SCORES_FILE), help="AI readiness scores JSON")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR), help="Output directory")
    args = parser.parse_args()

    scores_path = Path(args.scores)
    if not scores_path.exists():
        print(f"Error: scores file not found at {scores_path}")
        sys.exit(1)

    with open(scores_path, encoding="utf-8") as f:
        scores: dict = json.load(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.url:
        url = args.url.rstrip("/")
        if url not in scores:
            print(f"URL not found in scores: {url}")
            sys.exit(1)
        urls_to_process = {url: scores[url]}
    else:
        urls_to_process = scores

    generated = 0
    for url, score in urls_to_process.items():
        slug = url_to_slug(url)
        report_path = output_dir / f"{slug}.html"
        html = generate_report(url, score)
        report_path.write_text(html, encoding="utf-8")
        generated += 1

    print(f"Generated {generated} report(s) -> {output_dir}")


if __name__ == "__main__":
    main()
