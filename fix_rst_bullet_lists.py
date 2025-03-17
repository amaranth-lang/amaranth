#!/usr/bin/env python3
"""
Script to fix RST bullet list formatting in tutorial.rst
This ensures all bullet lists end with a blank line.
"""

import re
import sys

def fix_rst_bullet_lists(filename):
    """Fix bullet lists in the given RST file."""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        # Add the current line to our output
        fixed_lines.append(lines[i])
        
        # Check if this line starts a bullet point
        if lines[i].strip().startswith('- '):
            # Find the end of the bullet list
            j = i + 1
            
            # Look for more bullet points that continue the list
            while j < len(lines) and (lines[j].strip().startswith('- ') or lines[j].strip().startswith(' ')):
                fixed_lines.append(lines[j])
                j = j + 1
            
            # If the next line after the list isn't empty, add a blank line
            if j < len(lines) and lines[j].strip() != '':
                print(f"Adding blank line after bullet list at line {i+1}")
                fixed_lines.append('\n')
            
            i = j
        else:
            i += 1
    
    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.writelines(fixed_lines)
    
    print(f"Fixed bullet lists in {filename}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <rst_file>")
        sys.exit(1)
    
    fix_rst_bullet_lists(sys.argv[1])