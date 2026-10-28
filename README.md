# Lazor Solver

EN.540.635 Software Carpentry, Lazor group project (Fall 2026).

Automatically solves levels of the *Lazors* mobile game from `.bff` board files.

**Group members:** _add names here_

## Requirements

- Python 3.8+
- [Pillow](https://pypi.org/project/Pillow/) (optional; only used for the `.png` pictures of solutions)

```bash
pip install pillow
```

## Usage

Solve one board:

```bash
python lazor.py boards/mad_1.bff
```

Solve every board in a folder and write results somewhere else:

```bash
python lazor.py boards/ -o solutions
```

Each board gives:

- `solutions/<board>_solution.txt`: the solved grid in `.bff` style, plus a list of where each block went
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

## Running the tests

```bash
python -m unittest -v
```

The tests cover parsing (including malformed files), each block type, laser tracing (including loops), the output file, and the solver. They check that every board in `boards/` gets a valid solution and that the solver agrees with brute-force search on small boards.

## Code layout

| File | Purpose |
|---|---|
| `lazor.py` | Command-line entry point |
| `blocks.py` | `Block` base class and `ReflectBlock`, `OpaqueBlock`, `RefractBlock` |
| `board.py` | `Board` class (`.bff` parsing and validation) and `trace()` laser simulation |
| `solver.py` | Laser-guided depth-first search |
| `output.py` | Text and PNG solution writers |
| `test_board.py` | Unit tests for blocks, parsing and laser tracing |
| `test_solver.py` | Unit tests for the solver and output files |
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

## Benchmarks

| Board | Time (s) |
|---|---|
| dark_1 | 0.0002 |
| mad_1 | 0.0016 |
| mad_4 | 0.0005 |
| mad_7 | 0.0088 |
| numbered_6 | 0.0008 |
| showstopper_4 | < 0.0001 |
| tiny_5 | 0.0001 |
| yarn_5 | 0.0008 |
