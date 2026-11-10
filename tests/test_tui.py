"""Full-screen mode: the key-driven Session, and run_tui with a stand-in curses."""

import io
import os
import sys
import types
from datetime import date

import pytest

from minesweep import storage
from minesweep.board import DIFFICULTIES, LOST, WON, Board
from minesweep.cli import _Context, main
from minesweep.render import ASCII_GLYPHS
from minesweep.tui import KEYS_HELP, QUIT, SAVE, Session, key_name, run_tui


class Stream(io.StringIO):
    def __init__(self, text="", tty=True):
        super().__init__(text)
        self._tty = tty

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return "ascii"


class FakeCursesError(Exception):
    pass


class FakeScreen:
    """Records what is drawn and plays back scripted key codes."""

    def __init__(self, keys, size=(24, 80)):
        self.keys = list(keys)
        self.size = size
        self.frames = []
        self._lines = {}

    def getmaxyx(self):
        return self.size

    def erase(self):
        self._lines = {}

    def addstr(self, y, x, text):
        self._lines[y] = text

    def refresh(self):
        self.frames.append([self._lines[y] for y in sorted(self._lines)])

    def keypad(self, flag):
        pass

    def timeout(self, ms):
        pass

    def getch(self):
        if not self.keys:
            raise AssertionError("ran out of scripted keys")
        return self.keys.pop(0)


def fake_curses(screen):
    return types.SimpleNamespace(
        KEY_UP=259, KEY_DOWN=258, KEY_LEFT=260, KEY_RIGHT=261, KEY_ENTER=343,
        error=FakeCursesError,
        curs_set=lambda n: None,
        wrapper=lambda fn: fn(screen),
    )


def keys(*names):
    codes = {"up": 259, "down": 258, "left": 260, "right": 261, "enter": 10, "idle": -1}
    return [codes[n] if n in codes else ord(n) for n in names]


def context(stdin_tty=True, stdout_tty=True):
    out, err = Stream(tty=stdout_tty), Stream()
    ctx = _Context(Stream(tty=stdin_tty), out, err, dict(os.environ), lambda: 0.0, None)
    return ctx, out, err


def corner_board():
    # One mine in the top-left corner; revealing C3 opens every other cell.
    return Board.from_layout(["*..", "...", "..."], clock=lambda: 0.0)


# ---------------------------------------------------------------- session


def test_cursor_starts_in_the_centre_and_stays_on_the_board():
    s = Session(corner_board())
    assert s.cursor == (1, 1)
    for _ in range(5):
        s.handle("left")
        s.handle("up")
    assert s.cursor == (0, 0)
    for _ in range(5):
        s.handle("right")
        s.handle("down")
    assert s.cursor == (2, 2)


def test_space_reveals_and_on_a_number_chords():
    board = Board.from_layout(["*..", "...", "..*"], clock=lambda: 0.0)
    s = Session(board)
    s.handle(" ")  # B2 shows 2
    assert board.revealed == {(1, 1)}
    s.handle("up"), s.handle("left"), s.handle("f")
    s.handle("down"), s.handle("down"), s.handle("right"), s.handle("right"), s.handle("f")
    s.handle("up"), s.handle("left"), s.handle("enter")  # chord on B2
    assert board.state == WON
    assert s.done and s.outcome is None


def test_rejected_move_is_shown_and_cleared_by_the_next_key():
    s = Session(corner_board())
    s.handle("f")
    s.handle(" ")
    assert "flagged" in s.message
    assert not s.board.revealed
    s.handle("down")
    assert s.message == ""


def test_undo_moves_the_cursor_back_to_the_undone_cell():
    s = Session(corner_board())
    s.handle(" ")
    s.handle("right")
    s.handle("f")
    s.handle("left")
    s.handle("u")
    assert s.message == "Undid flag C2."
    assert s.cursor == (2, 1)
    assert s.board.undos == 1


def test_hint_moves_the_cursor_and_is_counted_once_per_position():
    board = Board.from_layout(["*..", "...", "..*"], clock=lambda: 0.0)
    s = Session(board)
    s.handle("h")
    assert "first reveal" in s.message and board.hints == 0
    s.handle("up")
    s.handle("right")
    s.handle(" ")  # C1 shows 0 and opens B1, B2, C2
    s.handle("h")
    s.handle("h")
    assert board.hints == 1
    assert s.message.startswith("Hint (")
    assert "not ranked" in s.message
    assert s.cursor not in board.revealed


def test_save_quit_and_help_keys():
    s = Session(corner_board())
    s.handle("?")
    assert s.message == KEYS_HELP
    s.handle("s")
    assert s.outcome == SAVE and s.done
    s = Session(corner_board())
    s.handle("q")
    assert s.outcome == QUIT
    s.handle(" ")  # ignored once the session is over
    assert not s.board.revealed


def test_daily_session_starts_on_the_opened_centre():
    board = Board.daily_challenge(DIFFICULTIES["beginner"], date(2026, 11, 9), lambda: 0.0)
    s = Session(board)
    assert s.cursor == (4, 4)
    assert "E5 was opened for you" in s.message


def test_screen_shows_cursor_brackets_status_and_keys():
    s = Session(corner_board())
    lines = s.screen_lines(ASCII_GLYPHS)
    assert lines[0].startswith("minesweep  custom 3x3, 1 mines")
    assert "  A B C" in lines
    assert "2 .[.]." in lines
    assert "Cursor: B2" in lines[-3]
    assert lines[-1] == KEYS_HELP


def test_key_name():
    curses = fake_curses(None)
    assert key_name(259, curses) == "up"
    assert key_name(13, curses) == "enter"
    assert key_name(27, curses) == "escape"
    assert key_name(ord("F"), curses) == "f"
    assert key_name(ord(" "), curses) == " "
    assert key_name(400, curses) is None


# ---------------------------------------------------------------- run_tui


def test_run_tui_plays_to_a_win_and_prints_the_result(monkeypatch):
    screen = FakeScreen(keys("idle", "down", "right", " "))
    monkeypatch.setitem(sys.modules, "curses", fake_curses(screen))
    ctx, out, err = context()
    assert run_tui(corner_board(), ctx, from_save=False) == 0
    assert any("Cursor: C3" in line for line in screen.frames[-1])
    text = out.getvalue()
    assert "You win!" in text
    assert "Custom boards are not ranked." in text
    assert err.getvalue() == ""


def test_run_tui_loss_reports_the_mine(monkeypatch):
    screen = FakeScreen(keys("down", "right", "f", "up", "left", "up", "left", " "))
    board = Board.from_layout(["*..", "...", "..*"], clock=lambda: 0.0)
    monkeypatch.setitem(sys.modules, "curses", fake_curses(screen))
    ctx, out, _ = context()
    assert run_tui(board, ctx, from_save=False) == 0
    assert board.state == LOST
    assert "BOOM! You hit a mine at A1." in out.getvalue()


def test_small_terminal_asks_for_more_room(monkeypatch):
    screen = FakeScreen(keys("q"), size=(5, 60))
    monkeypatch.setitem(sys.modules, "curses", fake_curses(screen))
    ctx, out, _ = context()
    assert run_tui(corner_board(), ctx, from_save=False) == 0
    assert screen.frames[0][0].startswith("Make the terminal bigger")
    assert "Quit without saving." in out.getvalue()


def test_play_tui_save_then_resume(monkeypatch):
    screen = FakeScreen(keys(" ", "s"))
    monkeypatch.setitem(sys.modules, "curses", fake_curses(screen))
    out = Stream()
    code = main(
        ["play", "--tui", "--seed", "7"],
        stdin=Stream(), stdout=out, stderr=Stream(), environ=dict(os.environ),
        clock=lambda: 0.0,
    )
    assert code == 0
    assert "Game saved to" in out.getvalue()
    saved = storage.load_game(lambda: 0.0, dict(os.environ))
    assert saved.revealed and (4, 4) in saved.revealed

    screen = FakeScreen(keys("q"))
    monkeypatch.setitem(sys.modules, "curses", fake_curses(screen))
    out = Stream()
    code = main(
        ["resume", "--tui"],
        stdin=Stream(), stdout=out, stderr=Stream(), environ=dict(os.environ),
        clock=lambda: 0.0,
    )
    assert code == 0
    assert any("Cursor: E5" in line for line in screen.frames[0])
    assert "Your earlier save is still there." in out.getvalue()


@pytest.mark.parametrize("stdin_tty,stdout_tty", [(False, True), (True, False)])
def test_tui_needs_a_terminal(monkeypatch, stdin_tty, stdout_tty):
    monkeypatch.setitem(sys.modules, "curses", fake_curses(FakeScreen([])))
    ctx, out, err = context(stdin_tty, stdout_tty)
    assert run_tui(corner_board(), ctx, from_save=False) == 2
    assert "needs an interactive terminal" in err.getvalue()
    assert out.getvalue() == ""


def test_tui_without_curses_explains_how_to_get_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "curses", None)  # makes "import curses" fail
    err = Stream()
    code = main(
        ["daily", "--tui"],
        stdin=Stream(), stdout=Stream(), stderr=err, environ=dict(os.environ),
        clock=lambda: 0.0,
    )
    assert code == 2
    assert 'pip install "minesweep-cli[tui]"' in err.getvalue()


# ------------------------------------------------------------------ mouse


def test_cell_at_matches_the_drawn_layout():
    board = Board.from_layout(["*" + "." * 11] + ["." * 12] * 11, clock=lambda: 0.0)
    s = Session(board)
    lines = s.screen_lines(ASCII_GLYPHS)
    # Row 3 is board row 1; "10" is a two-wide row label, columns are single letters.
    assert lines[2].lstrip().startswith("A")
    for x in range(12):
        col = lines[2].index(chr(ord("A") + x))
        assert s.cell_at(col, 3 + 4) == (x, 4)
    assert s.cell_at(0, 3) is None  # the row number
    assert s.cell_at(4, 3) is None  # the gap between columns A and B
    assert s.cell_at(lines[2].index("A"), 2) is None  # header row
    assert s.cell_at(lines[2].index("A"), 3 + 12) is None  # below the board
    assert s.cell_at(200, 3) is None


def test_left_click_reveals_and_chords_right_click_flags():
    board = Board.from_layout(["*..", "...", "..*"], clock=lambda: 0.0)
    s = Session(board)
    lines = s.screen_lines(ASCII_GLYPHS)
    col = lambda x: lines[2].index(chr(ord("A") + x))  # noqa: E731
    s.click(col(1), 4, "left")  # B2
    assert board.revealed == {(1, 1)} and s.cursor == (1, 1)
    s.click(col(0), 3, "right")  # A1
    s.click(col(2), 5, "right")  # C3
    assert board.flagged == {(0, 0), (2, 2)}
    s.click(col(1), 4, "left")  # chord on B2
    assert board.state == WON


def test_click_outside_the_board_or_after_the_game_does_nothing():
    board = corner_board()
    s = Session(board)
    s.click(0, 0)
    assert not board.revealed and s.cursor == (1, 1)
    s.handle("q")
    s.click(2, 3)
    assert not board.revealed


def test_mouse_events_drive_the_loop():
    screen = FakeScreen(keys("idle"))
    cur = fake_curses(screen)
    cur.KEY_MOUSE, cur.BUTTON1_CLICKED, cur.BUTTON3_CLICKED = 409, 4, 4096
    cur.BUTTON1_PRESSED = cur.BUTTON3_PRESSED = 0
    events = [(0, 4, 5, 0, 4), (0, 4, 5, 0, 4096), (0, 4, 5, 0, 0)]
    cur.getmouse = lambda: events.pop(0)
    masks = []
    cur.mousemask = masks.append
    from minesweep.tui import _loop, mouse_button

    assert mouse_button(4, cur) == "left" and mouse_button(4096, cur) == "right"
    assert mouse_button(0, cur) is None
    board = Board.from_layout(["*..", "..*", "..."], clock=lambda: 0.0)
    s = Session(board)
    screen.keys = [409, 409, 409, ord("q")]
    _loop(screen, s, ASCII_GLYPHS, cur)
    assert masks == [4 | 4096]
    assert board.revealed == {(1, 2)}  # left click on B3 (col 4, row 5)
    assert board.flagged == set()  # the right click on a revealed cell is refused
    assert s.outcome == QUIT
