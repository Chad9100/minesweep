"""`minesweep stats` and the --reset options of `scores` and `stats`."""

import io
import os

from minesweep import storage
from minesweep.cli import main


def run(args, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, stdin=io.StringIO(stdin), stdout=out, stderr=err, environ=dict(os.environ))
    return code, out.getvalue(), err.getvalue()


def seed_records():
    storage.record_score("beginner", 12.5, seed=1)
    storage.record_daily(
        "beginner", "2026-11-09", won=True, seconds=20.0, assisted=False, cleared=71, safe=71
    )
    for won in (True, False, True, True):
        storage.record_game("beginner", won=won, seconds=10.0)
    storage.record_game("expert", won=False, seconds=3.0)


# ---------------------------------------------------------------- stats view


def test_stats_with_no_games():
    code, out, err = run(["stats"])
    assert code == 0 and err == ""
    for name in ("beginner", "intermediate", "expert"):
        assert f"{name}: no games finished yet" in out
    assert "all:" not in out


def test_stats_shows_each_difficulty_and_a_total():
    seed_records()
    code, out, _ = run(["stats"])
    assert code == 0
    assert "beginner: 4 played, 3 won (75%), win streak 2 (best 2), average win 10.0s" in out
    assert "intermediate: no games finished yet" in out
    assert "expert: 1 played, 0 won (0%), win streak 0 (best 0)" in out
    assert "all: 5 played, 3 won (60%)" in out


def test_stats_reports_a_damaged_file(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "stats.json").write_text("[1, 2]", encoding="utf-8")
    code, _, err = run(["stats"])
    assert code == 1
    assert "not a minesweep statistics file" in err


# --------------------------------------------------------------------- reset


def test_scores_reset_with_yes_deletes_only_best_times(isolated_home):
    seed_records()
    code, out, _ = run(["scores", "--reset", "--yes"])
    assert code == 0
    assert "Deleted your best times." in out
    assert not (isolated_home / "scores.json").exists()
    assert (isolated_home / "daily.json").exists()
    assert (isolated_home / "stats.json").exists()
    assert storage.load_scores()["beginner"] == []


def test_scores_daily_reset_deletes_only_daily_results(isolated_home):
    seed_records()
    code, out, _ = run(["scores", "--daily", "--reset", "-y"])
    assert code == 0
    assert "Deleted your daily challenge results." in out
    assert not (isolated_home / "daily.json").exists()
    assert (isolated_home / "scores.json").exists()


def test_stats_reset_deletes_only_statistics(isolated_home):
    seed_records()
    code, out, _ = run(["stats", "--reset", "--yes"])
    assert code == 0
    assert "Deleted your statistics." in out
    assert not (isolated_home / "stats.json").exists()
    assert (isolated_home / "scores.json").exists()
    _, out, _ = run(["stats"])
    assert "beginner: no games finished yet" in out


def test_reset_asks_and_accepts_yes(isolated_home):
    seed_records()
    code, out, _ = run(["scores", "--reset"], stdin="y\n")
    assert code == 0
    assert "Delete your best times? This cannot be undone. [y/N] " in out
    assert not (isolated_home / "scores.json").exists()


def test_reset_answer_may_carry_a_byte_order_mark(isolated_home):
    seed_records()
    code, _, _ = run(["stats", "--reset"], stdin="﻿Yes\n")
    assert code == 0
    assert not (isolated_home / "stats.json").exists()


def test_reset_keeps_records_unless_confirmed(isolated_home):
    seed_records()
    for answer in ("n\n", "\n", "whatever\n", ""):
        code, out, _ = run(["scores", "--reset"], stdin=answer)
        assert code == 1
        assert out.endswith(f"[y/N] {answer.strip()}\nNothing deleted.\n")
        assert (isolated_home / "scores.json").exists()


def test_reset_at_end_of_input_finishes_the_prompt_line():
    seed_records()
    _, out, _ = run(["scores", "--reset"], stdin="")
    assert out.endswith("[y/N] \nNothing deleted.\n")


def test_reset_when_nothing_was_saved():
    code, out, _ = run(["scores", "--reset", "--yes"])
    assert code == 0
    assert "Nothing to delete: your best times were never saved." in out


def test_storage_reset_helpers_report_whether_a_file_was_removed():
    assert storage.reset_stats() is False
    storage.record_game("beginner", won=True, seconds=5.0)
    assert storage.reset_stats() is True
    assert storage.load_stats()["beginner"] == storage.empty_stats()
