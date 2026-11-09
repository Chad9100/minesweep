import pytest

from minesweep.board import (
    DIFFICULTIES,
    LOST,
    PLAYING,
    WON,
    Board,
    ConfigError,
    MoveError,
    make_config,
)


def new_board(width=9, height=9, mines=10, seed=1, clock=None):
    cfg = make_config(width, height, mines)
    return Board(cfg, seed, clock) if clock else Board(cfg, seed)


# ---------------------------------------------------------------- configs


def test_standard_difficulties():
    assert (DIFFICULTIES["beginner"].width, DIFFICULTIES["beginner"].mines) == (9, 10)
    assert (DIFFICULTIES["intermediate"].width, DIFFICULTIES["intermediate"].mines) == (16, 40)
    e = DIFFICULTIES["expert"]
    assert (e.width, e.height, e.mines) == (30, 16, 99)


def test_custom_size_matching_a_preset_is_labelled_with_it():
    assert make_config(16, 16, 40).difficulty == "intermediate"
    assert make_config(16, 16, 41).difficulty == "custom"
    assert not make_config(5, 5, 3).ranked


@pytest.mark.parametrize(
    "w,h,m,fragment",
    [
        (0, 5, 1, "width must be at least 1"),
        (5, 0, 1, "height must be at least 1"),
        (100, 5, 1, "width must be at most 99"),
        (3, 3, 9, "at most 8"),
        (3, 3, 50, "too many mines"),
        (5, 5, 0, "mines must be at least 1"),
    ],
)
def test_invalid_configs_are_rejected(w, h, m, fragment):
    with pytest.raises(ConfigError, match=fragment):
        make_config(w, h, m)


# ---------------------------------------------------------- mine placement


def test_mines_not_placed_until_first_reveal():
    b = new_board()
    assert not b.mines_placed and b.mines == set()
    b.reveal((4, 4))
    assert b.mines_placed and len(b.mines) == 10


def test_same_seed_and_click_gives_same_board():
    a, b = new_board(seed=7), new_board(seed=7)
    a.reveal((3, 3))
    b.reveal((3, 3))
    assert a.mines == b.mines


def test_different_seeds_give_different_boards():
    a, b = new_board(seed=1), new_board(seed=2)
    a.reveal((0, 0))
    b.reveal((0, 0))
    assert a.mines != b.mines


@pytest.mark.parametrize("seed", range(40))
def test_first_click_and_neighbours_are_safe_when_there_is_room(seed):
    b = new_board(seed=seed, mines=40, width=10, height=10)
    first = (seed % 10, (seed * 3) % 10)
    b.reveal(first)
    assert first not in b.mines
    assert not set(b.neighbors(first)) & b.mines
    assert b.state != LOST


def test_crowded_board_still_keeps_first_click_safe():
    # 3x3 with 8 mines: no room to clear the neighbours, only the clicked cell.
    for seed in range(20):
        b = new_board(3, 3, 8, seed=seed)
        b.reveal((1, 1))
        assert (1, 1) not in b.mines
        assert b.state == WON


def test_tiny_one_by_two_board():
    b = new_board(2, 1, 1, seed=3)
    b.reveal((0, 0))
    assert b.mines == {(1, 0)}
    assert b.state == WON


def test_corner_click_on_crowded_board_with_partial_room():
    # 4x4, 13 mines: the corner zone is 4 cells, leaving only 12 -> fall back.
    for seed in range(10):
        b = new_board(4, 4, 13, seed=seed)
        b.reveal((0, 0))
        assert (0, 0) not in b.mines and len(b.mines) == 13


def test_single_cell_wide_column_board():
    b = new_board(1, 5, 1, seed=2)
    b.reveal((0, 0))
    assert (0, 0) not in b.mines and (0, 1) not in b.mines


# ------------------------------------------------------------- flood fill


def test_flood_fill_opens_empty_region_and_its_border():
    b = Board.from_layout([
        ".....",
        ".....",
        ".....",
        "....*",
    ])
    opened = b.reveal((0, 0))
    assert (4, 3) not in b.revealed
    assert len(opened) == 19
    assert b.state == WON


def test_flood_fill_stops_at_numbers():
    b = Board.from_layout([
        "..*..",
        "..*..",
        "..*..",
    ])
    b.reveal((0, 0))
    assert b.revealed == {(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)}
    assert b.state == PLAYING


def test_flood_fill_does_not_open_flagged_cells():
    b = Board.from_layout(["....", "....", "...*"])
    b.toggle_flag((0, 2))
    b.reveal((0, 0))
    assert (0, 2) not in b.revealed and (0, 2) in b.flagged


def test_flood_fill_handles_huge_board_without_recursion():
    b = Board.from_layout(["." * 99 for _ in range(98)] + ["." * 98 + "*"])
    b.reveal((0, 0))
    assert b.state == WON


def test_number_cell_reveals_only_itself():
    b = Board.from_layout(["*..", "...", "..."])
    assert b.reveal((1, 1)) == [(1, 1)]


# ------------------------------------------------------------ win and loss


def test_revealing_a_mine_loses():
    b = Board.from_layout(["*.", ".."])
    b.reveal((0, 0))
    assert b.state == LOST and b.exploded == (0, 0)


def test_win_when_all_safe_cells_revealed_flags_not_needed():
    b = Board.from_layout(["*.", ".."])
    b.reveal((1, 0))
    b.reveal((0, 1))
    assert b.state == PLAYING
    b.reveal((1, 1))
    assert b.state == WON
    assert b.flagged == {(0, 0)}  # mines are auto-flagged on a win


def test_no_moves_after_game_over():
    b = Board.from_layout(["*.", ".."])
    b.reveal((0, 0))
    with pytest.raises(MoveError, match="game is over"):
        b.reveal((1, 1))
    with pytest.raises(MoveError):
        b.toggle_flag((1, 1))


def test_cannot_reveal_twice_or_reveal_a_flag():
    b = Board.from_layout(["*..", "...", "..."])
    b.reveal((1, 1))
    with pytest.raises(MoveError, match="already revealed"):
        b.reveal((1, 1))
    b.toggle_flag((2, 2))
    with pytest.raises(MoveError, match="flagged"):
        b.reveal((2, 2))


# ------------------------------------------------------------------ flags


def test_flag_toggles_and_counts_mines_left():
    b = new_board()
    assert b.toggle_flag((0, 0)) is True
    assert b.mines_left == 9
    assert b.toggle_flag((0, 0)) is False
    assert b.mines_left == 10


def test_flagging_a_revealed_cell_is_rejected():
    b = Board.from_layout(["*..", "...", "..."])
    b.reveal((1, 1))
    with pytest.raises(MoveError, match="cannot be flagged"):
        b.toggle_flag((1, 1))
    assert (1, 1) not in b.flagged


def test_mines_left_can_go_negative_when_overflagging():
    b = Board.from_layout(["*.", ".."])
    for c in [(0, 0), (1, 0), (0, 1)]:
        b.toggle_flag(c)
    assert b.mines_left == -2


# ----------------------------------------------------------------- chords


def test_chord_reveals_neighbours_when_flags_match():
    b = Board.from_layout(["*..", "...", "..."])
    b.reveal((1, 0))
    b.toggle_flag((0, 0))
    b.chord((1, 0))
    assert b.state == WON


def test_chord_with_wrong_flag_loses():
    b = Board.from_layout([
        "*...",
        "....",
        ".*..",
    ])
    b.reveal((1, 0))  # shows 1 (the mine at A1)
    b.toggle_flag((2, 1))  # wrong flag
    b.chord((1, 0))
    assert b.state == LOST
    assert b.exploded == (0, 0)


def test_chord_with_too_few_flags_is_rejected():
    b = Board.from_layout(["*..", "...", "..."])
    b.reveal((1, 1))
    with pytest.raises(MoveError, match="shows 1 but has 0 flag"):
        b.chord((1, 1))
    assert b.revealed == {(1, 1)}


def test_chord_on_hidden_or_zero_cell_is_rejected():
    b = Board.from_layout(["..*..", "..*..", "..*.."])
    with pytest.raises(MoveError, match="hidden"):
        b.chord((4, 0))
    b.reveal((0, 0))
    with pytest.raises(MoveError, match="nothing to chord"):
        b.chord((0, 0))


# ------------------------------------------------------------------ timing


def test_timer_starts_on_first_reveal_and_stops_at_end(clock):
    b = Board.from_layout(["*.", ".."], clock=clock)
    clock.advance(50)
    assert b.elapsed == 0
    b.reveal((1, 0))
    clock.advance(3)
    assert b.elapsed == 3
    b.reveal((0, 1))
    b.reveal((1, 1))
    clock.advance(100)
    assert b.state == WON and b.elapsed == 3


# ---------------------------------------------------------------- save data


def test_to_dict_from_dict_round_trip(clock):
    b = new_board(seed=9, clock=clock)
    b.reveal((4, 4))
    hidden = next(
        (x, y) for y in range(9) for x in range(9) if (x, y) not in b.revealed
    )
    b.toggle_flag(hidden)
    clock.advance(12.5)
    data = b.to_dict()
    clock.advance(1000)  # time spent while the game is saved does not count
    r = Board.from_dict(data, clock)
    assert (r.mines, r.revealed, r.flagged, r.seed, r.state) == (
        b.mines, b.revealed, b.flagged, 9, PLAYING,
    )
    assert r.elapsed == pytest.approx(12.5)
    clock.advance(2)
    assert r.elapsed == pytest.approx(14.5)


def test_from_dict_before_first_click_keeps_seed():
    b = new_board(seed=77)
    r = Board.from_dict(b.to_dict())
    r.reveal((4, 4))
    b.reveal((4, 4))
    assert r.mines == b.mines


@pytest.mark.parametrize(
    "patch",
    [
        {"version": 99},
        {"width": 0},
        {"state": "dancing"},
        {"mines": [[50, 50]]},
        {"revealed": "nope"},
    ],
)
def test_from_dict_rejects_bad_data(patch):
    b = new_board()
    b.reveal((4, 4))
    data = b.to_dict()
    data.update(patch)
    with pytest.raises(ValueError):
        Board.from_dict(data)
