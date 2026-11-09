"""Command-line interface: argument parsing and the turn-based game loop."""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime
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
    MoveError,
    cell_label,
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
from minesweep.storage import (
    StorageError,
    data_dir,
    delete_save,
    load_game,
    load_scores,
    record_score,
    save_game,
)

HELP_TEXT = """\
Commands:
  r B3    reveal a cell (typing just B3 works too)
  f B3    flag or unflag a hidden cell
  c B3    chord: on a number whose mines are all flagged, reveal its other neighbours
  u       undo your last move (a game where you undo is not ranked)
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

    play = sub.add_parser("play", parents=[color], help="start a new game")
    play.add_argument(
        "--difficulty", "-d", choices=tuple(DIFFICULTIES), default="beginner",
        help="board preset (default: beginner 9x9, 10 mines)",
    )
    play.add_argument("--width", type=int, help="custom number of columns")
    play.add_argument("--height", type=int, help="custom number of rows")
    play.add_argument("--mines", type=int, help="custom number of mines")
    play.add_argument("--seed", type=int, help="seed for a reproducible board")

    sub.add_parser("resume", parents=[color], help="continue your saved game")
    sub.add_parser("scores", help="show best times per difficulty")
    return parser


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
        if args.command == "resume":
            return _cmd_resume(args, ctx)
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
    board = Board(config, seed, ctx.clock)
    return run_game(board, ctx, color_mode=args.color, from_save=False, echo=args.echo)


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
    return run_game(board, ctx, color_mode=args.color, from_save=True, echo=args.echo)


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

    verb = "Resuming" if from_save else "New game"
    out.write(
        f"{verb}: {cfg.difficulty} {cfg.width}x{cfg.height}, {cfg.mines} mines, "
        f"seed {board.seed}. Type ? for help.\n"
    )
    echo = echo and not _isatty(ctx.stdin)
    redraw = True
    while True:
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
        if echo:  # scripted input: show the command so the transcript reads well
            out.write(line if line.endswith("\n") else line + "\n")
        words = line.split()
        if not words:
            continue
        cmd = words[0].lower()

        if cmd in ("?", "h", "help"):
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
    out = ctx.stdout
    if from_save:
        delete_save(ctx.environ)
    secs = board.elapsed
    if board.state == LOST:
        where = cell_label(board.exploded) if board.exploded else "?"
        out.write(f"BOOM! You hit a mine at {where}. Game over after {format_seconds(secs)}.\n")
        return 0
    assert board.state == WON
    out.write(f"You win! Cleared in {format_seconds(secs)}.\n")
    if not board.config.ranked:
        out.write("Custom boards are not ranked.\n")
        return 0
    if board.undos:
        times = "once" if board.undos == 1 else f"{board.undos} times"
        out.write(f"You used undo {times}, so this game is not ranked.\n")
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
