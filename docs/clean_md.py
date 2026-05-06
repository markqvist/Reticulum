#!/usr/bin/env python3

import os
import sys
import re
from pathlib import Path

LINE_START_PATTERNS = [
    r'<a\s+',           # HTML anchor tags: <a id="..."></a>
    r'\\\\newpage',       # LaTeX newpage commands
]

LINE_ANY_PATTERNS = [
    # r'<div[^>]*>',
    # r'</div>',
]

def compile_patterns():
    """Compile regex patterns for matching lines to remove."""
    start_patterns = [re.compile(p) for p in LINE_START_PATTERNS]
    any_patterns = [re.compile(p) for p in LINE_ANY_PATTERNS]
    return start_patterns, any_patterns


def should_remove_line(line, start_patterns, any_patterns):
    """Check if a line should be removed based on configured patterns."""
    stripped = line.strip()
    
    # Check start-of-line patterns
    for pattern in start_patterns:
        if pattern.match(stripped):
            return True
    
    # Check anywhere-in-line patterns
    for pattern in any_patterns:
        if pattern.search(stripped):
            return True
    
    return False


def clean_markdown_content(content, start_patterns, any_patterns):
    """
    Remove matching lines and collapse trailing empty lines.
    
    When a line is removed, any immediately following empty lines
    are also removed to avoid leaving gaps in the document.
    """
    lines = content.split('\n')
    result = []
    skip_next_empty = False
    
    for i, line in enumerate(lines):
        if should_remove_line(line, start_patterns, any_patterns):
            # Mark that we should skip trailing empty lines
            skip_next_empty = True
            continue
        
        if skip_next_empty:
            if line.strip() == '':
                # Skip this empty line (trailing from removed line)
                continue
            else:
                # Non-empty line, resume normal processing
                skip_next_empty = False
        
        result.append(line)
    
    # Remove trailing empty lines from end of file
    while result and result[-1].strip() == '':
        result.pop()
    
    return '\n'.join(result)


def process_file(filepath, start_patterns, any_patterns):
    """Process a single markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        cleaned_content = clean_markdown_content(
            original_content, start_patterns, any_patterns
        )
        
        # Only write if changes were made
        if cleaned_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            return True
        return False
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return False


def find_markdown_files(directory):
    """Recursively find all .md files in directory."""
    md_files = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.md'):
                md_files.append(Path(root) / filename)
    return md_files


def main():
    if len(sys.argv) < 2:
        print("Usage: python clean_markdown.py <directory_path>", file=sys.stderr)
        sys.exit(1)
    
    directory = sys.argv[1]
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a valid directory", file=sys.stderr)
        sys.exit(1)
    
    start_patterns, any_patterns = compile_patterns()
    md_files = find_markdown_files(directory)
    
    if not md_files:
        print(f"No markdown files found in '{directory}'")
        return
    
    modified_count = 0
    for filepath in md_files:
        if process_file(filepath, start_patterns, any_patterns):
            print(f"Cleaned: {filepath}")
            modified_count += 1
    
    print(f"\nProcessed {len(md_files)} file(s), modified {modified_count}")


if __name__ == '__main__':
    main()
