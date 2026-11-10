"""Command-line interface: argument parsing and the turn-based game loop."""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import date, datetime, timezone
from typing import Callable, Mapping, Sequence, TextIO

from minesweep import __version__
from minesweep.board import (
    DIFFICULTIES,
    LOST,
    WON,
    Board,
    Clock,
    ConfigError,
    CoordError,
    NO_GUESS_TRIES,
    MoveError,
    cell_label,
    daily_start,
    make_config,
    parse_coord,
)
from minesweep.render import (
    format_seconds,
    pick_glyphs,
    render_board,
    render_status,
    use_color,
)
from minesweep.solver import FLAG, REVEAL, suggest
from minesweep.storage import (
    StorageError,
    daily_leaderboard,
    data_dir,
    delete_save,
    load_daily,
    load_game,
    load_scores,
    load_stats,
    record_daily,
    record_game,
    record_score,
    reset_daily,
    reset_scores,
    reset_stats,
    save_game,
    stats_summary,
)
from minesweep.tui import run_tui

HELP_TEXT = """\
Commands:
  r B3    reveal a cell (typing just B3 works too)
  f B3    flag or unflag a hidden cell
  c B3    chord: on a number whose mines are all flagged, reveal its other neighbours
  u       undo your last move (a game where you undo is not ranked)
  h       hint: show one move the board proves (a hinted game is not ranked)
  s       save the game and quit (continue later with: minesweep resume)
  q       quit without saving
  ?       show this help
Columns are letters (A, B, C, ...), rows are numbers (1, 2, 3, ...)."""

MOVES = {
    "r": "reveal", "reveal": "reveal",
    "f": "flag", "flag": "flag",
    "c": "chord", "chord": "chord",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minesweep",
        description="Turn-based Minesweeper in your terminal.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    color = argparse.ArgumentParser(add_help=False)
    color.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="colour the numbers (default: auto = only on a terminal without NO_COLOR)",
    )
    color.add_argument(
        "--no-echo", dest="echo", action="store_false",
        help="do not repeat piped commands after the prompt (they are echoed by default "
        "when input is not a terminal, so transcripts read like a typed session)",
    )
    color.add_argument(
        "--tui", action="store_true",
        help="play full screen with the arrow keys (needs curses; on Windows: "
        'pip install "minesweep-cli[tui]")',
    )

    play = sub.add_parser("play", parents=[color], help="start a new game")
    play.add_argument(
        "--difficulty", "-d", choices=tuple(DIFFICULTIES), default="beginner",
        help="board preset (default: beginner 9x9, 10 mines)",
    )
    play.add_argument("--width", type=int, help="custom number of columns")
    play.add_argument("--height", type=int, help="custom number of rows")
    play.add_argument("--mines", type=int, help="custom number of mines")
    play.add_argument("--seed", type=int, help="seed for a reproducible board")
    play.add_argument(
        "--no-guess", action="store_true",
        help="only deal boards the solver can clear from your first click without "
        "guessing (such games are not ranked)",
    )

    daily = sub.add_parser(
        "daily", parents=[color],
        help="play the daily challenge: the same board for everyone",
        description="Play the daily challenge: a board seeded from the UTC date, with "
        "the centre cell opened for you, so everyone gets the same board.",
    )
    daily.add_argument(
        "--difficulty", "-d", choices=tuple(DIFFICULTIES), default="beginner",
        help="board preset (default: beginner)",
    )
    daily.add_argument(
        "--date", type=_iso_date, metavar="YYYY-MM-DD",
        help="play an earlier day's challenge (default: today, UTC)",
    )

    sub.add_parser("resume", parents=[color], help="continue your saved game")
    scores = sub.add_parser("scores", help="show best times per difficulty")
    scores.add_argument(
        "--daily", action="store_true",
        help="show your daily challenge results instead (first attempt per day)",
    )
    _add_reset_args(scores, "the records shown (best times, or daily results with --daily)")
    stats = sub.add_parser(
        "stats",
        help="show games played, wins, streaks and average win time",
        description="Show games played and won, win rate, win streaks and average "
        "winning time per difficulty.",
    )
    _add_reset_args(stats, "your statistics")
    return parser


def _add_reset_args(parser: argparse.ArgumentParser, what: str) -> None:
    parser.add_argument(
        "--reset", action="store_true",
        help=f"delete {what}; asks first, and other records are kept",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="with --reset: do not ask for confirmation",
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    clock: Clock | None = None,
    now: Callable[[], datetime] | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    environ = os.environ if environ is None else environ
    clock = clock or time.monotonic

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help, --version or a usage error (code 2)
        return int(exc.code or 0)

    ctx = _Context(stdin, stdout, stderr, environ, clock, now)
    try:
        if args.command == "play":
            return _cmd_play(args, ctx)
        if args.command == "daily":
            return _cmd_daily(args, ctx)
        if args.command == "resume":
            return _cmd_resume(args, ctx)
        if args.command == "stats":
            if args.reset:
                return _cmd_reset(ctx, "your statistics", reset_stats, args.yes)
            return _cmd_stats(ctx)
        if args.daily:
            if args.reset:
                return _cmd_reset(ctx, "your daily challenge results", reset_daily, args.yes)
            return _cmd_daily_scores(ctx)
        if args.reset:
            return _cmd_reset(ctx, "your best times", reset_scores, args.yes)
        return _cmd_scores(ctx)
    except KeyboardInterrupt:
        stdout.write("\nInterrupted; game not saved.\n")
        return 130


class _Context:
    def __init__(self, stdin, stdout, stderr, environ, clock, now):
        self.stdin: TextIO = stdin
        self.stdout: TextIO = stdout
        self.stderr: TextIO = stderr
        self.environ: Mapping[str, str] = environ
        self.clock: Clock = clock
        self.now = now

    def err(self, message: str) -> None:
        self.stderr.write(f"minesweep: error: {message}\n")


# ------------------------------------------------------------------- commands


def _cmd_play(args: argparse.Namespace, ctx: _Context) -> int:
    base = DIFFICULTIES[args.difficulty]
    custom = (args.width, args.height, args.mines)
    try:
        if any(v is not None for v in custom):
            config = make_config(
                args.width if args.width is not None else base.width,
                args.height if args.height is not None else base.height,
                args.mines if args.mines is not None else base.mines,
            )
        else:
            config = base
    except ConfigError as exc:
        ctx.err(str(exc))
        return 2
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    board = Board(config, seed, ctx.clock, no_guess=args.no_guess)
    return _play(board, args, ctx, from_save=False)


def _play(board: Board, args: argparse.Namespace, ctx: _Context, *, from_save: bool) -> int:
    """Run the game full screen with --tui, or with typed commands otherwise."""
    if args.tui:
        return run_tui(board, ctx, from_save=from_save)
    return run_game(board, ctx, color_mode=args.color, from_save=from_save, echo=args.echo)


def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date like 2026-11-09: {text!r}") from None


def _cmd_daily(args: argparse.Namespace, ctx: _Context) -> int:
    now = ctx.now() if ctx.now else datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    day = args.date or today
    if day > today:
        ctx.err(
            f"the daily challenge for {day.isoformat()} is not out yet "
            f"(today is {today.isoformat()} UTC)"
        )
        return 2
    board = Board.daily_challenge(DIFFICULTIES[args.difficulty], day, ctx.clock)
    return _play(board, args, ctx, from_save=False)


def _cmd_resume(args: argparse.Namespace, ctx: _Context) -> int:
    try:
        board = load_game(ctx.clock, ctx.environ)
    except StorageError as exc:
        ctx.err(str(exc))
        return 1
    if board is None:
        ctx.err(f"no saved game in {data_dir(ctx.environ)}; start one with: minesweep play")
        return 1
    if board.over:
        delete_save(ctx.environ)
        ctx.err("the saved game was already finished; start a new one with: minesweep play")
        return 1
    return _play(board, args, ctx, from_save=True)


def _cmd_scores(ctx: _Context) -> int:
    try:
        scores = load_scores(ctx.environ)
    except StorageError as exc:
        ctx.err(str(exc))
        return 1
    out = ctx.stdout
    out.write("Best times (custom boards are not ranked)\n")
    for name, cfg in DIFFICULTIES.items():
        out.write(f"\n{name} ({cfg.width}x{cfg.height}, {cfg.mines} mines)\n")
        entries = scores.get(name, [])
        if not entries:
            out.write("  no wins yet\n")
            continue
        for i, e in enumerate(entries, 1):
            seed = f"  seed {e['seed']}" if e.get("seed") is not None else ""
            out.write(f"  {i:>2}. {format_seconds(e['seconds']):>8}  {e.get('date', '?')}{seed}\n")
    return 0


def _cmd_daily_scores(ctx: _Context) -> int:
    try:
        results = load_daily(ctx.environ)
    except StorageError as exc:
        ctx.err(str(exc))
        return 1
    out = ctx.stdout
    out.write("Daily challenge results (only your first attempt each day counts)\n")
    for name, cfg in DIFFICULTIES.items():
        days = results.get(name, {})
        out.write(f"\n{name} ({cfg.width}x{cfg.height}, {cfg.mines} mines)\n")
        if not days:
            out.write("  not played yet\n")
            continue
        won = sum(1 for e in days.values() if e["result"] == "won")
        out.write(f"  played {len(days)}, won {won}\n")
        ranking = daily_leaderboard(days)
        if not ranking:
            out.write("  no ranked wins yet (wins with undo or a hint are not ranked)\n")
        for i, (day, secs) in enumerate(ranking, 1):
            out.write(f"  {i:>2}. {format_seconds(secs):>8}  {day}\n")
        latest = max(days)
        out.write(f"  latest: {share_line(name, latest, days[latest])}\n")
    return 0


def _cmd_stats(ctx: _Context) -> int:
    try:
        stats = load_stats(ctx.environ)
    except StorageError as exc:
        ctx.err(str(exc))
        return 1
    out = ctx.stdout
    out.write("Statistics (every finished game on a standard board; custom boards are not counted)\n\n")
    for name in DIFFICULTIES:
        out.write(f"  {stats_summary(name, stats[name])}\n")
    total = {
        "played": sum(e["played"] for e in stats.values()),
        "won": sum(e["won"] for e in stats.values()),
    }
    if total["played"]:
        pct = int(100 * total["won"] / total["played"])
        out.write(f"\n  all: {total['played']} played, {total['won']} won ({pct}%)\n")
    return 0


def _cmd_reset(ctx: _Context, what: str, reset: Callable[..., bool], yes: bool) -> int:
    """Delete one kind of record after a confirmation (skipped with --yes)."""
    if not yes:
        ctx.stdout.write(f"Delete {what}? This cannot be undone. [y/N] ")
        ctx.stdout.flush()
        line = ctx.stdin.readline()
        if not line:  # end of input: finish the prompt line
            ctx.stdout.write("\n")
        elif not _isatty(ctx.stdin):  # piped answer: echo it, as the game does
            ctx.stdout.write(strip_bom(line).strip() + "\n")
        if strip_bom(line).strip().lower() not in ("y", "yes"):
            ctx.stdout.write("Nothing deleted.\n")
            return 1
    try:
        removed = reset(ctx.environ)
    except StorageError as exc:
        ctx.err(str(exc))
        return 1
    if removed:
        ctx.stdout.write(f"Deleted {what}.\n")
    else:
        ctx.stdout.write(f"Nothing to delete: {what} were never saved.\n")
    return 0


def share_line(difficulty: str, day: str, entry: Mapping) -> str:
    """A one-line, spoiler-free daily result to paste to friends."""
    head = f"minesweep daily {day} {difficulty}: "
    secs = format_seconds(entry["seconds"])
    if entry["result"] == "won":
        return head + f"cleared in {secs}" + (" (assisted)" if entry.get("assisted") else "")
    cleared, safe = entry.get("cleared", 0), entry.get("safe", 0)
    pct = int(100 * cleared / safe) if safe else 0
    return head + f"hit a mine after {secs}, {cleared}/{safe} safe cells open ({pct}%)"


# ------------------------------------------------------------------ game loop


def run_game(
    board: Board,
    ctx: _Context,
    *,
    color_mode: str = "auto",
    from_save: bool = False,
    echo: bool = True,
) -> int:
    """Play until the game ends or the player saves/quits.

    ``echo=False`` turns off repeating piped commands; typed input on a
    terminal is never echoed (the terminal already shows it).
    """
    out = ctx.stdout
    color = use_color(color_mode, out, ctx.environ)
    if color:
        _enable_windows_ansi()
    glyphs = pick_glyphs(out)
    cfg = board.config

    if board.daily:
        verb = f"Resuming daily challenge {board.daily}" if from_save else f"Daily challenge {board.daily}"
    else:
        verb = "Resuming" if from_save else "New game"
    mode = ", no guessing" if board.no_guess else ""
    out.write(
        f"{verb}: {cfg.difficulty} {cfg.width}x{cfg.height}, {cfg.mines} mines, "
        f"seed {board.seed}{mode}. Type ? for help.\n"
    )
    if board.daily and not from_save:
        start = cell_label(daily_start(cfg))
        out.write(
            f"{start} was opened for you, so everyone starts from the same board. "
            f"The clock starts on your first reveal.\n"
        )
    echo = echo and not _isatty(ctx.stdin)
    hints_seen: set = set()  # (position, hint) pairs already counted this session
    warned_no_guess = board.no_guess_ok is False  # a resumed game was told already
    redraw = True
    while True:
        if board.no_guess_ok is False and not warned_no_guess:
            out.write(
                f"No board for this first click could be solved without guessing "
                f"in {NO_GUESS_TRIES} tries, so this one may need a guess.\n"
            )
            warned_no_guess = True
        if redraw:
            last = board.last_move
            highlight = last[1] if last else None
            out.write(render_board(board, color=color, glyphs=glyphs, highlight=highlight) + "\n")
            out.write(render_status(board) + "\n")
            redraw = False
        if board.over:
            return _finish(board, ctx, from_save)

        out.write("> ")
        out.flush()
        line = ctx.stdin.readline()
        if not line:
            out.write("\nEnd of input; game not saved.\n")
            return 0
        line = strip_bom(line)
        if echo:  # scripted input: show the command so the transcript reads well
            out.write(line if line.endswith("\n") else line + "\n")
        words = line.split()
        if not words:
            continue
        cmd = words[0].lower()

        if cmd in ("?", "help"):
            out.write(HELP_TEXT + "\n")
            continue
        if cmd in ("q", "quit", "exit"):
            note = " Your earlier save is still there." if from_save else ""
            out.write(f"Quit without saving.{note}\n")
            return 0
        if cmd in ("u", "undo"):
            try:
                action, cell = board.undo()
            except MoveError as exc:
                out.write(f"{exc}\n")
                continue
            out.write(f"Undid {action} {cell_label(cell)}.\n")
            redraw = True
            continue
        if cmd in ("h", "hint"):
            out.write(_hint_text(board, hints_seen) + "\n")
            continue
        if cmd in ("s", "save"):
            path = save_game(board, ctx.environ)
            out.write(f"Game saved to {path}. Continue with: minesweep resume\n")
            return 0

        if cmd in MOVES:
            action = MOVES[cmd]
            if len(words) != 2:
                out.write(f"Usage: {cmd} <cell>, for example {cmd} B3\n")
                continue
            target = words[1]
        elif len(words) == 1 and words[0][:1].isalpha() and words[0][-1:].isdigit():
            action, target = "reveal", words[0]
        else:
            out.write(f"Unknown command '{words[0]}'. Type ? for help.\n")
            continue

        try:
            cell = parse_coord(target, board.width, board.height)
            if action == "reveal":
                board.reveal(cell)
            elif action == "flag":
                board.toggle_flag(cell)
            else:
                board.chord(cell)
        except (CoordError, MoveError) as exc:
            out.write(f"{exc}\n")
            continue
        redraw = True


def _finish(board: Board, ctx: _Context, from_save: bool) -> int:
    if from_save:
        delete_save(ctx.environ)
    code = _report_result(board, ctx)
    _record_stats(board, ctx)
    return code


def _record_stats(board: Board, ctx: _Context) -> None:
    """Count a finished game on a standard board and print the running totals."""
    if not board.config.ranked:
        return
    name = board.config.difficulty
    try:
        entry = record_game(name, won=board.state == WON, seconds=board.elapsed, environ=ctx.environ)
    except (StorageError, OSError) as exc:
        ctx.err(f"could not update your statistics: {exc}")
        return
    if entry is not None:
        ctx.stdout.write(f"Stats: {stats_summary(name, entry)}\n")


def _report_result(board: Board, ctx: _Context) -> int:
    out = ctx.stdout
    secs = board.elapsed
    if board.state == LOST:
        where = cell_label(board.exploded) if board.exploded else "?"
        out.write(f"BOOM! You hit a mine at {where}. Game over after {format_seconds(secs)}.\n")
        if board.daily:
            _finish_daily(board, ctx)
        return 0
    assert board.state == WON
    out.write(f"You win! Cleared in {format_seconds(secs)}.\n")
    if not board.config.ranked:
        out.write("Custom boards are not ranked.\n")
        return 0
    if board.daily:
        out.write("Daily challenges are not entered in the regular best-times table.\n")
        _finish_daily(board, ctx)
        return 0
    used = []
    if board.undos:
        used.append("undo " + ("once" if board.undos == 1 else f"{board.undos} times"))
    if board.hints:
        used.append("1 hint" if board.hints == 1 else f"{board.hints} hints")
    if board.no_guess:
        used.append("a no-guess board")
    if used:
        out.write(f"You used {' and '.join(used)}, so this game is not ranked.\n")
        return 0
    try:
        rank = record_score(
            board.config.difficulty, secs, seed=board.seed,
            when=ctx.now() if ctx.now else None, environ=ctx.environ,
        )
    except (StorageError, OSError) as exc:
        ctx.err(f"could not record your time: {exc}")
        return 0
    if rank is None:
        out.write(f"Not in the {board.config.difficulty} top 10 this time.\n")
    else:
        out.write(f"New best time #{rank} for {board.config.difficulty}!\n")
    return 0


def _finish_daily(board: Board, ctx: _Context) -> None:
    """Record a finished daily challenge and print its shareable line."""
    out = ctx.stdout
    name, day = board.config.difficulty, board.daily
    assert day is not None
    won = board.state == WON
    assisted = bool(board.undos or board.hints)
    try:
        stored = record_daily(
            name, day, won=won, seconds=board.elapsed, assisted=assisted,
            cleared=len(board.revealed - board.mines),
            safe=board.config.cells - board.config.mines, environ=ctx.environ,
        )
        days = load_daily(ctx.environ)[name]
    except (StorageError, OSError) as exc:
        ctx.err(f"could not record your daily result: {exc}")
        return
    entry = days[day]
    if not stored:
        out.write(
            f"You already finished the {day} {name} daily; only your first result counts.\n"
        )
    elif won and assisted:
        out.write("You used undo or a hint, so this daily win is recorded but not ranked.\n")
    elif won:
        ranking = [d for d, _ in daily_leaderboard(days)]
        if day in ranking:
            out.write(f"Daily best #{ranking.index(day) + 1} for {name}!\n")
    out.write(f"Share: {share_line(name, day, entry)}\n")


def _hint_text(board: Board, seen: set) -> str:
    """Answer the ``h`` command.

    Only a hint that names a cell is counted, and asking again for the same
    hint in the same position (without a move in between) is not counted twice.
    """
    if not board.revealed:
        return "No hint needed yet: your first reveal is always safe."
    hint = suggest(board)
    if hint is None:
        return (
            "No certain move: nothing on the board proves a cell safe or a mine, "
            "so you have to guess."
        )
    key = (frozenset(board.revealed), frozenset(board.flagged), hint)
    if key not in seen:
        seen.add(key)
        board.hints += 1
    label = cell_label(hint.cell)
    if hint.action == REVEAL:
        what = f"{label} is safe. Reveal it: r {label}"
    elif hint.action == FLAG:
        what = f"{label} is a mine. Flag it: f {label}"
    else:
        what = f"{label} is flagged but safe. Unflag it: f {label}"
    count = "1 hint" if board.hints == 1 else f"{board.hints} hints"
    return f"Hint ({hint.rule} rule): {what}  ({count} used, so this game is not ranked)"


# A UTF-8 byte order mark as read through a UTF-8 stream, and as the three
# characters it becomes when piped input is decoded with Windows-1252 (what
# Python uses for a pipe on a Western-locale Windows without UTF-8 mode).
_BOMS = ("﻿", "ï»¿")


def strip_bom(line: str) -> str:
    """Drop a byte order mark from the start of an input line.

    Windows PowerShell can prefix piped text with one (``'r E5' | minesweep
    play``), which would otherwise turn the first command into an unknown one.
    """
    for bom in _BOMS:
        if line.startswith(bom):
            return line[len(bom):]
    return line


def _isatty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def _enable_windows_ansi() -> None:
    """Turn on ANSI escape handling in the classic Windows console (best effort)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:  # pragma: no cover - cosmetic only
        pass


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
