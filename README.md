# Lazor Project

EN.540.635 Software Carpentry, Lazor group project (Fall 2026).

Automatically solves levels of the *Lazors* mobile game from `.bff` board files.

**Group members:** Lu Li and Ou Shen

## Requirements

- Python 3 (no other packages are needed to solve boards and write the text solutions)
- Optional: [Pillow](https://python-pillow.org/), only for the PNG pictures. Install it with `pip install pillow`. Without it the program still runs and simply skips the pictures.

## Usage

Solve one board:

```bash
python lazor.py boards/mad_1.bff
```

Solve every board in a folder and write results somewhere else:

```bash
python lazor.py boards/ -o solutions
```

Options:

- `-o FOLDER` / `--out FOLDER`: where the solution files go (default: `solutions`)
- `--no-png`: write only the text files, even if Pillow is installed

The program prints one line per board with the solve time. If a file is missing or is not a valid `.bff` board, an error is printed for that file and the remaining boards are still solved. The exit status is 0 if every board was solved and 1 otherwise.

Each board gives:

- `solutions/<board>_solution.txt`: the solved grid in `.bff` style, a list of where each block went, and a character map of the laser paths
- `solutions/<board>_solution.png`: a picture of the board with the laser paths (if Pillow is installed)

Example (`mad_1`):

```
GRID START
o o C o
o o o A
A o o o
o o o o
GRID STOP
```

`A` = reflect, `B` = opaque, `C` = refract, `o` = empty, `x` = no block allowed.
Blocks that were fixed in the puzzle appear in lowercase (`a`, `b`, `c`). In the PNG they have an orange border.

The text file also contains a laser map, drawn in the same half-block coordinates as the `.bff` file, so the solution can be checked by eye without the picture:

```
  x 0 1 2 3 4 5 6 7 8
y
0         @
1     o   o * C   o
2             *
3     o   o @ o * A
4         *   *
5     A @ o * o   o
6         *
7     o L o @ o   o
8             *
```

`L` = laser start, `*` = laser path, `@` = target that is hit (`!` would mark a missed target). The file ends with a line such as `Targets hit: 4 of 4`.

## Running the tests

```bash
python -m unittest -v
```

The tests cover parsing (including malformed files), each block type, laser tracing (including loops), the solver, the output files, and the command line. They check that every board in `boards/` gets a valid solution, that fixed blocks are never moved, that the solver agrees with brute-force search on small boards, and that a bad or unsolvable board is reported without stopping the other boards.

## Code layout

| File | Purpose |
|---|---|
| `lazor.py` | Command-line entry point |
| `blocks.py` | `Block` base class and `ReflectBlock`, `OpaqueBlock`, `RefractBlock` |
| `board.py` | `Board` class (`.bff` parsing and validation) and `trace()` laser simulation |
| `solver.py` | Laser-guided depth-first search |
| `output.py` | Text and PNG solution writers |
| `test_board.py` | Unit tests for blocks, parsing and laser tracing |
| `test_solver.py` | Unit tests for the solver, output files and command line |
| `boards/` | Benchmark `.bff` files |

## How it works

**Coordinates.** As in the `.bff` format, one step is half a block. The block in column `c`, row `r` is centred at `(2c+1, 2r+1)`. A laser moves diagonally, so after each step exactly one of its coordinates is even, which means it sits on a block edge. With an even `x` it is on a vertical edge and the cell ahead is `(x+vx, y)`. With an even `y` it is on a horizontal edge and the cell ahead is `(x, y+vy)`. Each block's `interact()` method returns the outgoing direction(s):

- reflect: flip `vx` on a vertical edge, or flip `vy` on a horizontal edge
- opaque: stop the laser
- refract: two beams, one straight through and one reflected

The tracer stops a beam when it leaves the board or repeats a state `(x, y, vx, vy)`, so lasers stuck in a loop always finish.

**Search (the speed-up).** Brute force tries every arrangement of blocks in the open cells. That is hundreds of thousands of arrangements for `yarn_5`, and each one needs a full laser simulation. Our solver uses one observation instead: a block can only matter if a laser reaches it.

1. Every open cell starts as *undecided*.
2. Trace the lasers until one is about to enter an undecided cell.
3. Branch on that cell only. Put a reflect, refract or opaque block there (if any are left), or declare it permanently empty. Then recurse, which continues the trace.
4. If the lasers finish without meeting an undecided cell, their path is final. If it hits every target, the unused blocks go into cells that no laser touched, where they cannot change anything.

Any cell a laser never reaches is never branched on, and each branch decides each cell at most once, so no arrangement is tried twice. The search is still exhaustive: any real solution is reached by making the same choice as that solution at every cell the lasers visit. Every benchmark board solves in well under 0.1 s, with no parallelism.

**Checking the answer.** Before a solution is saved, `lazor.py` replays the lasers on the solved board and confirms that every target is hit, so a wrong answer can never be written to a file.
