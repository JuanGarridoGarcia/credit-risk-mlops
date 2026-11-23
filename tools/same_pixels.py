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

from PIL import Image


def _committed(path: Path) -> bytes:
    return subprocess.run(  # noqa: S603
        ["git", "show", f"HEAD:{path.as_posix()}"],  # noqa: S607
        check=True,
        capture_output=True,
    ).stdout


def _pixels(data: bytes) -> tuple[str, tuple[int, int], bytes]:
    with Image.open(io.BytesIO(data)) as image:
        return image.mode, image.size, image.tobytes()


def main(folder: str) -> int:
    changed = [
        path
        for path in sorted(Path(folder).glob("*.png"))
        if _pixels(path.read_bytes()) != _pixels(_committed(path))
    ]
    for path in changed:
        print(f"{path}: pixels differ from the committed image")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
