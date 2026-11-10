from minesweep.hexgrid import (
    hex_distance,
    hex_neighbours,
    render_hex_grid,
)


def test_even_row_neighbours():
    assert hex_neighbours((2, 2), 5, 5) == [(1, 1), (2, 1), (1, 2), (3, 2), (1, 3), (2, 3)]


def test_odd_row_neighbours():
    assert hex_neighbours((2, 1), 5, 5) == [(2, 0), (3, 0), (1, 1), (3, 1), (2, 2), (3, 2)]


def test_corner_and_edge_counts():
    assert hex_neighbours((0, 0), 5, 5) == [(1, 0), (0, 1)]
    assert hex_neighbours((4, 1), 5, 5) == [(4, 0), (3, 1), (4, 2)]
    assert hex_neighbours((0, 2), 5, 5) == [(0, 1), (1, 2), (0, 3)]
    assert len(hex_neighbours((0, 1), 5, 5)) == 5


def test_neighbours_are_symmetric_and_six_inside():
    w, h = 6, 7
    for y in range(h):
        for x in range(w):
            for n in hex_neighbours((x, y), w, h):
                assert (x, y) in hex_neighbours(n, w, h)
                assert hex_distance((x, y), n) == 1
    assert all(len(hex_neighbours((x, y), w, h)) == 6 for x in range(1, w - 1) for y in range(1, h - 1))


def test_distance():
    assert hex_distance((0, 0), (0, 0)) == 0
    assert hex_distance((0, 0), (3, 0)) == 3
    assert hex_distance((0, 0), (0, 2)) == 2
    assert hex_distance((1, 1), (2, 3)) == 2
    assert hex_distance((0, 0), (4, 4)) == hex_distance((4, 4), (0, 0))


def test_render_layout():
    text = render_hex_grid(3, 3, lambda c: "#" if c == (1, 1) else ".")
    assert text.splitlines() == [
        "  A B C",
        "1 . . .",
        "2  . # .",
        "3 . . .",
    ]


def test_render_pads_row_numbers():
    text = render_hex_grid(2, 10, lambda c: ".")
    lines = text.splitlines()
    assert lines[1] == " 1 . ."
    assert lines[2] == " 2  . ."
    assert lines[10] == "10  . ."
