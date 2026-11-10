"""Hints: solver.suggest() picks a certain move; the h command shows it and un-ranks the game."""

import io
import json
import os
from datetime import datetime, timezone

from minesweep import storage
from minesweep.board import Board, cell_label, make_config
from minesweep.cli import main
from minesweep.solver import FLAG, REVEAL, SINGLE, UNFLAG, Hint, suggest


def opened(rows, *cells):
    board = Board.from_layout(rows)
    for cell in cells:
        board.reveal(cell)
    return board


# The position from test_solver: D1 floods the top two rows open, B3 is the
# only mine, and A3, B4 and A4 are provably safe.
CORNER = ["....",
          "....",
          ".*..",
          "...."]

# A 2x4 board with a mine at A1 and one at A3. With B1, A2, B2, A4 and B4
# revealed, B1 = 1 sees only A1 (a certain mine), while the other numbers
# only say "one mine in A3/B3": a true 50/50, so nothing is certainly safe.
FIFTY_FIFTY = ["*.",
               "..",
               "*.",
               ".."]
FIFTY_FIFTY_OPEN = [(1, 0), (0, 1), (1, 1), (0, 3), (1, 3)]


def run(args, script, clock=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(
        args, stdin=io.StringIO(script), stdout=out, stderr=err,
        environ=dict(os.environ), clock=clock,
        now=lambda: datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc),
    )
    return code, out.getvalue(), err.getvalue()


# ----------------------------------------------------------------- suggest()


def test_no_hint_before_the_first_reveal():
    assert suggest(Board(make_config(9, 9, 10), seed=1)) is None


def test_safe_reveal_nearest_the_last_move_comes_first():
    board = opened(CORNER, (3, 0))
    # A3, B4 and A4 are all 3 steps from D1; the top row wins the tie.
    assert suggest(board) == Hint(REVEAL, (0, 2), SINGLE)


def test_hint_follows_the_last_move():
    board = Board(make_config(9, 9, 10), seed=1)
    board.reveal((4, 4))  # E5; safe: H2, E8, F8 (3 away), B9, C9, ... (further)
    board.reveal((7, 1))  # H2
    assert suggest(board).cell == (4, 7)  # E8 and F8 are closest to H2; leftmost wins
    board.toggle_flag((0, 8))  # A9: B9 is right next to it, E8 is not
    assert suggest(board) == Hint(REVEAL, (1, 8), SINGLE)


def test_wrong_flag_is_pointed_out_before_any_mine():
    board = opened(CORNER, (3, 0))
    board.toggle_flag((0, 2))  # A3 is safe, so this flag is wrong
    board.reveal((1, 3))
    board.reveal((0, 3))
    # Every unflagged safe cell is open; B3 (mine) and A3 (bad flag) remain.
    hint = suggest(board)
    assert hint.action == UNFLAG and hint.cell == (0, 2)


def test_flag_hint_when_only_a_mine_is_certain():
    board = opened(FIFTY_FIFTY, *FIFTY_FIFTY_OPEN)
    assert suggest(board) == Hint(FLAG, (0, 0), SINGLE)
    board.toggle_flag((0, 0))
    assert suggest(board) is None  # only the 50/50 is left: a guess


def test_hint_never_depends_on_the_hidden_mines():
    # Same visible board, mines moved inside the 50/50: same answer.
    a = opened(FIFTY_FIFTY, *FIFTY_FIFTY_OPEN)
    b = opened(["*.", "..", ".*", ".."], *FIFTY_FIFTY_OPEN)
    assert a.revealed == b.revealed
    assert suggest(a) == suggest(b)


def test_suggest_leaves_the_board_unchanged():
    board = opened(CORNER, (3, 0))
    before = (set(board.revealed), set(board.flagged), list(board.history), board.hints)
    suggest(board)
    assert (set(board.revealed), set(board.flagged), list(board.history), board.hints) == before


def test_hint_is_always_correct_in_random_games():
    for seed in range(1, 31):
        board = Board(make_config(9, 9, 10), seed)
        board.reveal((4, 4))
        while not board.over:
            hint = suggest(board)
            if hint is None:
                break
            if hint.action == REVEAL:
                assert hint.cell not in board.mines
                board.reveal(hint.cell)
            elif hint.action == FLAG:
                assert hint.cell in board.mines
                board.toggle_flag(hint.cell)
            else:
                assert hint.cell not in board.mines
                board.toggle_flag(hint.cell)
        assert board.state != "lost"


# ------------------------------------------------------------- save format


def test_hint_count_survives_a_save():
    board = opened(CORNER, (3, 0))
    board.hints = 2
    data = json.loads(json.dumps(board.to_dict()))
    assert data["hints"] == 2
    assert Board.from_dict(data).hints == 2


def test_saves_without_a_hint_count_still_load():
    board = opened(CORNER, (3, 0))
    data = board.to_dict()
    del data["hints"]  # saves written before hints existed
    assert Board.from_dict(data).hints == 0


def test_negative_hint_count_is_rejected():
    data = opened(CORNER, (3, 0)).to_dict()
    data["hints"] = -1
    try:
        Board.from_dict(data)
    except ValueError as exc:
        assert "hints" in str(exc)
    else:
        raise AssertionError("expected ValueError")


# --------------------------------------------------------------------- CLI


def test_h_before_first_reveal_is_free(clock):
    _, out, _ = run(["play", "--seed", "1"], "h\nq\n", clock)
    assert "first reveal is always safe" in out
    assert "Hints:" not in out


def test_h_names_a_safe_cell_and_counts_it(clock):
    _, out, _ = run(["play", "--seed", "1"], "r E5\nh\nr H2\nq\n", clock)
    assert "Hint (single rule): H2 is safe. Reveal it: r H2" in out
    assert "(1 hint used, so this game is not ranked)" in out
    assert "Mines left: 10   Time: 0s   Hints: 1" in out  # board after r H2


def test_asking_twice_in_the_same_position_counts_once(clock):
    _, out, _ = run(["play", "--seed", "1"], "r E5\nh\nh\nr H2\nh\nq\n", clock)
    assert out.count("1 hint used") == 2
    assert "2 hints used" in out


def test_h_is_no_longer_help(clock):
    _, out, _ = run(["play", "--seed", "1"], "h\nq\n", clock)
    assert "Commands:" not in out
    _, out, _ = run(["play", "--seed", "1"], "?\nq\n", clock)
    assert "h       hint" in out


def test_hint_count_is_saved_and_resumed(clock):
    run(["play", "--seed", "1"], "r E5\nh\ns\n", clock)
    assert json.loads(storage.save_path().read_text(encoding="utf-8"))["hints"] == 1
    _, out, _ = run(["resume"], "q\n", clock)
    assert "Hints: 1" in out


def test_hinted_win_is_not_ranked(clock):
    b = Board(make_config(9, 9, 10), 42)
    b.reveal((0, 0))
    safe = [
        (x, y) for y in range(9) for x in range(9)
        if (x, y) not in b.mines and (x, y) not in b.revealed
    ]
    script = ["r A1", "h"] + [f"r {cell_label(c)}" for c in safe]
    code, out, err = run(["play", "--seed", "42"], "\n".join(script) + "\n", clock)
    assert code == 0, err
    assert "You win!" in out
    assert "You used 1 hint, so this game is not ranked." in out
    assert storage.load_scores()["beginner"] == []
