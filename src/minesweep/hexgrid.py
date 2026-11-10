"""Hexagonal grid geometry and text layout. Pure: no game state, no I/O.

Cells are ``(x, y)`` like on the square board. The layout is "odd-r" offset
rows with pointy-top hexagons: every odd row (the 2nd, 4th, ... as the player
counts them) is shoved half a cell to the right, so each cell touches six
others instead of eight.
"""

from __future__ import annotations

from typing import Callable

from minesweep.board import Cell, column_label

# Neighbour offsets (dx, dy). Which list applies depends on the row's parity.
_EVEN_ROW = ((-1, 0), (1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
_ODD_ROW = ((-1, 0), (1, 0), (0, -1), (1, -1), (0, 1), (1, 1))


def in_bounds(cell: Cell, width: int, height: int) -> bool:
    x, y = cell
    return 0 <= x < width and 0 <= y < height


def hex_neighbours(cell: Cell, width: int, height: int) -> list[Cell]:
    """The (up to six) cells touching ``cell``, in reading order."""
    x, y = cell
    offsets = _ODD_ROW if y % 2 else _EVEN_ROW
    found = [(x + dx, y + dy) for dx, dy in offsets]
    return sorted((c for c in found if in_bounds(c, width, height)), key=lambda c: (c[1], c[0]))


def to_axial(cell: Cell) -> tuple[int, int]:
    """Offset ``(x, y)`` to axial ``(q, r)``, where distances are easy."""
    x, y = cell
    return x - (y - (y & 1)) // 2, y


def hex_distance(a: Cell, b: Cell) -> int:
    """Number of steps between two cells (1 for neighbours)."""
    aq, ar = to_axial(a)
    bq, br = to_axial(b)
    dq, dr = aq - bq, ar - br
    return max(abs(dq), abs(dr), abs(dq + dr))


def render_hex_grid(
    width: int, height: int, cell_text: Callable[[Cell], str]
) -> str:
    """Lay the grid out as text with column letters on top and row numbers left.

    ``cell_text`` gives the one-character text of each cell. Cells sit two
    characters apart; odd rows are indented one extra character, which puts
    each of them between two cells of the row above. The column letters label
    the even rows (letters wider than one character are not supported, so
    boards wider than 26 columns are labelled by their last letter only).
    """
    row_w = len(str(height))
    pad = " " * row_w
    header = pad + " " + " ".join(column_label(x)[-1] for x in range(width))
    lines = [header]
    for y in range(height):
        indent = " " if y % 2 else ""
        cells = " ".join(cell_text((x, y))[:1] or " " for x in range(width))
        lines.append(f"{y + 1:>{row_w}} {indent}{cells}".rstrip())
    return "\n".join(lines)
