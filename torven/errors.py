"""
errors.py — Custom exception hierarchy for the TORVEN compiler pipeline.

Each phase of the compiler (lex, parse, semantic, runtime) raises its own
typed exception so callers can catch exactly the phase that failed and display
a consistent, informative error message.
"""

from __future__ import annotations


class TorvenError(Exception):
    """Base class for all TORVEN compiler errors."""

    phase: str = "torven"

    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(str(self))

    def __str__(self) -> str:
        location = ""
        if self.line:
            location = f" [line {self.line}"
            if self.column:
                location += f", col {self.column}"
            location += "]"
        return f"[{self.phase.upper()} ERROR]{location} {self.message}"


class TorvenLexError(TorvenError):
    """Raised when the lexer encounters an unexpected character or token."""
    phase = "lex"


class TorvenParseError(TorvenError):
    """Raised when the parser encounters a syntax error."""
    phase = "parse"


class TorvenTypeError(TorvenError):
    """Raised during semantic analysis for type mismatches or undeclared vars."""
    phase = "type"


class TorvenRuntimeError(TorvenError):
    """Raised by the VM during bytecode execution."""
    phase = "runtime"


class TorvenCompileError(TorvenError):
    """Raised during bytecode compilation (AST → bytecode)."""
    phase = "compile"
