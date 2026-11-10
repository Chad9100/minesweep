# Changelog

All notable changes to minesweep. The package is not on PyPI yet, so nothing
below has a release number; the headings follow the roadmap stages.

## Unreleased

### Added

- Playable core: seeded mines with a safe first click, flood fill, flags,
  chording, win/loss detection, `play`, `resume` and `scores`, presets and
  validated custom boards, save/resume, top-10 best times, colour output.
- `u` undo with a move history in the save file; last-move highlight and
  `--no-echo`.
- Constraint solver, the `h` hint command (hinted games are not ranked) and
  `play --no-guess` boards.
- `minesweep daily`: one seeded board per UTC date, a separate daily
  leaderboard and a shareable result line.
- Statistics per difficulty, `minesweep stats` and `--reset` for scores,
  daily results and stats.
- `--tui` full-screen curses mode with keyboard, mouse and colour.
- `minesweep export [FILE]` and `minesweep import FILE` to move best times,
  daily results and statistics between machines; importing merges and can be
  repeated safely.
- A `version` field in `scores.json`, `daily.json` and `stats.json`; a file
  written by a newer minesweep is refused with a clear message instead of being
  overwritten. Files without the field (all earlier ones) load as version 1.

- `minesweep.hexgrid`: hexagonal grid geometry (odd-r offset rows, six
  neighbours, distance) and a text layout for it. A building block for hex
  boards; the game itself does not use it yet.

### Fixed

- A UTF-8 byte order mark on piped input (Windows PowerShell) no longer makes
  the first command unknown.
