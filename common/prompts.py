import os
from pathlib import Path

def load_prompt(prompt_name: str, folder_path: str = None) -> str:
    """Load the prompt from the specified file.
    
    Args:
        prompt_name: The name of the prompt file (without .md extension).
        folder_path: Optional path segments from workspace root to the prompts folder.
                     If None, uses common/prompts. Otherwise, uses the exact path provided.
    """
    script_dir = Path(__file__).parent.resolve()
    if folder_path is None:
        target_folder = script_dir / "prompts"
    else:
        target_folder = script_dir.parent / folder_path
    prompt_path = target_folder / f"{prompt_name}.md"
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()