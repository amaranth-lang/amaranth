# Documentation Tools

This directory contains utility scripts for maintaining Amaranth documentation.

## RST Formatting Tools

### `fix_rst_underlines.py`

Automatically fixes RST title underlines to match the length of their title text.

Usage:
```bash
pdm run python docs/tools/fix_rst_underlines.py docs/file.rst
```

### `fix_rst_bullet_lists.py`

Ensures all bullet lists in RST files end with a blank line, which is required by the RST parser.

Usage:
```bash
pdm run python docs/tools/fix_rst_bullet_lists.py docs/file.rst
```

## Using These Tools

These tools are helpful when you encounter warnings during documentation builds. You can run them on RST files
to automatically fix common formatting issues.

Example workflow:
1. Run `pdm run document` and observe formatting warnings
2. Run the appropriate fix script(s) on the problematic files
3. Verify the fixes with `pdm run document` again