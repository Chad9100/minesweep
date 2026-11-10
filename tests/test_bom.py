"""A byte order mark at the start of piped input (Windows PowerShell adds one)."""

import io
import os
import subprocess
import sys

import pytest

from minesweep.cli import main, strip_bom


class Stream(io.StringIO):
    def isatty(self):
        return False

    @property
    def encoding(self):
        return "utf-8"


def run(script, *extra):
    out, err = Stream(), Stream()
    code = main(
        ["play", "--seed", "1", *extra],
        stdin=Stream(script), stdout=out, stderr=err, environ=dict(os.environ),
    )
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("bom", ["﻿", "ï»¿"])
def test_strip_bom_removes_a_leading_mark(bom):
    assert strip_bom(bom + "r E5\n") == "r E5\n"


@pytest.mark.parametrize("line", ["r E5\n", "", "\n", "r E5﻿\n", "ï r E5\n"])
def test_strip_bom_leaves_other_lines_alone(line):
    assert strip_bom(line) == line


def test_strip_bom_removes_only_one_mark():
    assert strip_bom("﻿﻿q\n") == "﻿q\n"


def test_first_command_after_a_bom_is_played():
    plain = run("r E5\nq\n")
    marked = run("﻿r E5\nq\n")
    assert "Unknown command" not in marked[1]
    assert marked == plain


def test_echo_shows_the_command_without_the_mark():
    _, out, _ = run("﻿q\n")
    assert "> q\n" in out
    assert "﻿" not in out
    assert "Quit without saving." in out


def test_bare_cell_after_a_bom_is_a_reveal():
    assert run("﻿E5\nq\n") == run("E5\nq\n")


def test_piped_bytes_with_a_bom_end_to_end(tmp_path):
    # Real pipe, decoded with whatever encoding Python picks for this platform:
    # UTF-8 gives U+FEFF, a Windows-1252 locale gives the three-character form.
    env = dict(os.environ, MINESWEEP_HOME=str(tmp_path))
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONUTF8", None)
    proc = subprocess.run(
        [sys.executable, "-m", "minesweep", "play", "--seed", "1", "--no-echo"],
        input=b"\xef\xbb\xbfr E5\nq\n",
        capture_output=True,
        env=env,
        timeout=60,
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    assert "Unknown command" not in out
    assert "Quit without saving." in out
    assert "Mines left: 10   Time: 0s" in out
