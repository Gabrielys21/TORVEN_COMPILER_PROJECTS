"""
ast_nodes.py — AST node definitions for the TORVEN language.

Every node is a dataclass with a ``line`` field so error messages can always
report an accurate source location.  Nodes are intentionally plain data
containers; all logic lives in the compiler passes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass
class Node:
    line: int = 0


# ---------------------------------------------------------------------------
# Program root
# ---------------------------------------------------------------------------

@dataclass
class Program(Node):
    body: List[Node] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass
class ImportStmt(Node):
    module: str = ""


@dataclass
class LoadStmt(Node):
    """load x@torq => expr  (mutable variable declaration)"""
    name: str = ""
    type_ann: Optional[str] = None   # "torq" | "venom" | … | None
    value: Optional[Node] = None
    mutable: bool = True             # False for lock (const)


@dataclass
class AssignStmt(Node):
    """Plain re-assignment: x => expr  (no load/lock keyword)"""
    name: str = ""
    value: Optional[Node] = None


@dataclass
class EjectStmt(Node):
    """eject expr"""
    value: Optional[Node] = None


@dataclass
class VentStmt(Node):
    """vent expr -> transform -> …"""
    value: Optional[Node] = None


@dataclass
class KillStmt(Node):
    """kill  (break)"""


@dataclass
class IdleStmt(Node):
    """idle  (pass)"""


@dataclass
class RedlineStmt(Node):
    """redline expr  (raise)"""
    value: Optional[Node] = None


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------

@dataclass
class IgniteStmt(Node):
    """ignite cond: body  [drift ignite cond: body]* [drift: body]"""
    condition: Optional[Node] = None
    body: List[Node] = field(default_factory=list)
    orelse: List[Node] = field(default_factory=list)    # drift branches


@dataclass
class RevStmt(Node):
    """rev condition: body  (while)"""
    condition: Optional[Node] = None
    body: List[Node] = field(default_factory=list)


@dataclass
class BurnStmt(Node):
    """burn var in iterable: body  (for)"""
    var: str = ""
    iterable: Optional[Node] = None
    body: List[Node] = field(default_factory=list)


@dataclass
class StallStmt(Node):
    """stall: body  redline expr  (try/except)"""
    body: List[Node] = field(default_factory=list)
    handler: List[Node] = field(default_factory=list)
    exception: Optional[Node] = None


# ---------------------------------------------------------------------------
# Function definition
# ---------------------------------------------------------------------------

@dataclass
class Param(Node):
    """Single parameter: name@type"""
    name: str = ""
    type_ann: Optional[str] = None


@dataclass
class ForgeStmt(Node):
    """forge name(params): body"""
    name: str = ""
    params: List[Param] = field(default_factory=list)
    body: List[Node] = field(default_factory=list)
    return_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

@dataclass
class NumberLiteral(Node):
    value: int = 0


@dataclass
class FloatLiteral(Node):
    value: float = 0.0


@dataclass
class StringLiteral(Node):
    value: str = ""


@dataclass
class BoolLiteral(Node):
    value: bool = False


@dataclass
class NoneLiteral(Node):
    pass


@dataclass
class NameExpr(Node):
    name: str = ""


@dataclass
class ListExpr(Node):
    elements: List[Node] = field(default_factory=list)


@dataclass
class DictExpr(Node):
    keys: List[Node] = field(default_factory=list)
    values: List[Node] = field(default_factory=list)


@dataclass
class BinOp(Node):
    op: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None


@dataclass
class UnaryOp(Node):
    op: str = ""
    operand: Optional[Node] = None


@dataclass
class CallExpr(Node):
    func: str = ""
    args: List[Node] = field(default_factory=list)


@dataclass
class PipeExpr(Node):
    """expr -> func -> func …  resolved left-to-right"""
    left: Optional[Node] = None
    func: str = ""           # right-hand side must be a plain name for now
