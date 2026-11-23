"""Fail if a PNG under the given folder shows different pixels from its committed version.

``make notebooks`` compares every other output byte for byte. A PNG cannot be compared
that way: the same pixels compress to different bytes on different CPUs (E-024), so the
image is decoded and its pixels are compared instead.

Usage: python tools/same_pixels.py reports/data_audit
"""

import io
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops


def _committed(path: Path) -> bytes:
    return subprocess.run(  # noqa: S603
        ["git", "show", f"HEAD:{path.as_posix()}"],  # noqa: S607
        check=True,
        capture_output=True,
    ).stdout


def _image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGBA")


def difference(new: bytes, old: bytes) -> str | None:
    """None if both PNGs show the same pixels, otherwise what differs."""
    a, b = _image(new), _image(old)
    if a.size != b.size:
        return f"size {a.size} instead of {b.size}"
    diff = ImageChops.difference(a, b)
    box = diff.getbbox(alpha_only=False)
    if box is None:
        return None
    count = sum(1 for p in diff.get_flattened_data() if any(p))
    return f"{count} pixels differ, inside the box {box}"


def main(folder: str) -> int:
    failed = False
    for path in sorted(Path(folder).glob("*.png")):
        found = difference(path.read_bytes(), _committed(path))
        if found:
            print(f"{path}: {found}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
