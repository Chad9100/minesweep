"""No-guess boards: placement re-rolls until the solver can clear the board from the first click."""

import io
import json
import os
from datetime import datetime, timezone

from minesweep import storage
from minesweep.board import DIFFICULTIES, NO_GUESS_TRIES, Board, make_config
from minesweep.cli import main
from minesweep.solver import REVEAL, solves_without_guessing, suggest

BEGINNER = DIFFICULTIES["beginner"]
E5 = (4, 4)

# Found by playing seed 1 from E5 with the hint solver: every move is a
# certain reveal and the last one wins.
SEED1_NO_GUESS_WIN = [
    "r E5", "r C3", "r B2", "r C2", "r D2", "r E1", "r C1", "r B1", "r A3",
    "r C5", "r C6", "r B7", "r C7", "r D7", "r C8", "r B9", "r A8", "r A7",
    "r A6", "r A5", "r B6", "r A9", "r C9", "r I9",
]


def run(args, script):
    out, err = io.StringIO(), io.StringIO()
    code = main(
        args, stdin=io.StringIO(script), stdout=out, stderr=err,
        environ=dict(os.environ),
        now=lambda: datetime(2026, 3, 1, 9, 30, tzinfo=timezone.utc),
    )
    return code, out.getvalue(), err.getvalue()


def placed(config, seed, first=E5, **kwargs):
    board = Board(config, seed, **kwargs)
    board.reveal(first)
    return board


# ------------------------------------------------------ solves_without_guessing


def test_board_that_floods_open_is_solvable():
    config = make_config(3, 3, 1)
    assert solves_without_guessing(config, {(2, 2)}, (0, 0))


def test_a_coin_flip_is_not_solvable():
    # 2x2 with one mine: the first click always shows 1 and the other three
    # cells are equally likely to hold the mine.
    config = make_config(2, 2, 1)
    assert not solves_without_guessing(config, {(1, 1)}, (0, 0))


def test_first_click_on_a_mine_is_not_solvable():
    config = make_config(3, 3, 1)
    assert not solves_without_guessing(config, {(0, 0)}, (0, 0))


def test_needs_logic_beyond_the_first_flood():
    # One row: A1 floods to B1, which shows 1 and sees only C1, so C1 is a
    # mine and the mine count then proves D1 safe.
    config = make_config(4, 1, 1)
    assert solves_without_guessing(config, {(2, 0)}, (0, 0))


def test_flood_that_ends_in_a_coin_flip_is_not_solvable():
    # A2 floods A1, B1 and B2 open; both 1s see C1 and C2 and nothing tells
    # them apart.
    config = make_config(3, 2, 1)
    assert not solves_without_guessing(config, {(2, 0)}, (0, 1))


def test_plain_seed_1_needs_a_guess():
    # The README's seed 1 ends with a 50/50 between H1 and I1.
    board = placed(BEGINNER, 1)
    assert not solves_without_guessing(BEGINNER, board.mines, E5)


# ------------------------------------------------------------ board placement


def test_no_guess_rerolls_seed_1_into_a_solvable_board():
    plain = placed(BEGINNER, 1)
    board = placed(BEGINNER, 1, no_guess=True)
    assert board.no_guess_ok is True
    assert board.mines != plain.mines
    assert len(board.mines) == BEGINNER.mines
    assert solves_without_guessing(BEGINNER, board.mines, E5)
    # The safe zone around the first click still holds.
    assert not board.mines & {E5, *board.neighbors(E5)}


def test_no_guess_placement_is_deterministic():
    a = placed(BEGINNER, 1, no_guess=True)
    b = placed(BEGINNER, 1, no_guess=True)
    assert a.mines == b.mines


def test_already_solvable_first_placement_is_kept():
    for seed in range(2, 40):
        plain = placed(BEGINNER, seed)
        if solves_without_guessing(BEGINNER, plain.mines, E5):
            break
    else:  # pragma: no cover - would mean the placement code changed
        raise AssertionError("no solvable seed found")
    assert placed(BEGINNER, seed, no_guess=True).mines == plain.mines


def test_normal_board_does_not_report_no_guess():
    board = placed(BEGINNER, 1)
    assert board.no_guess is False and board.no_guess_ok is None


def test_impossible_board_falls_back_to_the_normal_placement():
    config = make_config(2, 2, 1)
    plain = placed(config, 5, first=(0, 0))
    board = Board(config, 5, no_guess=True)
    assert board.no_guess_ok is None  # nothing placed yet
    board.reveal((0, 0))
    assert board.no_guess_ok is False
    assert board.mines == plain.mines


def test_hints_can_finish_a_no_guess_board():
    board = placed(BEGINNER, 1, no_guess=True)
    while not board.over:
        hint = suggest(board)
        assert hint is not None and hint.action == REVEAL
        board.reveal(hint.cell)
    assert board.state == "won"


def test_undoing_the_first_reveal_rerolls_the_same_board():
    board = placed(BEGINNER, 1, no_guess=True)
    mines = set(board.mines)
    board.undo()
    assert not board.mines_placed and board.no_guess_ok is None
    board.reveal(E5)
    assert board.mines == mines and board.no_guess_ok is True


# ------------------------------------------------------------------ save files


def test_save_round_trip_keeps_no_guess():
    board = placed(BEGINNER, 1, no_guess=True)
    loaded = Board.from_dict(json.loads(json.dumps(board.to_dict())))
    assert loaded.no_guess is True and loaded.no_guess_ok is True
    assert loaded.mines == board.mines


def test_older_save_without_the_keys_is_a_normal_game():
    data = placed(BEGINNER, 1).to_dict()
    del data["no_guess"], data["no_guess_ok"]
    loaded = Board.from_dict(data)
    assert loaded.no_guess is False and loaded.no_guess_ok is None


def test_bad_no_guess_ok_is_rejected():
    data = placed(BEGINNER, 1, no_guess=True).to_dict()
    data["no_guess_ok"] = "yes"
    try:
        Board.from_dict(data)
    except ValueError as exc:
        assert "no_guess_ok" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("bad value accepted")


# ------------------------------------------------------------------------- CLI


def test_cli_no_guess_win_is_not_ranked():
    script = "\n".join(SEED1_NO_GUESS_WIN) + "\n"
    code, out, err = run(["play", "--seed", "1", "--no-guess", "--color", "never"], script)
    assert code == 0, err
    assert "seed 1, no guessing. Type ? for help." in out
    assert "You win!" in out
    assert "You used a no-guess board, so this game is not ranked." in out
    assert not storage.scores_path().exists()


def test_cli_warns_once_when_no_board_qualifies():
    code, out, _ = run(
        ["play", "--width", "2", "--height", "2", "--mines", "1", "--seed", "5",
         "--no-guess", "--color", "never"],
        "r A1\nh\nq\n",
    )
    assert code == 0
    warning = f"could be solved without guessing in {NO_GUESS_TRIES} tries"
    assert out.count(warning) == 1


def test_cli_resume_remembers_no_guess():
    run(["play", "--seed", "1", "--no-guess", "--color", "never"], "r E5\ns\n")
    saved = json.loads(storage.save_path().read_text(encoding="utf-8"))
    assert saved["no_guess"] is True and saved["no_guess_ok"] is True
    code, out, _ = run(["resume", "--color", "never"], "q\n")
    assert code == 0
    assert "Resuming: beginner 9x9, 10 mines, seed 1, no guessing." in out


def test_cli_plain_game_header_is_unchanged():
    _, out, _ = run(["play", "--seed", "1", "--color", "never"], "q\n")
    assert "New game: beginner 9x9, 10 mines, seed 1. Type ? for help." in out
