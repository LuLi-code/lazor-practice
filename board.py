"""
Reading .bff files and simulating lasers on a Lazor board.

Coordinates follow the .bff convention: (0, 0) is the top-left corner, +x
points right and +y points down, and one step is half a block.
"""

import os

from blocks import BLOCK_TYPES, make_block

OPEN = "o"
NO_BLOCK = "x"


class Board:
    """
    A Lazor puzzle as described by a .bff file.

    **Attributes**

        grid: *list of list of str*
            ``grid[row][col]`` is 'o', 'x', 'A', 'B' or 'C'.
        width, height: *int*
            Board size in blocks.
        blocks: *dict*
            Number of movable blocks of each type, e.g. ``{'A': 2, 'C': 1}``.
        lasers: *list of tuple of int*
            Each laser as ``(x, y, vx, vy)``.
        targets: *list of tuple of int*
            Points the lasers must pass through, as ``(x, y)``.
    """

    def __init__(self, grid, blocks, lasers, targets, name="board"):
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0]) if grid else 0
        self.blocks = blocks
        self.lasers = lasers
        self.targets = targets
        self.name = name
        self._validate()

    @classmethod
    def from_file(cls, path):
        """
        Parse a .bff file.

        **Parameters**

            path: *str*
                Path to the .bff file.

        **Returns**

            board: *Board*
        """
        with open(path) as f:
            text = f.read()
        name = os.path.splitext(os.path.basename(path))[0]
        return cls.from_string(text, name=name)

    @classmethod
    def from_string(cls, text, name="board"):
        """
        Parse the contents of a .bff file.

        **Parameters**

            text: *str*
                The file contents.
            name: *str, optional*
                Name used in output files.

        **Returns**

            board: *Board*
        """
        grid, blocks, lasers, targets = [], {}, [], []
        in_grid = seen_grid = False

        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            upper = line.upper()
            if upper == "GRID START":
                in_grid = seen_grid = True
                continue
            if upper == "GRID STOP":
                in_grid = False
                continue

            if in_grid:
                # Accept both "o o x" and "oox" styles.
                row = list(line.replace(" ", "").replace("\t", ""))
                for ch in row:
                    if ch not in (OPEN, NO_BLOCK) and ch not in BLOCK_TYPES:
                        raise ValueError("Line %d: invalid grid character "
                                         "'%s'" % (lineno, ch))
                grid.append(row)
                continue

            parts = line.split()
            key, values = parts[0], parts[1:]
            try:
                numbers = [int(v) for v in values]
            except ValueError:
                raise ValueError("Line %d: expected integers in '%s'"
                                 % (lineno, raw.strip()))

            if key in BLOCK_TYPES:
                if len(numbers) != 1 or numbers[0] < 0:
                    raise ValueError("Line %d: block line must be "
                                     "'<type> <count>'" % lineno)
                blocks[key] = blocks.get(key, 0) + numbers[0]
            elif key == "L":
                if len(numbers) != 4:
                    raise ValueError("Line %d: laser line must be "
                                     "'L x y vx vy'" % lineno)
                if abs(numbers[2]) != 1 or abs(numbers[3]) != 1:
                    raise ValueError("Line %d: laser direction components "
                                     "must be +1 or -1" % lineno)
                lasers.append(tuple(numbers))
            elif key == "P":
                if len(numbers) != 2:
                    raise ValueError("Line %d: point line must be 'P x y'"
                                     % lineno)
                targets.append(tuple(numbers))
            else:
                raise ValueError("Line %d: unrecognised line '%s'"
                                 % (lineno, raw.strip()))

        if not seen_grid:
            raise ValueError("No 'GRID START' section found")
        if in_grid:
            raise ValueError("'GRID START' without matching 'GRID STOP'")
        return cls(grid, blocks, lasers, targets, name=name)

    def _validate(self):
        """Check that the parsed board is self-consistent."""
        if not self.grid:
            raise ValueError("Grid is empty")
        if any(len(row) != self.width for row in self.grid):
            raise ValueError("Grid rows have different lengths")
        if not self.lasers:
            raise ValueError("Board has no lasers")
        if not self.targets:
            raise ValueError("Board has no target points")
        for x, y in self.targets + [laser[:2] for laser in self.lasers]:
            if not (0 <= x <= 2 * self.width and 0 <= y <= 2 * self.height):
                raise ValueError("Point (%d, %d) lies outside the board"
                                 % (x, y))
        n_open = sum(row.count(OPEN) for row in self.grid)
        if sum(self.blocks.values()) > n_open:
            raise ValueError("More blocks (%d) than open cells (%d)"
                             % (sum(self.blocks.values()), n_open))

    def open_cells(self):
        """Return the (col, row) of every cell a movable block may use."""
        return [(c, r) for r in range(self.height) for c in range(self.width)
                if self.grid[r][c] == OPEN]

    def block_grid(self, placement=None):
        """
        Build a grid of Block objects (None where there is no block).

        **Parameters**

            placement: *dict, optional*
                ``{(col, row): symbol}`` of movable blocks to add.

        **Returns**

            cells: *list of list of Block or None*
        """
        cells = [[make_block(ch, fixed=True) if ch in BLOCK_TYPES else None
                  for ch in row] for row in self.grid]
        for (c, r), symbol in (placement or {}).items():
            cells[r][c] = make_block(symbol)
        return cells


def trace(cells, lasers, width, height, undecided=None):
    """
    Follow every laser across the board.

    **Parameters**

        cells: *list of list of Block or None*
            The blocks on the board, indexed ``cells[row][col]``.
        lasers: *list of tuple of int*
            Starting lasers as ``(x, y, vx, vy)``.
        width, height: *int*
            Board size in blocks.
        undecided: *list of list of bool, optional*
            Used by the solver. If a laser is about to enter a cell flagged
            here, tracing stops and that cell is returned, because what the
            laser does next depends on what goes in the cell.

    **Returns**

        visited: *set of tuple of int*
            Every point ``(x, y)`` a laser passed through.
        segments: *list of tuple*
            ``((x1, y1), (x2, y2))`` laser segments, for drawing.
        pending: *tuple of int or None*
            The first undecided cell ``(col, row)`` reached, else None.
    """
    max_x, max_y = 2 * width, 2 * height
    visited, seen, segments = set(), set(), []
    stack = list(lasers)

    while stack:
        x, y, vx, vy = stack.pop()
        while 0 <= x <= max_x and 0 <= y <= max_y:
            state = (x, y, vx, vy)
            if state in seen:
                break  # this beam is retracing a path already followed
            seen.add(state)
            visited.add((x, y))

            # Find the cell the laser is about to enter. On a vertical edge
            # (even x) it is sideways; on a horizontal edge (even y) it is
            # above/below. Corners and block centres touch nothing.
            if x % 2 == 0 and y % 2 == 1:
                col, row, vertical = (x + vx) // 2, y // 2, True
            elif y % 2 == 0 and x % 2 == 1:
                col, row, vertical = x // 2, (y + vy) // 2, False
            else:
                col = row = -1
            if 0 <= col < width and 0 <= row < height:
                if undecided is not None and undecided[row][col]:
                    return visited, segments, (col, row)
                block = cells[row][col]
                if block is not None:
                    directions = block.interact((vx, vy), vertical)
                    if not directions:
                        break
                    for dx, dy in directions[1:]:
                        stack.append((x, y, dx, dy))
                    vx, vy = directions[0]

            segments.append(((x, y), (x + vx, y + vy)))
            x, y = x + vx, y + vy

    return visited, segments, None
