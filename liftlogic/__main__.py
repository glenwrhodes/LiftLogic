"""Command line for Lift Logic. Run with: python -m liftlogic

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

from __future__ import annotations

import argparse
import os
import sys

# Keep pygame's greeting out of the output of --check and --record.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from . import app  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="liftlogic",
        description="Elevator simulator comparing three scheduling algorithms.",
    )
    parser.add_argument("--seed", type=int, default=7,
                        help="which stream of passengers to use (default 7)")
    parser.add_argument("--speed", type=int, choices=app.SPEEDS, default=2,
                        help="simulated seconds per real second (default 2)")
    parser.add_argument("--check", action="store_true",
                        help="start up without a window, run briefly, and exit")
    parser.add_argument("--record", metavar="FOLDER",
                        help="save PNG frames to FOLDER instead of opening a window")
    parser.add_argument("--seconds", type=float, default=30.0,
                        help="length of the recording in video seconds (default 30)")
    parser.add_argument("--fps", type=int, default=60,
                        help="frames per second of the recording (default 60)")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace frames already in the recording folder")
    args = parser.parse_args(argv)

    if args.check:
        return app.run_check(args.seed)
    if args.record:
        return app.run_record(args.record, args.seconds, args.fps, args.speed,
                              args.seed, args.overwrite)
    return app.run_window(args.seed, args.speed)


if __name__ == "__main__":
    sys.exit(main())
