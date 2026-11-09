import pytest


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self, start: float = 100.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never let a test touch the real per-user data directory."""
    home = tmp_path / "minesweep-home"
    monkeypatch.setenv("MINESWEEP_HOME", str(home))
    monkeypatch.delenv("NO_COLOR", raising=False)
    return home


@pytest.fixture
def clock():
    return FakeClock()
