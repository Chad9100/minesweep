"""Save files and high scores, kept in a per-user data directory.

Location, first match wins:

1. ``$MINESWEEP_HOME``
2. Windows: ``%APPDATA%\\minesweep``
3. ``$XDG_DATA_HOME/minesweep``
4. ``~/.local/share/minesweep``
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from minesweep.board import DIFFICULTIES, Board, Clock

SAVE_NAME = "save.json"
SCORES_NAME = "scores.json"
MAX_SCORES = 10
RECORD_VERSION = 1  # format of scores.json, daily.json and stats.json


class StorageError(Exception):
    """A save or score file exists but cannot be used."""


def data_dir(environ: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    if env.get("MINESWEEP_HOME"):
        return Path(env["MINESWEEP_HOME"])
    if plat == "win32":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "minesweep"
    if env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]) / "minesweep"
    return Path.home() / ".local" / "share" / "minesweep"


def save_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_dir(environ) / SAVE_NAME


def scores_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_dir(environ) / SCORES_NAME


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError(f"cannot read {path}: {exc}") from exc


def _stamped(data: Mapping[str, Any]) -> dict[str, Any]:
    """The record file's contents with its format version first."""
    return {"version": RECORD_VERSION, **data}


def _check_record_version(path: Path, data: dict[str, Any]) -> None:
    """Refuse a record file written by a newer minesweep.

    Files written before versions existed have no ``version`` and are read as
    version 1, which is the same layout.
    """
    version = data.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise StorageError(f"{path} has an invalid format version {version!r}")
    if version > RECORD_VERSION:
        raise StorageError(
            f"{path} was written by a newer minesweep (format version {version}, "
            f"this one reads up to {RECORD_VERSION}); upgrade minesweep or delete the file"
        )


# ----------------------------------------------------------------------- saves


def save_game(board: Board, environ: Mapping[str, str] | None = None) -> Path:
    path = save_path(environ)
    _write_json(path, board.to_dict())
    return path


def load_game(clock: Clock = time.monotonic, environ: Mapping[str, str] | None = None) -> Board | None:
    """Return the saved board, or None if there is no save."""
    path = save_path(environ)
    try:
        data = _read_json(path)
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise StorageError(f"{path} is not a minesweep save file")
    try:
        return Board.from_dict(data, clock)
    except ValueError as exc:
        raise StorageError(f"{path} is damaged: {exc}") from exc


def delete_save(environ: Mapping[str, str] | None = None) -> bool:
    try:
        save_path(environ).unlink()
    except FileNotFoundError:
        return False
    return True


# ---------------------------------------------------------------------- scores


def load_scores(environ: Mapping[str, str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Best times per standard difficulty, fastest first."""
    path = scores_path(environ)
    try:
        data = _read_json(path)
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise StorageError(f"{path} is not a minesweep scores file")
    _check_record_version(path, data)
    out: dict[str, list[dict[str, Any]]] = {}
    for name in DIFFICULTIES:
        entries = data.get(name, [])
        if not isinstance(entries, list):
            raise StorageError(f"{path}: entry for {name} is not a list")
        good = [e for e in entries if isinstance(e, dict) and isinstance(e.get("seconds"), (int, float))]
        out[name] = sorted(good, key=lambda e: e["seconds"])[:MAX_SCORES]
    return out


def record_score(
    difficulty: str,
    seconds: float,
    *,
    seed: int | None = None,
    when: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> int | None:
    """Store a winning time. Returns its 1-based rank, or None if it did not
    make the top list (or the difficulty is not a ranked one)."""
    if difficulty not in DIFFICULTIES:
        return None
    scores = load_scores(environ)
    when = when or datetime.now(timezone.utc)
    entry = {
        "seconds": round(float(seconds), 2),
        "date": when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "seed": seed,
    }
    entries = scores[difficulty] + [entry]
    entries.sort(key=lambda e: e["seconds"])  # stable: earlier ties stay ahead
    entries = entries[:MAX_SCORES]
    scores[difficulty] = entries
    _write_json(scores_path(environ), _stamped(scores))
    for i, e in enumerate(entries):
        if e is entry:
            return i + 1
    return None


# ----------------------------------------------------------------- daily results

DAILY_NAME = "daily.json"


def daily_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_dir(environ) / DAILY_NAME


def _valid_daily_entry(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("result") in ("won", "lost")
        and isinstance(entry.get("seconds"), (int, float))
    )


def load_daily(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    """First daily result per difficulty, keyed by ISO date.

    Each entry is ``{"result": "won"|"lost", "seconds": float, "assisted":
    bool, "cleared": int, "safe": int}``. Malformed entries are skipped.
    """
    path = daily_path(environ)
    try:
        data = _read_json(path)
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise StorageError(f"{path} is not a minesweep daily results file")
    _check_record_version(path, data)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for name in DIFFICULTIES:
        days = data.get(name, {})
        if not isinstance(days, dict):
            raise StorageError(f"{path}: entry for {name} is not an object")
        out[name] = {day: e for day, e in days.items() if _valid_daily_entry(e)}
    return out


def record_daily(
    difficulty: str,
    day: str,
    *,
    won: bool,
    seconds: float,
    assisted: bool,
    cleared: int,
    safe: int,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Store the result of a finished daily challenge.

    Only the first finished attempt at a day's challenge counts, so a replay
    (after seeing where the mines are) cannot improve it. Returns True if this
    result was stored, False if that day was already played.
    """
    results = load_daily(environ)
    days = results[difficulty]
    if day in days:
        return False
    days[day] = {
        "result": "won" if won else "lost",
        "seconds": round(float(seconds), 2),
        "assisted": bool(assisted),
        "cleared": int(cleared),
        "safe": int(safe),
    }
    results[difficulty] = dict(sorted(days.items()))
    _write_json(daily_path(environ), _stamped(results))
    return True


def daily_leaderboard(
    results: Mapping[str, Mapping[str, Any]], limit: int = MAX_SCORES
) -> list[tuple[str, float]]:
    """The fastest unassisted daily wins as ``(date, seconds)``; ties go to the earlier day."""
    wins = [
        (day, float(e["seconds"]))
        for day, e in results.items()
        if e["result"] == "won" and not e.get("assisted")
    ]
    wins.sort(key=lambda w: (w[1], w[0]))
    return wins[:limit]


# ------------------------------------------------------------------ statistics

STATS_NAME = "stats.json"
_STAT_KEYS = ("played", "won", "streak", "best_streak")


def stats_path(environ: Mapping[str, str] | None = None) -> Path:
    return data_dir(environ) / STATS_NAME


def empty_stats() -> dict[str, Any]:
    return {"played": 0, "won": 0, "streak": 0, "best_streak": 0, "win_seconds": 0.0}


def _clean_stats(entry: Any) -> dict[str, Any]:
    """A usable stats record; damaged or missing fields fall back to zero."""
    out = empty_stats()
    if not isinstance(entry, dict):
        return out
    for key in _STAT_KEYS:
        value = entry.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[key] = value
    secs = entry.get("win_seconds")
    if isinstance(secs, (int, float)) and not isinstance(secs, bool) and secs >= 0:
        out["win_seconds"] = float(secs)
    out["won"] = min(out["won"], out["played"])
    out["streak"] = min(out["streak"], out["won"])
    out["best_streak"] = max(min(out["best_streak"], out["won"]), out["streak"])
    return out


def load_stats(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Games played and won, win streaks and total winning time per difficulty."""
    path = stats_path(environ)
    try:
        data = _read_json(path)
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise StorageError(f"{path} is not a minesweep statistics file")
    _check_record_version(path, data)
    return {name: _clean_stats(data.get(name)) for name in DIFFICULTIES}


def record_game(
    difficulty: str,
    *,
    won: bool,
    seconds: float,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Count one finished game. Returns the difficulty's updated record, or
    None for a custom board (those are not tracked)."""
    if difficulty not in DIFFICULTIES:
        return None
    stats = load_stats(environ)
    entry = stats[difficulty]
    entry["played"] += 1
    if won:
        entry["won"] += 1
        entry["streak"] += 1
        entry["best_streak"] = max(entry["best_streak"], entry["streak"])
        entry["win_seconds"] = round(entry["win_seconds"] + float(seconds), 2)
    else:
        entry["streak"] = 0
    _write_json(stats_path(environ), _stamped(stats))
    return entry


def stats_summary(difficulty: str, entry: Mapping[str, Any]) -> str:
    """One line such as ``beginner: 4 played, 3 won (75%), win streak 2 (best 3), average win 41.2s``."""
    played, won = entry["played"], entry["won"]
    if not played:
        return f"{difficulty}: no games finished yet"
    pct = int(100 * won / played)
    line = (
        f"{difficulty}: {played} played, {won} won ({pct}%), "
        f"win streak {entry['streak']} (best {entry['best_streak']})"
    )
    if won:
        line += f", average win {entry['win_seconds'] / won:.1f}s"
    return line


# ----------------------------------------------------------------------- reset


def _remove(path: Path) -> bool:
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StorageError(f"cannot delete {path}: {exc}") from exc
    return True


def reset_scores(environ: Mapping[str, str] | None = None) -> bool:
    """Delete the best-times table. Returns False if there was none."""
    return _remove(scores_path(environ))


def reset_daily(environ: Mapping[str, str] | None = None) -> bool:
    """Delete the daily challenge results. Returns False if there were none."""
    return _remove(daily_path(environ))


def reset_stats(environ: Mapping[str, str] | None = None) -> bool:
    """Delete the per-difficulty statistics. Returns False if there were none."""
    return _remove(stats_path(environ))
