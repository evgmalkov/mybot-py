#!/usr/bin/env python3
"""
Convert a high-resolution PNG into a multi-size ICO without losing quality.
Requires: pip install pillow
"""

from PIL import Image
import sys
from pathlib import Path

def png_to_ico(png_path: Path, ico_path: Path = None, sizes=None):
    """
    Reads png_path and writes ico_path (same stem) with multiple icon sizes.
    - png_path: Path to your high-res PNG (must be square).
    - ico_path: Optional Path for the output .ico (defaults to same stem).
    - sizes:   List of (width, height) tuples to include in the .ico.
    """
    if ico_path is None:
        ico_path = png_path.with_suffix(".ico")
    if sizes is None:
        # Common icon sizes; include your original resolution if it’s square:
        orig = Image.open(png_path)
        w, h = orig.size
        icon_sizes = [(w, h), (256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
        # filter out duplicates and sizes larger than the source
        sizes = sorted({s for s in icon_sizes if s[0] <= w and s[1] <= h}, reverse=True)
    else:
        sizes = sorted(sizes, reverse=True)

    # Load once, convert to RGBA to preserve transparency
    img = Image.open(png_path).convert("RGBA")

    # Save multi-size ICO
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"✅ Saved {ico_path} with sizes: {sizes}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python png_to_ico.py highres_logo.png [output.ico]")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    png_to_ico(src, dst)
