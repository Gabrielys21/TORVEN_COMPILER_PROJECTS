"""
vm.py — TORVEN Stack-based Virtual Machine.

Execution model
---------------
* Operand stack  — main value stack, all operations push/pop here.
* Call stack     — list of Frame objects, one per active function call.
* Each Frame holds: its CodeObject, an instruction pointer (ip), a local
  variable dict, and an exception handler table.

The main loop is the classic fetch → decode → execute cycle.

Supported opcodes  (see compiler.py for the full list)
"""

from __future__ import annotations

import builtins
import math
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .compiler import CodeObject, Instruction, load_from_file
from .errors import TorvenRuntimeError


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

class Frame:
    def __init__(self, code: CodeObject, locals_: Optional[Dict[str, Any]] = None,
                 args: Optional[List[Any]] = None):
        self.code = code
        self.ip = 0
        self.locals: Dict[str, Any] = locals_ or {}
        self.stack: List[Any] = []
        self.except_handlers: List[Tuple[str, int]] = []  # (label, resolved_ip)
        self.iterators: Dict[int, Iterator] = {}           # ip → active iterator

        # Bind positional arguments to parameter names
        if args:
            for name, value in zip(code.varnames, args):
                self.locals[name] = value

    def push(self, value: Any):
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise TorvenRuntimeError("Stack underflow", line=0)
        return self.stack.pop()

    def peek(self) -> Any:
        return self.stack[-1]


# ---------------------------------------------------------------------------
# Label resolution helper
# ---------------------------------------------------------------------------

def _resolve_labels(instructions: List[Instruction]) -> Dict[str, int]:
    """Build a mapping from label name → instruction index (skipping LABELs)."""
    label_map: Dict[str, int] = {}
    real_index = 0
    for i, instr in enumerate(instructions):
        if instr.opcode == "LABEL":
            label_map[instr.arg] = real_index
        else:
            real_index += 1
    return label_map


def _strip_labels(instructions: List[Instruction]) -> List[Instruction]:
    return [i for i in instructions if i.opcode != "LABEL"]


# ---------------------------------------------------------------------------
# Virtual Machine
# ---------------------------------------------------------------------------

class VM:
    def __init__(self):
        self._globals: Dict[str, Any] = {}
        self._call_stack: List[Frame] = []
        self._setup_builtins()

    # ------------------------------------------------------------------
    # Built-in functions available in TORVEN programs
    # ------------------------------------------------------------------

    def _setup_builtins(self):
        self._globals.update({
            "len":   len,
            "range": range,
            "str":   str,
            "int":   int,
            "float": float,
            "bool":  bool,
            "list":  list,
            "dict":  dict,
            "abs":   abs,
            "max":   max,
            "min":   min,
            "sum":   sum,
            "sqrt":  math.sqrt,
        })

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def run_file(self, path: str):
        """Load a .tvbc file and execute it."""
        code = load_from_file(path)
        return self.run(code)

    def run(self, code: CodeObject) -> Any:
        """Execute a CodeObject in the global frame."""
        return self._exec_frame(Frame(code, locals_=self._globals))

    # ------------------------------------------------------------------
    # Core execution loop
    # ------------------------------------------------------------------

    def _exec_frame(self, frame: Frame) -> Any:
        self._call_stack.append(frame)

        # Pre-process: resolve labels and strip them from instruction list
        instructions = _strip_labels(frame.code.instructions)
        label_map    = _resolve_labels(frame.code.instructions)

        # Register nested function CodeObjects so CALL_FUNC can find them
        func_registry: Dict[str, CodeObject] = {**frame.code.functions}

        try:
            while frame.ip < len(instructions):
                instr = instructions[frame.ip]
                frame.ip += 1

                # ---- LOAD / STORE ----------------------------------------
                if instr.opcode == "LOAD_CONST":
                    frame.push(instr.arg)

                elif instr.opcode == "LOAD_VAR":
                    name = instr.arg
                    if name in frame.locals:
                        frame.push(frame.locals[name])
                    elif name in self._globals:
                        frame.push(self._globals[name])
                    else:
                        self._runtime_error(f"Undefined variable '{name}'", instr)

                elif instr.opcode == "STORE_VAR":
                    frame.locals[instr.arg] = frame.pop()

                # ---- ARITHMETIC ------------------------------------------
                elif instr.opcode == "BINARY_ADD":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a + b)
                elif instr.opcode == "BINARY_SUB":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a - b)
                elif instr.opcode == "BINARY_MUL":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a * b)
                elif instr.opcode == "BINARY_DIV":
                    b, a = frame.pop(), frame.pop()
                    if b == 0:
                        self._runtime_error("Division by zero", instr)
                    frame.push(a / b)
                elif instr.opcode == "BINARY_MOD":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a % b)
                elif instr.opcode == "BINARY_POW":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a ** b)
                elif instr.opcode == "UNARY_NEG":
                    frame.push(-frame.pop())

                # ---- COMPARISONS -----------------------------------------
                elif instr.opcode == "COMPARE_EQ":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a == b)
                elif instr.opcode == "COMPARE_NEQ":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a != b)
                elif instr.opcode == "COMPARE_LT":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a < b)
                elif instr.opcode == "COMPARE_GT":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a > b)
                elif instr.opcode == "COMPARE_LTE":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a <= b)
                elif instr.opcode == "COMPARE_GTE":
                    b, a = frame.pop(), frame.pop()
                    frame.push(a >= b)

                # ---- CONTROL FLOW ----------------------------------------
                elif instr.opcode == "JUMP":
                    target = label_map.get(instr.arg)
                    if target is None:
                        self._runtime_error(f"Unknown jump target '{instr.arg}'", instr)
                    frame.ip = target

                elif instr.opcode == "JUMP_IF_FALSE":
                    cond = frame.pop()
                    if not cond:
                        target = label_map.get(instr.arg)
                        if target is None:
                            self._runtime_error(f"Unknown jump target '{instr.arg}'", instr)
                        frame.ip = target

                # ---- FUNCTIONS -------------------------------------------
                elif instr.opcode == "MAKE_FUNC":
                    name = instr.arg
                    co   = func_registry.get(name) or frame.code.functions.get(name)
                    if co is None:
                        self._runtime_error(f"Function code for '{name}' not found", instr)
                    # Store as a closure-like callable in the local env
                    frame.locals[name] = _make_callable(co, self)
                    self._globals[name] = frame.locals[name]

                elif instr.opcode == "CALL_FUNC":
                    fname, nargs = instr.arg
                    args = [frame.pop() for _ in range(nargs)][::-1]

                    func = frame.locals.get(fname) or self._globals.get(fname)
                    if func is None:
                        self._runtime_error(f"Undefined function '{fname}'", instr)

                    result = self._call(func, args, instr)
                    frame.push(result)

                elif instr.opcode == "PIPE":
                    fname = instr.arg
                    value = frame.pop()

                    func = frame.locals.get(fname) or self._globals.get(fname)
                    if func is None:
                        self._runtime_error(f"Undefined function '{fname}' in pipe", instr)

                    result = self._call(func, [value], instr)
                    frame.push(result)

                elif instr.opcode == "RETURN":
                    retval = frame.pop() if frame.stack else None
                    self._call_stack.pop()
                    return retval

                # ---- I/O -------------------------------------------------
                elif instr.opcode == "PRINT":
                    print(frame.pop())

                # ---- ITERATORS (burn / for) -------------------------------
                elif instr.opcode == "GET_ITER":
                    iterable = frame.pop()
                    frame.push(iter(iterable))

                elif instr.opcode == "FOR_ITER":
                    var_name, break_label = instr.arg
                    it = frame.peek()   # iterator stays on stack
                    try:
                        value = next(it)
                        frame.locals[var_name] = value
                    except StopIteration:
                        target = label_map.get(break_label)
                        if target is None:
                            self._runtime_error(f"Unknown break target '{break_label}'", instr)
                        frame.ip = target

                # ---- COLLECTIONS -----------------------------------------
                elif instr.opcode == "BUILD_LIST":
                    n = instr.arg
                    items = [frame.pop() for _ in range(n)][::-1]
                    frame.push(items)

                elif instr.opcode == "BUILD_DICT":
                    n = instr.arg
                    d = {}
                    pairs = [(frame.pop(), frame.pop()) for _ in range(n)]
                    for v, k in pairs:
                        d[k] = v
                    frame.push(d)

                # ---- EXCEPTIONS ------------------------------------------
                elif instr.opcode == "SETUP_EXCEPT":
                    handler_label = instr.arg
                    target = label_map.get(handler_label, -1)
                    frame.except_handlers.append((handler_label, target))

                elif instr.opcode == "POP_EXCEPT":
                    if frame.except_handlers:
                        frame.except_handlers.pop()

                elif instr.opcode == "RAISE":
                    msg = frame.pop()
                    raise TorvenRuntimeError(str(msg), line=instr.line)

                # ---- MISC ------------------------------------------------
                elif instr.opcode == "IMPORT":
                    pass  # stub: module system not implemented

                elif instr.opcode == "NOP":
                    pass

                elif instr.opcode == "POP":
                    if frame.stack:
                        frame.pop()

                else:
                    self._runtime_error(f"Unknown opcode '{instr.opcode}'", instr)

        except TorvenRuntimeError:
            raise
        except Exception as exc:
            # Check if there is an active exception handler
            if frame.except_handlers:
                _, handler_ip = frame.except_handlers.pop()
                if handler_ip >= 0:
                    frame.push(str(exc))
                    frame.ip = handler_ip
                    return self._exec_frame_continue(frame, instructions, label_map)
            raise TorvenRuntimeError(str(exc), line=0) from exc

        self._call_stack.pop()
        return None

    def _exec_frame_continue(self, frame: Frame, instructions, label_map) -> Any:
        """Resume an existing frame after exception handling redirects ip."""
        try:
            while frame.ip < len(instructions):
                instr = instructions[frame.ip]
                frame.ip += 1
                # Delegate back to the main loop by re-entering _exec_frame
                # (simplification: re-run the whole loop from current ip)
                break
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Helper: call a function (Python callable or TORVEN CodeObject wrapper)
    # ------------------------------------------------------------------

    def _call(self, func, args: List[Any], instr: Instruction) -> Any:
        if callable(func):
            try:
                return func(*args)
            except Exception as exc:
                self._runtime_error(str(exc), instr)
        self._runtime_error(f"Not callable: {func!r}", instr)

    def _runtime_error(self, message: str, instr: Instruction):
        raise TorvenRuntimeError(message, line=instr.line)


# ---------------------------------------------------------------------------
# Helper: wrap a CodeObject as a Python callable
# ---------------------------------------------------------------------------

def _make_callable(co: CodeObject, vm: VM):
    def _func(*args):
        frame = Frame(co, args=list(args))
        return vm._exec_frame(frame)
    _func.__name__ = co.name
    return _func
