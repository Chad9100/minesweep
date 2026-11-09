"""Undo: board-level replay, save format v2 (and v1 compatibility), CLI command."""

import io
import json
import os
from datetime import datetime, timezone

import pytest

from minesweep import storage
from minesweep.board import PLAYING, Board, MoveError, cell_label, make_config
from minesweep.cli import main


def new_board(seed=1, clock=None):
    cfg = make_config(9, 9, 10)
    return Board(cfg, seed, clock) if clock else Board(cfg, seed)


def snapshot(b):
    return (set(b.mines), set(b.revealed), set(b.flagged), b.state, list(b.history))


def hidden_safe(b):
    return next(
        (x, y) for y in range(b.height) for x in range(b.width)
        if (x, y) not in b.revealed and (x, y) not in b.mines and (x, y) not in b.flagged
    )


# ------------------------------------------------------------------ board


def test_moves_are_recorded_in_order():
    b = new_board()
    b.toggle_flag((0, 0))
    b.reveal((4, 4))
    assert b.history == [("flag", (0, 0)), ("reveal", (4, 4))]


def test_rejected_moves_are_not_recorded():
    b = new_board()
    b.reveal((4, 4))
    with pytest.raises(MoveError):
        b.reveal((4, 4))
    with pytest.raises(MoveError):
        b.toggle_flag((4, 4))
    assert b.history == [("reveal", (4, 4))]


def test_undo_reveal_restores_the_exact_position(clock):
    b = new_board(seed=3, clock=clock)
    b.reveal((4, 4))
    before = snapshot(b)
    cell = hidden_safe(b)
    b.reveal(cell)
    assert b.revealed != before[1]
    assert b.undo() == ("reveal", cell)
    assert snapshot(b) == before
    assert b.undos == 1 and b.state == PLAYING


def test_undo_flag_and_undo_unflag():
    b = new_board()
    b.reveal((4, 4))
    cell = next((x, y) for y in range(9) for x in range(9) if (x, y) not in b.revealed)
    b.toggle_flag(cell)
    assert b.undo() == ("flag", cell)
    assert cell not in b.flagged
    b.toggle_flag(cell)
    b.toggle_flag(cell)  # unflag
    b.undo()
    assert cell in b.flagged


def test_undo_chord():
    b = new_board(seed=8)
    b.reveal((4, 4))
    number = next(
        c for c in sorted(b.revealed)
        if b.adjacent_mines(c)
        and any(n not in b.revealed and n not in b.mines for n in b.neighbors(c))
    )
    for n in b.neighbors(number):
        if n in b.mines:
            b.toggle_flag(n)
    before = snapshot(b)
    b.chord(number)
    assert b.revealed != before[1]
    assert b.undo() == ("chord", number)
    assert snapshot(b) == before


def test_undo_does_not_rewind_the_clock(clock):
    b = new_board(clock=clock)
    b.reveal((4, 4))
    clock.advance(5)
    b.reveal(hidden_safe(b))
    clock.advance(3)
    b.undo()
    assert b.elapsed == pytest.approx(8)
    clock.advance(1)
    assert b.elapsed == pytest.approx(9)


def test_undoing_the_first_reveal_lifts_the_mines_and_keeps_the_seed():
    b = new_board(seed=21)
    b.toggle_flag((8, 8))
    b.reveal((4, 4))
    mines = set(b.mines)
    b.undo()
    assert not b.mines_placed and b.revealed == set() and b.flagged == {(8, 8)}
    b.reveal((4, 4))
    assert b.mines == mines
    b.undo()
    b.reveal((0, 0))  # a different first click is still safe
    assert b.state == PLAYING and (0, 0) not in b.mines


def test_fixed_layout_keeps_its_mines_after_undo():
    b = Board.from_layout(["*..", "...", "..*"])
    b.reveal((0, 2))
    b.undo()
    assert b.mines == {(0, 0), (2, 2)} and b.mines_placed


def test_nothing_to_undo_and_no_undo_after_game_over():
    b = new_board()
    with pytest.raises(MoveError, match="nothing to undo"):
        b.undo()
    b.reveal((4, 4))
    b.reveal(sorted(b.mines)[0])
    with pytest.raises(MoveError, match="game is over"):
        b.undo()


def test_several_undos_walk_back_one_move_at_a_time():
    b = new_board(seed=5)
    b.reveal((4, 4))
    positions = [snapshot(b)]
    for _ in range(3):
        b.reveal(hidden_safe(b))
        positions.append(snapshot(b))
    for expected in reversed(positions[:-1]):
        b.undo()
        assert snapshot(b) == expected
    assert b.undos == 3


# ------------------------------------------------------------- save data


def test_history_and_undos_survive_a_save(clock):
    b = new_board(seed=9, clock=clock)
    b.reveal((4, 4))
    b.reveal(hidden_safe(b))
    b.reveal(hidden_safe(b))
    b.undo()
    data = json.loads(json.dumps(b.to_dict()))
    assert data["version"] == 2
    r = Board.from_dict(data, clock)
    assert r.history == b.history and r.undos == 1
    before = snapshot(r)
    r.reveal(hidden_safe(r))
    r.undo()
    assert snapshot(r) == before


def test_version_1_save_still_loads_with_empty_history():
    b = new_board(seed=4)
    b.reveal((4, 4))
    data = b.to_dict()
    data["version"] = 1
    del data["history"], data["undos"]
    r = Board.from_dict(data)
    assert r.revealed == b.revealed and r.history == [] and r.undos == 0
    with pytest.raises(MoveError, match="nothing to undo"):
        r.undo()
    r.reveal(hidden_safe(r))
    r.undo()  # moves made after loading can be undone, back to the loaded position
    assert r.revealed == b.revealed and r.mines == b.mines
    resaved = Board.from_dict(json.loads(json.dumps(r.to_dict())))
    assert resaved.base_revealed == b.revealed
    resaved.reveal(hidden_safe(resaved))
    resaved.undo()
    assert resaved.revealed == b.revealed


@pytest.mark.parametrize(
    "history",
    [
        [["teleport", 4, 4]],
        [["reveal", 50, 50]],
        [["reveal", 4]],
        "nope",
        [["flag", 0, 0]],  # replays fine but does not match the saved board
        [],  # moves missing: the empty base does not match the board
    ],
)
def test_bad_history_is_rejected(history):
    b = new_board()
    b.reveal((4, 4))
    data = b.to_dict()
    data["history"] = history
    with pytest.raises(ValueError):
        Board.from_dict(data)


# ------------------------------------------------------------------- CLI


class Stream(io.StringIO):
    def isatty(self):
        return False

    @property
    def encoding(self):
        return "utf-8"


def play(args, script, clock):
    out, err = Stream(), Stream()
    code = main(
        args, stdin=Stream(script), stdout=out, stderr=err,
        environ=dict(os.environ), clock=clock,
        now=lambda: datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc),
    )
    return code, out.getvalue(), err.getvalue()


def test_cli_undo_command(clock):
    code, out, _ = play(["play", "--seed", "1"], "u\nr E5\nf A9\nu\nundo\nq\n", clock)
    assert code == 0
    assert "nothing to undo" in out
    assert "Undid flag A9." in out and "Undid reveal E5." in out
    assert "u       undo" in play(["play"], "?\nq\n", clock)[1]


def test_win_after_undo_is_not_ranked(clock):
    b = new_board(seed=42)
    b.reveal((0, 0))
    safe = [c for c in sorted(b.revealed ^ {
        (x, y) for y in range(9) for x in range(9) if (x, y) not in b.mines
    })]
    moves = ["r A1", f"f {cell_label(sorted(b.mines)[0])}", "u"] + [f"r {cell_label(c)}" for c in safe]
    code, out, _ = play(["play", "--seed", "42"], "\n".join(moves) + "\n", clock)
    assert code == 0 and "You win!" in out
    assert "You used undo once, so this game is not ranked." in out
    assert storage.load_scores()["beginner"] == []


def test_undo_works_across_save_and_resume(clock):
    play(["play", "--seed", "1"], "r E5\nf A9\ns\n", clock)
    assert json.loads(storage.save_path().read_text(encoding="utf-8"))["history"] == [
        ["reveal", 4, 4], ["flag", 0, 8],
    ]
    code, out, _ = play(["resume"], "u\nu\nu\nq\n", clock)
    assert code == 0
    assert "Undid flag A9." in out and "Undid reveal E5." in out
    assert "nothing to undo" in out
