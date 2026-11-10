# Roadmap

Estimates are rough working hours for one person, including tests and docs.

## v0.1 - playable core (done)

- [x] Pure game logic: seeded mine placement after a guaranteed-safe first click
- [x] Iterative flood fill, flags, chording (wrong flag loses), win/loss detection
- [x] Turn-based CLI: `play`, `resume`, `scores`; `r`/`f`/`c`/`s`/`q`/`?` commands
- [x] Beginner / intermediate / expert presets and validated custom boards (exit code 2)
- [x] Save/resume and top-10 best times in a per-user data directory
- [x] Colour on terminals (`--color`, `NO_COLOR`) with an ASCII fallback
- [x] pytest suite with scripted games; CI on Ubuntu and Windows, Python 3.10-3.13

## v0.2 - undo and quality of life (~3 h)

- [x] `u` undo the last move, with a move history kept in the save file (2 h)
- [x] Show the last move's cell highlighted; `--no-echo` for scripted input (1 h)

## v0.3 - hints and a solver (~5 h)

- [x] Constraint solver that finds certainly-safe cells and certain mines (3 h)
      (`minesweep.solver.analyze`: single, subset, mine-total and enumeration rules;
      wired into the game by the `h` item below)
- [x] `h` hint command built on it; hinted games are marked and not ranked (1 h)
      (safe reveal first, then a provably wrong flag, then a certain mine; nearest
      the last move; the hint count is shown in the status line and saved)
- [x] Optional "no guessing" boards: re-roll placement until the solver can finish (1 h)
      (`play --no-guess`; placements drawn from the seed's own sequence, so it stays
      reproducible; up to 1000 tries, then the normal board with a warning; not ranked)

## v0.4 - daily seeded challenge (~3 h)

- [x] `minesweep daily`: seed derived from the UTC date, same board for everyone (1.5 h)
      (seed = the date as YYYYMMDD; the centre cell is opened for you so the board
      does not depend on your first click; `--date` replays earlier days, future
      dates are refused; the date is kept in the save; not in the regular table)
- [x] Separate daily leaderboard and a shareable one-line result (1.5 h)
      (`daily.json` keeps only the first finished attempt per day and difficulty;
      `Share:` line on every finished daily; `minesweep scores --daily` ranks
      unassisted wins; undo/hint wins are recorded as assisted)

## v0.4.1 - input fixes (~0.5 h)

- [x] Strip a UTF-8 byte order mark from piped input: Windows PowerShell's
      `'r E5' | minesweep play` prefixes the first line with U+FEFF, so the
      first command is rejected as unknown (0.5 h)
      (a leading mark is dropped from each input line, both as U+FEFF and as the
      `ï»¿` it becomes when a pipe is decoded as Windows-1252)

## v0.5 - statistics (~3 h)

- [x] Games played/won, win rate, streaks and average time per difficulty (2 h)
      (`stats.json`; every finished game on a standard board counts, including
      assisted, no-guess and daily games; a `Stats:` line ends each such game)
- [x] `minesweep stats` view and `minesweep scores --reset` (1 h)
      (one summary line per difficulty plus an overall total; `--reset` on
      `scores`, `scores --daily` and `stats` deletes just that file after a
      `[y/N]` question, or straight away with `--yes`)

## v0.6 - full-screen UI as an optional extra (~6 h)

The original 5 h item ("a Textual or curses full-screen mode with arrow keys
and mouse clicks") is split into the three steps below.

- [x] `--tui` on `play`, `daily` and `resume`: curses full-screen mode driven
      by the keyboard; `pip install minesweep-cli[tui]` adds windows-curses on
      Windows (1.5 h)
      (arrow-key cursor, space/Enter reveals or chords, `f`/`c`/`u`/`h`/`s`/`q`;
      the key handling is a plain `Session` class tested without a terminal;
      results, saves, scores and stats are shared with the turn-based mode)
- [x] Mouse clicks in `--tui`: left click reveals, right click flags (1.5 h)
      (`Session.cell_at` maps a screen position to a cell and is tested against
      the drawn layout; curses only supplies the click coordinates)
- [ ] Coloured numbers and flags in `--tui` (curses colour pairs, honouring
      `--color` and `NO_COLOR`) (1 h)
- [x] Keep the turn-based mode as the default and dependency-free (1 h)
      (`--tui` is opt-in; curses is imported only when it is used)

## v0.7 - hex boards (~4 h)

- [ ] Hexagonal grid geometry (6 neighbours) behind the same board API (2.5 h)
- [ ] Rendering and coordinates for offset hex rows (1.5 h)

## v1.0 - release on PyPI (~2 h)

- [ ] Trusted-publishing release workflow and a `minesweep-cli` PyPI release (1 h)
- [ ] Changelog, versioned save format migration, final docs pass (1 h)

**Total remaining: about 7 hours.**
