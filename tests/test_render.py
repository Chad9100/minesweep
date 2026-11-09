import io

from minesweep.board import Board
from minesweep.render import (
    ASCII_GLYPHS,
    NUMBER_COLORS,
    RESET,
    UNICODE_GLYPHS,
    pick_glyphs,
    render_board,
    render_status,
    use_color,
)


class FakeStream(io.StringIO):
    def __init__(self, tty=False, encoding="utf-8"):
        super().__init__()
        self._tty = tty
        self._enc = encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._enc


def sample():
    b = Board.from_layout(["*..", "...", "..*"])
    b.reveal((2, 0))
    b.toggle_flag((0, 0))
    return b


def test_plain_render_has_labels_and_cells():
    text = render_board(sample(), glyphs=ASCII_GLYPHS)
    assert text.splitlines() == [
        "  A B C",
        "1 F 1",
        "2 . 2 1",
        "3 . . .",
    ]
    assert "\x1b" not in text


def test_color_render_wraps_numbers_in_ansi():
    text = render_board(sample(), color=True, glyphs=ASCII_GLYPHS)
    assert f"{NUMBER_COLORS[2]}2{RESET}" in text
    assert f"{NUMBER_COLORS[1]}1{RESET}" in text


def test_unicode_glyphs_used_for_hidden_and_flag():
    text = render_board(sample(), glyphs=UNICODE_GLYPHS)
    assert "⚑" in text and "·" in text


def test_loss_shows_all_mines_exploded_and_wrong_flags():
    b = Board.from_layout(["*..", "...", "..*"])
    b.toggle_flag((1, 2))  # wrong flag
    b.reveal((0, 0))
    lines = render_board(b, glyphs=ASCII_GLYPHS).splitlines()
    assert lines[1].startswith("1 X")
    assert lines[3] == "3 . x *"


def test_hidden_mines_not_shown_while_playing():
    b = Board.from_layout(["*..", "...", "..*"])
    b.reveal((1, 1))
    assert "*" not in render_board(b, glyphs=ASCII_GLYPHS)


def test_wide_board_columns_align():
    b = Board.from_layout(["." * 28, "." * 27 + "*"])
    lines = render_board(b, glyphs=ASCII_GLYPHS).splitlines()
    assert lines[0].endswith(" Z AA AB")
    assert len(lines[1]) == len(lines[0])


def test_status_line(clock):
    b = Board.from_layout(["*..", "...", "..*"], clock=clock)
    b.reveal((1, 1))
    clock.advance(7.9)
    b.toggle_flag((0, 0))
    assert render_status(b) == "Mines left: 1   Time: 7s"


def test_use_color_modes():
    tty, pipe = FakeStream(tty=True), FakeStream(tty=False)
    assert use_color("auto", tty, {}) is True
    assert use_color("auto", pipe, {}) is False
    assert use_color("auto", tty, {"NO_COLOR": "1"}) is False
    assert use_color("always", pipe, {"NO_COLOR": "1"}) is True
    assert use_color("never", tty, {}) is False


def test_ascii_fallback_when_stream_cannot_encode():
    assert pick_glyphs(FakeStream(encoding="utf-8")) is UNICODE_GLYPHS
    assert pick_glyphs(FakeStream(encoding="ascii")) is ASCII_GLYPHS
    assert pick_glyphs(FakeStream(encoding="cp1252")) is ASCII_GLYPHS
    assert pick_glyphs(FakeStream(encoding=None)) is ASCII_GLYPHS
