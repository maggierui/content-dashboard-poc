"""
Generate human-readable Markdown reports from retrievability analysis JSON files.

This script reads the consolidated JSON file and creates a readable Markdown report with:
- Issue count per dimension
- Recommendations grouped by dimension with evidence
- Optional source file excerpts showing problematic areas
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path to access common module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.common import read_file

# Optional Azure OpenAI client imports (used when --include-diff is set)
try:
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
except ImportError:
    AzureOpenAI = None
    DefaultAzureCredential = None
    get_bearer_token_provider = None

# Dimension display names (matches dimension IDs in the JSON output)
DIMENSION_DISPLAY = {
    "heading_hierarchy": "Heading Hierarchy",
    "chunk_autonomy": "Chunk Autonomy",
    "context_completeness": "Context Completeness",
    "entity_normalization": "Entity Normalization",
    "disambiguation": "Disambiguation",
    "structured_data_utilization": "Structured Data Utilization",
}


def load_json_file(filepath: str) -> Dict:
    """Load and parse a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_source_content(source_file: str, input_dir: str) -> Optional[str]:
    """Load the original source markdown file."""
    source_path = os.path.join(input_dir, source_file)
    if not os.path.exists(source_path):
        return None
    
    lines = read_file(source_path)
    return "".join(lines)


def extract_context_around_text(content: str, search_text: str, context_lines: int = 3) -> Optional[str]:
    """
    Extract context around a specific text phrase in the source content.
    
    Args:
        content: Full source content
        search_text: Text to search for (can be a partial phrase)
        context_lines: Number of lines to include before and after
        
    Returns:
        Extracted context or None if not found
    """
    if not content or not search_text:
        return None
    
    lines = content.split('\n')
    
    # Clean up search text - take first 50 chars, remove quotes
    clean_search = search_text[:50].strip().strip('"\'`')
    if len(clean_search) < 5:
        return None
    
    search_pattern = re.escape(clean_search.lower())
    
    for i, line in enumerate(lines):
        if re.search(search_pattern, line.lower(), re.IGNORECASE):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            
            context_block = lines[start:end]
            
            # Add line numbers
            numbered_lines = []
            for idx, ctx_line in enumerate(context_block, start=start + 1):
                numbered_lines.append(f"{idx:3d} | {ctx_line}")
            
            return "\n".join(numbered_lines)
    
    return None


def format_recommendation(rec: Dict, idx: int, source_content: Optional[str] = None) -> List[str]:
    """Format a single recommendation into Markdown lines."""
    lines = []
    
    dimension = rec.get("dimension", "Unknown")
    evidence = rec.get("evidence", "")
    action = rec.get("action", "No action specified")
    impact = rec.get("impact", "")
    
    lines.append(f"#### {idx}. {dimension}")
    lines.append("")
    
    if evidence:
        lines.append(f"**Evidence:** {evidence}")
        lines.append("")
    
    lines.append(f"**Action:** {action}")
    lines.append("")
    
    if impact:
        lines.append(f"**Impact:** {impact}")
        lines.append("")
    
    # Try to extract source context from evidence
    if source_content and evidence:
        # Look for quoted text in evidence
        quoted_matches = re.findall(r'["`\'"]([^"`\'"]{10,})["`\'"]', evidence)
        if not quoted_matches:
            # Try the first substantial part of evidence
            evidence_words = evidence.split()
            if len(evidence_words) >= 5:
                quoted_matches = [" ".join(evidence_words[:8])]
        
        for quote in quoted_matches[:1]:  # Show first match only
            context = extract_context_around_text(source_content, quote, context_lines=2)
            if context:
                lines.append("**Source context:**")
                lines.append("```markdown")
                lines.append(context)
                lines.append("```")
                lines.append("")
                break
    
    return lines


def generate_consolidated_report(
    consolidated_json: Dict,
    source_content: Optional[str] = None,
    include_source_excerpts: bool = True,
    diff_guidance: Optional[str] = None,
) -> str:
    """Generate a comprehensive report from consolidated JSON."""
    
    source_file = consolidated_json.get("source_file", "Unknown")
    analysis_date = consolidated_json.get("analysis_date", "Unknown")
    summary = consolidated_json.get("summary", {})
    recommendations = consolidated_json.get("recommendations", [])
    dimensions_analyzed = consolidated_json.get("dimensions_analyzed", [])
    
    total_recommendations = summary.get("total_recommendations", len(recommendations))
    by_dimension = summary.get("by_dimension", {})
    
    # Header
    lines = [
        "# Retrievability Analysis Report",
        "",
        f"**Source File:** `{source_file}`",
        f"**Analysis Date:** {analysis_date}",
        f"**Total Issues:** {total_recommendations}",
        "",
        "---",
        "",
    ]
    
    # Dimension summary table
    lines.extend([
        "## Dimensions",
        "",
        "| Dimension | Issues |",
        "|-----------|--------|",
    ])
    
    dimensions_with_recs = set(rec.get("dimension") for rec in recommendations)
    
    for dim in dimensions_analyzed:
        display = DIMENSION_DISPLAY.get(dim, dim)
        count = by_dimension.get(dim, 0)
        if count > 0:
            lines.append(f"| {display} | {count} |")
        else:
            lines.append(f"| {display} | — |")
    
    lines.extend(["", "---", ""])
    
    # Recommendations grouped by dimension
    if recommendations:
        recs_by_dim: Dict[str, List[Dict]] = {}
        for rec in recommendations:
            dim = rec.get("dimension", "unknown")
            recs_by_dim.setdefault(dim, []).append(rec)
        
        global_idx = 1
        for dim in dimensions_analyzed:
            dim_recs = recs_by_dim.get(dim, [])
            if not dim_recs:
                continue
            
            display = DIMENSION_DISPLAY.get(dim, dim)
            lines.extend([
                f"## {display}",
                "",
            ])
            
            for rec in dim_recs:
                rec_lines = format_recommendation(
                    rec, 
                    global_idx, 
                    source_content if include_source_excerpts else None
                )
                lines.extend(rec_lines)
                global_idx += 1
            
            lines.append("---")
            lines.append("")
    else:
        lines.extend([
            "No issues were identified. The article meets the quality benchmark for all analyzed dimensions.",
            "",
        ])
    
    # Optional LLM-generated diff guidance section for writers
    if diff_guidance:
        lines.extend([
            "---",
            "",
            "## Proposed Edits (Writer Diff Guidance)",
            "",
            diff_guidance.strip(),
            "",
        ])
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate human-readable reports from consolidated retrievability analysis JSON files"
    )
    
    parser.add_argument(
        "json_file",
        help="Path to consolidated JSON file (*_consolidated_*.json)"
    )
    
    parser.add_argument(
        "--input-dir",
        default="input/test",
        help="Directory containing source markdown files (default: input/test)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Directory to write report (default: same directory as JSON file)"
    )
    
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Disable source file context extraction (faster)"
    )

    parser.add_argument(
        "--include-diff",
        action="store_true",
        help=(
            "Include an LLM-generated 'proposed edits' diff section; "
            "uses Azure OpenAI via Responses API, "
            "configured from ENDPOINT_URL and API_KEY/API_VERSION."
        ),
    )
    
    args = parser.parse_args()
    
    # Validate JSON file exists
    if not os.path.isfile(args.json_file):
        print(f"Error: File not found: {args.json_file}")
        print("\nUsage example:")
        print("  py generate_readable_report.py output/test/consolidated/filename_consolidated_20251113.json")
        return 1
    
    # Load the consolidated JSON
    print(f"Loading analysis from: {args.json_file}")
    consolidated = load_json_file(args.json_file)
    
    # Determine source file from JSON metadata
    source_filename = consolidated.get("source_file")
    if not source_filename:
        print("Warning: Could not determine source filename from JSON")
        source_content = None
    else:
        # Try to load source content for context extraction
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(script_dir, args.input_dir)
        
        print(f"Looking for source file: {source_filename} in {input_path}")
        source_content = load_source_content(source_filename, input_path)
        
        if source_content:
            print(f"✓ Loaded source content ({len(source_content)} characters)")
        else:
            print("⚠ Source file not found, context extraction disabled")

    # Optionally call Azure OpenAI to generate writer diff guidance
    diff_guidance = None
    if args.include_diff:
        if not source_filename:
            print("⚠ Cannot generate diff guidance: source filename missing in JSON.")
        elif not source_content:
            print("⚠ Cannot generate diff guidance: source content unavailable.")
        elif AzureOpenAI is None:
            print("⚠ Cannot generate diff guidance: Azure OpenAI SDK not installed.")
        else:
            print("Calling Azure OpenAI to generate writer diff guidance...")

            endpoint = os.getenv("ENDPOINT_URL")
            api_key = os.getenv("API_KEY")
            api_version = os.getenv("API_VERSION", "2025-04-01-preview")
            deployment = "gpt-4.1-mini"

            if not endpoint:
                print("⚠ Cannot generate diff guidance: ENDPOINT_URL is not set.")
            else:
                if api_key:
                    client = AzureOpenAI(
                        azure_endpoint=endpoint,
                        api_key=api_key,
                        api_version=api_version,
                    )
                else:
                    if DefaultAzureCredential is None or get_bearer_token_provider is None:
                        print("⚠ Cannot generate diff guidance: azure-identity not available and API_KEY is not set.")
                        client = None
                    else:
                        token_provider = get_bearer_token_provider(
                            DefaultAzureCredential(),
                            "https://cognitiveservices.azure.com/.default",
                        )
                        client = AzureOpenAI(
                            azure_endpoint=endpoint,
                            azure_ad_token_provider=token_provider,
                            api_version=api_version,
                        )

                if client is not None:
                    system_prompt = (
                        "You are a senior technical writer for Microsoft documentation. "
                        "Using the retrievability analysis JSON (with recommendations and evidence) "
                        "and the original markdown article, produce concise, writer-facing diff guidance. "
                        "Focus only on edits that materially improve Retrieval-Augmented Generation (RAG) retrieval. "
                        "Do not rewrite the article wholesale. Suggest inline edits as unified diff-style snippets "
                        "(context + - old / + new lines). Group related hunks under clear markdown subheadings. "
                        "Keep narrative explanation minimal and let the diffs speak for themselves."
                    )

                    user_prompt = (
                        "Retrievability analysis JSON (recommendations with evidence):\n\n"
                        + json.dumps(consolidated, indent=2, ensure_ascii=False)
                        + "\n\nOriginal markdown article content:\n\n"
                        + source_content
                        + "\n\nBased on the analysis, propose a small set of high-impact, retrieval-focused edits as unified diff-style blocks."
                    )

                    try:
                        response = client.responses.create(
                            model=deployment,
                            input=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            max_output_tokens=2500,
                            temperature=0.2,
                        )

                        diff_guidance = getattr(response, "output_text", None)
                        if not diff_guidance:
                            parts = []
                            for block in getattr(response, "output", []):
                                for item in getattr(block, "content", []):
                                    if getattr(item, "type", None) in ("output_text", "text"):
                                        parts.append(getattr(item, "text", ""))
                            diff_guidance = "\n".join(p for p in parts if p).strip() or None

                        if diff_guidance:
                            print("✓ Diff guidance generated.")
                        else:
                            print("⚠ Model returned an empty diff guidance response.")
                    except Exception as e:
                        print(f"⚠ Error while calling Azure OpenAI for diff guidance: {e}")

    # Generate report
    print("Generating report...")
    report = generate_consolidated_report(
        consolidated,
        source_content if not args.no_context else None,
        include_source_excerpts=not args.no_context,
        diff_guidance=diff_guidance,
    )
    
    # Determine output path
    output_dir = args.output_dir or os.path.dirname(args.json_file)
    base_name = Path(args.json_file).stem.replace("_consolidated", "")
    output_filename = f"{base_name}_report.md"
    output_path = os.path.join(output_dir, output_filename)
    
    # Write report
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✓ Report generated: {output_path}")
    print(f"  {len(report)} characters written")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
