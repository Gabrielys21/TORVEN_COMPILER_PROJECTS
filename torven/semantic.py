"""
semantic.py — Semantic analysis pass for TORVEN.

Walks the AST produced by parser.py and performs:
  1. Scope tracking  — variables are resolved through a stack of symbol tables.
  2. Type annotation checking — @torq, @venom, @exhaust, @spark, @barrel,
     @chassis, @void are recorded and their literal-value compatibility is
     verified at declaration time.
  3. Undefined-variable detection.
  4. Const mutation detection (lock variables cannot be re-assigned).

All errors are collected into a list so that a single pass reports every
problem rather than stopping on the first one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .ast_nodes import *
from .errors import TorvenTypeError


# ---------------------------------------------------------------------------
# Type system helpers
# ---------------------------------------------------------------------------

TORVEN_TYPES = {"torq", "venom", "exhaust", "spark", "barrel", "chassis", "void"}

# Python type → TORVEN type name
_PY_TO_TORVEN: Dict[type, str] = {
    int:   "torq",
    float: "venom",
    str:   "exhaust",
    bool:  "spark",
    list:  "barrel",
    dict:  "chassis",
    type(None): "void",
}

def _infer_literal_type(node: Node) -> Optional[str]:
    """Return the TORVEN type name for a literal node, or None."""
    mapping = {
        NumberLiteral: "torq",
        FloatLiteral:  "venom",
        StringLiteral: "exhaust",
        BoolLiteral:   "spark",
        ListExpr:      "barrel",
        DictExpr:      "chassis",
        NoneLiteral:   "void",
    }
    return mapping.get(type(node))


# ---------------------------------------------------------------------------
# Symbol table entry
# ---------------------------------------------------------------------------

class Symbol:
    def __init__(self, name: str, type_ann: Optional[str], mutable: bool, line: int):
        self.name = name
        self.type_ann = type_ann
        self.mutable = mutable
        self.line = line


# ---------------------------------------------------------------------------
# Scope stack
# ---------------------------------------------------------------------------

class Scope:
    def __init__(self, parent: Optional["Scope"] = None):
        self._table: Dict[str, Symbol] = {}
        self.parent = parent

    def define(self, sym: Symbol):
        self._table[sym.name] = sym

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self._table:
            return self._table[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self._table.get(name)


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class SemanticAnalyser:
    def __init__(self):
        self.errors: List[TorvenTypeError] = []
        self._scope: Scope = Scope()           # global scope
        self._current_func: Optional[str] = None

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _error(self, message: str, line: int):
        self.errors.append(TorvenTypeError(message, line=line))

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    def _push_scope(self):
        self._scope = Scope(parent=self._scope)

    def _pop_scope(self):
        self._scope = self._scope.parent  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def analyse(self, program: Program) -> List[TorvenTypeError]:
        self._visit_stmts(program.body)
        return self.errors

    # ------------------------------------------------------------------
    # Statement visitors
    # ------------------------------------------------------------------

    def _visit_stmts(self, stmts: List[Node]):
        for stmt in stmts:
            self._visit(stmt)

    def _visit(self, node: Node):
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, self._visit_generic)
        visitor(node)

    def _visit_generic(self, node: Node):
        pass

    def _visit_ImportStmt(self, node: ImportStmt):
        pass  # module resolution happens at runtime

    def _visit_LoadStmt(self, node: LoadStmt):
        if node.value is not None:
            self._check_expr(node.value)
            inferred = _infer_literal_type(node.value)
            if node.type_ann and inferred and inferred != node.type_ann:
                self._error(
                    f"Type mismatch: variable '{node.name}' declared as "
                    f"@{node.type_ann} but assigned a {inferred} literal",
                    node.line,
                )
        sym = Symbol(node.name, node.type_ann, node.mutable, node.line)
        self._scope.define(sym)

    def _visit_AssignStmt(self, node: AssignStmt):
        sym = self._scope.lookup(node.name)
        if sym is None:
            self._error(f"Assignment to undefined variable '{node.name}'", node.line)
            return
        if not sym.mutable:
            self._error(
                f"Cannot reassign lock (const) variable '{node.name}' "
                f"defined at line {sym.line}",
                node.line,
            )
        if node.value is not None:
            self._check_expr(node.value)
            inferred = _infer_literal_type(node.value)
            if sym.type_ann and inferred and inferred != sym.type_ann:
                self._error(
                    f"Type mismatch: '{node.name}' is @{sym.type_ann} "
                    f"but assigned a {inferred} literal",
                    node.line,
                )

    def _visit_EjectStmt(self, node: EjectStmt):
        if node.value:
            self._check_expr(node.value)

    def _visit_VentStmt(self, node: VentStmt):
        if node.value:
            self._check_expr(node.value)

    def _visit_KillStmt(self, node: KillStmt):
        pass

    def _visit_IdleStmt(self, node: IdleStmt):
        pass

    def _visit_RedlineStmt(self, node: RedlineStmt):
        if node.value:
            self._check_expr(node.value)

    def _visit_ForgeStmt(self, node: ForgeStmt):
        # Register function name in current scope
        sym = Symbol(node.name, node.return_type, mutable=True, line=node.line)
        self._scope.define(sym)

        prev_func = self._current_func
        self._current_func = node.name
        self._push_scope()

        for param in node.params:
            psym = Symbol(param.name, param.type_ann, mutable=True, line=param.line)
            self._scope.define(psym)

        self._visit_stmts(node.body)
        self._pop_scope()
        self._current_func = prev_func

    def _visit_IgniteStmt(self, node: IgniteStmt):
        if node.condition:
            self._check_expr(node.condition)
        self._push_scope()
        self._visit_stmts(node.body)
        self._pop_scope()
        if node.orelse:
            self._push_scope()
            self._visit_stmts(node.orelse)
            self._pop_scope()

    def _visit_RevStmt(self, node: RevStmt):
        if node.condition:
            self._check_expr(node.condition)
        self._push_scope()
        self._visit_stmts(node.body)
        self._pop_scope()

    def _visit_BurnStmt(self, node: BurnStmt):
        if node.iterable:
            self._check_expr(node.iterable)
        self._push_scope()
        # loop variable is defined inside the block
        loop_sym = Symbol(node.var, None, mutable=True, line=node.line)
        self._scope.define(loop_sym)
        self._visit_stmts(node.body)
        self._pop_scope()

    def _visit_StallStmt(self, node: StallStmt):
        self._push_scope()
        self._visit_stmts(node.body)
        self._pop_scope()
        if node.handler:
            self._push_scope()
            self._visit_stmts(node.handler)
            self._pop_scope()

    # ------------------------------------------------------------------
    # Expression checker (resolves names, recurses into sub-expressions)
    # ------------------------------------------------------------------

    def _check_expr(self, node: Node):
        if isinstance(node, NameExpr):
            if self._scope.lookup(node.name) is None:
                self._error(f"Undefined variable '{node.name}'", node.line)
        elif isinstance(node, BinOp):
            self._check_expr(node.left)   # type: ignore[arg-type]
            self._check_expr(node.right)  # type: ignore[arg-type]
        elif isinstance(node, UnaryOp):
            self._check_expr(node.operand)  # type: ignore[arg-type]
        elif isinstance(node, CallExpr):
            if self._scope.lookup(node.func) is None:
                # Allow built-in names through
                if node.func not in _BUILTINS:
                    self._error(f"Call to undefined function '{node.func}'", node.line)
            for arg in node.args:
                self._check_expr(arg)
        elif isinstance(node, PipeExpr):
            self._check_expr(node.left)  # type: ignore[arg-type]
            if self._scope.lookup(node.func) is None and node.func not in _BUILTINS:
                self._error(f"Pipe to undefined function '{node.func}'", node.line)
        elif isinstance(node, ListExpr):
            for el in node.elements:
                self._check_expr(el)
        elif isinstance(node, DictExpr):
            for k, v in zip(node.keys, node.values):
                self._check_expr(k)
                self._check_expr(v)


_BUILTINS = {"len", "range", "str", "int", "float", "bool", "list", "dict", "print"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse(program: Program) -> List[TorvenTypeError]:
    """Run semantic analysis and return a (possibly empty) list of errors."""
    analyser = SemanticAnalyser()
    return analyser.analyse(program)
