"""Per-difficulty statistics: games played and won, win streaks, average win time."""

import io
import json
import os
from datetime import date, datetime, timezone

from minesweep import storage
from minesweep.board import DIFFICULTIES, Board, cell_label, make_config
from minesweep.cli import main


class StepClock:
    """Moves forward by ``step`` seconds every time it is read."""

    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


def run(args, script, clock=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(
        args, stdin=io.StringIO(script), stdout=out, stderr=err,
        environ=dict(os.environ), clock=clock or StepClock(),
        now=lambda: datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
    )
    return code, out.getvalue(), err.getvalue()


def win_script(seed, width=9, height=9, mines=10):
    b = Board(make_config(width, height, mines), seed)
    b.reveal((0, 0))
    moves = ["r A1"] + [
        f"r {cell_label((x, y))}"
        for y in range(height) for x in range(width)
        if (x, y) not in b.mines and (x, y) not in b.revealed
    ]
    return "\n".join(moves) + "\n"


def lose_script(seed):
    b = Board(make_config(9, 9, 10), seed)
    b.reveal((0, 0))
    return f"r A1\nr {cell_label(sorted(b.mines)[0])}\n"


# ------------------------------------------------------------------ storage


def test_record_game_counts_wins_losses_and_streaks():
    for won in (True, True, False, True):
        entry = storage.record_game("beginner", won=won, seconds=10.0)
    assert entry == {"played": 4, "won": 3, "streak": 1, "best_streak": 2, "win_seconds": 30.0}
    stats = storage.load_stats()
    assert stats["beginner"] == entry
    assert stats["expert"] == storage.empty_stats()


def test_custom_boards_are_not_tracked():
    assert storage.record_game("custom", won=True, seconds=1.0) is None
    assert not storage.stats_path().exists()


def test_damaged_fields_fall_back_to_safe_values():
    path = storage.stats_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "beginner": {"played": 2, "won": 5, "streak": "x", "best_streak": -1, "win_seconds": True},
        "intermediate": [1, 2],
    }), encoding="utf-8")
    stats = storage.load_stats()
    assert stats["beginner"] == {"played": 2, "won": 2, "streak": 0, "best_streak": 0, "win_seconds": 0.0}
    assert stats["intermediate"] == storage.empty_stats()


def test_a_stats_file_that_is_not_an_object_is_an_error():
    path = storage.stats_path()
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    try:
        storage.load_stats()
    except storage.StorageError as exc:
        assert "statistics" in str(exc)
    else:
        raise AssertionError("expected StorageError")


def test_summary_line():
    entry = {"played": 4, "won": 3, "streak": 1, "best_streak": 2, "win_seconds": 30.5}
    assert storage.stats_summary("beginner", entry) == (
        "beginner: 4 played, 3 won (75%), win streak 1 (best 2), average win 10.2s"
    )
    lost = dict(storage.empty_stats(), played=1)
    assert storage.stats_summary("expert", lost) == (
        "expert: 1 played, 0 won (0%), win streak 0 (best 0)"
    )
    assert storage.stats_summary("expert", storage.empty_stats()) == "expert: no games finished yet"


# ---------------------------------------------------------------------- CLI


def test_finished_games_update_and_print_stats():
    code, out, err = run(["play", "--seed", "42"], win_script(42), StepClock(0.5))
    assert code == 0, err
    assert "You win!" in out
    assert "Stats: beginner: 1 played, 1 won (100%), win streak 1 (best 1), average win" in out

    code, out, _ = run(["play", "--seed", "5"], lose_script(5))
    assert "BOOM!" in out
    assert "Stats: beginner: 2 played, 1 won (50%), win streak 0 (best 1)" in out
    assert storage.load_stats()["beginner"]["played"] == 2


def test_unranked_and_daily_games_still_count():
    hinted = win_script(42).replace("r A1\n", "r A1\nh\n", 1)  # a hint: not ranked
    code, out, _ = run(["play", "--seed", "42"], hinted)
    assert "not ranked" in out and "Stats: beginner: 1 played, 1 won" in out

    daily = Board.daily_challenge(DIFFICULTIES["beginner"], date(2026, 11, 9))
    mine = cell_label(sorted(daily.mines)[0])
    code, out, _ = run(["daily", "--date", "2026-11-09"], f"r {mine}\n")
    assert "BOOM!" in out and "Stats: beginner: 2 played, 1 won (50%), win streak 0 (best 1)" in out
    assert storage.load_scores()["beginner"] == []


def test_quitting_or_saving_does_not_count():
    run(["play", "--seed", "42"], "r A1\nq\n")
    run(["play", "--seed", "42"], "r A1\ns\n")
    assert not storage.stats_path().exists()


def test_custom_board_prints_no_stats():
    code, out, _ = run(["play", "--width", "3", "--height", "3", "--mines", "8", "--seed", "1"], "r B2\n")
    assert "You win!" in out and "Stats:" not in out
    assert not storage.stats_path().exists()


def test_unreadable_stats_file_is_reported_but_the_game_still_ends():
    path = storage.stats_path()
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    code, out, err = run(["play", "--seed", "42"], win_script(42))
    assert code == 0 and "You win!" in out
    assert "could not update your statistics" in err
