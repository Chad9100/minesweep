"""Constraint solver: which hidden cells are certainly safe or certainly mines.

Pure logic, like :mod:`minesweep.board`. The solver only uses what a player
can see: the numbers on revealed cells and the total mine count. It never
looks at ``board.mines`` and it ignores flags (a flag is the player's guess,
not a fact), so every cell it reports is provably safe or provably a mine
from the visible board alone.

Rules, tried in this order until nothing new is found:

``single``
    A number whose remaining hidden neighbours are all mines, or none of them.
``subset``
    One number's unknown neighbours are a subset of another's, so the cells
    only the larger one sees hold the difference of the two counts.
``count``
    The same two rules applied to the whole board and the mines still unaccounted
    for (for example, the last few mines in the endgame).
``enumeration``
    Every mine arrangement of a group of connected border cells is tried; a
    cell that is safe in all of them is safe, a mine in all of them is a mine.
    Groups too large to search within the step budget are skipped, which only
    means fewer answers, never a wrong one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from minesweep.board import Board, Cell

SINGLE = "single"
SUBSET = "subset"
COUNT = "count"
ENUMERATION = "enumeration"
RULES = (SINGLE, SUBSET, COUNT, ENUMERATION)

# Search steps allowed per group of border cells before enumeration gives up.
DEFAULT_STEP_BUDGET = 200_000


@dataclass(frozen=True)
class Analysis:
    """What the visible board proves.

    ``safe`` and ``mines`` map each certain cell to the rule that found it
    (one of :data:`RULES`). ``skipped`` counts border groups that were too
    large to enumerate within the step budget.
    """

    safe: dict[Cell, str] = field(default_factory=dict)
    mines: dict[Cell, str] = field(default_factory=dict)
    skipped: int = 0

    @property
    def stuck(self) -> bool:
        """True when nothing is certain: the next move would be a guess."""
        return not self.safe and not self.mines


@dataclass
class _Constraint:
    cells: frozenset[Cell]
    count: int
    rule: str  # rule credited for what this constraint proves on its own


def analyze(board: Board, *, step_budget: int = DEFAULT_STEP_BUDGET) -> Analysis:
    """Find every hidden cell the visible board proves safe or a mine.

    Returns an empty analysis before the first reveal (nothing is visible yet)
    and once the game is over. The board is not changed.
    """
    if board.over or not board.revealed:
        return Analysis()
    hidden = {
        (x, y)
        for y in range(board.height)
        for x in range(board.width)
        if (x, y) not in board.revealed
    }
    safe: dict[Cell, str] = {}
    mines: dict[Cell, str] = {}
    skipped = 0

    def settle(cells, is_mine: bool, rule: str) -> bool:
        target = mines if is_mine else safe
        new = False
        for c in cells:
            if c not in safe and c not in mines:
                target[c] = rule
                new = True
        return new

    while True:
        constraints = _constraints(board, hidden, safe, mines)
        if not constraints:
            break
        progress = False
        for con in constraints:
            if con.count == 0:
                progress |= settle(con.cells, False, con.rule)
            elif con.count == len(con.cells):
                progress |= settle(con.cells, True, con.rule)
        if progress:
            continue
        for small, big, rule in _subset_pairs(constraints):
            rest = big.cells - small.cells
            diff = big.count - small.count
            if diff == 0:
                progress |= settle(rest, False, rule)
            elif diff == len(rest):
                progress |= settle(rest, True, rule)
        if progress:
            continue
        found, skipped = _enumerate(constraints, step_budget)
        for cell, is_mine in found.items():
            progress |= settle((cell,), is_mine, ENUMERATION)
        if not progress:
            break
    return Analysis(safe=safe, mines=mines, skipped=skipped)


def _constraints(
    board: Board, hidden: set[Cell], safe: dict[Cell, str], mines: dict[Cell, str]
) -> list[_Constraint]:
    """One constraint per revealed number with unknown neighbours, plus the global count.

    The global constraint (all unknown cells hold the unaccounted mines) comes last.
    """
    out: list[_Constraint] = []
    seen: set[frozenset[Cell]] = set()
    for cell in board.revealed:
        unknown = []
        known_mines = 0
        for n in board.neighbors(cell):
            if n in board.revealed or n in safe:
                continue
            if n in mines:
                known_mines += 1
            else:
                unknown.append(n)
        if not unknown:
            continue
        cells = frozenset(unknown)
        if cells in seen:
            continue
        seen.add(cells)
        out.append(_Constraint(cells, board.adjacent_mines(cell) - known_mines, SINGLE))
    rest = frozenset(c for c in hidden if c not in safe and c not in mines)
    if rest and rest not in seen:
        out.append(_Constraint(rest, board.config.mines - len(mines), COUNT))
    return out


def _subset_pairs(constraints: list[_Constraint]):
    """Yield ``(small, big, rule)`` where small's cells are a strict subset of big's."""
    by_cell: dict[Cell, list[int]] = {}
    for i, con in enumerate(constraints):
        if con.rule == SINGLE:
            for c in con.cells:
                by_cell.setdefault(c, []).append(i)
    for i, small in enumerate(constraints):
        if small.rule != SINGLE:
            continue
        candidates: set[int] = set()
        for c in small.cells:
            candidates.update(by_cell[c])
        for j in sorted(candidates):
            big = constraints[j]
            if j != i and small.cells < big.cells:
                yield small, big, SUBSET
        glob = constraints[-1]
        if glob.rule == COUNT and small.cells < glob.cells:
            yield small, glob, COUNT


def _enumerate(constraints: list[_Constraint], budget: int) -> tuple[dict[Cell, bool], int]:
    """Try every arrangement of each connected group of border cells.

    Returns ``({cell: is_mine}, groups_skipped)`` for cells fixed in every
    arrangement. The global count only prunes (a group may not hold more
    mines than are left), so the candidate set is never smaller than the
    true one and every answer stays sound.
    """
    local = [c for c in constraints if c.rule == SINGLE]
    glob = constraints[-1] if constraints and constraints[-1].rule == COUNT else None
    mines_left = glob.count if glob else sum(c.count for c in local)

    # Group border cells that share a constraint (union-find).
    parent: dict[Cell, Cell] = {}

    def find(c: Cell) -> Cell:
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for con in local:
        cells = sorted(con.cells)
        for c in cells:
            parent.setdefault(c, c)
        for c in cells[1:]:
            parent[find(c)] = find(cells[0])
    groups: dict[Cell, list[_Constraint]] = {}
    for con in local:
        groups.setdefault(find(next(iter(con.cells))), []).append(con)

    found: dict[Cell, bool] = {}
    skipped = 0
    for cons in groups.values():
        result = _enumerate_group(cons, mines_left, budget)
        if result is None:
            skipped += 1
        else:
            found.update(result)
    return found, skipped


def _enumerate_group(
    cons: list[_Constraint], mines_left: int, budget: int
) -> dict[Cell, bool] | None:
    # Visit cells constraint by constraint so each one is closed off early.
    order: list[Cell] = []
    placed: set[Cell] = set()
    for con in sorted(cons, key=lambda k: (len(k.cells), sorted(k.cells))):
        for c in sorted(con.cells):
            if c not in placed:
                placed.add(c)
                order.append(c)
    index = {c: i for i, c in enumerate(order)}
    cell_cons: list[list[int]] = [[] for _ in order]
    for k, con in enumerate(cons):
        for c in con.cells:
            cell_cons[index[c]].append(k)
    need = [con.count for con in cons]  # mines still to place per constraint
    open_cells = [len(con.cells) for con in cons]  # unassigned cells per constraint

    assignment = [False] * len(order)
    mine_hits = [0] * len(order)  # in how many solutions each cell is a mine
    solutions = 0
    steps = 0

    def place(i: int, mines_used: int) -> bool:
        nonlocal solutions, steps
        steps += 1
        if steps > budget:
            return False
        if i == len(order):
            solutions += 1
            for j, is_mine in enumerate(assignment):
                if is_mine:
                    mine_hits[j] += 1
            return True
        for is_mine in (False, True):
            if is_mine and mines_used >= mines_left:
                continue
            ok = True
            for k in cell_cons[i]:
                n = need[k] - is_mine
                if n < 0 or n > open_cells[k] - 1:
                    ok = False
                    break
            if not ok:
                continue
            for k in cell_cons[i]:
                need[k] -= is_mine
                open_cells[k] -= 1
            assignment[i] = is_mine
            alive = place(i + 1, mines_used + is_mine)
            for k in cell_cons[i]:
                need[k] += is_mine
                open_cells[k] += 1
            assignment[i] = False
            if not alive:
                return False
        return True

    if not place(0, 0) or solutions == 0:
        return None
    return {
        c: mine_hits[i] == solutions
        for i, c in enumerate(order)
        if mine_hits[i] in (0, solutions)
    }


# ----------------------------------------------------------------------- hints

REVEAL = "reveal"      # a hidden, unflagged cell that is certainly safe
UNFLAG = "unflag"      # a flagged cell that is certainly safe (the flag is wrong)
FLAG = "flag"          # a hidden, unflagged cell that is certainly a mine


@dataclass(frozen=True)
class Hint:
    """One suggested move: ``action`` is :data:`REVEAL`, :data:`UNFLAG` or
    :data:`FLAG`, ``rule`` is the solver rule that proves it."""

    action: str
    cell: Cell
    rule: str


def suggest(board: Board, *, step_budget: int = DEFAULT_STEP_BUDGET) -> Hint | None:
    """Pick the most useful certain move on the visible board, or None.

    Priority: reveal a safe cell (it makes progress), then remove a flag the
    board proves wrong (a wrong flag loses a chord), then flag a certain mine.
    Among equals the cell closest to the last move wins (ties: top row first,
    then leftmost), so the hint lands where the player is looking. Returns
    None before the first reveal, after the game, and when every remaining
    move is a guess. Like :func:`analyze`, it never looks at ``board.mines``.
    """
    result = analyze(board, step_budget=step_budget)
    groups = (
        (REVEAL, {c: r for c, r in result.safe.items() if c not in board.flagged}),
        (UNFLAG, {c: r for c, r in result.safe.items() if c in board.flagged}),
        (FLAG, {c: r for c, r in result.mines.items() if c not in board.flagged}),
    )
    last = board.last_move
    anchor = last[1] if last else None

    def key(cell: Cell) -> tuple[int, int, int]:
        x, y = cell
        dist = max(abs(x - anchor[0]), abs(y - anchor[1])) if anchor else 0
        return (dist, y, x)

    for action, found in groups:
        if found:
            cell = min(found, key=key)
            return Hint(action, cell, found[cell])
    return None
