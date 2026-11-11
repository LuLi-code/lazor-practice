"""
Unit tests for the solver, the solution output files and the command line.
Run with::

    python -m unittest -v
"""

import contextlib
import copy
import glob
import importlib.util
import io
import itertools
import os
import tempfile
import time
import unittest

import lazor
from board import Board, trace
from output import (laser_map, missed_targets, solved_grid, write_png,
                    write_text)
from solver import solve
from test_board import MAD_1

HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = sorted(glob.glob(os.path.join(HERE, "boards", "*.bff")))
HAVE_PILLOW = importlib.util.find_spec("PIL") is not None

# A board with one fixed block of every type and one block to place.
FIXED = """
GRID START
o B o
A o C
o o x
GRID STOP
A 1
L 2 5 1 -1
P 3 2
P 5 2
"""

# The laser leaves the board at once and can never reach the target.
UNSOLVABLE = "GRID START\no\nGRID STOP\nB 1\nL 0 1 1 1\nP 2 1\n"


def is_solution(board, placement):
    """Independently check a placement: right block counts, open cells only,
    and every target is hit."""
    counts = {}
    for (c, r), symbol in placement.items():
        if board.grid[r][c] != "o":
            return False
        counts[symbol] = counts.get(symbol, 0) + 1
    wanted = {k: v for k, v in board.blocks.items() if v}
    if counts != wanted:
        return False
    visited, _, _ = trace(board.block_grid(placement), board.lasers,
                          board.width, board.height)
    return set(board.targets) <= visited


def brute_force_exists(board):
    """Try every arrangement of the blocks (only feasible on tiny boards)."""
    cells = board.open_cells()
    symbols = [s for s, n in board.blocks.items() for _ in range(n)]
    for spots in itertools.permutations(cells, len(symbols)):
        if is_solution(board, dict(zip(spots, symbols))):
            return True
    return False


def run_main(*args):
    """Run the command line quietly; return (exit status, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = lazor.main(list(args))
    return status, out.getvalue(), err.getvalue()


class TestSolver(unittest.TestCase):

    def test_mad_1_known_answer(self):
        placement = solve(Board.from_string(MAD_1))
        self.assertEqual(placement, {(2, 0): "C", (3, 1): "A",
                                     (0, 2): "A"})

    def test_all_boards_valid(self):
        self.assertTrue(BOARDS, "no boards found")
        for path in BOARDS:
            board = Board.from_file(path)
            with self.subTest(board.name):
                placement = solve(board)
                self.assertIsNotNone(placement)
                self.assertTrue(is_solution(board, placement))

    def test_all_boards_fast(self):
        # The assignment allows 2 minutes per board; we expect far less.
        for path in BOARDS:
            board = Board.from_file(path)
            with self.subTest(board.name):
                start = time.perf_counter()
                solve(board)
                self.assertLess(time.perf_counter() - start, 5.0)

    def test_matches_brute_force(self):
        # On small boards, the solver must agree with exhaustive search
        # about whether a solution exists.
        texts = [
            MAD_1,
            MAD_1.replace("C 1", "B 1"),
            FIXED,
            FIXED.replace("A 1", "B 1"),
            FIXED.replace("A 1", "C 1"),
            "GRID START\no o\no o\nGRID STOP\nA 1\nL 0 1 1 1\nP 3 0\n",
            "GRID START\no o\no o\nGRID STOP\nB 1\nL 0 1 1 1\nP 3 4\n",
        ]
        for text in texts:
            board = Board.from_string(text)
            with self.subTest(text=text[:40]):
                self.assertEqual(solve(board) is not None,
                                 brute_force_exists(board))

    def test_unsolvable(self):
        self.assertIsNone(solve(Board.from_string(UNSOLVABLE)))

    def test_fixed_blocks_stay_put(self):
        # Movable blocks may only go on 'o' cells, never on a fixed block
        # or an 'x' cell.
        board = Board.from_string(FIXED)
        placement = solve(board)
        self.assertTrue(is_solution(board, placement))
        for col, row in placement:
            self.assertEqual(board.grid[row][col], "o")

    def test_every_block_is_used(self):
        # Blocks the lasers never touch must still be placed somewhere.
        for path in BOARDS:
            board = Board.from_file(path)
            with self.subTest(board.name):
                self.assertEqual(len(solve(board)),
                                 sum(board.blocks.values()))

    def test_board_not_modified(self):
        # Solving must not change the board, so it can be solved again.
        board = Board.from_string(FIXED)
        before = copy.deepcopy((board.grid, board.blocks, board.lasers,
                                board.targets))
        first = solve(board)
        self.assertEqual(before, (board.grid, board.blocks, board.lasers,
                                  board.targets))
        self.assertEqual(first, solve(board))

    def test_no_blocks_needed(self):
        # A laser that already crosses the target needs no blocks at all.
        board = Board.from_string("GRID START\no o\no o\nGRID STOP\n"
                                  "L 0 1 1 1\nP 1 2\n")
        self.assertEqual(solve(board), {})


class TestOutput(unittest.TestCase):

    def setUp(self):
        self.board = Board.from_string(MAD_1, name="mad_1")
        self.placement = solve(self.board)

    def test_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            write_text(self.board, self.placement, path, elapsed=0.5)
            with open(path) as f:
                text = f.read()
        self.assertIn("Solution for mad_1", text)
        self.assertIn("o o C o", text)
        self.assertIn("o o o A", text)
        self.assertIn("C at (2, 0)", text)
        self.assertIn("Targets hit: 4 of 4", text)
        self.assertIn("Solved in 0.5000 s", text)
        self.assertNotIn("WARNING", text)

    def test_text_grid_parses_back(self):
        # The GRID section of the output must be a valid .bff grid again.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            write_text(self.board, self.placement, path)
            with open(path) as f:
                text = f.read()
        grid = text[text.index("GRID START"):text.index("GRID STOP") + 9]
        solved = Board.from_string(grid + "\nL 2 7 1 -1\nP 3 0\n")
        self.assertEqual(solved.grid[0], ["o", "o", "C", "o"])
        self.assertEqual(sum(row.count("A") for row in solved.grid), 2)

    def test_fixed_blocks_lowercase(self):
        board = Board.from_string(FIXED)
        grid = solved_grid(board, solve(board))
        self.assertEqual(grid[0][1], "b")
        self.assertEqual(grid[1][0], "a")
        self.assertEqual(grid[1][2], "c")
        self.assertEqual(grid[2][2], "x")
        self.assertEqual(sum(row.count("A") for row in grid), 1)
        # The board itself keeps its original uppercase grid.
        self.assertEqual(board.grid[0][1], "B")

    def test_missed_targets(self):
        self.assertEqual(missed_targets(self.board, self.placement), [])
        # With no blocks at all the laser runs straight off the board.
        self.assertEqual(missed_targets(self.board, {}),
                         self.board.targets)

    def test_laser_map(self):
        lines = laser_map(self.board, self.placement)
        rows = lines[2:]                      # skip the two header lines
        self.assertEqual(len(rows), 2 * self.board.height + 1)
        picture = "\n".join(rows)
        self.assertEqual(picture.count("@"), 4)   # every target is hit
        self.assertNotIn("!", picture)
        self.assertEqual(picture.count("C"), 1)
        self.assertEqual(picture.count("A"), 2)
        # A missed target is flagged with '!'.
        self.assertIn("!", "\n".join(laser_map(self.board, {})))

    def test_png_without_pillow_or_with(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            written = write_png(self.board, self.placement, path)
            # A picture exists exactly when Pillow is available.
            self.assertEqual(written, HAVE_PILLOW)
            self.assertEqual(os.path.exists(path), HAVE_PILLOW)


class TestCommandLine(unittest.TestCase):

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, _ = run_main(BOARDS[0], "-o", tmp)
            name = os.path.splitext(os.path.basename(BOARDS[0]))[0]
            self.assertEqual(status, 0)
            self.assertIn(name, out)
            self.assertTrue(os.path.exists(
                os.path.join(tmp, name + "_solution.txt")))

    def test_whole_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, out, _ = run_main(os.path.join(HERE, "boards"),
                                      "-o", tmp, "--no-png")
            self.assertEqual(status, 0)
            self.assertEqual(len(glob.glob(os.path.join(tmp, "*.txt"))),
                             len(BOARDS))
            self.assertEqual(glob.glob(os.path.join(tmp, "*.png")), [])
            self.assertIn("Solved %d of %d boards" % (len(BOARDS),
                                                      len(BOARDS)), out)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _, err = run_main(os.path.join(tmp, "nope.bff"),
                                      "-o", tmp)
        self.assertEqual(status, 1)
        self.assertIn("ERROR", err)

    def test_bad_file_does_not_stop_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.bff")
            with open(bad, "w") as f:
                f.write("this is not a board\n")
            status, out, err = run_main(bad, BOARDS[0], "-o", tmp)
            self.assertEqual(status, 1)
            self.assertIn("bad.bff", err)
            self.assertIn("Solved 1 of 2 boards", out)

    def test_unsolvable_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "stuck.bff")
            with open(path, "w") as f:
                f.write(UNSOLVABLE)
            status, out, _ = run_main(path, "-o", tmp)
            self.assertEqual(status, 1)
            self.assertIn("no solution", out)
            self.assertFalse(os.path.exists(
                os.path.join(tmp, "stuck_solution.txt")))

    def test_empty_folder(self):
        # argparse reports the problem and exits with status 2.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                run_main(tmp, "-o", tmp)


if __name__ == "__main__":
    unittest.main()
