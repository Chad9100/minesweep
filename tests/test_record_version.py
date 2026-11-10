import json

import pytest

from minesweep import storage


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_record_files_are_stamped_with_a_version(isolated_home):
    storage.record_score("beginner", 12.5)
    storage.record_game("beginner", won=True, seconds=12.5)
    storage.record_daily("beginner", "2026-01-01", won=True, seconds=9.0, assisted=False, cleared=71, safe=71)
    for path in (storage.scores_path(), storage.stats_path(), storage.daily_path()):
        assert json.loads(path.read_text(encoding="utf-8"))["version"] == storage.RECORD_VERSION


def test_files_without_a_version_still_load_and_get_stamped(isolated_home):
    write(storage.stats_path(), {"beginner": {"played": 2, "won": 1, "streak": 1, "best_streak": 1, "win_seconds": 5.0}})
    assert storage.load_stats()["beginner"]["played"] == 2
    storage.record_game("beginner", won=False, seconds=1)
    data = json.loads(storage.stats_path().read_text(encoding="utf-8"))
    assert data["version"] == storage.RECORD_VERSION
    assert data["beginner"]["played"] == 3


@pytest.mark.parametrize(
    "loader, path_fn",
    [
        (storage.load_scores, storage.scores_path),
        (storage.load_daily, storage.daily_path),
        (storage.load_stats, storage.stats_path),
    ],
)
def test_newer_format_is_refused_not_overwritten(isolated_home, loader, path_fn):
    write(path_fn(), {"version": storage.RECORD_VERSION + 1})
    with pytest.raises(storage.StorageError, match="newer minesweep"):
        loader()
    with pytest.raises(storage.StorageError):
        storage.record_game("beginner", won=True, seconds=1) if loader is storage.load_stats else loader()
    assert json.loads(path_fn().read_text(encoding="utf-8")) == {"version": storage.RECORD_VERSION + 1}


@pytest.mark.parametrize("bad", [0, -1, "1", True, 1.5, None])
def test_invalid_version_is_rejected(isolated_home, bad):
    write(storage.scores_path(), {"version": bad})
    with pytest.raises(storage.StorageError, match="invalid format version"):
        storage.load_scores()
