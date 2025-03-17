#!/usr/bin/env python3
"""
Script to automatically fix RST title underlines in tutorial.rst
This ensures all underlines match the length of their title text.
"""

import re
import sys

def fix_rst_underlines(filename):
    """Fix all RST title underlines in the given file."""
    with open(filename, 'r') as f:
        content = f.read()
    
    # Pattern to match a title line followed by an underline
    # Group 1 = Title text
    # Group 2 = Underline character (= or - or ~)
    # Group 3 = Full underline
    pattern = r'([^\n]+)\n([=\-~]+)'
    
    def replace_underline(match):
        title = match.group(1)
        underline_char = match.group(2)[0]  # Get the first character of the underline
        # Create a new underline with the same length as the title
        new_underline = underline_char * len(title)
        
        # Check if it's already correct
        if match.group(2) == new_underline:
            # If already correct, no change
            return match.group(0)
        
        # Report the change
        print(f"Fixing: '{title}'\n  Old: {match.group(2)}\n  New: {new_underline}")
        
        # Return the title with the fixed underline
        return f"{title}\n{new_underline}"
    
    # Replace all underlines with correct length ones
    fixed_content = re.sub(pattern, replace_underline, content)
    
    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.write(fixed_content)
    
    print(f"Fixed underlines in {filename}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <rst_file>")
        sys.exit(1)
    
    fix_rst_underlines(sys.argv[1])