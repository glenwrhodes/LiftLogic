"""Entry point for the packaged Windows program (see tools/build_windows.ps1).

From source, run `python -m liftlogic` instead.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

import sys
import traceback

from liftlogic.__main__ import main


def run() -> int:
    windowless = any(arg in ("--check", "--record") for arg in sys.argv[1:])
    try:
        return main()
    except Exception:
        if not windowless:
            raise
        # The packaged program has no console, so an error would open a
        # message box and wait for a click. With no window, nobody is there
        # to click it: report the error and exit with a failure code instead.
        if sys.stderr is not None:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run())
