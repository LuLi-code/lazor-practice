"""
Search for a block placement that makes the lasers hit every target.

Approach (laser-guided depth-first search)
------------------------------------------
Brute force would try every way of dropping the blocks into the open cells,
which grows combinatorially (yarn_5 alone has hundreds of thousands of
arrangements) and re-simulates the lasers for each one.

Instead, note that a block only matters if a laser actually reaches it. So
we start with every open cell "undecided" and trace the lasers until one of
them is about to enter an undecided cell. Only that cell is branched on:
it gets a reflect, opaque or refract block (if any are left), or it is
declared empty for good. Then tracing continues. When the lasers finish
without meeting any undecided cell, their path is final; if it covers every
target, the leftover blocks go into cells no laser touches, where they
cannot change anything.

This search is complete (every real solution is reachable along one branch)
and each cell is decided at most once per branch, so no placement is tried
twice. Cells the lasers never reach are never enumerated at all, which is
where almost all of the speed-up comes from.
"""

from blocks import make_block
from board import OPEN, trace

# Try the placeable block types in this order at each branch point.
ORDER = ("A", "C", "B")

# Blocks hold no per-cell state, so one shared instance per type suffices.
_BLOCKS = {s: make_block(s) for s in ORDER}


def solve(board):
    """
    Solve a Lazor board.

    **Parameters**

        board: *Board*
            The parsed puzzle.

    **Returns**

        placement: *dict or None*
            ``{(col, row): symbol}`` for every movable block, or None if the
            puzzle has no solution.
    """
    width, height = board.width, board.height
    cells = board.block_grid()
    undecided = [[ch == OPEN for ch in row] for row in board.grid]
    remaining = {s: board.blocks.get(s, 0) for s in ORDER}
    targets = set(board.targets)
    placement = {}
    n_undecided = [sum(row.count(True) for row in undecided)]

    def search():
        if n_undecided[0] < sum(remaining.values()):
            return False  # not enough cells left for the blocks
        visited, _, pending = trace(cells, board.lasers, width, height,
                                    undecided)
        if pending is None:
            if not targets <= visited:
                return False
            _fill_leftovers(undecided, remaining, placement)
            return True

        col, row = pending
        undecided[row][col] = False
        n_undecided[0] -= 1
        for symbol in ORDER:
            if remaining[symbol]:
                remaining[symbol] -= 1
                placement[(col, row)] = symbol
                cells[row][col] = _BLOCKS[symbol]
                if search():
                    return True
                cells[row][col] = None
                del placement[(col, row)]
                remaining[symbol] += 1
        if search():  # leave the cell empty
            return True
        undecided[row][col] = True
        n_undecided[0] += 1
        return False

    return dict(placement) if search() else None


def _fill_leftovers(undecided, remaining, placement):
    """Put unused blocks into cells the lasers never reach."""
    free = [(c, r) for r, row in enumerate(undecided)
            for c, flag in enumerate(row) if flag]
    for symbol in ORDER:
        for _ in range(remaining[symbol]):
            placement[free.pop()] = symbol
