# minesweep

Classic Minesweeper, played turn by turn in your terminal. You type a move
(`r B3` to reveal, `f B3` to flag), the board is printed again, and you keep
going until you clear every safe cell or hit a mine.

- **What it is:** a small, dependency-free command-line game with the real
  rules (safe first click, flood fill, chording), save/resume and a best-times
  table for the three standard difficulties.
- **Who it is for:** anyone who wants a quick game in a terminal window, over
  SSH, or on a machine where you can't install a GUI; and people who like
  reading a small, well-tested Python codebase.
- **Built with:** Python 3.10+ and the standard library only. No curses, so it
  works the same in Windows Terminal, PowerShell, cmd.exe, macOS and Linux.
  Tests use pytest.

## Install

```sh
git clone https://github.com/Chad9100/minesweep.git
cd minesweep
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
minesweep --version
```

You can also run it without the console script: `python -m minesweep play`.

## How to play

```sh
minesweep play                              # beginner: 9x9, 10 mines
minesweep play --difficulty intermediate    # 16x16, 40 mines
minesweep play --difficulty expert          # 30x16, 99 mines
minesweep play --width 20 --height 10 --mines 30   # any custom board
minesweep play --seed 1                     # same seed + same first click = same board
minesweep resume                            # continue a saved game
minesweep play --seed 1 --no-echo < moves.txt   # scripted: don't repeat piped commands
minesweep scores                            # best times per difficulty
```

Columns are letters (`A`, `B`, ... `Z`, `AA`, ...), rows are numbers starting at 1.

| Command | What it does |
| --- | --- |
| `r B3` (or just `B3`) | Reveal a cell. Empty cells open their whole region automatically. |
| `f B3` | Flag or unflag a hidden cell you think is a mine. |
| `c B3` | Chord: on a revealed number whose mines are all flagged, reveal every other neighbour at once. A wrong flag means you lose. |
| `u` | Undo your last move (reveal, flag or chord). Repeat to go further back. |
| `s` | Save the game and quit. Continue later with `minesweep resume`. |
| `q` | Quit without saving. |
| `?` | Show the help. |

Rules in short:

- Your first reveal is always safe. Mines are placed *after* it, away from the
  clicked cell and its neighbours whenever the board has room for that.
- A number tells you how many of the 8 surrounding cells are mines.
- You win when every safe cell is revealed (flags are optional). The clock
  starts on your first reveal.
- Only the standard difficulties are ranked in `minesweep scores`; custom
  boards are not.

Invalid boards are refused with a clear message and exit code 2, for example
`minesweep play --width 3 --height 3 --mines 9` prints
`minesweep: error: too many mines: a 3x3 board holds at most 8 (one cell must stay safe), got 9`.

### Sample session

This is a real session, captured by piping the moves into the game (when input
is piped, the game echoes each command after the `>` prompt, so the transcript
reads like you typed it). It uses `--seed 1`, so you get exactly this board if
you open it with `r E5`. The data directory was pointed at `demo-home` with
`MINESWEEP_HOME`.

```text
$ minesweep play --seed 1
New game: beginner 9x9, 10 mines, seed 1. Type ? for help.
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . . . . . . .
5 . . . . . . . . .
6 . . . . . . . . .
7 . . . . . . . . .
8 . . . . . . . . .
9 . . . . . . . . .
Mines left: 10   Time: 0s
> r E5
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5        [ ]    1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1
Mines left: 10   Time: 0s
> f A9
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9[F]. . . . . . 1
Mines left: 9   Time: 0s
> c B8
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1[1]2 . . . . 1
9 F 1 1 . . . . 1
Mines left: 9   Time: 0s
> f B8
B8 is already revealed and cannot be flagged
> Z1
column Z is off the board (A-I)
> s
Game saved to demo-home\save.json. Continue with: minesweep resume
$ minesweep resume
Resuming: beginner 9x9, 10 mines, seed 1. Type ? for help.
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1[1]2 . . . . 1
9 F 1 1 . . . . 1
Mines left: 9   Time: 0s
> q
Quit without saving. Your earlier save is still there.
$ minesweep scores
Best times (custom boards are not ranked)

beginner (9x9, 10 mines)
  no wins yet

intermediate (16x16, 40 mines)
  no wins yet

expert (30x16, 99 mines)
  no wins yet
```

On a real terminal the numbers are coloured, hidden cells are shown as a
middle dot and flags as a flag symbol. When output is piped, or the terminal
can't show those characters, it falls back to plain ASCII (`.` and `F`) as above.

### Undo

`u` takes back your last move, and you can keep pressing it to step further
back. The board is rebuilt by replaying your earlier moves on the same mines,
so it ends up exactly as it was. A few details:

- The clock is not rewound.
- Undo works while the game is running, not after you have hit a mine.
- The move history is part of the save file, so you can still undo after
  `minesweep resume`. Saves made by v0.1 (before undo existed) still load;
  undo then goes back as far as the position you resumed from.
- A game in which you used undo is not ranked in `minesweep scores`.
- If you undo your very first reveal, the mines are lifted again, so the next
  reveal is a safe first click once more.

Real captured session (`--seed 1`, moves piped in, `MINESWEEP_HOME` set to a
temporary directory):

```text
$ minesweep play --seed 1
New game: beginner 9x9, 10 mines, seed 1. Type ? for help.
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . . . . . . .
5 . . . . . . . . .
6 . . . . . . . . .
7 . . . . . . . . .
8 . . . . . . . . .
9 . . . . . . . . .
Mines left: 10   Time: 0s
> u
nothing to undo
> r E5
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5        [ ]    1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1
Mines left: 10   Time: 0s
> f B9
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 .[F]. . . . . 1
Mines left: 9   Time: 0s
> u
Undid flag B9.
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5        [ ]    1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1
Mines left: 10   Time: 0s
> f A9
  A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9[F]. . . . . . 1
Mines left: 9   Time: 0s
> q
Quit without saving.
```

### Last move and scripted input

After every move the board marks the cell you just played with square
brackets, so on a big board you can see at a glance where you were: `[F]` for
a flag, `[ ]` or `[3]` for a reveal, and the number you chorded on for a chord.
The brackets take the place of the spaces between cells, so the columns stay
lined up, and they show up without colour too. After `u` the mark moves back to
the move before; after `minesweep resume` it is restored from the save file's
move history (saves from v0.1, which have no history, start with no mark).

When input is piped in, the game repeats each command after the `>` prompt so
a transcript reads like a typed session (that is how the samples above were
made). If you drive the game from a script and only want its replies, pass
`--no-echo` to `play` or `resume`. Typed input on a terminal is never echoed
twice either way. A real captured run:

```text
$ printf 'r E5\nf A9\nc B8\nZ1\nq\n' | minesweep play --seed 1 --no-echo
New game: beginner 9x9, 10 mines, seed 1. Type ? for help.
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . . . . . . .
5 . . . . . . . . .
6 . . . . . . . . .
7 . . . . . . . . .
8 . . . . . . . . .
9 . . . . . . . . .
Mines left: 10   Time: 0s
>   A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5        [ ]    1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1
Mines left: 10   Time: 0s
>   A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9[F]. . . . . . 1
Mines left: 9   Time: 0s
>   A B C D E F G H I
1           2 . . .
2           2 . . .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1[1]2 . . . . 1
9 F 1 1 . . . . 1
Mines left: 9   Time: 0s
> column Z is off the board (A-I)
> Quit without saving.
```

### Colour

`--color auto` (the default) colours the numbers only when output is a
terminal and the `NO_COLOR` environment variable is not set. Use
`--color always` or `--color never` to force it either way.

### Where saves and scores live

| Platform | Directory |
| --- | --- |
| Windows | `%APPDATA%\minesweep` |
| Linux / other | `$XDG_DATA_HOME/minesweep`, or `~/.local/share/minesweep` |
| Any (override) | `$MINESWEEP_HOME` |

It holds `save.json` (one saved game, including its move history for undo) and `scores.json` (top 10 times per
difficulty). Both are plain JSON.

## Development

```sh
git clone https://github.com/Chad9100/minesweep.git
cd minesweep
python -m venv .venv
# activate it, then:
pip install -e ".[dev]"
pytest -q
```

Layout:

- `src/minesweep/board.py` - the game rules. Pure logic, no I/O; mine placement
  is deterministic for a given seed and the clock is injectable, so every rule
  is tested without sleeping or randomness.
- `src/minesweep/render.py` - turns a board into text (colour and ASCII fallback).
- `src/minesweep/storage.py` - save file and best times in the per-user data directory.
- `src/minesweep/cli.py` - argument parsing and the turn-based game loop.
- `tests/` - pytest suite, including full scripted games through fake stdin.
  The tests always set `MINESWEEP_HOME` to a temporary directory, so they never
  touch your real saves or scores.

CI runs the suite on Ubuntu and Windows with Python 3.10, 3.12 and 3.13
(`.github/workflows/tests.yml`). See [ROADMAP.md](ROADMAP.md) for what's next.

## License

MIT, see [LICENSE](LICENSE).
