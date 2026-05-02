"""
main.py — TORVEN command-line interface.

Usage
-----
    torven compile  <file.trv>              Compile to <file.tvbc>
    torven run      <file.tvbc>             Execute bytecode
    torven exec     <file.trv>              Compile + execute in one step
    torven disasm   <file.trv|file.tvbc>    Pretty-print bytecode instructions
    torven tokens   <file.trv>              Dump token stream (debug)
    torven ast      <file.trv>              Dump AST (debug)
"""

from __future__ import annotations

import os
import sys


def _ensure_package_on_path():
    """Allow running as ``python torven/main.py`` or ``python main.py``."""
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if parent not in sys.path:
        sys.path.insert(0, parent)


_ensure_package_on_path()

from torven.errors import TorvenError
from torven.lexer  import make_lexer
from torven.parser import parse
from torven import semantic, compiler as comp
from torven.vm import VM


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_compile(src_path: str) -> str:
    """Compile *src_path* (.trv) → .tvbc; returns the output path."""
    source = _read_source(src_path)
    ast    = _parse(source)
    _check_semantics(ast)
    out_path = _tvbc_path(src_path)
    comp.compile_to_file(ast, out_path)
    print(f"[torven] Compiled → {out_path}")
    return out_path


def cmd_run(tvbc_path: str):
    """Execute a .tvbc bytecode file."""
    vm = VM()
    vm.run_file(tvbc_path)


def cmd_exec(src_path: str):
    """Compile and immediately execute a .trv source file."""
    source = _read_source(src_path)
    ast    = _parse(source)
    _check_semantics(ast)
    code   = comp.compile_ast(ast)
    vm     = VM()
    vm.run(code)


def cmd_disasm(path: str):
    """Pretty-print bytecode instructions."""
    if path.endswith(".trv"):
        source = _read_source(path)
        ast    = _parse(source)
        code   = comp.compile_ast(ast)
    else:
        code = comp.load_from_file(path)

    _print_disasm(code, indent=0)


def cmd_tokens(src_path: str):
    """Dump the token stream to stdout (useful for debugging the lexer)."""
    source = _read_source(src_path)
    lexer  = make_lexer()
    print(f"{'TYPE':<20}  {'VALUE':<30}  LINE")
    print("-" * 60)
    for tok in lexer.tokenize(source):
        print(f"{tok.type:<20}  {str(tok.value):<30}  {tok.lineno}")


def cmd_ast(src_path: str):
    """Dump the AST to stdout (useful for debugging the parser)."""
    import pprint
    source = _read_source(src_path)
    ast    = _parse(source)
    pprint.pprint(ast)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_source(path: str) -> str:
    if not os.path.exists(path):
        _die(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse(source: str):
    try:
        return parse(source)
    except TorvenError as e:
        _die(str(e))


def _check_semantics(ast):
    errors = semantic.analyse(ast)
    if errors:
        for err in errors:
            print(str(err), file=sys.stderr)
        _die(f"{len(errors)} semantic error(s) found.")


def _tvbc_path(src_path: str) -> str:
    base, _ = os.path.splitext(src_path)
    return base + ".tvbc"


def _print_disasm(code, indent: int):
    prefix = "  " * indent
    print(f"{prefix}=== {code.name} ===")
    # Strip LABEL pseudo-instructions when printing
    for i, instr in enumerate(code.instructions):
        if instr.opcode == "LABEL":
            print(f"{prefix}  .{instr.arg}:")
        else:
            arg_str = repr(instr.arg) if instr.arg is not None else ""
            print(f"{prefix}  {i:>4}  {instr.opcode:<16} {arg_str:<24} ; line {instr.line}")
    for sub_name, sub_code in code.functions.items():
        print()
        _print_disasm(sub_code, indent + 1)


def _die(message: str):
    print(f"[torven] Error: {message}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

USAGE = """\
Usage:
  torven compile  <file.trv>          Compile to bytecode (.tvbc)
  torven run      <file.tvbc>         Run bytecode
  torven exec     <file.trv>          Compile + run
  torven disasm   <file.trv|.tvbc>    Disassemble bytecode
  torven tokens   <file.trv>          Dump token stream
  torven ast      <file.trv>          Dump AST
"""


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(USAGE)
        sys.exit(0)

    cmd  = args[0].lower()
    path = args[1]

    dispatch = {
        "compile": cmd_compile,
        "run":     cmd_run,
        "exec":    cmd_exec,
        "disasm":  cmd_disasm,
        "tokens":  cmd_tokens,
        "ast":     cmd_ast,
    }

    if cmd not in dispatch:
        print(f"Unknown command '{cmd}'\n")
        print(USAGE)
        sys.exit(1)

    try:
        dispatch[cmd](path)
    except TorvenError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
