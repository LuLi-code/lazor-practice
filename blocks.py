"""
Block classes for the Lazor solver.

Every block occupies one grid cell. In the half-block coordinate system used
by the .bff format, the block in column ``col`` and row ``row`` is centred at
``(2 * col + 1, 2 * row + 1)`` and its four edges sit at even x or even y.

A laser always travels diagonally, so whenever it touches a block it is
sitting on exactly one of that block's edges. Each block class decides what
happens to the laser at that edge via :meth:`Block.interact`.
"""


class Block:
    """
    Base class for all placeable blocks.

    Subclasses override :meth:`interact`, which receives the laser direction
    and which edge of the block was struck, and returns the list of outgoing
    directions (empty if the laser is absorbed).
    """

    symbol = "?"
    name = "block"

    def __init__(self, fixed=False):
        """
        Create a block.

        **Parameters**

            fixed: *bool*
                True if the block was fixed on the board by the .bff file
                (it cannot be moved by the solver).
        """
        self.fixed = fixed

    def interact(self, direction, vertical_edge):
        """
        Compute the outgoing laser direction(s).

        **Parameters**

            direction: *tuple of int*
                The incoming laser direction ``(vx, vy)``.
            vertical_edge: *bool*
                True if the laser struck a left/right (vertical) edge,
                False if it struck a top/bottom (horizontal) edge.

        **Returns**

            directions: *list of tuple of int*
                Outgoing directions. An empty list means the laser stops.
        """
        raise NotImplementedError

    def __repr__(self):
        return "%s(fixed=%s)" % (type(self).__name__, self.fixed)


def _reflect(direction, vertical_edge):
    """Mirror a direction off a vertical or horizontal edge."""
    vx, vy = direction
    return (-vx, vy) if vertical_edge else (vx, -vy)


class ReflectBlock(Block):
    """Block 'A': reflects the laser like a mirror."""

    symbol = "A"
    name = "reflect"

    def interact(self, direction, vertical_edge):
        return [_reflect(direction, vertical_edge)]


class OpaqueBlock(Block):
    """Block 'B': absorbs the laser completely."""

    symbol = "B"
    name = "opaque"

    def interact(self, direction, vertical_edge):
        return []


class RefractBlock(Block):
    """
    Block 'C': splits the laser. One beam passes straight through, the other
    reflects as if from a reflect block.
    """

    symbol = "C"
    name = "refract"

    def interact(self, direction, vertical_edge):
        return [direction, _reflect(direction, vertical_edge)]


BLOCK_TYPES = {cls.symbol: cls for cls in (ReflectBlock, OpaqueBlock,
                                           RefractBlock)}


def make_block(symbol, fixed=False):
    """
    Build a block from its .bff letter.

    **Parameters**

        symbol: *str*
            One of 'A', 'B' or 'C'.
        fixed: *bool*
            Whether the block is fixed on the board.

    **Returns**

        block: *Block*
    """
    try:
        return BLOCK_TYPES[symbol](fixed=fixed)
    except KeyError:
        raise ValueError("Unknown block type '%s' (expected A, B or C)"
                         % symbol)
