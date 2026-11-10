"""Full-screen keyboard mode (``--tui``), drawn with curses.

The game rules stay in :class:`~minesweep.board.Board`. :class:`Session`
turns key names into moves and is plain Python, so it is tested without a
terminal; :func:`run_tui` is the thin curses layer around it. curses ships
with Python on Linux and macOS; on Windows it comes from the
``windows-curses`` package that ``pip install "minesweep-cli[tui]"`` adds.
"""

from __future__ import annotations

from typing import Any

from minesweep.board import (
    NO_GUESS_TRIES,
    Board,
    Cell,
    CoordError,
    MoveError,
    cell_label,
    daily_start,
)
from minesweep.render import pick_glyphs, render_board, render_status
from minesweep.solver import FLAG, REVEAL, suggest

KEYS_HELP = (
    "arrows move   space/enter reveal (chord on a number)   f flag   "
    "u undo   h hint   s save+quit   q quit"
)
INSTALL_HINT = 'on Windows, install it with: pip install "minesweep-cli[tui]"'

STEPS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

SAVE, QUIT = "save", "quit"


class Session:
    """One full-screen game: a board, a cursor and the line shown under it.

    :meth:`handle` takes a key name (``"up"``, ``"enter"``, ``"f"``, ...).
    ``outcome`` becomes ``"save"`` or ``"quit"`` when the player leaves, and
    stays None while playing or once the game is over (see ``board.over``).
    """

    def __init__(self, board: Board):
        self.board = board
        self.cursor: Cell = _start_cursor(board)
        self.message = ""
        self.outcome: str | None = None
        self._hints_seen: set = set()
        self._warned_no_guess = board.no_guess_ok is False
        if board.daily and not board.history:
            self.message = (
                f"{cell_label(daily_start(board.config))} was opened for you. "
                "The clock starts on your first reveal."
            )

    @property
    def done(self) -> bool:
        return self.outcome is not None or self.board.over

    def handle(self, key: str) -> None:
        if self.done:
            return
        self.message = ""
        if key in STEPS:
            dx, dy = STEPS[key]
            x, y = self.cursor
            self.cursor = (
                min(max(x + dx, 0), self.board.width - 1),
                min(max(y + dy, 0), self.board.height - 1),
            )
        elif key in (" ", "enter", "r"):
            self._move("chord" if self.cursor in self.board.revealed else "reveal")
        elif key == "c":
            self._move("chord")
        elif key == "f":
            self._move("flag")
        elif key == "u":
            try:
                action, cell = self.board.undo()
            except MoveError as exc:
                self.message = str(exc)
                return
            self.cursor = cell
            self.message = f"Undid {action} {cell_label(cell)}."
        elif key == "h":
            self._hint()
        elif key == "s":
            self.outcome = SAVE
        elif key in ("q", "escape"):
            self.outcome = QUIT
        elif key == "?":
            self.message = KEYS_HELP

    def _move(self, action: str) -> None:
        board, cell = self.board, self.cursor
        try:
            if action == "reveal":
                board.reveal(cell)
            elif action == "flag":
                board.toggle_flag(cell)
            else:
                board.chord(cell)
        except (CoordError, MoveError) as exc:
            self.message = str(exc)
            return
        if board.no_guess_ok is False and not self._warned_no_guess:
            self._warned_no_guess = True
            self.message = (
                f"No board for this first click could be solved without guessing "
                f"in {NO_GUESS_TRIES} tries, so this one may need a guess."
            )

    def _hint(self) -> None:
        """Move the cursor to a move the board proves; counted like the ``h`` command."""
        board = self.board
        if not board.revealed:
            self.message = "No hint needed yet: your first reveal is always safe."
            return
        hint = suggest(board)
        if hint is None:
            self.message = "No certain move: you have to guess."
            return
        key = (frozenset(board.revealed), frozenset(board.flagged), hint)
        if key not in self._hints_seen:
            self._hints_seen.add(key)
            board.hints += 1
        self.cursor = hint.cell
        label = cell_label(hint.cell)
        if hint.action == REVEAL:
            what = f"{label} is safe (press space)"
        elif hint.action == FLAG:
            what = f"{label} is a mine (press f)"
        else:
            what = f"{label} is flagged but safe (press f to unflag)"
        self.message = f"Hint ({hint.rule} rule): {what}. Hinted games are not ranked."

    def screen_lines(self, glyphs) -> list[str]:
        """Everything drawn on screen, top to bottom."""
        board = self.board
        cfg = board.config
        title = f"minesweep  {cfg.difficulty} {cfg.width}x{cfg.height}, {cfg.mines} mines"
        if board.daily:
            title += f"  daily {board.daily}"
        lines = [title, ""]
        lines += render_board(board, glyphs=glyphs, highlight=self.cursor).split("\n")
        lines += ["", f"{render_status(board)}   Cursor: {cell_label(self.cursor)}"]
        lines += [self.message or "Press ? for keys.", KEYS_HELP]
        return lines


def _start_cursor(board: Board) -> Cell:
    if board.last_move:
        return board.last_move[1]
    if board.daily:
        return daily_start(board.config)
    return (board.width // 2, board.height // 2)


def key_name(code: int, curses: Any) -> str | None:
    """Translate a ``getch()`` code into the key names :class:`Session` knows."""
    special = {
        curses.KEY_UP: "up",
        curses.KEY_DOWN: "down",
        curses.KEY_LEFT: "left",
        curses.KEY_RIGHT: "right",
        curses.KEY_ENTER: "enter",
        10: "enter",
        13: "enter",
        27: "escape",
    }
    if code in special:
        return special[code]
    if 32 <= code < 127:
        return chr(code).lower()
    return None


def _draw(screen: Any, session: Session, glyphs, curses: Any) -> None:
    screen.erase()
    rows, cols = screen.getmaxyx()
    lines = session.screen_lines(glyphs)
    if len(lines) > rows or max(len(line) for line in lines[:-1]) >= cols:
        lines = [f"Make the terminal bigger ({rows}x{cols} is too small)."]
    for y, line in enumerate(lines[:rows]):
        try:
            screen.addstr(y, 0, line[: max(cols - 1, 0)])
        except curses.error:  # writing the bottom-right cell raises; harmless
            pass
    screen.refresh()


def _loop(screen: Any, session: Session, glyphs, curses: Any) -> None:
    try:
        curses.curs_set(0)
    except curses.error:  # some terminals cannot hide the cursor
        pass
    screen.keypad(True)
    screen.timeout(1000)  # wake up every second so the clock keeps moving
    while not session.done:
        _draw(screen, session, glyphs, curses)
        code = screen.getch()
        if code == -1:
            continue
        name = key_name(code, curses)
        if name:
            session.handle(name)


def run_tui(board: Board, ctx: Any, *, from_save: bool) -> int:
    """Play ``board`` full screen, then print the result like the line mode does."""
    from minesweep import cli  # imported here: cli imports this module

    try:
        import curses
    except ImportError:
        ctx.err(f"--tui needs the curses module, which this Python lacks; {INSTALL_HINT}")
        return 2
    if not (cli._isatty(ctx.stdin) and cli._isatty(ctx.stdout)):
        ctx.err("--tui needs an interactive terminal; leave it out to play with typed commands")
        return 2

    session = Session(board)
    glyphs = pick_glyphs(ctx.stdout)
    try:
        curses.wrapper(lambda screen: _loop(screen, session, glyphs, curses))
    except KeyboardInterrupt:
        ctx.stdout.write("Interrupted; game not saved.\n")
        return 130

    out = ctx.stdout
    out.write(render_board(board, glyphs=pick_glyphs(out), highlight=session.cursor) + "\n")
    out.write(render_status(board) + "\n")
    if session.outcome == SAVE:
        path = cli.save_game(board, ctx.environ)
        out.write(f"Game saved to {path}. Continue with: minesweep resume\n")
        return 0
    if session.outcome == QUIT:
        note = " Your earlier save is still there." if from_save else ""
        out.write(f"Quit without saving.{note}\n")
        return 0
    return cli._finish(board, ctx, from_save)
