import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from minesweep import storage
from minesweep.board import Board, make_config


def at(minute):
    return datetime(2026, 1, 1, 12, minute, tzinfo=timezone.utc)


def test_data_dir_precedence():
    assert storage.data_dir({"MINESWEEP_HOME": "/x/y"}, "linux") == Path("/x/y")
    assert storage.data_dir({"MINESWEEP_HOME": "/x/y", "APPDATA": "/a"}, "win32") == Path("/x/y")
    assert storage.data_dir({"APPDATA": "/roaming"}, "win32") == Path("/roaming") / "minesweep"
    assert storage.data_dir({"XDG_DATA_HOME": "/data"}, "linux") == Path("/data") / "minesweep"
    assert storage.data_dir({}, "linux") == Path.home() / ".local" / "share" / "minesweep"


def test_tests_use_isolated_home(isolated_home):
    assert storage.data_dir() == isolated_home


def test_save_and_load_round_trip(clock):
    b = Board(make_config(9, 9, 10), 5, clock)
    b.reveal((4, 4))
    path = storage.save_game(b)
    assert path.exists()
    loaded = storage.load_game(clock)
    assert loaded.revealed == b.revealed and loaded.mines == b.mines
    assert storage.delete_save() is True
    assert storage.load_game(clock) is None
    assert storage.delete_save() is False


def test_load_corrupt_save_raises_storage_error(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "save.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(storage.StorageError, match="cannot read"):
        storage.load_game()
    (isolated_home / "save.json").write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(storage.StorageError, match="damaged"):
        storage.load_game()


def test_record_score_ranks_fastest_first():
    assert storage.record_score("beginner", 30, when=at(0)) == 1
    assert storage.record_score("beginner", 10, when=at(1)) == 1
    assert storage.record_score("beginner", 20, when=at(2)) == 2
    assert [e["seconds"] for e in storage.load_scores()["beginner"]] == [10, 20, 30]


def test_tie_goes_to_the_earlier_time():
    storage.record_score("expert", 50, seed=1, when=at(0))
    assert storage.record_score("expert", 50, seed=2, when=at(1)) == 2
    assert [e["seed"] for e in storage.load_scores()["expert"]] == [1, 2]


def test_only_top_ten_kept():
    for s in range(1, 11):
        storage.record_score("intermediate", s * 10)
    assert storage.record_score("intermediate", 500) is None
    assert storage.record_score("intermediate", 5) == 1
    entries = storage.load_scores()["intermediate"]
    assert len(entries) == 10 and entries[-1]["seconds"] == 90


def test_custom_boards_are_not_ranked(isolated_home):
    assert storage.record_score("custom", 1) is None
    assert not (isolated_home / "scores.json").exists()


def test_difficulties_ranked_separately():
    storage.record_score("beginner", 99)
    storage.record_score("expert", 1)
    s = storage.load_scores()
    assert [e["seconds"] for e in s["beginner"]] == [99]
    assert s["intermediate"] == []


def test_scores_file_is_plain_json(isolated_home):
    storage.record_score("beginner", 12.345, seed=4, when=at(5))
    data = json.loads((isolated_home / "scores.json").read_text(encoding="utf-8"))
    assert data["beginner"] == [{"seconds": 12.35, "date": "2026-01-01 12:05", "seed": 4}]
