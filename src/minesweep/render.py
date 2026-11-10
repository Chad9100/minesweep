"""Turn a board into text. No reading or writing happens here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TextIO

from minesweep.board import LOST, WON, Board, Cell, column_label

RESET = "\x1b[0m"
NUMBER_COLORS = {
    1: "\x1b[94m",  # bright blue
    2: "\x1b[32m",  # green
    3: "\x1b[91m",  # bright red
    4: "\x1b[34m",  # blue
    5: "\x1b[31m",  # red
    6: "\x1b[36m",  # cyan
    7: "\x1b[35m",  # magenta
    8: "\x1b[90m",  # grey
}
FLAG_COLOR = "\x1b[1;31m"
MINE_COLOR = "\x1b[1m"
EXPLODED_COLOR = "\x1b[1;37;41m"
HIDDEN_COLOR = "\x1b[2m"


@dataclass(frozen=True)
class Glyphs:
    hidden: str
    flag: str
    mine: str
    exploded: str
    wrong_flag: str
    empty: str


UNICODE_GLYPHS = Glyphs(hidden="·", flag="⚑", mine="*", exploded="X", wrong_flag="x", empty=" ")
ASCII_GLYPHS = Glyphs(hidden=".", flag="F", mine="*", exploded="X", wrong_flag="x", empty=" ")


def can_encode(stream: TextIO, text: str) -> bool:
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def pick_glyphs(stream: TextIO) -> Glyphs:
    """Unicode glyphs if the stream can encode them, plain ASCII otherwise."""
    g = UNICODE_GLYPHS
    sample = g.hidden + g.flag + g.mine + g.exploded + g.wrong_flag
    return UNICODE_GLYPHS if can_encode(stream, sample) else ASCII_GLYPHS


def use_color(mode: str, stream: TextIO, environ: Mapping[str, str]) -> bool:
    """``always``/``never`` win; ``auto`` means a TTY and NO_COLOR not set."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if environ.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    try:
        return bool(isatty and isatty())
    except (ValueError, OSError):
        return False


def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{RESET}" if color and code else text


def render_board(
    board: Board,
    *,
    color: bool = False,
    glyphs: Glyphs = ASCII_GLYPHS,
    show_mines: bool | None = None,
    highlight: Cell | None = None,
) -> str:
    """Render the grid with column letters on top and row numbers on the left.

    ``show_mines`` defaults to True once the game is over. ``highlight`` puts
    square brackets around one cell (the last move) in place of the spaces
    that separate it from its neighbours, so the columns stay aligned and the
    mark is visible without colour too.
    """
    if show_mines is None:
        show_mines = board.state in (WON, LOST)
    cell_w = len(column_label(board.width - 1))
    row_w = len(str(board.height))

    header = " " * (row_w + 1) + " ".join(
        column_label(x).rjust(cell_w) for x in range(board.width)
    )
    lines = [header.rstrip()]
    for y in range(board.height):
        row = f"{y + 1:>{row_w}}"
        for x in range(board.width):
            if highlight == (x, y):
                sep = "["
            elif highlight == (x - 1, y):
                sep = "]"
            else:
                sep = " "
            text, code = _cell(board, (x, y), glyphs, show_mines)
            row += sep + _paint(text.rjust(cell_w), code, color)
        if highlight == (board.width - 1, y):
            row += "]"
        lines.append(row.rstrip())
    return "\n".join(lines)


def _cell(board: Board, cell: tuple[int, int], g: Glyphs, show_mines: bool) -> tuple[str, str]:
    is_mine = cell in board.mines
    if cell == board.exploded:
        return g.exploded, EXPLODED_COLOR
    if cell in board.flagged:
        if show_mines and board.state == LOST and not is_mine:
            return g.wrong_flag, FLAG_COLOR
        return g.flag, FLAG_COLOR
    if cell in board.revealed:
        n = board.adjacent_mines(cell)
        return (str(n), NUMBER_COLORS[n]) if n else (g.empty, "")
    if show_mines and is_mine:
        return g.mine, MINE_COLOR
    return g.hidden, HIDDEN_COLOR


def render_status(board: Board) -> str:
    status = f"Mines left: {board.mines_left}   Time: {int(board.elapsed)}s"
    if board.hints:
        status += f"   Hints: {board.hints}"
    return status


def format_seconds(seconds: float) -> str:
    return f"{seconds:.1f}s"
