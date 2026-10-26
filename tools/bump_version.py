"""Bump the patch number (0.X.Y -> 0.X.Y+1) in atlasforge/__init__.py.

X is changed by hand when the roadmap stage advances; Y is bumped once per
commit on main (via tools/githooks/pre-commit). Usage:
    python tools/bump_version.py          # Y += 1
    python tools/bump_version.py --minor  # X += 1, Y = 0
"""
import re
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "atlasforge" / "__init__.py"
PAT = re.compile(r'__version__ = "(\d+)\.(\d+)\.(\d+)"')


def main() -> None:
    text = INIT.read_text(encoding="utf-8")
    m = PAT.search(text)
    if not m:
        sys.exit("__version__ not found")
    major, minor, patch = map(int, m.groups())
    if "--minor" in sys.argv:
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"
    INIT.write_text(PAT.sub(f'__version__ = "{new}"', text, count=1), encoding="utf-8")
    print(new)


if __name__ == "__main__":
    main()
