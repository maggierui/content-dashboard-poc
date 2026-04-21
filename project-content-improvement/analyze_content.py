import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to access common module
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))

from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Dimension prompt configuration - maps dimension ID to prompt file
DIMENSION_PROMPTS = {
    "heading_hierarchy": "dimensions/dim-heading-hierarchy.md",
    "chunk_autonomy": "dimensions/dim-chunk-autonomy.md",
    "context_completeness": "dimensions/dim-context-completeness.md",
    "entity_normalization": "dimensions/dim-entity-normalization.md",
    "disambiguation": "dimensions/dim-disambiguation.md",
    "structured_data_utilization": "dimensions/dim-structured-data-utilization.md",
}

# All dimensions in evaluation order
ALL_DIMENSIONS = list(DIMENSION_PROMPTS.keys())


def load_prompt_file(path: Path) -> str:
    """Load a prompt file and return its content."""
    return path.read_text(encoding="utf-8")


def load_dimension_prompt(dimension: str) -> str:
    """Load a dimension-specific prompt from the prompts/dimensions directory."""
    if dimension not in DIMENSION_PROMPTS:
        raise ValueError(f"Unknown dimension: {dimension}. Valid: {list(DIMENSION_PROMPTS.keys())}")
    
    return load_prompt_file(SCRIPT_DIR / "prompts" / DIMENSION_PROMPTS[dimension])


def load_shared_foundation() -> str:
    """Load the shared foundation prompt with RAG context and scoring rules."""
    return load_prompt_file(SCRIPT_DIR / "prompts" / "prompt-shared-foundation.md")


def create_dimension_messages(dimension: str, content: str) -> list[dict[str, str]]:
    """Create messages array for a specific dimension analysis."""
    system_content = f"{load_shared_foundation()}\n\n---\n\n{load_dimension_prompt(dimension)}"
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Please analyze the following documentation content for the {dimension} dimension:\n\n{content}"},
    ]


async def call_dimension_analysis(
    client: AsyncAzureOpenAI, deployment: str, dimension: str, content: str
) -> dict[str, Any]:
    """Call OpenAI API for a single dimension analysis."""
    
    def make_result(data: dict | None = None, raw: str = "", error: str | None = None) -> dict[str, Any]:
        result = {"dimension": dimension, "data": data, "raw_response": raw}
        if error:
            result["error"] = error
        return result
    try:
        print(f"  Analyzing dimension: {dimension}...")

        response = await asyncio.wait_for(
            client.responses.create(
                model=deployment,
                input=create_dimension_messages(dimension, content),
                max_output_tokens=4000,
                reasoning={"effort": "medium"},
            ),
            timeout=120,
        )

        # Extract response text from Responses API structure
        response_text = ""
        
        # Try output_text first (direct attribute)
        if hasattr(response, "output_text") and response.output_text:
            response_text = response.output_text
        # Fallback: iterate through output blocks
        elif hasattr(response, "output") and response.output:
            for block in response.output:
                # Handle message blocks with content array
                if hasattr(block, "content") and block.content:
                    for item in block.content:
                        if hasattr(item, "text") and item.text:
                            response_text += item.text
                # Handle direct text attribute on block
                elif hasattr(block, "text") and block.text:
                    response_text += block.text
        
        if not response_text.strip():
            print(f"    Warning: Empty response from model for {dimension}")
            return make_result(error="Empty response from model")
        
        try:
            return make_result(data=json.loads(response_text), raw=response_text)
        except json.JSONDecodeError as e:
            print(f"    Warning: Failed to parse JSON for {dimension}: {e}")
            print(f"    Response preview: {response_text[:200]}...")
            return make_result(raw=response_text, error=str(e))
            
    except Exception as e:
        print(f"    Error calling API for {dimension}: {e}")
        return make_result(error=str(e))


async def analyze_dimensions(
    client: AsyncAzureOpenAI, deployment: str, content: str, dimensions: list[str]
) -> dict[str, Any]:
    """Run specified dimension analyses in parallel."""
    results = await asyncio.gather(
        *(call_dimension_analysis(client, deployment, dim, content) for dim in dimensions)
    )
    return {r["dimension"]: r for r in results if r}


# Regex pattern for extracting ms.topic from YAML front matter
_MS_TOPIC_PATTERN = re.compile(r'^ms\.topic:\s*["\']?([^"\']*)["\'\\s]*$', re.MULTILINE)


def extract_content_type(content: str) -> str | None:
    """Extract ms.topic value from markdown front matter."""
    if not content.strip().startswith('---'):
        return None
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    
    if match := _MS_TOPIC_PATTERN.search(parts[1]):
        return match.group(1).strip() or None
    return None


def save_dimension_results(
    content_filename: str, dimension: str, dimension_data: dict[str, Any],
    output_dir: str, timestamp: str
) -> bool:
    """Save a single dimension's analysis results."""
    try:
        dimensions_dir = Path(output_dir) / "dimensions"
        dimensions_dir.mkdir(parents=True, exist_ok=True)
        
        base_name = Path(content_filename).stem
        output_path = dimensions_dir / f"{base_name}_{dimension}_{timestamp}.json"
        
        output_data = {
            "source_file": content_filename,
            "analysis_date": datetime.now().isoformat(),
            "dimension": dimension,
            "result": dimension_data.get("data") or {"error": dimension_data.get("error", "Unknown error")},
        }
        
        output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"    Saved {dimension}: {output_path.name}")
        return True
        
    except Exception as e:
        print(f"    Error saving {dimension} results: {e}")
        return False


def save_dimension_consolidated(
    content_filename: str, all_results: dict[str, dict], output_dir: str,
    timestamp: str, content: str | None = None, dimensions_analyzed: list[str] | None = None
) -> bool:
    """Save consolidated analysis with all recommendations combined."""
    try:
        base_name = Path(content_filename).stem
        content_type = extract_content_type(content) if content else None
        
        # Collect all recommendations with dimension attribution
        recommendations = []
        for dimension, result in all_results.items():
            if data := result.get("data"):
                for rec in data.get("recommendations", []):
                    recommendations.append({
                        "dimension": dimension,
                        **rec
                    })
        
        # Count recommendations per dimension
        dimension_counts = {}
        for rec in recommendations:
            dim = rec["dimension"]
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
        
        # Build consolidated output
        consolidated_data: dict[str, Any] = {
            "source_file": content_filename,
            "analysis_date": datetime.now().isoformat(),
            "content_type": content_type,
            "dimensions_analyzed": dimensions_analyzed or list(all_results.keys()),
            "summary": {
                "total_recommendations": len(recommendations),
                "by_dimension": dimension_counts,
            },
            "recommendations": recommendations,
        }
        
        # Save to file
        consolidated_dir = Path(output_dir) / "consolidated"
        consolidated_dir.mkdir(parents=True, exist_ok=True)
        output_path = consolidated_dir / f"{base_name}_consolidated_{timestamp}.json"
        output_path.write_text(json.dumps(consolidated_data, indent=2, ensure_ascii=False), encoding="utf-8")
        
        print(f"    Saved consolidated: {output_path.name}")
        return True
        
    except Exception as e:
        print(f"    Error saving consolidated results: {e}")
        return False


async def process_content_file(
    client: AsyncAzureOpenAI, deployment: str, file_path: str,
    output_dir: str, dimensions: list[str]
) -> dict[str, Any] | None:
    """Process a single content file through specified dimension analyses."""
    try:
        path = Path(file_path)
        print(f"Processing: {path.name}")
        print(f"  Dimensions: {', '.join(dimensions)}")
        
        content = path.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        all_results = await analyze_dimensions(client, deployment, content, dimensions)
        
        # Save results
        for dimension, result in all_results.items():
            save_dimension_results(path.name, dimension, result, output_dir, timestamp)
        save_dimension_consolidated(path.name, all_results, output_dir, timestamp, content, dimensions)
        
        print(f"  ✓ Completed: {path.name}")
        return {"filename": path.name, "timestamp": timestamp, "dimensions": dimensions, "results": all_results}
        
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return None


def parse_dimensions_arg(dimensions_arg: str | None) -> list[str]:
    """Parse dimensions argument into list of dimension IDs."""
    if not dimensions_arg:
        return ALL_DIMENSIONS.copy()
    
    dimensions = []
    for item in dimensions_arg.split(','):
        item = item.strip().lower()
        if item in DIMENSION_PROMPTS:
            dimensions.append(item)
        else:
            print(f"Warning: Unknown dimension '{item}', skipping.")
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(dimensions))


async def main_async() -> None:
    """Async main function to orchestrate content analysis."""
    import os
    
    parser = argparse.ArgumentParser(
        description="Analyze documentation content for RAG retrieval optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  py analyze_content.py                                      # Run all dimensions
  py analyze_content.py -d heading_hierarchy,chunk_autonomy  # Specific dimensions
  py analyze_content.py --list-dimensions                    # Show available

Available dimensions:
  {', '.join(ALL_DIMENSIONS)}
"""
    )
    parser.add_argument('-d', '--dimensions', help='Comma-separated dimension IDs')
    parser.add_argument('-i', '--input', help='Input directory (default: input/test)')
    parser.add_argument('-o', '--output', help='Output directory (default: output/test)')
    parser.add_argument('--list-dimensions', action='store_true', help='List available dimensions')
    args = parser.parse_args()
    
    if args.list_dimensions:
        print("\nAvailable dimensions:")
        print("=" * 60)
        for dim in ALL_DIMENSIONS:
            print(f"  {dim}")
        return
    
    dimensions = parse_dimensions_arg(args.dimensions)
    if not dimensions:
        print("Error: No valid dimensions specified. Use --list-dimensions to see options.")
        return
    
    print("=== Content Analysis Tool (Dimension-based / Responses API) ===")
    print(f"Running {len(dimensions)} dimension(s): {', '.join(dimensions)}")
    
    # Azure OpenAI configuration
    endpoint = os.environ.get("ENDPOINT_URL")
    api_key = os.environ.get("API_KEY")
    api_version = os.environ.get("API_VERSION", "2025-04-01-preview")
    deployment = "gpt-5-mini"
    
    if not endpoint:
        print("Error: ENDPOINT_URL environment variable required.")
        return
    
    # Initialize client
    if api_key:
        client = AsyncAzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
    else:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, azure_ad_token_provider=token_provider, api_version=api_version
        )
    
    # Paths
    input_dir = Path(args.input) if args.input else SCRIPT_DIR / "input" / "test"
    output_dir = Path(args.output) if args.output else SCRIPT_DIR / "output" / "test"
    
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return
    
    content_files = list(input_dir.glob("*.md"))
    if not content_files:
        print(f"No markdown files found in {input_dir}")
        return
    
    print(f"\nFound {len(content_files)} file(s) to analyze\n")
    
    # Process files
    successful = 0
    for i, file_path in enumerate(content_files, 1):
        print(f"--- File {i}/{len(content_files)} ---")
        if await process_content_file(client, deployment, str(file_path), str(output_dir), dimensions):
            successful += 1
        print()
    
    print("--- Analysis Complete ---")
    print(f"Successfully analyzed: {successful}/{len(content_files)} files")
    print(f"Results saved in: {output_dir}")


def main():
    """Entry point - runs async main"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
