"""
parser.py — TORVEN Parser built with PLY.

Consumes the token stream produced by TorvenLexer (including synthetic
INDENT / DEDENT tokens) and builds a typed AST using the node classes in
ast_nodes.py.

Grammar overview
----------------
program         : stmt_list
stmt_list       : stmt*
stmt            : simple_stmt NEWLINE
                | compound_stmt
simple_stmt     : load_stmt | lock_stmt | assign_stmt | eject_stmt
                | vent_stmt | import_stmt | kill_stmt | idle_stmt
                | redline_stmt | expr_stmt
compound_stmt   : forge_stmt | ignite_stmt | rev_stmt | burn_stmt | stall_stmt
block           : NEWLINE INDENT stmt_list DEDENT
"""

from __future__ import annotations

from typing import List, Optional

import ply.yacc as yacc

from .lexer import tokens, make_lexer  # noqa: F401  (PLY needs ``tokens`` importable)
from .ast_nodes import *
from .errors import TorvenParseError

# PLY needs the ``tokens`` name at module level
__all__ = ["make_parser", "tokens"]


# ---------------------------------------------------------------------------
# Precedence table (lowest → highest)
# ---------------------------------------------------------------------------

precedence = (
    ("left",  "PIPE"),
    ("left",  "EQ", "NEQ"),
    ("left",  "LT", "GT", "LTE", "GTE"),
    ("left",  "PLUS", "MINUS"),
    ("left",  "TIMES", "DIVIDE", "MOD"),
    ("right", "POW"),
    ("right", "UMINUS"),
)


# ---------------------------------------------------------------------------
# Grammar rules
# ---------------------------------------------------------------------------

def p_program(p):
    "program : stmt_list"
    p[0] = Program(body=p[1], line=1)


# --- statement list --------------------------------------------------------

def p_stmt_list_empty(p):
    "stmt_list : empty"
    p[0] = []

def p_stmt_list(p):
    "stmt_list : stmt_list stmt"
    p[0] = p[1] + ([p[2]] if p[2] is not None else [])


# --- statement dispatch ----------------------------------------------------

def p_stmt_simple(p):
    """stmt : load_stmt NEWLINE
            | lock_stmt NEWLINE
            | assign_stmt NEWLINE
            | eject_stmt NEWLINE
            | vent_stmt NEWLINE
            | import_stmt NEWLINE
            | kill_stmt NEWLINE
            | idle_stmt NEWLINE
            | redline_stmt NEWLINE
            | expr_stmt NEWLINE"""
    p[0] = p[1]

def p_stmt_compound(p):
    """stmt : forge_stmt
            | ignite_stmt
            | rev_stmt
            | burn_stmt
            | stall_stmt"""
    p[0] = p[1]

def p_stmt_newline(p):
    "stmt : NEWLINE"
    p[0] = None


# --- import ---------------------------------------------------------------

def p_import_stmt(p):
    "import_stmt : INJECT NAME"
    p[0] = ImportStmt(module=p[2], line=p.lineno(1))


# --- variable declarations ------------------------------------------------

def p_load_stmt_typed(p):
    "load_stmt : LOAD NAME AT type_ann ASSIGN expr"
    p[0] = LoadStmt(name=p[2], type_ann=p[4], value=p[6], mutable=True, line=p.lineno(1))

def p_load_stmt_untyped(p):
    "load_stmt : LOAD NAME ASSIGN expr"
    p[0] = LoadStmt(name=p[2], type_ann=None, value=p[4], mutable=True, line=p.lineno(1))

def p_lock_stmt_typed(p):
    "lock_stmt : LOCK NAME AT type_ann ASSIGN expr"
    p[0] = LoadStmt(name=p[2], type_ann=p[4], value=p[6], mutable=False, line=p.lineno(1))

def p_lock_stmt_untyped(p):
    "lock_stmt : LOCK NAME ASSIGN expr"
    p[0] = LoadStmt(name=p[2], type_ann=None, value=p[4], mutable=False, line=p.lineno(1))

def p_assign_stmt(p):
    "assign_stmt : NAME ASSIGN expr"
    p[0] = AssignStmt(name=p[1], value=p[3], line=p.lineno(1))


# --- type annotations -----------------------------------------------------

def p_type_ann(p):
    """type_ann : TYPE_TORQ
               | TYPE_VENOM
               | TYPE_EXHAUST
               | TYPE_SPARK
               | TYPE_BARREL
               | TYPE_CHASSIS
               | TYPE_VOID"""
    p[0] = p[1]


# --- eject / return -------------------------------------------------------

def p_eject_stmt(p):
    "eject_stmt : EJECT expr"
    p[0] = EjectStmt(value=p[2], line=p.lineno(1))

def p_eject_stmt_empty(p):
    "eject_stmt : EJECT"
    p[0] = EjectStmt(value=None, line=p.lineno(1))


# --- vent / print ---------------------------------------------------------

def p_vent_stmt(p):
    "vent_stmt : VENT expr"
    p[0] = VentStmt(value=p[2], line=p.lineno(1))


# --- kill / break ---------------------------------------------------------

def p_kill_stmt(p):
    "kill_stmt : KILL"
    p[0] = KillStmt(line=p.lineno(1))


# --- idle / pass ----------------------------------------------------------

def p_idle_stmt(p):
    "idle_stmt : IDLE"
    p[0] = IdleStmt(line=p.lineno(1))


# --- redline / raise ------------------------------------------------------

def p_redline_stmt(p):
    "redline_stmt : REDLINE expr"
    p[0] = RedlineStmt(value=p[2], line=p.lineno(1))


# --- expr as statement (bare function calls) ------------------------------

def p_expr_stmt(p):
    "expr_stmt : expr"
    p[0] = p[1]


# --- forge / function definition ------------------------------------------

def p_forge_stmt(p):
    "forge_stmt : FORGE NAME LPAREN param_list RPAREN COLON block"
    p[0] = ForgeStmt(name=p[2], params=p[4], body=p[7], line=p.lineno(1))

def p_param_list_empty(p):
    "param_list : empty"
    p[0] = []

def p_param_list_single(p):
    "param_list : param"
    p[0] = [p[1]]

def p_param_list_multi(p):
    "param_list : param_list COMMA param"
    p[0] = p[1] + [p[3]]

def p_param_typed(p):
    "param : NAME AT type_ann"
    p[0] = Param(name=p[1], type_ann=p[3], line=p.lineno(1))

def p_param_untyped(p):
    "param : NAME"
    p[0] = Param(name=p[1], type_ann=None, line=p.lineno(1))


# --- ignite / if ----------------------------------------------------------

def p_ignite_stmt(p):
    "ignite_stmt : IGNITE expr COLON block drift_chain"
    p[0] = IgniteStmt(condition=p[2], body=p[4], orelse=p[5], line=p.lineno(1))

def p_drift_chain_empty(p):
    "drift_chain : empty"
    p[0] = []

def p_drift_ignite(p):
    "drift_chain : DRIFT IGNITE expr COLON block drift_chain"
    node = IgniteStmt(condition=p[3], body=p[5], orelse=p[6], line=p.lineno(1))
    p[0] = [node]

def p_drift_else(p):
    "drift_chain : DRIFT COLON block"
    p[0] = p[3]


# --- rev / while ----------------------------------------------------------

def p_rev_stmt(p):
    "rev_stmt : REV expr COLON block"
    p[0] = RevStmt(condition=p[2], body=p[4], line=p.lineno(1))


# --- burn / for -----------------------------------------------------------

def p_burn_stmt(p):
    "burn_stmt : BURN NAME IN expr COLON block"
    p[0] = BurnStmt(var=p[2], iterable=p[4], body=p[6], line=p.lineno(1))


# --- stall / try-except ---------------------------------------------------

def p_stall_stmt(p):
    "stall_stmt : STALL COLON block REDLINE expr NEWLINE"
    p[0] = StallStmt(body=p[3], handler=[], exception=p[5], line=p.lineno(1))

def p_stall_stmt_block(p):
    "stall_stmt : STALL COLON block REDLINE expr NEWLINE stall_handler"
    p[0] = StallStmt(body=p[3], handler=p[7], exception=p[5], line=p.lineno(1))

def p_stall_handler(p):
    "stall_handler : COLON block"
    p[0] = p[2]


# --- block ----------------------------------------------------------------

def p_block(p):
    "block : NEWLINE INDENT stmt_list DEDENT"
    p[0] = [s for s in p[3] if s is not None]


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

def p_expr_binop(p):
    """expr : expr PLUS expr
            | expr MINUS expr
            | expr TIMES expr
            | expr DIVIDE expr
            | expr MOD expr
            | expr EQ expr
            | expr NEQ expr
            | expr LT expr
            | expr GT expr
            | expr LTE expr
            | expr GTE expr"""
    p[0] = BinOp(op=p[2], left=p[1], right=p[3], line=p.lineno(2))

def p_expr_pow(p):
    "expr : expr POW expr"
    p[0] = BinOp(op='^^', left=p[1], right=p[3], line=p.lineno(2))

def p_expr_pipe(p):
    "expr : expr PIPE NAME"
    p[0] = PipeExpr(left=p[1], func=p[3], line=p.lineno(2))

def p_expr_pipe_call(p):
    "expr : expr PIPE call_expr"
    p[0] = PipeExpr(left=p[1], func=p[3].func, line=p.lineno(2))

def p_expr_uminus(p):
    "expr : MINUS expr %prec UMINUS"
    p[0] = UnaryOp(op='-', operand=p[2], line=p.lineno(1))

def p_expr_group(p):
    "expr : LPAREN expr RPAREN"
    p[0] = p[2]

def p_expr_call(p):
    "expr : call_expr"
    p[0] = p[1]

def p_call_expr(p):
    "call_expr : NAME LPAREN arg_list RPAREN"
    p[0] = CallExpr(func=p[1], args=p[3], line=p.lineno(1))

def p_arg_list_empty(p):
    "arg_list : empty"
    p[0] = []

def p_arg_list_single(p):
    "arg_list : expr"
    p[0] = [p[1]]

def p_arg_list_multi(p):
    "arg_list : arg_list COMMA expr"
    p[0] = p[1] + [p[3]]

def p_expr_name(p):
    "expr : NAME"
    p[0] = NameExpr(name=p[1], line=p.lineno(1))

def p_expr_number(p):
    "expr : NUMBER"
    p[0] = NumberLiteral(value=p[1], line=p.lineno(1))

def p_expr_float(p):
    "expr : FLOAT"
    p[0] = FloatLiteral(value=p[1], line=p.lineno(1))

def p_expr_string(p):
    "expr : STRING"
    p[0] = StringLiteral(value=p[1], line=p.lineno(1))

def p_expr_true(p):
    "expr : TRUE"
    p[0] = BoolLiteral(value=True, line=p.lineno(1))

def p_expr_false(p):
    "expr : FALSE"
    p[0] = BoolLiteral(value=False, line=p.lineno(1))

def p_expr_void(p):
    "expr : TYPE_VOID"
    p[0] = NoneLiteral(line=p.lineno(1))

def p_expr_list(p):
    "expr : LBRACKET arg_list RBRACKET"
    p[0] = ListExpr(elements=p[2], line=p.lineno(1))

def p_expr_dict(p):
    "expr : LBRACE dict_items RBRACE"
    keys, values = zip(*p[2]) if p[2] else ([], [])
    p[0] = DictExpr(keys=list(keys), values=list(values), line=p.lineno(1))

def p_dict_items_empty(p):
    "dict_items : empty"
    p[0] = []

def p_dict_items_single(p):
    "dict_items : expr COLON expr"
    p[0] = [(p[1], p[3])]

def p_dict_items_multi(p):
    "dict_items : dict_items COMMA expr COLON expr"
    p[0] = p[1] + [(p[3], p[5])]


# --- empty production -----------------------------------------------------

def p_empty(p):
    "empty :"
    pass


# --- error recovery -------------------------------------------------------

def p_error(p):
    if p is None:
        raise TorvenParseError("Unexpected end of file", line=0)
    raise TorvenParseError(
        f"Unexpected token '{p.value}' (type={p.type})",
        line=p.lineno,
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_parser(debug: bool = False):
    """Return a (lexer, parser) pair ready to parse TORVEN source."""
    lexer = make_lexer()
    parser = yacc.yacc(debug=debug, errorlog=yacc.NullLogger() if not debug else None,
                       outputdir="/tmp" if not debug else ".")
    return lexer, parser


def parse(source: str, debug: bool = False) -> Program:
    """Parse *source* and return the AST root."""
    lexer, parser = make_parser(debug=debug)
    lexer.input(source)
    result = parser.parse(lexer=lexer, tracking=True)
    return result
