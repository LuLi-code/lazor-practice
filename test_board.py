"""
Unit tests for the block classes, .bff parsing and laser tracing.
Run with::

    python -m unittest -v
"""

import unittest

from blocks import OpaqueBlock, ReflectBlock, RefractBlock, make_block
from board import Board, trace

MAD_1 = """
# comment line
GRID START
o o o o
o o o o
o o o o
o o o o
GRID STOP
A 2
C 1
L 2 7 1 -1
P 3 0
P 4 3
P 2 5
P 4 7
"""


class TestBlocks(unittest.TestCase):

    def test_reflect(self):
        self.assertEqual(ReflectBlock().interact((1, 1), True), [(-1, 1)])
        self.assertEqual(ReflectBlock().interact((1, 1), False), [(1, -1)])

    def test_opaque(self):
        self.assertEqual(OpaqueBlock().interact((1, -1), True), [])

    def test_refract(self):
        self.assertEqual(RefractBlock().interact((1, 1), False),
                         [(1, 1), (1, -1)])

    def test_make_block(self):
        self.assertIsInstance(make_block("C", fixed=True), RefractBlock)
        self.assertTrue(make_block("A", fixed=True).fixed)
        with self.assertRaises(ValueError):
            make_block("Z")


class TestParsing(unittest.TestCase):

    def test_mad_1(self):
        board = Board.from_string(MAD_1)
        self.assertEqual((board.width, board.height), (4, 4))
        self.assertEqual(board.blocks, {"A": 2, "C": 1})
        self.assertEqual(board.lasers, [(2, 7, 1, -1)])
        self.assertEqual(board.targets, [(3, 0), (4, 3), (2, 5), (4, 7)])

    def test_unspaced_grid_and_fixed_blocks(self):
        board = Board.from_string("GRID START\noBo\nxoo\nGRID STOP\n"
                                  "A 1\nL 0 1 1 1\nP 1 2\n")
        self.assertEqual(board.grid, [["o", "B", "o"], ["x", "o", "o"]])
        self.assertTrue(board.block_grid()[0][1].fixed)

    def test_errors(self):
        bad = {
            "no grid": "A 1\nL 0 1 1 1\nP 1 2\n",
            "ragged": "GRID START\no o\no\nGRID STOP\nL 0 1 1 1\nP 1 2\n",
            "bad char": "GRID START\no q\nGRID STOP\nL 0 1 1 1\nP 1 0\n",
            "bad laser": "GRID START\no\nGRID STOP\nL 0 1 2 1\nP 1 0\n",
            "no target": "GRID START\no\nGRID STOP\nL 0 1 1 1\n",
            "too many": "GRID START\no\nGRID STOP\nA 2\nL 0 1 1 1\nP 1 0\n",
            "outside": "GRID START\no\nGRID STOP\nL 0 1 1 1\nP 9 9\n",
            "unclosed": "GRID START\no\nL 0 1 1 1\nP 1 0\n",
        }
        for label, text in bad.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    Board.from_string(text)


class TestTrace(unittest.TestCase):

    def test_straight_line(self):
        visited, _, _ = trace([[None, None], [None, None]],
                              [(0, 1, 1, 1)], 2, 2)
        self.assertEqual(visited, {(0, 1), (1, 2), (2, 3), (3, 4)})

    def test_opaque_stops_laser(self):
        cells = [[None, OpaqueBlock()], [None, None]]
        visited, _, _ = trace(cells, [(1, 2, 1, -1)], 2, 2)
        self.assertEqual(visited, {(1, 2), (2, 1)})

    def test_reflect_bounces(self):
        cells = [[None, ReflectBlock()], [None, None]]
        visited, _, _ = trace(cells, [(1, 2, 1, -1)], 2, 2)
        self.assertIn((1, 0), visited)
        self.assertNotIn((3, 0), visited)

    def test_refract_splits(self):
        cells = [[None, RefractBlock()], [None, None]]
        visited, _, _ = trace(cells, [(1, 2, 1, -1)], 2, 2)
        self.assertIn((1, 0), visited)   # reflected beam
        self.assertIn((3, 0), visited)   # transmitted beam

    def test_loop_terminates(self):
        # Four reflectors around an empty centre can trap a beam forever.
        a = ReflectBlock()
        cells = [[None, a, None], [a, None, a], [None, a, None]]
        visited, _, _ = trace(cells, [(2, 3, 1, -1)], 3, 3)
        self.assertTrue(visited)


if __name__ == "__main__":
    unittest.main()
