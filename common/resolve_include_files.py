import re
import os

def find_include_blocks(content: str) -> list[tuple[str, str]]:
    """
    Find all [!INCLUDE ...] blocks in the content.
    Returns a list of tuples: (full_match, relative_path)
    """
    # Pattern matches [!INCLUDE [optional-text](relative/path/to/file.md)]
    pattern = r'\[!INCLUDE\s*\[[^\]]*\]\(([^)]+)\)\]'
    matches = re.findall(pattern, content)
    full_matches = re.finditer(pattern, content)
    
    results = []
    for match in full_matches:
        full_match = match.group(0)
        relative_path = match.group(1)
        results.append((full_match, relative_path))
    
    return results


def resolve_include_path(base_file_path: str, relative_path: str) -> str:
    """
    Resolve the include file path relative to the base file.
    """
    base_dir = os.path.dirname(os.path.abspath(base_file_path))
    resolved_path = os.path.normpath(os.path.join(base_dir, relative_path))
    return resolved_path


def read_include_file(include_path: str) -> str | None:
    """
    Read the content of an include file.
    Returns None if the file doesn't exist.
    """
    try:
        with open(include_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # remove yaml metadata if present
        yaml_pattern = r'^---\s*\n(.*?\n)?---\s*\n'
        content = re.sub(yaml_pattern, '', content, flags=re.DOTALL)

        # Strip leading/trailing whitespace but preserve internal formatting
        return content.strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading {include_path}: {e}")
        return None


def read_file_with_includes(file_path: str, recursive: bool = True) -> str:
    """
    Process a markdown file and replace all [!INCLUDE ...] blocks.
    
    Args:
        file_path: Path to the markdown file
        recursive: If True, also process includes within include files
    
    Returns:
        The content of the file with includes resolved.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""
    
    include_blocks = find_include_blocks(content)
    
    if not include_blocks:
        return content
    
    for full_match, relative_path in include_blocks:
        include_path = resolve_include_path(file_path, relative_path)
        include_content = read_include_file(include_path)
        
        if include_content is None:
            print(f"  WARNING: Include file not found: {include_path}")
            continue
        
        # If recursive, process includes within the include file
        if recursive and '[!INCLUDE' in include_content:
            # Create a temporary representation to process nested includes
            temp_file_path = include_path
            nested_content = include_content
            nested_includes = find_include_blocks(nested_content)
            
            for nested_match, nested_path in nested_includes:
                nested_include_path = resolve_include_path(temp_file_path, nested_path)
                nested_include_content = read_include_file(nested_include_path)
                
                if nested_include_content is not None:
                    nested_content = nested_content.replace(nested_match, nested_include_content)
                else:
                    print(f"    WARNING: Nested include file not found: {nested_include_path}")
            
            include_content = nested_content
        
        content = content.replace(full_match, include_content)
        
    return content

