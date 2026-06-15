#!/usr/bin/env python3
"""Run the external MediaCrawler from this project.

This wrapper keeps the Skill callable from a fresh DoodleStory conversation
without remembering the external project path from chat history.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


DEFAULT_MEDIACRAWLER_HOME = Path("/Users/pengfei.shi/workspace/tmp-project/MediaCrawler")


def main() -> int:
    crawler_home = Path(os.environ.get("MEDIACRAWLER_HOME", str(DEFAULT_MEDIACRAWLER_HOME))).expanduser()
    main_py = crawler_home / "main.py"
    python_bin = crawler_home / ".venv" / "bin" / "python"
    if not crawler_home.exists():
        print(
            f"MediaCrawler directory not found: {crawler_home}\n"
            "Set MEDIACRAWLER_HOME to the local MediaCrawler checkout.",
            file=sys.stderr,
        )
        return 2
    if not main_py.exists():
        print(f"MediaCrawler main.py not found: {main_py}", file=sys.stderr)
        return 2
    if not python_bin.exists():
        print(
            f"MediaCrawler virtualenv python not found: {python_bin}\n"
            "Create the MediaCrawler .venv before running this wrapper.",
            file=sys.stderr,
        )
        return 2
    cmd = [str(python_bin), str(main_py), *sys.argv[1:]]
    return subprocess.call(cmd, cwd=str(crawler_home))


if __name__ == "__main__":
    raise SystemExit(main())
