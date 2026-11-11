"""
Command-line entry point for the Lazor solver.

Usage::

    python lazor.py boards/mad_1.bff            # solve one board
    python lazor.py boards/*.bff                # solve several
    python lazor.py boards/ -o my_solutions     # solve a whole folder

Each solution is written to ``<output dir>/<board name>_solution.txt`` and,
if Pillow is installed, ``<board name>_solution.png``.

This module only glues the other ones together:

    board.py  (read the .bff file)  ->  solver.py  (find the placement)
        ->  output.py  (check it and write the solution files)
"""

import argparse
import glob
import os
import sys
import time

from board import Board
from output import missed_targets, write_png, write_text
from solver import solve


def find_boards(paths):
    """
    Turn the command-line arguments into a list of .bff files.

    **Parameters**

        paths: *list of str*
            Files and/or folders given by the user. A folder stands for
            every ``*.bff`` file directly inside it.

    **Returns**

        files: *list of str*
            Board files in the order given, without duplicates.
    """
    files = []
    for p in paths:
        if os.path.isdir(p):
            found = sorted(glob.glob(os.path.join(p, "*.bff")))
        else:
            # Kept even if it does not exist, so that solve_file() reports
            # a clear error for it instead of silently skipping it.
            found = [p]
        files += [f for f in found if f not in files]
    return files


def solve_file(path, out_dir, png=True):
    """
    Read, solve and save one .bff board.

    **Parameters**

        path: *str*
            Path to the .bff file.
        out_dir: *str*
            Directory where solution files are written.
        png: *bool, optional*
            Also draw a PNG picture (needs Pillow).

    **Returns**

        solved: *bool*
            True if a solution was found.

    **Raises**

        OSError: the file cannot be read or the output cannot be written.
        ValueError: the file is not a valid .bff board.
    """
    board = Board.from_file(path)

    # Only the search itself is timed, not file reading or writing.
    start = time.perf_counter()
    placement = solve(board)
    elapsed = time.perf_counter() - start

    if placement is None:
        print("%-16s no solution exists (%.4f s)" % (board.name, elapsed))
        return False

    # Safety net: replay the lasers on the answer before saving it.
    missed = missed_targets(board, placement)
    if missed:
        raise ValueError("solver answer misses targets %s" % missed)

    base = os.path.join(out_dir, board.name + "_solution")
    write_text(board, placement, base + ".txt", elapsed)
    wrote_png = png and write_png(board, placement, base + ".png")
    print("%-16s solved in %.4f s -> %s.txt%s"
          % (board.name, elapsed, base, " (+ .png)" if wrote_png else ""))
    return True


def main(argv=None):
    """
    Parse command-line arguments and solve the requested boards.

    **Parameters**

        argv: *list of str, optional*
            Arguments to use instead of ``sys.argv[1:]`` (handy for tests).

    **Returns**

        status: *int*
            0 if every board was solved, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description="Solve Lazor puzzles.")
    parser.add_argument("paths", nargs="+",
                        help=".bff files, or folders containing them")
    parser.add_argument("-o", "--out", default="solutions",
                        help="output folder (default: solutions)")
    parser.add_argument("--no-png", action="store_true",
                        help="write only the text file, not the picture")
    args = parser.parse_args(argv)

    files = find_boards(args.paths)
    if not files:
        parser.error("no .bff files found")
    try:
        os.makedirs(args.out, exist_ok=True)
    except OSError as err:
        parser.error("cannot create output folder: %s" % err)

    failures = 0
    start = time.perf_counter()
    for path in files:
        try:
            if not solve_file(path, args.out, png=not args.no_png):
                failures += 1
        except (OSError, ValueError) as err:
            # One bad file must not stop the remaining boards.
            print("%-16s ERROR: %s" % (os.path.basename(path), err),
                  file=sys.stderr)
            failures += 1
    total = time.perf_counter() - start

    if len(files) > 1:
        print("Solved %d of %d boards in %.4f s"
              % (len(files) - failures, len(files), total))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
