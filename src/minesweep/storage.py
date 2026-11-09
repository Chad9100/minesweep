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
    _write_json(scores_path(environ), scores)
    for i, e in enumerate(entries):
        if e is entry:
            return i + 1
    return None
