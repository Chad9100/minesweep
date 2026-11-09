"""Constraint solver: certain safe cells and certain mines from the visible board."""

import random

import pytest

from minesweep.board import Board, make_config
from minesweep.solver import COUNT, ENUMERATION, SINGLE, SUBSET, analyze


def opened(rows, *cells):
    """A fixed layout with the given cells revealed (zeros flood-fill as in play)."""
    board = Board.from_layout(rows)
    for cell in cells:
        board.reveal(cell)
    return board


def test_nothing_is_known_before_the_first_reveal():
    board = Board(make_config(9, 9, 10), seed=1)
    result = analyze(board)
    assert result.stuck and result.safe == {} and result.mines == {}


def test_single_and_count_rules():
    #   A B C D
    # 1                D1 floods the top open. A2 is a 1 that sees only A3/B3,
    # 2 1 1 1          C2 a 1 that sees only B3, so B3 is the mine and A3 is
    # 3 . . 1          safe; C3 and C4 then clear B4. A4 touches no number,
    # 4 . . 1          so only the mine total (1, already found) proves it safe.
    board = opened(
        ["....",
         "....",
         ".*..",
         "...."],
        (3, 0),
    )
    result = analyze(board)
    assert result.mines == {(1, 2): SINGLE}
    assert result.safe == {(0, 2): SINGLE, (1, 3): SINGLE, (0, 3): COUNT}


def test_subset_rule_on_three_ones_against_a_wall():
    #   A B C D E
    # 1 . . . 1        D1/D2/D3 all show 1. D2 sees C1:C3, D1 sees C1:C2,
    # 2 . . . 1        so C3 is safe (subset); likewise C1. That leaves C2,
    # 3 . . . 1        which D2 then proves a mine.
    board = opened(
        [".....",
         "*.*..",
         "....."],
        (4, 0),
    )
    result = analyze(board)
    assert result.safe == {(2, 0): SUBSET, (2, 2): SUBSET}
    assert result.mines == {(2, 1): SINGLE}


def test_one_two_one_pattern():
    # Classic 1-2-1 along a wall: the mines sit under the two 1s.
    board = opened(
        ["*.*.",
         "....",
         "....",
         "...."],
        (0, 3),
    )
    result = analyze(board)
    assert set(result.mines) == {(0, 0), (2, 0)}
    assert set(result.safe) == {(1, 0), (3, 0)}
    assert SUBSET in set(result.mines.values()) | set(result.safe.values())


def test_a_true_fifty_fifty_is_reported_as_stuck():
    #   A B C D E F
    # 1 . 1     1 .    One mine in A1/A2 and one in F1/F2: nothing on the
    # 2 . 1     1 .    board (or the total of 2) can tell which.
    board = opened(
        ["*.....",
         ".....*"],
        (2, 0),
    )
    assert board.revealed == {(x, y) for x in range(1, 5) for y in range(2)}
    result = analyze(board)
    assert result.stuck and result.skipped == 0


def test_enumeration_rule_is_needed_on_some_positions():
    # Seeded random positions: the enumeration step must fire somewhere,
    # proving it adds deductions beyond single/subset/count.
    used = set()
    for seed in range(1, 40):
        board = Board(make_config(16, 16, 40), seed)
        board.reveal((8, 8))
        for _ in range(60):
            result = analyze(board)
            used |= set(result.safe.values()) | set(result.mines.values())
            if result.stuck or board.over:
                break
            for cell in result.safe:
                if not board.over and cell not in board.revealed:
                    board.reveal(cell)
        if ENUMERATION in used:
            break
    assert ENUMERATION in used


def test_flags_are_ignored_even_wrong_ones():
    rows = ["....", "....", ".*..", "...."]
    board = opened(rows, (3, 0))
    board.toggle_flag((1, 2))  # a right flag: still reported as a mine
    assert set(analyze(board).mines) == {(1, 2)}

    board = opened(rows, (3, 0))
    board.toggle_flag((0, 2))  # a wrong flag must not fool the solver
    result = analyze(board)
    assert (0, 2) in result.safe
    assert set(result.mines) == {(1, 2)}


def test_analysis_does_not_change_the_board():
    board = Board(make_config(9, 9, 10), seed=1, clock=lambda: 0.0)
    board.reveal((4, 4))
    board.toggle_flag((0, 8))
    before = board.to_dict()
    analyze(board)
    assert board.to_dict() == before


def test_finished_game_has_nothing_to_analyze():
    board = opened(["*.", ".."], (1, 1))
    board.reveal((0, 0))  # boom
    assert board.over and analyze(board).stuck


def test_tiny_budget_skips_groups_instead_of_guessing():
    board = Board(make_config(30, 16, 99), seed=7)
    board.reveal((15, 8))
    full = analyze(board)
    tight = analyze(board, step_budget=1)
    # A starved search may find less, but never anything the full one disagrees with.
    assert set(tight.safe) <= set(full.safe)
    assert set(tight.mines) <= set(full.mines)
    assert full.skipped == 0 and tight.skipped > 0
    assert len(tight.safe) + len(tight.mines) < len(full.safe) + len(full.mines)


@pytest.mark.parametrize("difficulty", ["beginner", "intermediate", "expert"])
def test_every_answer_is_correct_on_many_seeded_games(difficulty):
    """Soundness: play by the solver and check each claim against the real mines."""
    from minesweep.board import DIFFICULTIES

    cfg = DIFFICULTIES[difficulty]
    rng = random.Random(difficulty)
    checked = 0
    for seed in range(1, 16):
        board = Board(cfg, seed)
        board.reveal((cfg.width // 2, cfg.height // 2))
        while not board.over:
            result = analyze(board)
            for cell in result.mines:
                assert cell in board.mines, (seed, cell)
            for cell in result.safe:
                assert cell not in board.mines, (seed, cell)
            checked += len(result.mines) + len(result.safe)
            if result.safe:
                for cell in result.safe:
                    if cell not in board.revealed:
                        board.reveal(cell)
            else:
                # Stuck: take a random guess so the game moves on.
                hidden = [
                    (x, y) for y in range(cfg.height) for x in range(cfg.width)
                    if (x, y) not in board.revealed
                ]
                board.reveal(rng.choice(sorted(hidden)))
    assert checked > 100


def test_solver_alone_clears_some_beginner_boards():
    wins = 0
    for seed in range(1, 31):
        board = Board(make_config(9, 9, 10), seed)
        board.reveal((4, 4))
        while not board.over:
            result = analyze(board)
            if result.stuck:
                break
            for cell in result.safe:
                if cell not in board.revealed:
                    board.reveal(cell)
            if not result.safe:
                break  # only mines left to find: the game is already won
        wins += board.state == "won"
    assert wins >= 10
