"""
compiler.py — AST → TORVEN Bytecode compiler.

Walks the AST and emits a flat list of Instruction objects.  The instruction
set is intentionally close to CPython's dis module so the architecture is easy
to explain and extend.

Instruction set
---------------
LOAD_CONST   value          push a constant onto the stack
LOAD_VAR     name           push the value of a variable
STORE_VAR    name           pop TOS and store in variable
BINARY_ADD                  pop two values, push sum
BINARY_SUB                  pop two values, push difference
BINARY_MUL                  pop two values, push product
BINARY_DIV                  pop two values, push quotient
BINARY_MOD                  pop two values, push modulo
BINARY_POW                  pop two values, push power
COMPARE_EQ                  pop two values, push (a == b)
COMPARE_NEQ                 pop two values, push (a != b)
COMPARE_LT                  pop two values, push (a < b)
COMPARE_GT                  pop two values, push (a > b)
COMPARE_LTE                 pop two values, push (a <= b)
COMPARE_GTE                 pop two values, push (a >= b)
UNARY_NEG                   pop TOS, push -TOS
JUMP_IF_FALSE target        pop TOS; if falsy jump to target index
JUMP          target        unconditional jump to target index
CALL_FUNC     name nargs    pop nargs args + call named function
MAKE_FUNC     name code     define function in current scope
RETURN                      pop TOS and return from current frame
PRINT                       pop TOS and print it
PUSH                        (generic; used internally)
POP                         discard TOS
BUILD_LIST    n             pop n items, push list
BUILD_DICT    n             pop 2n items (k,v pairs), push dict
PIPE          func          pop TOS, call func(TOS), push result
ITER_NEXT     target        advance iterator; jump to target if exhausted
FOR_ITER      var           store next() into var
SETUP_EXCEPT  handler       register exception handler at index
POP_EXCEPT                  unregister the current exception handler
RAISE                       pop TOS and raise it as a runtime error
IMPORT        name          import module (stub)
LABEL         name          pseudo-instruction resolved to an index
"""

from __future__ import annotations

import pickle
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .ast_nodes import *
from .errors import TorvenCompileError

# ---------------------------------------------------------------------------
# Instruction definition
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    opcode: str
    arg: Any = None
    line: int = 0

    def __repr__(self):
        if self.arg is not None:
            return f"{self.opcode:<16} {self.arg!r:<20}  ; line {self.line}"
        return f"{self.opcode:<16}                      ; line {self.line}"


# ---------------------------------------------------------------------------
# Code object (analogous to CPython code object)
# ---------------------------------------------------------------------------

@dataclass
class CodeObject:
    name: str
    instructions: List[Instruction] = field(default_factory=list)
    constants: List[Any] = field(default_factory=list)
    varnames: List[str] = field(default_factory=list)
    # nested code objects keyed by function name
    functions: Dict[str, "CodeObject"] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

class Compiler:
    def __init__(self):
        self._code: CodeObject = CodeObject(name="<module>")
        self._scope_stack: List[CodeObject] = [self._code]
        self._label_counter: int = 0
        self._loop_stack: List[Tuple[str, str]] = []  # (continue_label, break_label)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _current(self) -> CodeObject:
        return self._scope_stack[-1]

    def _emit(self, opcode: str, arg: Any = None, line: int = 0):
        self._current.instructions.append(Instruction(opcode, arg, line))

    def _new_label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}_{self._label_counter}"

    def _patch_label(self, label: str):
        """Emit a LABEL pseudo-instruction at the current position."""
        self._emit("LABEL", label)

    def _push_scope(self, name: str) -> CodeObject:
        co = CodeObject(name=name)
        self._scope_stack.append(co)
        return co

    def _pop_scope(self) -> CodeObject:
        return self._scope_stack.pop()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def compile(self, program: Program) -> CodeObject:
        self._visit_stmts(program.body)
        self._emit("LOAD_CONST", None)
        self._emit("RETURN")
        return self._code

    # ------------------------------------------------------------------
    # Statement dispatch
    # ------------------------------------------------------------------

    def _visit_stmts(self, stmts: List[Node]):
        for stmt in stmts:
            if stmt is not None:
                self._visit(stmt)

    def _visit(self, node: Node):
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, None)
        if visitor is None:
            raise TorvenCompileError(
                f"No compiler handler for {type(node).__name__}", line=node.line
            )
        visitor(node)

    def _visit_CallExpr(self, node: CallExpr):
        """Bare function call used as a statement — evaluate and discard result."""
        self._expr_CallExpr(node)
        self._emit("POP", None, node.line)

    def _visit_PipeExpr(self, node: PipeExpr):
        self._expr_PipeExpr(node)
        self._emit("POP", None, node.line)

    def _visit_BinOp(self, node: BinOp):
        self._expr_BinOp(node)
        self._emit("POP", None, node.line)

    def _visit_NameExpr(self, node: NameExpr):
        pass  # bare name as statement is a no-op

    def _visit_ImportStmt(self, node: ImportStmt):
        self._emit("IMPORT", node.module, node.line)

    def _visit_LoadStmt(self, node: LoadStmt):
        if node.value is not None:
            self._visit_expr(node.value)
        else:
            self._emit("LOAD_CONST", None, node.line)
        self._emit("STORE_VAR", node.name, node.line)

    def _visit_AssignStmt(self, node: AssignStmt):
        self._visit_expr(node.value)
        self._emit("STORE_VAR", node.name, node.line)

    def _visit_EjectStmt(self, node: EjectStmt):
        if node.value is not None:
            self._visit_expr(node.value)
        else:
            self._emit("LOAD_CONST", None, node.line)
        self._emit("RETURN", None, node.line)

    def _visit_VentStmt(self, node: VentStmt):
        self._visit_expr(node.value)
        self._emit("PRINT", None, node.line)

    def _visit_KillStmt(self, node: KillStmt):
        if not self._loop_stack:
            raise TorvenCompileError("'kill' outside loop", node.line)
        _, break_label = self._loop_stack[-1]
        self._emit("JUMP", break_label, node.line)

    def _visit_IdleStmt(self, node: IdleStmt):
        self._emit("NOP", None, node.line)

    def _visit_RedlineStmt(self, node: RedlineStmt):
        self._visit_expr(node.value)
        self._emit("RAISE", None, node.line)

    # --- forge / function -------------------------------------------------

    def _visit_ForgeStmt(self, node: ForgeStmt):
        # Compile function body into its own CodeObject
        func_co = self._push_scope(node.name)
        for param in node.params:
            func_co.varnames.append(param.name)
        self._visit_stmts(node.body)
        # Ensure every path returns
        self._emit("LOAD_CONST", None, node.line)
        self._emit("RETURN", None, node.line)
        self._pop_scope()

        # Register in parent code object and emit MAKE_FUNC
        self._current.functions[node.name] = func_co
        self._emit("MAKE_FUNC", node.name, node.line)

    # --- ignite / if ------------------------------------------------------

    def _visit_IgniteStmt(self, node: IgniteStmt):
        end_label = self._new_label("END_IF")
        self._visit_expr(node.condition)
        if node.orelse:
            else_label = self._new_label("ELSE")
            self._emit("JUMP_IF_FALSE", else_label, node.line)
            self._visit_stmts(node.body)
            self._emit("JUMP", end_label, node.line)
            self._patch_label(else_label)
            self._visit_stmts(node.orelse)
        else:
            self._emit("JUMP_IF_FALSE", end_label, node.line)
            self._visit_stmts(node.body)
        self._patch_label(end_label)

    # --- rev / while ------------------------------------------------------

    def _visit_RevStmt(self, node: RevStmt):
        loop_label  = self._new_label("REV_START")
        break_label = self._new_label("REV_END")
        self._loop_stack.append((loop_label, break_label))

        self._patch_label(loop_label)
        self._visit_expr(node.condition)
        self._emit("JUMP_IF_FALSE", break_label, node.line)
        self._visit_stmts(node.body)
        self._emit("JUMP", loop_label, node.line)
        self._patch_label(break_label)

        self._loop_stack.pop()

    # --- burn / for -------------------------------------------------------

    def _visit_BurnStmt(self, node: BurnStmt):
        loop_label  = self._new_label("BURN_NEXT")
        break_label = self._new_label("BURN_END")
        self._loop_stack.append((loop_label, break_label))

        # Build iterator from iterable
        self._visit_expr(node.iterable)
        self._emit("GET_ITER", None, node.line)

        self._patch_label(loop_label)
        self._emit("FOR_ITER", (node.var, break_label), node.line)
        self._visit_stmts(node.body)
        self._emit("JUMP", loop_label, node.line)
        self._patch_label(break_label)
        self._emit("POP", None, node.line)   # discard exhausted iterator

        self._loop_stack.pop()

    # --- stall / try ------------------------------------------------------

    def _visit_StallStmt(self, node: StallStmt):
        handler_label = self._new_label("STALL_HANDLER")
        end_label     = self._new_label("STALL_END")

        self._emit("SETUP_EXCEPT", handler_label, node.line)
        self._visit_stmts(node.body)
        self._emit("POP_EXCEPT", None, node.line)
        self._emit("JUMP", end_label, node.line)

        self._patch_label(handler_label)
        if node.exception:
            self._visit_expr(node.exception)
            self._emit("RAISE", None, node.line)
        if node.handler:
            self._visit_stmts(node.handler)

        self._patch_label(end_label)

    # ------------------------------------------------------------------
    # Expression dispatch
    # ------------------------------------------------------------------

    def _visit_expr(self, node: Node):
        method = f"_expr_{type(node).__name__}"
        visitor = getattr(self, method, None)
        if visitor is None:
            raise TorvenCompileError(
                f"No expression handler for {type(node).__name__}", line=node.line
            )
        visitor(node)

    def _expr_NumberLiteral(self, node: NumberLiteral):
        self._emit("LOAD_CONST", node.value, node.line)

    def _expr_FloatLiteral(self, node: FloatLiteral):
        self._emit("LOAD_CONST", node.value, node.line)

    def _expr_StringLiteral(self, node: StringLiteral):
        self._emit("LOAD_CONST", node.value, node.line)

    def _expr_BoolLiteral(self, node: BoolLiteral):
        self._emit("LOAD_CONST", node.value, node.line)

    def _expr_NoneLiteral(self, node: NoneLiteral):
        self._emit("LOAD_CONST", None, node.line)

    def _expr_NameExpr(self, node: NameExpr):
        self._emit("LOAD_VAR", node.name, node.line)

    def _expr_ListExpr(self, node: ListExpr):
        for el in node.elements:
            self._visit_expr(el)
        self._emit("BUILD_LIST", len(node.elements), node.line)

    def _expr_DictExpr(self, node: DictExpr):
        for k, v in zip(node.keys, node.values):
            self._visit_expr(k)
            self._visit_expr(v)
        self._emit("BUILD_DICT", len(node.keys), node.line)

    _BINOP_MAP = {
        "+":  "BINARY_ADD",
        "-":  "BINARY_SUB",
        "*":  "BINARY_MUL",
        "/":  "BINARY_DIV",
        "%":  "BINARY_MOD",
        "^^": "BINARY_POW",
        "~~": "COMPARE_EQ",
        "!~": "COMPARE_NEQ",
        "<":  "COMPARE_LT",
        ">":  "COMPARE_GT",
        "<=": "COMPARE_LTE",
        ">=": "COMPARE_GTE",
    }

    def _expr_BinOp(self, node: BinOp):
        self._visit_expr(node.left)
        self._visit_expr(node.right)
        opcode = self._BINOP_MAP.get(node.op)
        if opcode is None:
            raise TorvenCompileError(f"Unknown binary op '{node.op}'", node.line)
        self._emit(opcode, None, node.line)

    def _expr_UnaryOp(self, node: UnaryOp):
        self._visit_expr(node.operand)
        if node.op == '-':
            self._emit("UNARY_NEG", None, node.line)

    def _expr_CallExpr(self, node: CallExpr):
        for arg in node.args:
            self._visit_expr(arg)
        self._emit("CALL_FUNC", (node.func, len(node.args)), node.line)

    def _expr_PipeExpr(self, node: PipeExpr):
        # Evaluate left side (becomes the single argument)
        self._visit_expr(node.left)
        # PIPE pops TOS, passes it as argument to func
        self._emit("PIPE", node.func, node.line)


# ---------------------------------------------------------------------------
# Serialisation (to .tvbc)
# ---------------------------------------------------------------------------

MAGIC = b"TORVEN\x01"  # 7-byte magic header


def serialize(code_obj: CodeObject) -> bytes:
    """Pickle the CodeObject and prepend a magic header."""
    payload = pickle.dumps(code_obj, protocol=4)
    return MAGIC + struct.pack(">I", len(payload)) + payload


def deserialize(data: bytes) -> CodeObject:
    if not data.startswith(MAGIC):
        raise ValueError("Not a TORVEN bytecode file (.tvbc)")
    size = struct.unpack(">I", data[len(MAGIC): len(MAGIC) + 4])[0]
    payload = data[len(MAGIC) + 4: len(MAGIC) + 4 + size]
    return pickle.loads(payload)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_ast(program: Program) -> CodeObject:
    return Compiler().compile(program)


def compile_to_file(program: Program, path: str):
    co = compile_ast(program)
    with open(path, "wb") as f:
        f.write(serialize(co))
    return co


def load_from_file(path: str) -> CodeObject:
    with open(path, "rb") as f:
        return deserialize(f.read())
