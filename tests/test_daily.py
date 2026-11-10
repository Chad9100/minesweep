"""Daily challenge: a board seeded from the UTC date, the same for everyone."""

import io
import json
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from minesweep import storage
from minesweep.board import (
    DIFFICULTIES,
    PLAYING,
    Board,
    MoveError,
    cell_label,
    daily_seed,
    daily_start,
)
from minesweep.cli import main
from minesweep.solver import analyze

DAY = date(2026, 11, 9)
BEGINNER = DIFFICULTIES["beginner"]


class Clock:
    def __init__(self):
        self.now = 50.0

    def __call__(self):
        return self.now


def run(args, script, now=datetime(2026, 11, 9, 23, 30, tzinfo=timezone.utc), clock=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(
        args, stdin=io.StringIO(script), stdout=out, stderr=err,
        environ=dict(os.environ), now=lambda: now, clock=clock,
    )
    return code, out.getvalue(), err.getvalue()


def winning_moves(board):
    """Reveal every safe hidden cell (the test knows where the mines are)."""
    return [
        f"r {cell_label((x, y))}"
        for y in range(board.height)
        for x in range(board.width)
        if (x, y) not in board.mines and (x, y) not in board.revealed
    ]


# ------------------------------------------------------------------ board level


def test_seed_is_the_date_and_start_is_the_centre():
    assert daily_seed(DAY) == 20261109
    assert daily_seed(date(2027, 1, 2)) == 20270102
    assert daily_start(BEGINNER) == (4, 4)  # E5
    assert daily_start(DIFFICULTIES["expert"]) == (15, 8)  # P9


def test_same_day_gives_the_same_board_and_other_days_differ():
    a = Board.daily_challenge(BEGINNER, DAY)
    b = Board.daily_challenge(BEGINNER, DAY)
    c = Board.daily_challenge(BEGINNER, DAY + timedelta(days=1))
    assert a.mines == b.mines and a.revealed == b.revealed
    assert a.mines != c.mines
    assert a.daily == "2026-11-09" and a.seed == 20261109


def test_daily_board_matches_play_with_its_seed_from_the_centre():
    daily = Board.daily_challenge(BEGINNER, DAY)
    replay = Board(BEGINNER, daily_seed(DAY))
    replay.reveal(daily_start(BEGINNER))
    assert replay.mines == daily.mines and replay.revealed == daily.revealed


@pytest.mark.parametrize("name", list(DIFFICULTIES))
def test_opening_is_revealed_safe_and_gives_something_to_work_with(name):
    config = DIFFICULTIES[name]
    board = Board.daily_challenge(config, DAY)
    start = daily_start(config)
    assert start in board.revealed and start not in board.mines
    assert board.adjacent_mines(start) == 0  # the start and its neighbours are kept clear
    assert len(board.revealed) > 1 and board.state == PLAYING


def test_opening_cannot_be_undone_and_clock_waits_for_first_reveal():
    clock = Clock()
    board = Board.daily_challenge(BEGINNER, DAY, clock)
    opened = set(board.revealed)
    assert board.history == [] and board.last_move is None
    clock.now += 30
    assert board.elapsed == 0
    with pytest.raises(MoveError, match="nothing to undo"):
        board.undo()
    safe = next(iter(analyze(board).safe))
    board.reveal(safe)
    clock.now += 4
    assert board.elapsed == 4
    board.undo()
    # Back to the opening, with the same mines (no new first click).
    assert board.revealed == opened and board.mines_placed


def test_daily_save_round_trip_keeps_the_date(clock):
    board = Board.daily_challenge(BEGINNER, DAY, clock)
    data = json.loads(json.dumps(board.to_dict()))
    assert data["daily"] == "2026-11-09"
    loaded = Board.from_dict(data, clock)
    assert loaded.daily == "2026-11-09"
    assert loaded.revealed == board.revealed and loaded.mines == board.mines
    # Saved before the first move: the clock still waits for it.
    clock.advance(10)
    assert loaded.elapsed == 0


def test_older_saves_without_daily_still_load(clock):
    board = Board(BEGINNER, 3, clock)
    board.reveal((0, 0))
    data = board.to_dict()
    del data["daily"]
    assert Board.from_dict(data, clock).daily is None


@pytest.mark.parametrize("bad", [5, "yesterday", "2026-02-30"])
def test_damaged_daily_field_is_refused(bad, clock):
    data = Board.daily_challenge(BEGINNER, DAY, clock).to_dict()
    data["daily"] = bad
    with pytest.raises(ValueError, match="daily must be a date"):
        Board.from_dict(data, clock)


# -------------------------------------------------------------------- CLI level


def test_daily_uses_the_utc_date():
    # 23:30 at UTC-5 on Nov 8 is already Nov 9 in UTC.
    local = datetime(2026, 11, 8, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    code, out, _ = run(["daily"], "q\n", now=local)
    assert code == 0
    first = out.splitlines()[0]
    assert first.startswith("Daily challenge 2026-11-09: beginner 9x9, 10 mines, seed 20261109.")
    assert "E5 was opened for you" in out


def test_daily_board_is_shown_already_opened():
    code, out, _ = run(["daily", "-d", "intermediate", "--date", "2026-01-15"], "q\n")
    assert code == 0
    assert "Daily challenge 2026-01-15: intermediate 16x16, 40 mines, seed 20260115." in out
    assert "I9 was opened for you" in out
    board = Board.daily_challenge(DIFFICULTIES["intermediate"], date(2026, 1, 15))
    assert "Mines left: 40" in out and len(board.revealed) > 1


def test_future_date_is_refused():
    code, out, err = run(["daily", "--date", "2026-11-10"], "")
    assert code == 2 and out == ""
    assert "the daily challenge for 2026-11-10 is not out yet (today is 2026-11-09 UTC)" in err


def test_malformed_date_is_a_usage_error(capsys):
    code, _, _ = run(["daily", "--date", "11/09/2026"], "")
    assert code == 2
    assert "not a date like 2026-11-09" in capsys.readouterr().err


def test_undo_at_the_start_of_a_daily_says_nothing_to_undo():
    _, out, _ = run(["daily", "--date", "2026-11-09"], "u\nq\n")
    assert "nothing to undo" in out


def test_winning_a_daily_is_not_put_in_the_regular_table(isolated_home):
    board = Board.daily_challenge(BEGINNER, DAY)
    script = "\n".join(winning_moves(board)) + "\n"
    code, out, _ = run(["daily", "--date", "2026-11-09"], script)
    assert code == 0
    assert "You win!" in out
    assert "Daily challenges are not entered in the regular best-times table." in out
    assert storage.load_scores()["beginner"] == []


def test_save_and_resume_a_daily(isolated_home):
    code, out, _ = run(["daily", "--date", "2026-11-09"], "s\n")
    assert code == 0 and "Game saved" in out
    saved = json.loads((isolated_home / "save.json").read_text(encoding="utf-8"))
    assert saved["daily"] == "2026-11-09" and saved["seed"] == 20261109
    code, out, _ = run(["resume"], "q\n")
    assert code == 0
    assert out.startswith("Resuming daily challenge 2026-11-09: beginner 9x9, 10 mines, seed 20261109.")
    assert "was opened for you" not in out  # only said when the challenge starts

    board = Board.daily_challenge(BEGINNER, DAY)
    script = "\n".join(winning_moves(board)) + "\n"
    code, out, _ = run(["resume"], script)
    assert "You win!" in out and "regular best-times table" in out
    assert not (isolated_home / "save.json").exists()


def test_flags_alone_do_not_start_the_clock_after_resume(clock):
    board = Board.daily_challenge(BEGINNER, DAY, clock)
    hidden = next(
        (x, y) for y in range(9) for x in range(9) if (x, y) not in board.revealed
    )
    board.toggle_flag(hidden)
    loaded = Board.from_dict(board.to_dict(), clock)
    clock.advance(10)
    assert loaded.elapsed == 0
    safe = next(iter(analyze(loaded).safe))
    loaded.reveal(safe)
    clock.advance(3)
    assert loaded.elapsed == 3
