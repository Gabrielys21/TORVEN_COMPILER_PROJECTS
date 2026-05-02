"""
tests/test_pipeline.py — Smoke tests for the full TORVEN compiler pipeline.

Run with: python -m pytest torven/tests/ -v
"""

import pytest
from torven.parser import parse
from torven import semantic, compiler as comp
from torven.vm import VM


def run_source(src: str) -> list:
    """Compile + run *src*, capturing printed output as a list of strings."""
    import io, sys
    ast  = parse(src)
    errs = semantic.analyse(ast)
    assert not errs, "\n".join(str(e) for e in errs)
    code = comp.compile_ast(ast)
    captured = []
    original_print = builtins_print = __builtins__["print"] if isinstance(__builtins__, dict) else print
    # Patch print by running inside the VM with a custom stdout
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        VM().run(code)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue().strip().splitlines()


def test_load_and_vent():
    out = run_source("load x@torq => 42\nvent x\n")
    assert out == ["42"]


def test_arithmetic():
    out = run_source("load r => (3 ^^ 2) + 1\nvent r\n")
    assert out == ["10"]


def test_function_call():
    src = """
forge doble(n@torq):
    eject n * 2

vent doble(5)
"""
    out = run_source(src)
    assert out == ["10"]


def test_ignite_drift():
    src = """
load x@torq => -1
ignite x > 0:
    vent "pos"
drift:
    vent "neg"
"""
    out = run_source(src)
    assert out == ["neg"]


def test_burn_loop():
    src = """
load nums@barrel => [1, 2, 3]
burn n in nums:
    vent n
"""
    out = run_source(src)
    assert out == ["1", "2", "3"]


def test_rev_loop():
    src = """
load i@torq => 0
rev i < 3:
    vent i
    i => i + 1
"""
    out = run_source(src)
    assert out == ["0", "1", "2"]


def test_pipe():
    src = """
forge neg(x@torq):
    eject x * -1

load v@torq => 5
vent v -> neg
"""
    out = run_source(src)
    assert out == ["-5"]


def test_semantic_type_error():
    src = "load x@torq => 3.14\n"
    ast  = parse(src)
    errs = semantic.analyse(ast)
    assert len(errs) == 1
    assert "venom" in str(errs[0])


def test_semantic_undefined_var():
    src = "vent undefined_name\n"
    ast  = parse(src)
    errs = semantic.analyse(ast)
    assert any("undefined_name" in str(e) for e in errs)
