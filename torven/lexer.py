"""
lexer.py — TORVEN Lexer built with PLY.

Handles INDENT/DEDENT using an indentation stack, exactly mirroring CPython's
tokenizer behaviour.  Every logical line that increases indentation emits an
INDENT token; every decrease emits one DEDENT per level unwound.

Token categories
----------------
Keywords    : forge, ignite, drift, rev, burn, inject, eject, lock, load,
              kill, idle, vent, stall, redline, in
Types       : torq, venom, exhaust, spark, barrel, chassis, void
Literals    : on (True), off (False), NUMBER, FLOAT, STRING
Identifiers : NAME
Operators   : => ~~ !~ ^^ -> + - * / % < > <= >= ( ) [ ] { } , : .
Structure   : INDENT, DEDENT, NEWLINE
"""

from __future__ import annotations

import re
from typing import Generator, List

import ply.lex as lex

from .errors import TorvenLexError

# ---------------------------------------------------------------------------
# Token list — PLY requires a module-level ``tokens`` tuple
# ---------------------------------------------------------------------------

reserved: dict[str, str] = {
    # Control flow
    "ignite":  "IGNITE",
    "drift":   "DRIFT",
    "rev":     "REV",
    "burn":    "BURN",
    "in":      "IN",
    "kill":    "KILL",
    "idle":    "IDLE",
    # Function / scope
    "forge":   "FORGE",
    "eject":   "EJECT",
    "inject":  "INJECT",
    # Variables
    "load":    "LOAD",
    "lock":    "LOCK",
    # I/O
    "vent":    "VENT",
    # Error handling
    "stall":   "STALL",
    "redline": "REDLINE",
    # Type names (used after @ annotation)
    "torq":    "TYPE_TORQ",
    "venom":   "TYPE_VENOM",
    "exhaust": "TYPE_EXHAUST",
    "spark":   "TYPE_SPARK",
    "barrel":  "TYPE_BARREL",
    "chassis": "TYPE_CHASSIS",
    "void":    "TYPE_VOID",
    # Boolean literals
    "on":      "TRUE",
    "off":     "FALSE",
}

tokens: tuple = (
    # Literals
    "NUMBER",
    "FLOAT",
    "STRING",
    "NAME",
    # Operators
    "ASSIGN",       # =>
    "EQ",           # ~~
    "NEQ",          # !~
    "POW",          # ^^
    "PIPE",         # ->
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    "MOD",
    "LT",
    "GT",
    "LTE",
    "GTE",
    # Delimiters
    "LPAREN",
    "RPAREN",
    "LBRACKET",
    "RBRACKET",
    "LBRACE",
    "RBRACE",
    "COMMA",
    "COLON",
    "DOT",
    "AT",
    # Structure
    "NEWLINE",
    "INDENT",
    "DEDENT",
) + tuple(reserved.values())


# ---------------------------------------------------------------------------
# Lexer class (encapsulated to avoid PLY global-state issues)
# ---------------------------------------------------------------------------

class TorvenLexer:
    """Wraps PLY lex and post-processes the token stream to inject
    INDENT / DEDENT tokens, matching Python's tokenizer semantics."""

    tokens = tokens

    # --- simple operator rules (string or regex) --------------------------

    t_ASSIGN   = r'=>'
    t_EQ       = r'~~'
    t_NEQ      = r'!~'
    t_POW      = r'\^\^'
    t_PIPE     = r'->'
    t_PLUS     = r'\+'
    t_MINUS    = r'-'
    t_TIMES    = r'\*'
    t_DIVIDE   = r'/'
    t_MOD      = r'%'
    t_LTE      = r'<='
    t_GTE      = r'>='
    t_LT       = r'<'
    t_GT       = r'>'
    t_LPAREN   = r'\('
    t_RPAREN   = r'\)'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_LBRACE   = r'\{'
    t_RBRACE   = r'\}'
    t_COMMA    = r','
    t_COLON    = r':'
    t_DOT      = r'\.'
    t_AT       = r'@'

    # ignored characters inside a logical line
    t_ignore = ' \t'

    # --- complex token rules -----------------------------------------------

    def t_FLOAT(self, t):
        r'\d+\.\d+'
        t.value = float(t.value)
        return t

    def t_NUMBER(self, t):
        r'\d+'
        t.value = int(t.value)
        return t

    def t_STRING(self, t):
        r'(\"([^\"\\]|\\.)*\"|\'([^\'\\]|\\.)*\')'
        # strip surrounding quotes and handle basic escapes
        raw = t.value[1:-1]
        raw = raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
        t.value = raw
        return t

    def t_NAME(self, t):
        r'[A-Za-z_][A-Za-z0-9_]*'
        t.type = reserved.get(t.value, "NAME")
        return t

    def t_COMMENT(self, t):
        r'\#[^\n]*'
        pass  # discard comments

    def t_newline(self, t):
        r'\n[ \t]*'
        t.lexer.lineno += 1
        t.type = "NEWLINE"
        # Extract indentation of the *next* line from the matched token
        t.value = len(t.value) - 1  # chars after \n = indentation of next line
        return t

    def t_error(self, t):
        raise TorvenLexError(
            f"Unexpected character '{t.value[0]}'",
            line=t.lineno,
            column=self._find_column(t),
        )

    # -----------------------------------------------------------------------

    def __init__(self):
        self._lexer = lex.lex(module=self, debug=False, errorlog=lex.NullLogger())
        self._indent_stack: List[int] = [0]
        self._token_queue: List[lex.LexToken] = []
        self._source: str = ""

    # PLY reads lexer.lineno directly during parsing
    # --- PLY-required attributes forwarded to the inner lexer ---------------

    @property
    def lineno(self) -> int:
        return getattr(self._lexer, "lineno", 1) if hasattr(self, "_lexer") else 1

    @lineno.setter
    def lineno(self, value: int):
        if hasattr(self, "_lexer"):
            self._lexer.lineno = value

    @property
    def lexpos(self) -> int:
        return getattr(self._lexer, "lexpos", 0) if hasattr(self, "_lexer") else 0

    @lexpos.setter
    def lexpos(self, value: int):
        if hasattr(self, "_lexer"):
            self._lexer.lexpos = value

    def _find_column(self, token) -> int:
        last_nl = self._source.rfind('\n', 0, token.lexpos)
        return token.lexpos - last_nl

    def input(self, data: str):
        self._source = data
        self._lexer.input(data)
        self._indent_stack = [0]
        self._token_queue = []

    def _make_token(self, ttype: str, value, lineno: int) -> lex.LexToken:
        tok = lex.LexToken()
        tok.type  = ttype
        tok.value = value
        tok.lineno = lineno
        tok.lexpos = 0
        return tok

    def token(self) -> lex.LexToken | None:
        """Return the next token with INDENT/DEDENT injected."""
        if self._token_queue:
            return self._token_queue.pop(0)

        while True:
            tok = self._lexer.token()
            if tok is None:
                # End of file: flush pending DEDENTs
                if len(self._indent_stack) > 1:
                    lineno = self._lexer.lineno
                    while len(self._indent_stack) > 1:
                        self._indent_stack.pop()
                        self._token_queue.append(
                            self._make_token("DEDENT", "", lineno)
                        )
                    return self._token_queue.pop(0) if self._token_queue else None
                return None

            if tok.type == "NEWLINE":
                new_indent = tok.value  # indentation of the following line
                current_indent = self._indent_stack[-1]

                # Emit the NEWLINE first, then handle indent changes
                nl_tok = self._make_token("NEWLINE", "\n", tok.lineno)

                if new_indent > current_indent:
                    self._indent_stack.append(new_indent)
                    self._token_queue.append(
                        self._make_token("INDENT", new_indent, tok.lineno)
                    )
                elif new_indent < current_indent:
                    while self._indent_stack[-1] > new_indent:
                        self._indent_stack.pop()
                        self._token_queue.append(
                            self._make_token("DEDENT", "", tok.lineno)
                        )
                    if self._indent_stack[-1] != new_indent:
                        raise TorvenLexError(
                            "Inconsistent indentation level",
                            line=tok.lineno,
                        )

                return nl_tok

            return tok

    # convenience: iterate over all tokens (for debugging)
    def tokenize(self, source: str) -> Generator[lex.LexToken, None, None]:
        self.input(source)
        while True:
            tok = self.token()
            if tok is None:
                break
            yield tok


# ---------------------------------------------------------------------------
# Module-level factory used by parser.py
# ---------------------------------------------------------------------------

def make_lexer() -> TorvenLexer:
    return TorvenLexer()
