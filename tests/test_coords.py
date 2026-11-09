import pytest

from minesweep.board import CoordError, cell_label, column_index, column_label, parse_coord


@pytest.mark.parametrize(
    "text,expected",
    [("A1", (0, 0)), ("a1", (0, 0)), ("B3", (1, 2)), (" i9 ", (8, 8)), ("c 4", (2, 3)), ("AD16", (29, 15))],
)
def test_parse_valid_coordinates(text, expected):
    assert parse_coord(text, 30, 16) == expected


@pytest.mark.parametrize("text", ["", "5A", "A", "7", "A-1", "B3x", "!!", "A1.5"])
def test_parse_rejects_garbage(text):
    with pytest.raises(CoordError, match="not a cell"):
        parse_coord(text, 9, 9)


def test_parse_rejects_off_board_column_and_row():
    with pytest.raises(CoordError, match=r"column J is off the board \(A-I\)"):
        parse_coord("J1", 9, 9)
    with pytest.raises(CoordError, match=r"row 10 is off the board \(1-9\)"):
        parse_coord("A10", 9, 9)
    with pytest.raises(CoordError, match="row 0"):
        parse_coord("A0", 9, 9)


def test_column_labels_go_past_z():
    assert [column_label(i) for i in (0, 25, 26, 27, 51, 52)] == ["A", "Z", "AA", "AB", "AZ", "BA"]
    for i in range(200):
        assert column_index(column_label(i)) == i


def test_cell_label_is_inverse_of_parse():
    for cell in [(0, 0), (8, 8), (29, 15)]:
        assert parse_coord(cell_label(cell), 30, 16) == cell
