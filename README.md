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
- **Built with:** Python 3.10+ and the standard library only. The default
  turn-based mode needs no curses, so it works the same in Windows Terminal,
  PowerShell, cmd.exe, macOS and Linux; an optional full-screen mode
  (`--tui`) uses curses. Tests use pytest.

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
minesweep play --no-guess                   # a board you can clear by logic alone
minesweep daily                             # today's daily challenge, same board for everyone
minesweep resume                            # continue a saved game
minesweep play --tui                        # full screen with the arrow keys (see below)
minesweep play --seed 1 --no-echo < moves.txt   # scripted: don't repeat piped commands
minesweep scores                            # best times per difficulty
minesweep scores --daily                    # your daily challenge results
minesweep stats                             # games played, win rate, streaks
minesweep export records.json               # records to one file; `import` merges it back
minesweep scores --reset                    # start the best times over (asks first)
```

Columns are letters (`A`, `B`, ... `Z`, `AA`, ...), rows are numbers starting at 1.

| Command | What it does |
| --- | --- |
| `r B3` (or just `B3`) | Reveal a cell. Empty cells open their whole region automatically. |
| `f B3` | Flag or unflag a hidden cell you think is a mine. |
| `c B3` | Chord: on a revealed number whose mines are all flagged, reveal every other neighbour at once. A wrong flag means you lose. |
| `u` | Undo your last move (reveal, flag or chord). Repeat to go further back. |
| `h` | Hint: show one move the board proves is right. A hinted game is not ranked. |
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
  boards, daily challenges, and games where you used undo or a hint or
  played a no-guess board, are not.

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
twice either way. A UTF-8 byte order mark at the start of a line, which Windows
PowerShell can put in front of piped text (`'r E5', 'q' | minesweep play`), is
ignored rather than making the first command unknown. A real captured run:

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

### Hints

Stuck? Type `h` and the game names one move the visible board proves is
right, together with the solver rule that proves it (see the table below):

- a hidden cell that is certainly safe (`r` it), or failing that
- a flag you placed on a cell that is certainly safe (take it off: a wrong
  flag makes a chord lose), or failing that
- a cell that is certainly a mine (`f` it).

Among equal choices it picks the cell closest to your last move. The hint only
uses what you can see, never where the mines really are, so when nothing is
certain it says so and the next move is a guess. Before your first reveal
there is nothing to hint: the first reveal is always safe.

A game in which you took a hint is not ranked. The status line shows how many
hints you used, and the count is kept in the save file (saves from earlier
versions load with 0). Asking again in the same position, without a move in
between, gives the same hint and is not counted twice; a "no certain move"
answer is not counted at all. `?` (or `help`) shows the command list.

Real captured session (`--seed 1`, moves piped in, `MINESWEEP_HOME` set to a
temporary `demo-home`):

```text
$ printf 'h\nr E5\nh\nh\nr H2\nf A9\nh\ns\n' | minesweep play --seed 1
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
> h
No hint needed yet: your first reveal is always safe.
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
> h
Hint (single rule): H2 is safe. Reveal it: r H2  (1 hint used, so this game is not ranked)
> h
Hint (single rule): H2 is safe. Reveal it: r H2  (1 hint used, so this game is not ranked)
> r H2
  A B C D E F G H I
1           2 . . .
2           2 .[5].
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1
Mines left: 10   Time: 0s   Hints: 1
> f A9
  A B C D E F G H I
1           2 . . .
2           2 . 5 .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9[F]. . . . . . 1
Mines left: 9   Time: 0s   Hints: 1
> h
Hint (single rule): B9 is safe. Reveal it: r B9  (2 hints used, so this game is not ranked)
> s
Game saved to demo-home\save.json. Continue with: minesweep resume
$ minesweep resume
Resuming: beginner 9x9, 10 mines, seed 1. Type ? for help.
  A B C D E F G H I
1           2 . . .
2           2 . 5 .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9[F]. . . . . . 1
Mines left: 9   Time: 0s   Hints: 2
> q
Quit without saving. Your earlier save is still there.
```

After `f A9` the hint moves to B9, right next to the flag, rather than a safe
cell further away.

### No-guess boards

Some random boards end in a pure coin flip: the seed 1 board above finishes
with one mine in either H1 or I1 and nothing on the board can tell which.
`minesweep play --no-guess` avoids that. When you make your first reveal, the
game keeps drawing mine placements until the [solver](#solver) can clear the
whole board from that click using logic alone, so every position has at least
one provably safe cell to reveal (and `h` can always name one).

- It is still reproducible: the placements come from the seed's own random
  sequence, so the same seed and the same first click give the same board.
  If the seed's normal board already qualifies, you get exactly that board.
- The search is quick: a few milliseconds on beginner, typically well under a
  second on expert. It gives up after 1000 placements (for example on a tiny,
  crowded custom board where every layout is a coin flip); you are told, and
  the game goes on with the normal board for that seed.
- No-guess games are not ranked in `minesweep scores`, because they are
  easier than the classic boards the table is for.
- The mode is kept in the save file. Saves from earlier versions load as
  normal games. Undoing your first reveal and making it again rebuilds the
  same no-guess board.

Real captured session: the same `--seed 1` and first click as above, now with
`--no-guess` (`MINESWEEP_HOME` set to a temporary `demo-home`).

```text
$ printf 'r E5\nh\ns\n' | minesweep play --seed 1 --no-guess
New game: beginner 9x9, 10 mines, seed 1, no guessing. Type ? for help.
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
1 . . . . . 1
2 . . . . . 1
3 . . . 2 1 1
4 . . . 1
5 . . . 1[ ]
6 . . . 1 1 1
7 . . . . . 1   1 1
8 . . . . 3 1   1 .
9 . . . . 2     1 .
Mines left: 10   Time: 0s
> h
Hint (single rule): C3 is safe. Reveal it: r C3  (1 hint used, so this game is not ranked)
> s
Game saved to demo-home\save.json. Continue with: minesweep resume
$ minesweep resume
Resuming: beginner 9x9, 10 mines, seed 1, no guessing. Type ? for help.
```

Following the hints all the way, every move is a certain reveal and the 24th
wins; no flag is ever needed. The end of that real run:

```text
$ printf 'r E5\nr C3\nr B2\nr C2\nr D2\nr E1\nr C1\nr B1\nr A3\nr C5\nr C6\nr B7\nr C7\nr D7\nr C8\nr B9\nr A8\nr A7\nr A6\nr A5\nr B6\nr A9\nr C9\nr I9\n' \
    | minesweep play --seed 1 --no-guess --no-echo | tail -13
>   A B C D E F G H I
1 F 1 1 F 2 1
2 1 1 1 2 F 1
3   1 1 2 1 1
4 1 2 F 1
5 1 F 2 1
6 1 1 1 1 1 1
7 1 1 2 2 F 1   1 1
8 1 F 3 F 3 1   1 F
9 1 1 3 F 2     1[1]
Mines left: 0   Time: 0s
You win! Cleared in 0.0s.
You used a no-guess board, so this game is not ranked.
```

### Daily challenge

`minesweep daily` deals the day's challenge: the same board for everyone who
plays it that day, so you can compare notes (or times) with friends.

- The seed is the UTC date written as `YYYYMMDD` (seed `20261110` on
  10 November 2026), and the day turns over at midnight UTC, wherever you are.
- Because mines are placed after the first click, the game makes that click
  for you: it opens the centre cell (E5 on beginner, I9 on intermediate, P9 on
  expert), which is always an empty cell with an open area around it. That
  opening cannot be undone, and the clock starts on your first own reveal.
- `--difficulty` / `-d` picks the board size (default beginner), and
  `--date YYYY-MM-DD` replays an earlier day's challenge. Dates after today
  (UTC) are refused with exit code 2.
- A daily is an ordinary game otherwise: `u`, `h`, save and `minesweep resume`
  all work, and the save remembers which day's challenge it is (saves from
  earlier versions load as normal games). You can also replay a daily as a
  normal game with `minesweep play --seed 20261110` and `r E5`.
- Daily wins are not entered in the regular best-times table. They go in a
  separate daily table instead, see below.

When a daily ends, win or lose, the game records the result and prints a
one-line summary you can paste to friends. It gives nothing away about where
the mines are:

```text
Share: minesweep daily 2026-11-09 beginner: cleared in 41.2s
Share: minesweep daily 2026-11-09 beginner: hit a mine after 0.0s, 56/71 safe cells open (78%)
```

- Only your **first finished attempt** at a day's challenge counts, so
  replaying a day after seeing its mines cannot improve it. A replay says
  `You already finished the 2026-11-09 beginner daily; only your first result
  counts.` and repeats the first result's line. Quitting or saving does not
  finish a daily, so nothing is recorded until you win or lose.
- The cells in the opening the game makes for you count towards "safe cells
  open".
- A win where you used undo or a hint is recorded and shared with
  `(assisted)`, but it is not ranked.
- `minesweep scores --daily` shows, per difficulty, how many dailies you
  played and won, your 10 fastest unassisted daily wins (ties go to the
  earlier day), and the share line of your latest day.

Real output after the losing game above:

```text
$ minesweep scores --daily
Daily challenge results (only your first attempt each day counts)

beginner (9x9, 10 mines)
  played 1, won 0
  no ranked wins yet (wins with undo or a hint are not ranked)
  latest: minesweep daily 2026-11-09 beginner: hit a mine after 0.0s, 56/71 safe cells open (78%)

intermediate (16x16, 40 mines)
  not played yet

expert (30x16, 99 mines)
  not played yet
```

Real captured session, played on 10 November 2026 (UTC) with the moves piped
in and `MINESWEEP_HOME` set to a temporary `demo-home`:

```text
$ printf 'u\nf G8\nr G9\ns\n' | minesweep daily
Daily challenge 2026-11-10: beginner 9x9, 10 mines, seed 20261110. Type ? for help.
E5 was opened for you, so everyone starts from the same board. The clock starts on your first reveal.
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . 2 2 2 1 1 .
5 . . . 2       1 .
6 . . . 2       1 .
7 . . . 2   1 1 1 .
8 . . . 2   1 . . .
9 . . . 1   1 . . .
Mines left: 10   Time: 0s
> u
nothing to undo
> f G8
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . 2 2 2 1 1 .
5 . . . 2       1 .
6 . . . 2       1 .
7 . . . 2   1 1 1 .
8 . . . 2   1[F]. .
9 . . . 1   1 . . .
Mines left: 9   Time: 0s
> r G9
  A B C D E F G H I
1 . . . . . . . . .
2 . . . . . . . . .
3 . . . . . . . . .
4 . . . 2 2 2 1 1 .
5 . . . 2       1 .
6 . . . 2       1 .
7 . . . 2   1 1 1 .
8 . . . 2   1 F . .
9 . . . 1   1[1]. .
Mines left: 9   Time: 0s
> s
Game saved to demo-home\save.json. Continue with: minesweep resume
$ minesweep resume
Resuming daily challenge 2026-11-10: beginner 9x9, 10 mines, seed 20261110. Type ? for help.
$ minesweep daily --date 2026-11-11
minesweep: error: the daily challenge for 2026-11-11 is not out yet (today is 2026-11-10 UTC)
```

### Statistics

Every game you finish on a standard difficulty (beginner, intermediate,
expert) is counted, win or lose, and the game ends with your running totals
for that difficulty:

```text
BOOM! You hit a mine at A3. Game over after 0.0s.
Stats: beginner: 1 played, 0 won (0%), win streak 0 (best 0)
```

After a few games it reads like
`Stats: beginner: 4 played, 3 won (75%), win streak 1 (best 2), average win 41.2s`.

- Unlike the best-times table, the statistics include every finished game:
  games with undo or a hint, no-guess boards and daily challenges (replays
  too). Custom boards are not counted.
- Quitting or saving does not finish a game, so it does not count, and a
  resumed game counts once, when it ends.
- The win streak is the number of wins since your last loss; the average is
  over winning times only.

`minesweep stats` shows the totals for every difficulty at once:

```text
$ minesweep stats
Statistics (every finished game on a standard board; custom boards are not counted)

  beginner: 4 played, 3 won (75%), win streak 1 (best 2), average win 41.2s
  intermediate: 1 played, 0 won (0%), win streak 0 (best 0)
  expert: no games finished yet

  all: 5 played, 3 won (60%)
```

### Starting over

Each kind of record can be wiped on its own; the others, and your saved game,
are kept:

```sh
minesweep scores --reset            # best times (scores.json)
minesweep scores --daily --reset    # daily challenge results (daily.json)
minesweep stats --reset             # statistics (stats.json)
```

It asks first and only deletes on `y` or `yes`; anything else, including the
end of piped input, keeps the file and exits with code 1. Add `--yes` (`-y`)
to skip the question in scripts:

```text
$ minesweep scores --reset
Delete your best times? This cannot be undone. [y/N] n
Nothing deleted.
$ minesweep stats --reset --yes
Deleted your statistics.
```

### Moving records between machines

`minesweep export` writes your best times, daily results and statistics to one
JSON file (or to standard output without a file name); `minesweep import`
merges such a file into the records on another machine. Saved games are not
included.

```text
$ minesweep export records.json
Exported your records to records.json.
$ minesweep import records.json
Imported 1 best time(s) and 0 daily result(s); statistics replaced for 1 difficulty(ies).
$ minesweep import records.json
Imported 0 best time(s) and 0 daily result(s); statistics replaced for 0 difficulty(ies).
```

Importing is safe to repeat: best times are combined (identical entries kept
once, top 10 per difficulty), a daily result you already have for a day is
kept, and for statistics the side with more games played wins per difficulty
(counts are not added together). A file that is not an export, or was written
by a newer minesweep, is refused and nothing is changed.

### Full-screen mode

Add `--tui` to `play`, `daily` or `resume` to play full screen: move a cursor
with the arrow keys instead of typing coordinates. It uses curses, which comes
with Python on Linux and macOS; on Windows install the extra first:

```sh
pip install -e ".[tui]"     # adds windows-curses on Windows, nothing elsewhere
minesweep play --tui
```

| Key | What it does |
| --- | --- |
| arrow keys | Move the cursor (shown in square brackets). |
| space, Enter or `r` | Reveal the cell; on a revealed number, chord. |
| `f` | Flag or unflag the cell. |
| `c` | Chord on the cell. |
| `u` | Undo; the cursor jumps to the cell that was undone. |
| `h` | Hint: the cursor jumps to a cell the board proves (not ranked). |
| `s` | Save and quit (`minesweep resume --tui` continues). |
| `q` or Esc | Quit without saving. |
| `?` | Show the keys. |
| left click | Move the cursor to the cell and reveal it (chord on a revealed number). |
| right click | Move the cursor to the cell and flag or unflag it. |

The screen after revealing E5 on `--seed 1` and flagging G2 (rendered by
`minesweep.tui.Session`, the same code that feeds curses):

```text
minesweep  beginner 9x9, 10 mines

  A B C D E F G H I
1           2 . . .
2           2[F]. .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . . . . 1
9 . . . . . . . 1

Mines left: 9   Time: 0s   Cursor: G2
Press ? for keys.
arrows move   space/enter reveal (chord on a number)   f flag   u undo   h hint   s save+quit   q quit
```

When the game ends, or you save or quit, the screen is restored and the final
board is printed with the same result lines as the turn-based mode, so wins
are ranked and counted in `minesweep stats` the same way. Saves are shared:
a game saved in one mode resumes in the other. `--tui` needs a real terminal
and exits with code 2 when input or output is redirected, or when curses is
missing (with the install command above). Mouse clicks need a terminal that reports them; the keyboard always works.

Numbers, flags, mines and hidden cells are coloured with the same palette as
the turn-based mode, on terminals that support colour. `--color never` or the
`NO_COLOR` environment variable turns it off (`--color always` forces it on);
the default `auto` colours only when `NO_COLOR` is unset.

### Solver

`minesweep.solver.analyze(board)` works out which hidden cells the visible
board *proves* safe and which it proves are mines. The `h` hint command above
is built on it, and you can also call it yourself on any board, including a
saved game. It only
uses what a player can see: the numbers on revealed cells and the total mine
count. It never peeks at where the mines are, and it ignores your flags (a
flag is a guess, not a fact). Each answer names the rule that found it:

| Rule | Meaning |
| --- | --- |
| `single` | A number whose hidden neighbours must all be mines, or must all be safe. |
| `subset` | One number's hidden neighbours are a subset of another's, so the cells only the bigger one sees hold the difference. |
| `count` | The same reasoning over the whole board with the mines still unaccounted for (useful in the endgame). |
| `enumeration` | Every mine arrangement along a stretch of the border is tried; a cell that is the same in all of them is certain. |

Very large border groups that would take too long to enumerate are skipped,
which only means fewer answers, never a wrong one. When nothing is certain,
`result.stuck` is true: the next move has to be a guess.

A real run: play a few moves of `--seed 1` and save, then analyse the save
(`MINESWEEP_HOME` pointed at a temporary `demo-home`).

```text
$ printf 'r E5\nr H2\nr E8\nr F8\nr G9\nr B9\nr C9\nr D9\ns\n' | minesweep play --seed 1 --no-echo | tail -12
>   A B C D E F G H I
1           2 . . .
2           2 . 5 .
3           1 1 4 .
4               2 .
5               1 1
6     1 1 1
7     2 . 2 1 1 1
8 1 1 2 . 2 1 . 1
9 . 1 1[1]. . 1 1
Mines left: 10   Time: 0s
> Game saved to demo-home\save.json. Continue with: minesweep resume
$ python analyze.py
 E9 safe (single)
 F9 safe (single)
 G1 mine (single)
 G2 mine (single)
 I2 mine (single)
 I3 mine (single)
 I4 mine (single)
 D7 mine (single)
 D8 mine (single)
 G8 mine (single)
 A9 mine (single)
```

H1 and I1 are not listed: one of them is the last mine, and nothing on the
board can tell which. `analyze.py` is:

```python
from minesweep.board import cell_label
from minesweep.solver import analyze
from minesweep.storage import load_game

board = load_game()
result = analyze(board)
for name, found in (("safe", result.safe), ("mine", result.mines)):
    for cell, rule in sorted(found.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"{cell_label(cell):>3} {name:<4} ({rule})")
if result.stuck:
    print("nothing is certain: the next move is a guess")
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

It holds `save.json` (one saved game, including its move history for undo), `scores.json` (top 10 times per
difficulty) and `daily.json` (your first result for each daily challenge) and `stats.json` (games
played and won, streaks and total winning time per difficulty). All are plain JSON.
`scores.json`, `daily.json` and `stats.json` carry a `"version"` number (currently 1); files
without one are read as version 1. If a file was written by a newer minesweep, this one stops
with an error naming the file instead of overwriting it. Upgrade, or delete the file. Release
history is in [CHANGELOG.md](CHANGELOG.md).

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
- `src/minesweep/solver.py` - constraint solver: which hidden cells the visible
  board proves safe or mined. Pure logic like `board.py`.
- `src/minesweep/render.py` - turns a board into text (colour and ASCII fallback).
- `src/minesweep/storage.py` - save file, best times, daily results and statistics in the
  per-user data directory.
- `src/minesweep/cli.py` - argument parsing and the turn-based game loop.
- `tests/` - pytest suite, including full scripted games through fake stdin.
  The tests always set `MINESWEEP_HOME` to a temporary directory, so they never
  touch your real saves or scores.

CI runs the suite on Ubuntu and Windows with Python 3.10, 3.12 and 3.13
(`.github/workflows/tests.yml`). See [ROADMAP.md](ROADMAP.md) for what's next.

## License

MIT, see [LICENSE](LICENSE).
