"""
Writing solved boards to disk.

Two kinds of output file are produced for every solved board:

* a text file (always) holding the solved grid in .bff style, a character
  "laser map" that shows where the beams travel, and a list of where each
  block was placed;
* a PNG picture of the board and its laser paths (only if Pillow is
  installed, since it is an optional dependency).
"""

from board import trace

LEGEND = """Legend:
  o = empty cell        x = no block allowed
  A = reflect block     B = opaque block      C = refract block
  Fixed blocks from the puzzle are shown in lowercase (a, b, c)."""

MAP_LEGEND = """Laser map legend (half-block coordinates, as in the .bff file):
  L = laser start       * = laser path
  @ = target that is hit            ! = target that is missed
  letters sit at the centre of each cell, as in the grid above."""


def solved_grid(board, placement):
    """
    Return the grid with the solver's blocks filled in.

    Fixed blocks are lowercased so they can be told apart from the placed
    ones; the result can be pasted straight back into a .bff GRID section
    once any a/b/c are turned back into A/B/C.

    **Parameters**

        board: *Board*
            The parsed puzzle.
        placement: *dict*
            ``{(col, row): symbol}`` from the solver.

    **Returns**

        grid: *list of list of str*
            ``grid[row][col]`` is 'o', 'x', a placed block ('A', 'B', 'C')
            or a fixed block ('a', 'b', 'c').
    """
    grid = [[ch.lower() if ch in "ABC" else ch for ch in row]
            for row in board.grid]
    for (c, r), symbol in placement.items():
        grid[r][c] = symbol
    return grid


def laser_path(board, placement):
    """
    Re-run the laser simulation on the solved board.

    **Parameters**

        board: *Board*
        placement: *dict*
            ``{(col, row): symbol}`` from the solver.

    **Returns**

        visited: *set of tuple of int*
            Every point ``(x, y)`` a laser passes through.
        segments: *list of tuple*
            ``((x1, y1), (x2, y2))`` pieces of the laser path, for drawing.
    """
    cells = board.block_grid(placement)
    visited, segments, _ = trace(cells, board.lasers, board.width,
                                 board.height)
    return visited, segments


def missed_targets(board, placement):
    """
    List the targets that the lasers do NOT pass through.

    An empty list means the placement really is a solution, so this doubles
    as an independent check of the solver's answer.

    **Returns**

        missed: *list of tuple of int*
            Target points ``(x, y)`` that no laser reaches.
    """
    visited, _ = laser_path(board, placement)
    return [t for t in board.targets if t not in visited]


def laser_map(board, placement):
    """
    Draw the solved board and its laser paths with plain characters.

    The picture uses the half-block coordinates of the .bff file, so it is
    ``2 * width + 1`` characters wide and ``2 * height + 1`` tall. Cell
    centres (odd x, odd y) show the block letter; a laser only ever sits on
    cell edges, so the two never overlap.

    **Returns**

        lines: *list of str*
            The rows of the picture, with x and y axis labels.
    """
    visited, _ = laser_path(board, placement)
    grid = solved_grid(board, placement)
    targets = set(board.targets)
    starts = {(x, y) for x, y, _, _ in board.lasers}
    n_x, n_y = 2 * board.width + 1, 2 * board.height + 1

    # Axis labels use the last digit only so that columns stay aligned.
    lines = ["  x " + " ".join(str(x % 10) for x in range(n_x)), "y"]
    for y in range(n_y):
        chars = []
        for x in range(n_x):
            if (x, y) in targets:
                chars.append("@" if (x, y) in visited else "!")
            elif (x, y) in starts:
                chars.append("L")
            elif (x, y) in visited:
                chars.append("*")
            elif x % 2 == 1 and y % 2 == 1:
                chars.append(grid[y // 2][x // 2])
            else:
                chars.append(" ")
        lines.append(("%-3d " % y + " ".join(chars)).rstrip())
    return lines


def write_text(board, placement, path, elapsed=None):
    """
    Write the solution as a human-readable text file.

    **Parameters**

        board: *Board*
        placement: *dict*
            ``{(col, row): symbol}`` from the solver.
        path: *str*
            Output file path.
        elapsed: *float, optional*
            Solve time in seconds, recorded in the file.
    """
    missed = missed_targets(board, placement)

    lines = ["Solution for %s" % board.name, ""]
    lines += ["GRID START"]
    lines += [" ".join(row) for row in solved_grid(board, placement)]
    lines += ["GRID STOP", "", LEGEND, ""]

    lines += ["Placed blocks (col, row), 0-indexed from top-left:"]
    # Sort by row first, then column, i.e. normal reading order.
    for (c, r), symbol in sorted(placement.items(), key=lambda i: i[0][::-1]):
        lines.append("  %s at (%d, %d)" % (symbol, c, r))
    if not placement:
        lines.append("  (none needed)")

    lines += ["", "Laser map:", ""]
    lines += laser_map(board, placement)
    lines += ["", MAP_LEGEND, ""]

    n_targets = len(board.targets)
    lines.append("Targets hit: %d of %d" % (n_targets - len(missed),
                                            n_targets))
    if missed:
        lines.append("WARNING, missed targets: %s"
                     % ", ".join("(%d, %d)" % t for t in missed))
    if elapsed is not None:
        lines.append("Solved in %.4f s" % elapsed)

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_png(board, placement, path, scale=80):
    """
    Draw the solved board with its laser paths as a PNG.

    **Parameters**

        board: *Board*
        placement: *dict*
            ``{(col, row): symbol}`` from the solver.
        path: *str*
            Output file path.
        scale: *int, optional*
            Size of one block in pixels.

    **Returns**

        written: *bool*
            False (and nothing is written) if Pillow is not installed.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    colors = {"o": (235, 235, 235), "x": (120, 120, 120),
              "A": (250, 205, 90), "B": (20, 20, 20),
              "C": (150, 200, 240)}
    red, orange = (220, 0, 0), (255, 140, 0)
    black, white = (0, 0, 0), (255, 255, 255)
    half = scale // 2
    img = Image.new("RGB", (board.width * scale + 1, board.height * scale + 1),
                    white)
    draw = ImageDraw.Draw(img)

    # 1. The cells and blocks.
    grid = solved_grid(board, placement)
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            box = [c * scale + 3, r * scale + 3,
                   (c + 1) * scale - 3, (r + 1) * scale - 3]
            fixed = ch in "abc"  # fixed blocks get an orange border
            draw.rectangle(box, fill=colors[ch.upper() if fixed else ch],
                           outline=orange if fixed else black,
                           width=4 if fixed else 1)
            if ch.upper() in "ABC":
                draw.text((c * scale + 8, r * scale + 6), ch.upper(),
                          fill=white if ch.upper() == "B" else black)

    # 2. The laser beams, drawn on top of the blocks.
    _, segments = laser_path(board, placement)
    for (x1, y1), (x2, y2) in segments:
        draw.line([x1 * half, y1 * half, x2 * half, y2 * half],
                  fill=red, width=3)

    # 3. Laser sources (solid red) and targets (white with a black ring).
    for x, y, _, _ in board.lasers:
        draw.ellipse([x * half - 7, y * half - 7, x * half + 7,
                      y * half + 7], fill=red)
    for x, y in board.targets:
        draw.ellipse([x * half - 7, y * half - 7, x * half + 7,
                      y * half + 7], outline=black, width=3, fill=white)
    img.save(path)
    return True
