"""Pure game logic: no printing, no files, no reading input.

Cells are addressed as ``(x, y)`` with 0-based column ``x`` and row ``y``.
Players see columns as letters (A, B, ... Z, AA, AB, ...) and rows as
1-based numbers, so ``(0, 4)`` is ``A5``.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator

Cell = tuple[int, int]
Clock = Callable[[], float]

MAX_SIDE = 99
SAVE_VERSION = 1

PLAYING = "playing"
WON = "won"
LOST = "lost"


class ConfigError(ValueError):
    """The requested board cannot be built."""


class MoveError(ValueError):
    """The move is not allowed right now (the board is unchanged)."""


class CoordError(ValueError):
    """Text could not be turned into a cell on this board."""


@dataclass(frozen=True)
class Config:
    width: int
    height: int
    mines: int
    difficulty: str = "custom"

    @property
    def cells(self) -> int:
        return self.width * self.height

    @property
    def ranked(self) -> bool:
        return self.difficulty in DIFFICULTIES


DIFFICULTIES: dict[str, Config] = {
    "beginner": Config(9, 9, 10, "beginner"),
    "intermediate": Config(16, 16, 40, "intermediate"),
    "expert": Config(30, 16, 99, "expert"),
}


def make_config(width: int, height: int, mines: int) -> Config:
    """Validate a board size and label it with a standard difficulty if it is one."""
    for name, value in (("width", width), ("height", height)):
        if value < 1:
            raise ConfigError(f"{name} must be at least 1 (got {value})")
        if value > MAX_SIDE:
            raise ConfigError(f"{name} must be at most {MAX_SIDE} (got {value})")
    if mines < 1:
        raise ConfigError(f"mines must be at least 1 (got {mines})")
    limit = width * height - 1
    if mines > limit:
        raise ConfigError(
            f"too many mines: a {width}x{height} board holds at most {limit} "
            f"(one cell must stay safe), got {mines}"
        )
    for name, std in DIFFICULTIES.items():
        if (std.width, std.height, std.mines) == (width, height, mines):
            return Config(width, height, mines, name)
    return Config(width, height, mines, "custom")


# ---------------------------------------------------------------- coordinates


def column_label(x: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (spreadsheet style)."""
    if x < 0:
        raise ValueError("column index must be >= 0")
    label = ""
    n = x + 1
    while n:
        n, rem = divmod(n - 1, 26)
        label = chr(ord("A") + rem) + label
    return label


def column_index(label: str) -> int:
    n = 0
    for ch in label.upper():
        if not "A" <= ch <= "Z":
            raise ValueError(f"not a column label: {label!r}")
        n = n * 26 + (ord(ch) - ord("A") + 1)
    if n == 0:
        raise ValueError("empty column label")
    return n - 1


def cell_label(cell: Cell) -> str:
    x, y = cell
    return f"{column_label(x)}{y + 1}"


_COORD_RE = re.compile(r"([A-Za-z]+)\s*(\d+)")


def parse_coord(text: str, width: int, height: int) -> Cell:
    """Parse ``B3`` (case-insensitive) into ``(1, 2)``, checking it is on the board."""
    raw = text.strip()
    match = _COORD_RE.fullmatch(raw)
    if not match:
        raise CoordError(
            f"'{raw}' is not a cell: use a column letter then a row number, like B3"
        )
    letters, digits = match.groups()
    x = column_index(letters)
    y = int(digits) - 1
    if x >= width:
        raise CoordError(
            f"column {letters.upper()} is off the board (A-{column_label(width - 1)})"
        )
    if not 0 <= y < height:
        raise CoordError(f"row {int(digits)} is off the board (1-{height})")
    return (x, y)


# ---------------------------------------------------------------------- board


class Board:
    """One game of Minesweeper.

    Mines are placed on the first reveal, using ``random.Random(seed)``, so the
    same seed and the same first click always give the same board. ``clock``
    returns seconds (monotonic); the timer starts at the first reveal.
    """

    def __init__(self, config: Config, seed: int, clock: Clock = time.monotonic):
        self.config = config
        self.seed = seed
        self.mines: set[Cell] = set()
        self.mines_placed = False
        self.revealed: set[Cell] = set()
        self.flagged: set[Cell] = set()
        self.state = PLAYING
        self.exploded: Cell | None = None
        self._clock = clock
        self._elapsed = 0.0
        self._started: float | None = None

    # -- construction helpers -------------------------------------------------

    @classmethod
    def from_layout(
        cls, rows: Iterable[str], seed: int = 0, clock: Clock = time.monotonic
    ) -> "Board":
        """Build a board with fixed mines: ``*`` is a mine, anything else is safe."""
        rows = list(rows)
        height = len(rows)
        width = len(rows[0]) if rows else 0
        if any(len(r) != width for r in rows):
            raise ConfigError("layout rows must all be the same length")
        mines = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "*"}
        board = cls(make_config(width, height, len(mines)), seed, clock)
        board.mines = mines
        board.mines_placed = True
        return board

    # -- geometry -------------------------------------------------------------

    @property
    def width(self) -> int:
        return self.config.width

    @property
    def height(self) -> int:
        return self.config.height

    def in_bounds(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, cell: Cell) -> Iterator[Cell]:
        x, y = cell
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    n = (x + dx, y + dy)
                    if self.in_bounds(n):
                        yield n

    def adjacent_mines(self, cell: Cell) -> int:
        return sum(1 for n in self.neighbors(cell) if n in self.mines)

    # -- status ---------------------------------------------------------------

    @property
    def mines_left(self) -> int:
        """Mines minus flags (may go negative if the player over-flags)."""
        return self.config.mines - len(self.flagged)

    @property
    def safe_cells_left(self) -> int:
        return self.config.cells - self.config.mines - len(self.revealed)

    @property
    def elapsed(self) -> float:
        if self._started is None:
            return self._elapsed
        return self._elapsed + max(0.0, self._clock() - self._started)

    @property
    def over(self) -> bool:
        return self.state != PLAYING

    # -- moves ----------------------------------------------------------------

    def reveal(self, cell: Cell) -> list[Cell]:
        """Reveal one cell (flood-filling zeros). Returns the newly revealed cells."""
        self._check_move(cell)
        if cell in self.flagged:
            raise MoveError(f"{cell_label(cell)} is flagged; unflag it first (f {cell_label(cell)})")
        if cell in self.revealed:
            raise MoveError(f"{cell_label(cell)} is already revealed")
        if not self.mines_placed:
            self._place_mines(cell)
        if self._started is None:
            self._started = self._clock()
        if cell in self.mines:
            self._lose(cell)
            return []
        opened = self._flood(cell)
        self._check_win()
        return opened

    def toggle_flag(self, cell: Cell) -> bool:
        """Flag or unflag a hidden cell. Returns True if the cell is now flagged."""
        self._check_move(cell)
        if cell in self.revealed:
            raise MoveError(f"{cell_label(cell)} is already revealed and cannot be flagged")
        if cell in self.flagged:
            self.flagged.discard(cell)
            return False
        self.flagged.add(cell)
        return True

    def chord(self, cell: Cell) -> list[Cell]:
        """Reveal every unflagged hidden neighbour of a number whose flags are all placed.

        If a flag is wrong, a mine gets revealed and the game is lost.
        """
        self._check_move(cell)
        label = cell_label(cell)
        if cell not in self.revealed:
            raise MoveError(f"{label} is hidden; you can only chord on a revealed number")
        need = self.adjacent_mines(cell)
        if need == 0:
            raise MoveError(f"{label} has no mines around it; nothing to chord")
        flags = sum(1 for n in self.neighbors(cell) if n in self.flagged)
        if flags != need:
            raise MoveError(f"{label} shows {need} but has {flags} flag(s) around it")
        targets = [
            n for n in self.neighbors(cell) if n not in self.revealed and n not in self.flagged
        ]
        for t in targets:
            if t in self.mines:
                self._lose(t)
                return []
        opened: list[Cell] = []
        for t in targets:
            if t not in self.revealed:
                opened.extend(self._flood(t))
        self._check_win()
        return opened

    # -- internals ------------------------------------------------------------

    def _check_move(self, cell: Cell) -> None:
        if self.over:
            raise MoveError(f"the game is over (you {self.state})")
        if not self.in_bounds(cell):
            raise MoveError(f"{cell} is off the board")

    def _place_mines(self, first: Cell) -> None:
        """Place mines avoiding ``first`` and, when there is room, its neighbours."""
        zone = {first, *self.neighbors(first)}
        if self.config.cells - len(zone) < self.config.mines:
            zone = {first}
        candidates = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in zone
        ]
        rng = random.Random(self.seed)
        self.mines = set(rng.sample(candidates, self.config.mines))
        self.mines_placed = True

    def _flood(self, start: Cell) -> list[Cell]:
        """Iterative flood fill from a safe cell; flagged cells are left alone."""
        opened: list[Cell] = []
        stack = [start]
        while stack:
            cell = stack.pop()
            if cell in self.revealed or cell in self.flagged or cell in self.mines:
                continue
            self.revealed.add(cell)
            opened.append(cell)
            if self.adjacent_mines(cell) == 0:
                stack.extend(
                    n for n in self.neighbors(cell)
                    if n not in self.revealed and n not in self.flagged
                )
        return opened

    def _stop_clock(self) -> None:
        if self._started is not None:
            self._elapsed += max(0.0, self._clock() - self._started)
            self._started = None

    def _lose(self, cell: Cell) -> None:
        self.state = LOST
        self.exploded = cell
        self._stop_clock()

    def _check_win(self) -> None:
        if self.safe_cells_left == 0:
            self.state = WON
            self.flagged = set(self.mines)
            self._stop_clock()

    # -- persistence ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SAVE_VERSION,
            "width": self.width,
            "height": self.height,
            "mines_total": self.config.mines,
            "difficulty": self.config.difficulty,
            "seed": self.seed,
            "mines_placed": self.mines_placed,
            "mines": sorted(self.mines),
            "revealed": sorted(self.revealed),
            "flagged": sorted(self.flagged),
            "state": self.state,
            "exploded": list(self.exploded) if self.exploded else None,
            "elapsed": round(self.elapsed, 3),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], clock: Clock = time.monotonic) -> "Board":
        """Rebuild a board saved by :meth:`to_dict`. Raises ValueError on bad data."""
        try:
            if data.get("version") != SAVE_VERSION:
                raise ValueError(f"unsupported save version {data.get('version')!r}")
            config = make_config(int(data["width"]), int(data["height"]), int(data["mines_total"]))
            board = cls(config, int(data["seed"]), clock)

            def cells(key: str) -> set[Cell]:
                out = {(int(c[0]), int(c[1])) for c in data[key]}
                bad = [c for c in out if not board.in_bounds(c)]
                if bad:
                    raise ValueError(f"{key} has cells off the board: {bad[:3]}")
                return out

            board.mines_placed = bool(data["mines_placed"])
            board.mines = cells("mines")
            board.revealed = cells("revealed")
            board.flagged = cells("flagged")
            if board.mines_placed and len(board.mines) != config.mines:
                raise ValueError("mine count does not match the board size")
            if board.revealed & board.flagged:
                raise ValueError("a cell cannot be both revealed and flagged")
            state = data["state"]
            if state not in (PLAYING, WON, LOST):
                raise ValueError(f"unknown state {state!r}")
            board.state = state
            exploded = data.get("exploded")
            board.exploded = (int(exploded[0]), int(exploded[1])) if exploded else None
            board._elapsed = float(data.get("elapsed", 0.0))
            if state == PLAYING and board.mines_placed:
                board._started = clock()
            return board
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError(f"malformed save data ({exc.__class__.__name__}: {exc})") from exc
        except ConfigError as exc:
            raise ValueError(f"bad board size in save: {exc}") from exc
