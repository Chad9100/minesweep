"""Scripted games driven through main() with fake stdin/stdout."""

import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from minesweep import storage
from minesweep.board import Board, cell_label, make_config
from minesweep.cli import main


class Stream(io.StringIO):
    def __init__(self, text="", tty=False, encoding="utf-8"):
        super().__init__(text)
        self._tty = tty
        self._enc = encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._enc


def play(args, script, clock=None, tty=False):
    out, err = Stream(tty=tty), Stream()
    code = main(
        args,
        stdin=Stream(script),
        stdout=out,
        stderr=err,
        environ=dict(os.environ),
        clock=clock,
        now=lambda: datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc),
    )
    return code, out.getvalue(), err.getvalue()


def solve_moves(width, height, mines, seed, first=(0, 0)):
    """Predict the board the CLI will build and return a winning script."""
    b = Board(make_config(width, height, mines), seed)
    b.reveal(first)
    safe = [
        (x, y) for y in range(height) for x in range(width)
        if (x, y) not in b.mines and (x, y) != first
    ]
    return b, [f"r {cell_label(first)}"] + [f"r {cell_label(c)}" for c in safe]


def test_scripted_win_records_best_time(clock):
    _, moves = solve_moves(9, 9, 10, seed=42)
    # The solver lists every safe cell; already-opened ones just print a notice.
    code, out, err = play(["play", "--seed", "42"], "\n".join(moves) + "\n", clock)
    assert code == 0, err
    assert "You win!" in out
    assert "New best time #1 for beginner!" in out
    scores = storage.load_scores()["beginner"]
    assert len(scores) == 1 and scores[0]["seed"] == 42 and scores[0]["date"] == "2026-03-01 09:30"


def test_win_time_comes_from_injected_clock(clock):
    b, moves = solve_moves(9, 9, 10, seed=3)

    class TickingStdin(Stream):
        def readline(self):
            clock.advance(2)
            return super().readline()

    out = Stream()
    main(
        ["play", "--seed", "3"],
        stdin=TickingStdin("\n".join(moves) + "\n"),
        stdout=out,
        stderr=Stream(),
        environ=dict(os.environ),
        clock=clock,
    )
    text = out.getvalue()
    assert "You win! Cleared in " in text
    seconds = storage.load_scores()["beginner"][0]["seconds"]
    assert seconds > 0 and seconds % 2 == 0


def test_scripted_loss_shows_all_mines(clock):
    b, _ = solve_moves(9, 9, 10, seed=5)
    mine = sorted(b.mines)[0]
    code, out, _ = play(["play", "--seed", "5"], f"r A1\nr {cell_label(mine)}\n", clock)
    assert code == 0
    assert f"BOOM! You hit a mine at {cell_label(mine)}" in out
    final_board = out.split("BOOM")[0].rsplit("> ", 1)[1]
    assert final_board.count("*") == 9 and final_board.count("X") == 1
    assert storage.load_scores()["beginner"] == []


def test_custom_win_is_not_ranked(clock):
    code, out, _ = play(["play", "--width", "3", "--height", "3", "--mines", "8", "--seed", "1"], "r B2\n", clock)
    assert code == 0
    assert "You win!" in out and "Custom boards are not ranked." in out
    assert not storage.scores_path().exists()


def test_bare_coordinate_reveals_and_bad_input_is_explained(clock):
    script = "B2\nf B2\nhello\nr\nr Z99\nr 5A\n\nq\n"
    code, out, _ = play(["play", "--seed", "1"], script, clock)
    assert code == 0
    assert "B2 is already revealed and cannot be flagged" in out
    assert "Unknown command 'hello'" in out
    assert "Usage: r <cell>" in out
    assert "column Z is off the board (A-I)" in out
    assert "'5A' is not a cell" in out
    assert "Quit without saving." in out


def test_help_command(clock):
    _, out, _ = play(["play"], "?\nq\n", clock)
    assert "c B3    chord" in out and "rows are numbers" in out


def test_flag_and_chord_through_cli(clock):
    b, _ = solve_moves(9, 9, 10, seed=8, first=(4, 4))
    # Find a revealed number with exactly its mines flaggable, then chord it.
    number = next(
        c for c in sorted(b.revealed)
        if b.adjacent_mines(c) and any(n not in b.revealed and n not in b.mines for n in b.neighbors(c))
    )
    flags = [f"f {cell_label(n)}" for n in b.neighbors(number) if n in b.mines]
    script = "\n".join(["r E5", *flags, f"c {cell_label(number)}", "q"]) + "\n"
    code, out, _ = play(["play", "--seed", "8"], script, clock)
    assert code == 0
    assert "needs" not in out and "flag(s) around it" not in out
    assert "BOOM" not in out


def test_save_then_resume_round_trip(clock):
    code, out, _ = play(["play", "--seed", "11"], "f A1\nr E5\ns\n", clock)
    assert code == 0 and "Game saved to" in out
    saved = json.loads(storage.save_path().read_text(encoding="utf-8"))
    assert saved["seed"] == 11 and [0, 0] in saved["flagged"]

    code, out, _ = play(["resume"], "q\n", clock)
    assert code == 0
    assert "Resuming: beginner 9x9, 10 mines, seed 11" in out
    assert "Mines left: 9" in out
    assert "earlier save is still there" in out
    assert storage.save_path().exists()


def test_finishing_a_resumed_game_deletes_the_save(clock):
    b, moves = solve_moves(9, 9, 10, seed=12)
    play(["play", "--seed", "12"], "r A1\ns\n", clock)
    code, out, _ = play(["resume"], "\n".join(moves[1:]) + "\n", clock)
    assert code == 0 and "You win!" in out
    assert not storage.save_path().exists()


def test_resume_without_save_fails_cleanly(clock):
    code, out, err = play(["resume"], "", clock)
    assert code == 1
    assert "no saved game" in err


def test_resume_with_corrupt_save(isolated_home, clock):
    isolated_home.mkdir(parents=True)
    (isolated_home / "save.json").write_text("garbage", encoding="utf-8")
    code, _, err = play(["resume"], "", clock)
    assert code == 1 and "cannot read" in err


@pytest.mark.parametrize(
    "args,fragment",
    [
        (["--width", "3", "--height", "3", "--mines", "20"], "too many mines"),
        (["--width", "0"], "width must be at least 1"),
        (["--height", "0", "--width", "5", "--mines", "1"], "height must be at least 1"),
        (["--mines", "0"], "mines must be at least 1"),
        (["--mines", "81"], "at most 80"),
    ],
)
def test_invalid_config_exits_2(args, fragment, clock):
    code, out, err = play(["play", *args], "", clock)
    assert code == 2
    assert fragment in err
    assert out == ""


def test_bad_arguments_exit_2(capsys):
    assert main(["play", "--difficulty", "insane"]) == 2
    assert main(["fly"]) == 2
    assert main([]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_scores_command_lists_best_times(clock):
    storage.record_score("beginner", 41.25, seed=4)
    storage.record_score("beginner", 12.5, seed=9)
    code, out, _ = play(["scores"], "", clock)
    assert code == 0
    lines = out.splitlines()
    i = lines.index("beginner (9x9, 10 mines)")
    assert lines[i + 1].startswith("   1.    12.5s") and "seed 9" in lines[i + 1]
    assert lines[i + 2].startswith("   2.    41.2s") or lines[i + 2].startswith("   2.    41.3s")
    assert "expert (30x16, 99 mines)\n  no wins yet" in out


def test_color_always_vs_never(clock):
    _, colored, _ = play(["play", "--seed", "1", "--color", "always"], "r E5\nq\n", clock)
    _, plain, _ = play(["play", "--seed", "1", "--color", "never"], "r E5\nq\n", clock, tty=True)
    assert "\x1b[" in colored
    assert "\x1b[" not in plain


def test_color_auto_respects_tty_and_no_color(monkeypatch, clock):
    _, piped, _ = play(["play", "--seed", "1"], "r E5\nq\n", clock)
    _, tty, _ = play(["play", "--seed", "1"], "r E5\nq\n", clock, tty=True)
    monkeypatch.setenv("NO_COLOR", "1")
    _, no_color, _ = play(["play", "--seed", "1"], "r E5\nq\n", clock, tty=True)
    assert "\x1b[" not in piped
    assert "\x1b[" in tty
    assert "\x1b[" not in no_color


def test_ascii_fallback_on_narrow_encoding(clock):
    out = Stream(encoding="ascii")
    main(["play", "--seed", "1", "--color", "never"], stdin=Stream("f A1\nq\n"), stdout=out,
         stderr=Stream(), environ=dict(os.environ), clock=clock)
    text = out.getvalue()
    text.encode("ascii")
    assert "1[F]." in text  # the flag is the last move, so it is bracketed


def test_end_of_input_quits_without_saving(clock):
    code, out, _ = play(["play"], "r A1\n", clock)
    assert code == 0 and "End of input" in out
    assert not storage.save_path().exists()


def test_python_dash_m_entry_point(isolated_home):
    env = dict(os.environ, MINESWEEP_HOME=str(isolated_home), PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "minesweep", "play", "--seed", "42", "--width", "4", "--height", "3", "--mines", "1"],
        input="r A1\nq\n", capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "New game: custom 4x3, 1 mines, seed 42" in proc.stdout
