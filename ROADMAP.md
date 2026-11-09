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
- [ ] Show the last move's cell highlighted; `--no-echo` for scripted input (1 h)

## v0.3 - hints and a solver (~5 h)

- [ ] Constraint solver that finds certainly-safe cells and certain mines (3 h)
- [ ] `h` hint command built on it; hinted games are marked and not ranked (1 h)
- [ ] Optional "no guessing" boards: re-roll placement until the solver can finish (1 h)

## v0.4 - daily seeded challenge (~3 h)

- [ ] `minesweep daily`: seed derived from the UTC date, same board for everyone (1.5 h)
- [ ] Separate daily leaderboard and a shareable one-line result (1.5 h)

## v0.5 - statistics (~3 h)

- [ ] Games played/won, win rate, streaks and average time per difficulty (2 h)
- [ ] `minesweep stats` view and `minesweep scores --reset` (1 h)

## v0.6 - full-screen UI as an optional extra (~6 h)

- [ ] `pip install minesweep-cli[tui]` adds a Textual (or curses where available)
      full-screen mode with arrow keys and mouse clicks (5 h)
- [ ] Keep the turn-based mode as the default and dependency-free (1 h)

## v0.7 - hex boards (~4 h)

- [ ] Hexagonal grid geometry (6 neighbours) behind the same board API (2.5 h)
- [ ] Rendering and coordinates for offset hex rows (1.5 h)

## v1.0 - release on PyPI (~2 h)

- [ ] Trusted-publishing release workflow and a `minesweep-cli` PyPI release (1 h)
- [ ] Changelog, versioned save format migration, final docs pass (1 h)

**Total remaining: about 24 hours.**
