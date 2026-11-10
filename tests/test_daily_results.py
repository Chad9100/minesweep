"""Daily leaderboard (scores --daily) and the shareable one-line result."""

import io
import json
import os
from datetime import date, datetime, timezone

from minesweep import storage
from minesweep.board import DIFFICULTIES, Board, cell_label
from minesweep.cli import main, share_line

BEGINNER = DIFFICULTIES["beginner"]
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class Clock:
    """Moves forward by ``step`` seconds every time it is read."""

    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


def run(args, script="", clock=None):
    clock = clock or Clock()
    out, err = io.StringIO(), io.StringIO()
    code = main(
        args, stdin=io.StringIO(script), stdout=out, stderr=err,
        environ=dict(os.environ), now=lambda: NOW, clock=clock,
    )
    return code, out.getvalue(), err.getvalue()


def daily_board(day):
    return Board.daily_challenge(BEGINNER, date.fromisoformat(day))


def win_script(day, extra=()):
    board = daily_board(day)
    moves = [
        f"r {cell_label((x, y))}"
        for y in range(board.height)
        for x in range(board.width)
        if (x, y) not in board.mines and (x, y) not in board.revealed
    ]
    return "\n".join(list(extra) + moves) + "\n"


def lose_script(day):
    board = daily_board(day)
    mine = sorted(board.mines)[0]
    return f"r {cell_label(mine)}\n"


# ---------------------------------------------------------------- share line


def test_share_line_for_a_win_a_loss_and_an_assisted_win():
    won = {"result": "won", "seconds": 23.44, "assisted": False, "cleared": 71, "safe": 71}
    assert share_line("beginner", "2026-11-09", won) == (
        "minesweep daily 2026-11-09 beginner: cleared in 23.4s"
    )
    assert share_line("beginner", "2026-11-09", dict(won, assisted=True)).endswith(
        "cleared in 23.4s (assisted)"
    )
    lost = {"result": "lost", "seconds": 5.0, "assisted": False, "cleared": 30, "safe": 71}
    assert share_line("expert", "2026-11-09", lost) == (
        "minesweep daily 2026-11-09 expert: hit a mine after 5.0s, 30/71 safe cells open (42%)"
    )


# ------------------------------------------------------------- recording


def test_a_daily_win_is_recorded_ranked_and_shared(isolated_home):
    code, out, _ = run(["daily", "--date", "2026-11-09"], win_script("2026-11-09"), Clock(0.5))
    assert code == 0 and "You win!" in out
    assert "Daily best #1 for beginner!" in out
    share = [line for line in out.splitlines() if line.startswith("Share: ")]
    assert len(share) == 1
    assert share[0].startswith("Share: minesweep daily 2026-11-09 beginner: cleared in ")
    data = json.loads((isolated_home / "daily.json").read_text(encoding="utf-8"))
    entry = data["beginner"]["2026-11-09"]
    assert entry["result"] == "won" and entry["assisted"] is False
    assert entry["cleared"] == entry["safe"] == 71 and entry["seconds"] > 0
    # The regular best-times table stays untouched.
    assert storage.load_scores()["beginner"] == []


def test_a_daily_loss_is_recorded_with_progress(isolated_home):
    board = daily_board("2026-11-09")
    opened = len(board.revealed)
    code, out, _ = run(["daily", "--date", "2026-11-09"], lose_script("2026-11-09"))
    assert code == 0 and "BOOM!" in out
    pct = int(100 * opened / 71)
    assert (
        f"Share: minesweep daily 2026-11-09 beginner: hit a mine after 0.0s, "
        f"{opened}/71 safe cells open ({pct}%)"
    ) in out
    entry = storage.load_daily()["beginner"]["2026-11-09"]
    assert entry["result"] == "lost" and entry["cleared"] == opened


def test_only_the_first_attempt_counts():
    run(["daily", "--date", "2026-11-09"], lose_script("2026-11-09"))
    code, out, _ = run(["daily", "--date", "2026-11-09"], win_script("2026-11-09"))
    assert code == 0 and "You win!" in out
    assert "You already finished the 2026-11-09 beginner daily; only your first result counts." in out
    assert "hit a mine after" in out  # the share line shows the first (lost) result
    assert "Daily best" not in out
    assert storage.load_daily()["beginner"]["2026-11-09"]["result"] == "lost"


def test_assisted_win_is_recorded_but_not_ranked():
    board = daily_board("2026-11-09")
    hidden = next(
        (x, y) for y in range(9) for x in range(9)
        if (x, y) not in board.revealed and (x, y) not in board.mines
    )
    extra = [f"r {cell_label(hidden)}", "u"]
    code, out, _ = run(["daily", "--date", "2026-11-09"], win_script("2026-11-09", extra))
    assert code == 0 and "You win!" in out
    assert "recorded but not ranked" in out
    assert "(assisted)" in out
    days = storage.load_daily()["beginner"]
    assert days["2026-11-09"]["assisted"] is True
    assert storage.daily_leaderboard(days) == []


def test_quitting_or_saving_records_nothing(isolated_home):
    run(["daily", "--date", "2026-11-09"], "q\n")
    run(["daily", "--date", "2026-11-08"], "s\n")
    assert not (isolated_home / "daily.json").exists()


def test_difficulties_are_kept_apart():
    run(["daily", "--date", "2026-11-09"], lose_script("2026-11-09"))
    days = storage.load_daily()
    assert "2026-11-09" in days["beginner"] and days["intermediate"] == {}


# ------------------------------------------------------------- leaderboard


def test_leaderboard_orders_by_time_then_date():
    days = {
        "2026-11-03": {"result": "won", "seconds": 30.0, "assisted": False},
        "2026-11-01": {"result": "won", "seconds": 30.0, "assisted": False},
        "2026-11-02": {"result": "won", "seconds": 12.5, "assisted": False},
        "2026-11-04": {"result": "lost", "seconds": 3.0, "assisted": False},
        "2026-11-05": {"result": "won", "seconds": 1.0, "assisted": True},
    }
    assert storage.daily_leaderboard(days) == [
        ("2026-11-02", 12.5), ("2026-11-01", 30.0), ("2026-11-03", 30.0),
    ]
    assert len(storage.daily_leaderboard(days, limit=1)) == 1


def test_scores_daily_view():
    run(["daily", "--date", "2026-11-08"], lose_script("2026-11-08"))
    run(["daily", "--date", "2026-11-09"], win_script("2026-11-09"), Clock(0.25))
    code, out, _ = run(["scores", "--daily"])
    assert code == 0
    assert out.startswith("Daily challenge results (only your first attempt each day counts)")
    beginner = out.split("beginner (9x9, 10 mines)\n")[1].split("\n\n")[0]
    lines = beginner.splitlines()
    assert lines[0] == "  played 2, won 1"
    assert lines[1].startswith("   1. ") and lines[1].endswith("  2026-11-09")
    assert lines[2].startswith("  latest: minesweep daily 2026-11-09 beginner: cleared in ")
    assert "intermediate (16x16, 40 mines)\n  not played yet" in out


def test_scores_daily_with_only_losses():
    run(["daily", "--date", "2026-11-08"], lose_script("2026-11-08"))
    _, out, _ = run(["scores", "--daily"])
    assert "  played 1, won 0\n  no ranked wins yet" in out


def test_empty_daily_view():
    code, out, _ = run(["scores", "--daily"])
    assert code == 0 and out.count("not played yet") == len(DIFFICULTIES)


def test_damaged_daily_file_is_reported(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "daily.json").write_text("[1, 2]", encoding="utf-8")
    code, _, err = run(["scores", "--daily"])
    assert code == 1 and "is not a minesweep daily results file" in err
    (isolated_home / "daily.json").write_text("{not json", encoding="utf-8")
    code, _, err = run(["scores", "--daily"])
    assert code == 1 and "cannot read" in err


def test_malformed_entries_are_skipped(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "daily.json").write_text(json.dumps({
        "beginner": {
            "2026-11-01": {"result": "won", "seconds": 9.0, "assisted": False},
            "2026-11-02": {"result": "maybe", "seconds": 1.0},
            "2026-11-03": "fast",
        }
    }), encoding="utf-8")
    assert list(storage.load_daily()["beginner"]) == ["2026-11-01"]


def test_a_damaged_file_does_not_break_finishing_a_daily(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "daily.json").write_text("[]", encoding="utf-8")
    code, out, err = run(["daily", "--date", "2026-11-09"], lose_script("2026-11-09"))
    assert code == 0 and "BOOM!" in out
    assert "could not record your daily result" in err
