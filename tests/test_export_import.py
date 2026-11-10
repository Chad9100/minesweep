"""`minesweep export` and `minesweep import`."""

import io
import json
import os

from minesweep import storage
from minesweep.cli import main


def run(args, environ=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, stdin=io.StringIO(""), stdout=out, stderr=err, environ=environ or dict(os.environ))
    return code, out.getvalue(), err.getvalue()


def seed_records():
    storage.record_score("beginner", 12.5, seed=1)
    storage.record_score("beginner", 30.0, seed=2)
    storage.record_daily(
        "beginner", "2026-11-09", won=True, seconds=20.0, assisted=False, cleared=71, safe=71
    )
    for won in (True, False, True):
        storage.record_game("beginner", won=won, seconds=10.0)


def test_export_to_stdout_is_json_with_every_record():
    seed_records()
    code, out, err = run(["export"])
    assert code == 0 and err == ""
    data = json.loads(out)
    assert data["format"] == storage.EXPORT_FORMAT
    assert [e["seconds"] for e in data["scores"]["beginner"]] == [12.5, 30.0]
    assert "2026-11-09" in data["daily"]["beginner"]
    assert data["stats"]["beginner"]["played"] == 3


def test_export_to_a_file_then_import_into_a_fresh_home(tmp_path):
    seed_records()
    target = tmp_path / "records.json"
    code, out, _ = run(["export", str(target)])
    assert code == 0 and "Exported" in out

    other = dict(os.environ, MINESWEEP_HOME=str(tmp_path / "other-home"))
    code, out, err = run(["import", str(target)], environ=other)
    assert code == 0 and err == ""
    assert "Imported 2 best time(s) and 1 daily result(s)" in out
    assert "replaced for 1 difficulty" in out
    assert storage.load_scores(other)["beginner"][0]["seconds"] == 12.5
    assert storage.load_stats(other)["beginner"]["won"] == 2
    assert storage.load_daily(other)["beginner"]["2026-11-09"]["seconds"] == 20.0


def test_import_twice_changes_nothing(tmp_path):
    seed_records()
    target = tmp_path / "records.json"
    run(["export", str(target)])
    code, out, _ = run(["import", str(target)])
    assert code == 0
    assert "Imported 0 best time(s) and 0 daily result(s)" in out
    assert len(storage.load_scores()["beginner"]) == 2
    assert storage.load_stats()["beginner"]["played"] == 3


def test_import_merges_with_existing_records(tmp_path):
    seed_records()
    target = tmp_path / "records.json"
    run(["export", str(target)])
    storage.reset_scores()
    storage.reset_stats()
    storage.record_score("beginner", 20.0, seed=3)
    storage.record_game("beginner", won=True, seconds=5.0)
    code, _, _ = run(["import", str(target)])
    assert code == 0
    times = [e["seconds"] for e in storage.load_scores()["beginner"]]
    assert times == [12.5, 20.0, 30.0]
    assert storage.load_stats()["beginner"]["played"] == 3  # the larger record wins


def test_existing_daily_result_is_kept(tmp_path):
    seed_records()
    target = tmp_path / "records.json"
    run(["export", str(target)])
    storage.reset_daily()
    storage.record_daily(
        "beginner", "2026-11-09", won=False, seconds=3.0, assisted=False, cleared=1, safe=71
    )
    run(["import", str(target)])
    assert storage.load_daily()["beginner"]["2026-11-09"]["result"] == "lost"


def test_import_rejects_other_json_and_changes_nothing(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    code, out, err = run(["import", str(bad)])
    assert code == 1 and out == ""
    assert "not a minesweep export file" in err
    assert not storage.scores_path().exists()


def test_import_rejects_newer_format(tmp_path):
    newer = tmp_path / "new.json"
    newer.write_text(
        json.dumps({"format": storage.EXPORT_FORMAT, "version": storage.RECORD_VERSION + 1}),
        encoding="utf-8",
    )
    code, _, err = run(["import", str(newer)])
    assert code == 1 and "newer minesweep" in err


def test_import_missing_or_broken_file(tmp_path):
    code, _, err = run(["import", str(tmp_path / "nope.json")])
    assert code == 1 and "cannot read" in err
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    code, _, err = run(["import", str(broken)])
    assert code == 1 and "cannot read" in err
