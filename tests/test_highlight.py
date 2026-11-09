"""Last-move highlight (board, renderer, CLI) and the --no-echo option."""

import io
import json
import os

from minesweep import storage
from minesweep.board import Board, make_config
from minesweep.cli import main
from minesweep.render import ASCII_GLYPHS, NUMBER_COLORS, RESET, render_board


class Stream(io.StringIO):
    def __init__(self, text="", tty=False):
        super().__init__(text)
        self._tty = tty

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return "ascii"  # plain glyphs (. and F) keep the assertions readable


def run(args, script, stdin_tty=False):
    out, err = Stream(), Stream()
    code = main(
        args,
        stdin=Stream(script, tty=stdin_tty),
        stdout=out,
        stderr=err,
        environ=dict(os.environ),
        clock=lambda: 0.0,
    )
    return code, out.getvalue(), err.getvalue()


def layout():
    return Board.from_layout(["*..", "...", "..*"])


# ------------------------------------------------------------------ board


def test_last_move_follows_history_and_undo():
    b = layout()
    assert b.last_move is None
    b.reveal((2, 0))
    b.toggle_flag((0, 0))
    assert b.last_move == ("flag", (0, 0))
    b.undo()
    assert b.last_move == ("reveal", (2, 0))
    b.undo()
    assert b.last_move is None


def test_rejected_move_does_not_change_last_move():
    b = layout()
    b.reveal((2, 0))
    try:
        b.reveal((2, 0))
    except ValueError:
        pass
    assert b.last_move == ("reveal", (2, 0))


# --------------------------------------------------------------- renderer


def test_highlight_brackets_a_middle_cell_and_keeps_alignment():
    b = layout()
    b.reveal((1, 1))
    plain = render_board(b).splitlines()
    marked = render_board(b, highlight=(1, 1)).splitlines()
    assert marked[2] == "2 .[2]."
    assert len(marked[2]) == len(plain[2])
    assert marked[:2] + marked[3:] == plain[:2] + plain[3:]


def test_highlight_first_and_last_column():
    b = layout()
    assert render_board(b, highlight=(2, 0)).splitlines()[1] == "1 . .[.]"
    assert render_board(b, highlight=(0, 2)).splitlines()[3] == "3[.]. ."


def test_highlight_on_an_empty_cell_is_still_visible():
    b = Board.from_layout(["....", "....", "...*"])
    b.reveal((0, 0))
    assert render_board(b, highlight=(0, 0)).splitlines()[1] == "1[ ]"


def test_highlight_on_wide_columns():
    b = Board.from_layout(["." * 28, "." * 27 + "*"])
    lines = render_board(b, glyphs=ASCII_GLYPHS, highlight=(27, 0)).splitlines()
    assert lines[1].endswith(" .[ .]")
    assert len(lines[1]) == len(lines[0]) + 1  # closing bracket after the last column


def test_highlight_wraps_outside_the_colour_codes():
    b = layout()
    b.reveal((1, 1))
    line = render_board(b, color=True, highlight=(1, 1)).splitlines()[2]
    assert f"[{NUMBER_COLORS[2]}2{RESET}]" in line


# --------------------------------------------------------------------- CLI


def test_cli_highlights_the_last_move_and_follows_undo():
    _, out, _ = run(["play", "--seed", "1"], "r E5\nf A9\nu\nq\n")
    assert "9[F]. . . . . . 1" in out  # after f A9
    # after undo the reveal at E5 is the last move again
    after_undo = out.split("Undid flag A9.")[1]
    assert "\n5        [ ]    1 1\n" in after_undo
    assert "[F]" not in after_undo


def test_resume_keeps_the_highlight_from_the_save():
    run(["play", "--seed", "1"], "r E5\nf A9\ns\n")
    assert json.loads(storage.save_path().read_text())["history"][-1] == ["flag", 0, 8]
    _, out, _ = run(["resume"], "q\n")
    assert "9[F]" in out


def test_v1_save_resumes_without_a_highlight():
    b = Board(make_config(9, 9, 10), 1)
    b.reveal((4, 4))
    data = b.to_dict()
    data["version"] = 1
    for key in ("history", "undos", "base_revealed", "base_flagged"):
        del data[key]
    path = storage.save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, out, err = run(["resume"], "q\n")
    assert code == 0, err
    assert "[" not in out


def test_piped_input_is_echoed_by_default():
    _, out, _ = run(["play", "--seed", "1"], "r E5\nq\n")
    assert "> r E5\n" in out


def test_no_echo_hides_piped_commands():
    code, out, _ = run(["play", "--seed", "1", "--no-echo"], "r E5\nZ1\nq\n")
    assert code == 0
    assert "r E5" not in out
    assert "> column Z is off the board (A-I)\n" in out
    assert "Quit without saving." in out


def test_no_echo_works_for_resume():
    run(["play", "--seed", "1"], "r E5\ns\n")
    _, out, _ = run(["resume", "--no-echo"], "q\n")
    assert "> Quit without saving." in out


def test_terminal_input_is_never_echoed():
    _, out, _ = run(["play", "--seed", "1"], "r E5\nq\n", stdin_tty=True)
    assert "r E5" not in out
