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
    column_label,
    daily_start,
)
from minesweep.render import (
    EXPLODED_COLOR,
    FLAG_COLOR,
    HIDDEN_COLOR,
    MINE_COLOR,
    NUMBER_COLORS,
    _cell,
    pick_glyphs,
    render_board,
    render_status,
    use_color,
)
from minesweep.solver import FLAG, REVEAL, suggest

# Style name -> (curses colour name, attributes). Same palette as the
# turn-based mode's ANSI colours; "bold" stands in for the bright variants.
STYLE_SPEC = {
    "n1": ("blue", ("bold",)),
    "n2": ("green", ()),
    "n3": ("red", ("bold",)),
    "n4": ("blue", ()),
    "n5": ("red", ()),
    "n6": ("cyan", ()),
    "n7": ("magenta", ()),
    "n8": ("white", ("dim",)),
    "flag": ("red", ("bold",)),
    "mine": ("white", ("bold",)),
    "exploded": ("white", ("bold",)),  # drawn on a red background, see EXPLODED_BG
    "hidden": ("white", ("dim",)),
}
EXPLODED_BG = "red"
_STYLE_OF_CODE = {NUMBER_COLORS[n]: f"n{n}" for n in NUMBER_COLORS}
_STYLE_OF_CODE.update(
    {FLAG_COLOR: "flag", MINE_COLOR: "mine", EXPLODED_COLOR: "exploded", HIDDEN_COLOR: "hidden"}
)

KEYS_HELP = (
    "arrows/click move+reveal   space/enter reveal (chord on a number)   f flag (right click)   "
    "u undo   h hint   s save+quit   q quit"
)
INSTALL_HINT = 'on Windows, install it with: pip install "minesweep-cli[tui]"'

STEPS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

SAVE, QUIT = "save", "quit"
BOARD_TOP = 3  # title, blank line and the column letters come first


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

    def cell_at(self, col: int, row: int) -> Cell | None:
        """The board cell drawn at screen column ``col``, row ``row``, or None.

        Mirrors the layout of :meth:`screen_lines`: a title and a blank line,
        then the column letters, then one line per board row that starts with
        the row number and a space.
        """
        board = self.board
        cell_w = len(column_label(board.width - 1))
        row_w = len(str(board.height))
        y = row - BOARD_TOP
        offset = col - (row_w + 1)
        if not 0 <= y < board.height or offset < 0:
            return None
        x, within = divmod(offset, cell_w + 1)
        if x >= board.width:
            return None
        if within >= cell_w:  # the space between two cells
            return None
        return (x, y)

    def click(self, col: int, row: int, button: str = "left") -> None:
        """Mouse click: left reveals (or chords on a number), right flags."""
        if self.done:
            return
        cell = self.cell_at(col, row)
        if cell is None:
            return
        self.cursor = cell
        if button == "right":
            self.handle("f")
        else:
            self.handle(" ")

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

    def cell_styles(self, glyphs) -> list[tuple[int, int, int, str]]:
        """``(screen row, screen column, width, style)`` for every board cell.

        Positions match :meth:`screen_lines` and :meth:`cell_at`; style names
        are the keys of ``STYLE_SPEC``. Blank revealed cells have no style.
        """
        board = self.board
        cell_w = len(column_label(board.width - 1))
        row_w = len(str(board.height))
        spans = []
        for y in range(board.height):
            for x in range(board.width):
                _text, code = _cell(board, (x, y), glyphs, board.over)
                style = _STYLE_OF_CODE.get(code)
                if style:
                    spans.append((BOARD_TOP + y, row_w + 1 + x * (cell_w + 1), cell_w, style))
        return spans


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


def mouse_button(state: int, curses: Any) -> str | None:
    """"left" or "right" for a click in the curses button state, else None."""
    if state & getattr(curses, "BUTTON1_CLICKED", 0) or state & getattr(
        curses, "BUTTON1_PRESSED", 0
    ):
        return "left"
    if state & getattr(curses, "BUTTON3_CLICKED", 0) or state & getattr(
        curses, "BUTTON3_PRESSED", 0
    ):
        return "right"
    return None


def _enable_mouse(curses: Any) -> None:
    mask = getattr(curses, "BUTTON1_PRESSED", 0) | getattr(curses, "BUTTON3_PRESSED", 0)
    mask |= getattr(curses, "BUTTON1_CLICKED", 0) | getattr(curses, "BUTTON3_CLICKED", 0)
    if mask and hasattr(curses, "mousemask"):
        try:
            curses.mousemask(mask)
        except curses.error:
            pass


def setup_colors(curses: Any) -> dict[str, int]:
    """Create colour pairs and return ``{style: curses attribute}``; {} if unsupported."""
    try:
        if not curses.has_colors():
            return {}
        curses.start_color()
        try:
            curses.use_default_colors()
            default_bg = -1
        except curses.error:
            default_bg = getattr(curses, "COLOR_BLACK", 0)
        attrs: dict[str, int] = {}
        for i, (style, (fg, extra)) in enumerate(STYLE_SPEC.items(), start=1):
            bg = getattr(curses, f"COLOR_{EXPLODED_BG.upper()}") if style == "exploded" else default_bg
            curses.init_pair(i, getattr(curses, f"COLOR_{fg.upper()}"), bg)
            attr = curses.color_pair(i)
            for name in extra:
                attr |= getattr(curses, f"A_{name.upper()}", 0)
            attrs[style] = attr
        return attrs
    except (AttributeError, curses.error):
        return {}


def _draw(
    screen: Any, session: Session, glyphs, curses: Any, attrs: dict[str, int] | None = None
) -> None:
    screen.erase()
    rows, cols = screen.getmaxyx()
    lines = session.screen_lines(glyphs)
    fits = not (len(lines) > rows or max(len(line) for line in lines[:-1]) >= cols)
    if not fits:
        lines = [f"Make the terminal bigger ({rows}x{cols} is too small)."]
    for y, line in enumerate(lines[:rows]):
        try:
            screen.addstr(y, 0, line[: max(cols - 1, 0)])
        except curses.error:  # writing the bottom-right cell raises; harmless
            pass
    if attrs and fits:
        for row, col, width, style in session.cell_styles(glyphs):
            try:
                screen.addstr(row, col, lines[row][col : col + width], attrs[style])
            except curses.error:
                pass
    screen.refresh()


def _loop(screen: Any, session: Session, glyphs, curses: Any, color: bool = False) -> None:
    try:
        curses.curs_set(0)
    except curses.error:  # some terminals cannot hide the cursor
        pass
    attrs = setup_colors(curses) if color else {}
    screen.keypad(True)
    _enable_mouse(curses)
    screen.timeout(1000)  # wake up every second so the clock keeps moving
    while not session.done:
        _draw(screen, session, glyphs, curses, attrs)
        code = screen.getch()
        if code == -1:
            continue
        if code == getattr(curses, "KEY_MOUSE", None):
            try:
                _id, col, row, _z, state = curses.getmouse()
            except curses.error:
                continue
            button = mouse_button(state, curses)
            if button:
                session.click(col, row, button)
            continue
        name = key_name(code, curses)
        if name:
            session.handle(name)


def run_tui(board: Board, ctx: Any, *, from_save: bool, color_mode: str = "auto") -> int:
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
    color = use_color(color_mode, ctx.stdout, ctx.environ)
    try:
        curses.wrapper(lambda screen: _loop(screen, session, glyphs, curses, color))
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
