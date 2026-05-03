"""
visualizer.py — Generador de árboles AST gráficos para TORVEN.

Genera imágenes PNG usando matplotlib (sin binarios externos).

Por cada archivo .trv produce:
  {base}_estructura.png          Vista de estructura del programa completo
  {base}_func_{nombre}.png       Árbol AST detallado por cada función
  {base}_main.png                Árbol de los statements del nivel principal
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paleta de colores  (fondo, texto, borde)
# ---------------------------------------------------------------------------

PALETTE = {
    "root":    ("#1A1A2E", "#E2E8F0", "#64748B"),
    "forge":   ("#581C87", "#F3E8FF", "#9333EA"),
    "param":   ("#6B21A8", "#EDE9FE", "#7C3AED"),
    "load":    ("#1E3A5F", "#DBEAFE", "#3B82F6"),
    "assign":  ("#1E3A5F", "#BFDBFE", "#2563EB"),
    "flow":    ("#7C2D12", "#FED7AA", "#F97316"),
    "eject":   ("#14532D", "#DCFCE7", "#22C55E"),
    "vent":    ("#134E4A", "#CCFBF1", "#14B8A6"),
    "error":   ("#7F1D1D", "#FEE2E2", "#EF4444"),
    "import":  ("#1E293B", "#CBD5E1", "#475569"),
    "call":    ("#064E3B", "#D1FAE5", "#10B981"),
    "pipe":    ("#052E16", "#BBF7D0", "#16A34A"),
    "binop":   ("#431407", "#FED7AA", "#EA580C"),
    "unary":   ("#422006", "#FEF3C7", "#D97706"),
    "num":     ("#713F12", "#FEF9C3", "#CA8A04"),
    "float":   ("#7C2D12", "#FFEDD5", "#F97316"),
    "string":  ("#4A044E", "#FAE8FF", "#A855F7"),
    "bool":    ("#172554", "#DBEAFE", "#1D4ED8"),
    "none":    ("#1C1917", "#D6D3D1", "#78716C"),
    "name":    ("#1E293B", "#94A3B8", "#475569"),
    "list":    ("#042F2E", "#CCFBF1", "#0D9488"),
    "dict":    ("#0C1A4A", "#DBEAFE", "#1E40AF"),
    "kill":    ("#450A0A", "#FECACA", "#DC2626"),
    "idle":    ("#1C1917", "#D6D3D1", "#57534E"),
    "default": ("#0F172A", "#CBD5E1", "#334155"),
}

# ---------------------------------------------------------------------------
# Nodo de layout (independiente del AST)
# ---------------------------------------------------------------------------

@dataclass
class VNode:
    label:       str
    category:    str
    children:    List["VNode"] = field(default_factory=list)
    edge_labels: List[str]     = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0

# ---------------------------------------------------------------------------
# Importar nodos del AST
# ---------------------------------------------------------------------------

from .ast_nodes import (
    Program, ImportStmt, LoadStmt, AssignStmt, EjectStmt, VentStmt,
    KillStmt, IdleStmt, RedlineStmt, ForgeStmt,
    IgniteStmt, RevStmt, BurnStmt, StallStmt,
    NumberLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral,
    NameExpr, ListExpr, DictExpr, BinOp, UnaryOp, CallExpr, PipeExpr,
)


def _trunc(s: str, n: int = 12) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


# ---------------------------------------------------------------------------
# AST → VNode
# ---------------------------------------------------------------------------

def _conv(node: Any, simplified: bool = False) -> VNode:
    """Convierte recursivamente un nodo AST en un VNode."""

    def ch_stmts(nodes) -> Tuple[List[VNode], List[str]]:
        vns = [_conv(s, simplified) for s in nodes if s is not None]
        return vns, [""] * len(vns)

    if isinstance(node, Program):
        children, elabels = ch_stmts(node.body)
        return VNode("Program", "root", children, elabels)

    if isinstance(node, ImportStmt):
        return VNode(f"inject\n{node.module}", "import")

    if isinstance(node, LoadStmt):
        kw  = "lock" if not node.mutable else "load"
        ann = f"@{node.type_ann}" if node.type_ann else ""
        ch  = [_conv(node.value, simplified)] if node.value else []
        return VNode(f"{kw}\n{node.name}{ann}", "load", ch, ["val"] if ch else [])

    if isinstance(node, AssignStmt):
        ch = [_conv(node.value, simplified)] if node.value else []
        return VNode(f"assign\n{node.name}", "assign", ch, ["val"] if ch else [])

    if isinstance(node, EjectStmt):
        ch = [_conv(node.value, simplified)] if node.value else []
        return VNode("eject", "eject", ch, ["expr"] if ch else [])

    if isinstance(node, VentStmt):
        ch = [_conv(node.value, simplified)] if node.value else []
        return VNode("vent", "vent", ch, ["expr"] if ch else [])

    if isinstance(node, KillStmt):
        return VNode("kill", "kill")

    if isinstance(node, IdleStmt):
        return VNode("idle", "idle")

    if isinstance(node, RedlineStmt):
        ch = [_conv(node.value, simplified)] if node.value else []
        return VNode("redline", "error", ch, ["msg"] if ch else [])

    if isinstance(node, ForgeStmt):
        param_nodes = [
            VNode(f"{p.name}\n@{p.type_ann}" if p.type_ann else p.name, "param")
            for p in node.params
        ]
        params_vn = VNode("params", "param", param_nodes, [""] * len(param_nodes))
        if simplified:
            body_vn = VNode(f"body\n({len(node.body)} stmts)", "default")
        else:
            bns, bls = ch_stmts(node.body)
            body_vn = VNode("body", "default", bns, bls)
        return VNode(f"forge\n{node.name}()", "forge",
                     [params_vn, body_vn], ["params", "body"])

    if isinstance(node, IgniteStmt):
        cond_vn = _conv(node.condition, simplified)
        ch, elbls = [cond_vn], ["cond"]
        if node.body:
            bns, _ = ch_stmts(node.body)
            ch.append(VNode("then", "flow", bns, [""] * len(bns)))
            elbls.append("then")
        if node.orelse:
            ons, _ = ch_stmts(node.orelse)
            ch.append(VNode("drift", "flow", ons, [""] * len(ons)))
            elbls.append("drift")
        return VNode("ignite", "flow", ch, elbls)

    if isinstance(node, RevStmt):
        cond_vn = _conv(node.condition, simplified)
        bns, _ = ch_stmts(node.body)
        body_vn = VNode("body", "flow", bns, [""] * len(bns))
        return VNode("rev (while)", "flow", [cond_vn, body_vn], ["cond", "body"])

    if isinstance(node, BurnStmt):
        iter_vn = _conv(node.iterable, simplified)
        bns, _ = ch_stmts(node.body)
        body_vn = VNode("body", "flow", bns, [""] * len(bns))
        return VNode(f"burn\n{node.var} in", "flow",
                     [iter_vn, body_vn], ["iter", "body"])

    if isinstance(node, StallStmt):
        bns, _ = ch_stmts(node.body)
        body_vn = VNode("try", "error", bns, [""] * len(bns))
        ch, elbls = [body_vn], ["body"]
        if node.exception:
            ch.append(_conv(node.exception, simplified))
            elbls.append("redline")
        return VNode("stall", "error", ch, elbls)

    if isinstance(node, NumberLiteral):
        return VNode(str(node.value), "num")

    if isinstance(node, FloatLiteral):
        return VNode(str(node.value), "float")

    if isinstance(node, StringLiteral):
        return VNode(f'"{_trunc(node.value)}"', "string")

    if isinstance(node, BoolLiteral):
        return VNode("on" if node.value else "off", "bool")

    if isinstance(node, NoneLiteral):
        return VNode("void", "none")

    if isinstance(node, NameExpr):
        return VNode(node.name, "name")

    if isinstance(node, ListExpr):
        if simplified or not node.elements:
            return VNode(f"[ list ]\n{len(node.elements)} items", "list")
        ch = [_conv(e, simplified) for e in node.elements]
        return VNode("[ list ]", "list", ch, [""] * len(ch))

    if isinstance(node, DictExpr):
        return VNode(f"{{ dict }}\n{len(node.keys)} pares", "dict")

    if isinstance(node, BinOp):
        lv = _conv(node.left, simplified)
        rv = _conv(node.right, simplified)
        return VNode(node.op, "binop", [lv, rv], ["izq", "der"])

    if isinstance(node, UnaryOp):
        return VNode(node.op, "unary", [_conv(node.operand, simplified)], [""])

    if isinstance(node, CallExpr):
        ch = [_conv(a, simplified) for a in node.args]
        return VNode(f"call\n{node.func}()", "call",
                     ch, [f"arg{i}" for i in range(len(ch))])

    if isinstance(node, PipeExpr):
        lv = _conv(node.left, simplified)
        return VNode(f"pipe\n→ {node.func}", "pipe", [lv], ["in"])

    return VNode(type(node).__name__, "default")


# ---------------------------------------------------------------------------
# Layout  (Reingold-Tilford simplificado)
# ---------------------------------------------------------------------------

MIN_W  = 2.2    # ancho mínimo de un nodo hoja
X_GAP  = 0.35   # espacio horizontal entre hermanos
Y_STEP = 2.4    # distancia vertical entre niveles


def _compute_width(vn: VNode):
    if not vn.children:
        vn.w = MIN_W
        return
    for c in vn.children:
        _compute_width(c)
    vn.w = sum(c.w for c in vn.children) + X_GAP * (len(vn.children) - 1)


def _assign_pos(vn: VNode, x: float, depth: int):
    vn.y = -depth * Y_STEP
    if not vn.children:
        vn.x = x + vn.w / 2
        return
    cursor = x
    for child in vn.children:
        _assign_pos(child, cursor, depth + 1)
        cursor += child.w + X_GAP
    vn.x = (vn.children[0].x + vn.children[-1].x) / 2


def layout(root: VNode):
    _compute_width(root)
    _assign_pos(root, 0.0, 0)


# ---------------------------------------------------------------------------
# Renderizado matplotlib
# ---------------------------------------------------------------------------

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch


NW = 1.7     # ancho del rectángulo de nodo
NH = 0.72    # alto del rectángulo de nodo
FS = 8.5     # font size del label
ES = 7.5     # font size del label de arista


def _bounds(vn: VNode, xs: list, ys: list):
    xs.append(vn.x); ys.append(vn.y)
    for c in vn.children:
        _bounds(c, xs, ys)


def _used_cats(vn: VNode, out: set):
    out.add(vn.category)
    for c in vn.children:
        _used_cats(c, out)


def _draw_all(ax, vn: VNode):
    bg, fg, border = PALETTE.get(vn.category, PALETTE["default"])

    rect = FancyBboxPatch(
        (vn.x - NW / 2, vn.y - NH / 2), NW, NH,
        boxstyle="round,pad=0.07",
        linewidth=1.4, edgecolor=border, facecolor=bg, zorder=3,
    )
    ax.add_patch(rect)

    ax.text(vn.x, vn.y, vn.label,
            ha="center", va="center",
            fontsize=FS, color=fg, fontweight="bold",
            linespacing=1.35, zorder=4)

    for i, child in enumerate(vn.children):
        x0, y0 = vn.x, vn.y - NH / 2
        x1, y1 = child.x, child.y + NH / 2
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#475569",
                                   lw=1.1, connectionstyle="arc3,rad=0.0"),
                    zorder=1)
        if i < len(vn.edge_labels) and vn.edge_labels[i]:
            ax.text((x0 + x1) / 2 + 0.08, (y0 + y1) / 2,
                    vn.edge_labels[i],
                    ha="left", va="center",
                    fontsize=ES, color="#64748B", fontstyle="italic", zorder=5)

    for child in vn.children:
        _draw_all(ax, child)


_CAT_NAMES = {
    "root":   "Program (raíz)",
    "forge":  "forge — función",
    "param":  "Parámetro",
    "load":   "load / lock — variable",
    "assign": "Asignación (=>)",
    "flow":   "ignite / rev / burn",
    "eject":  "eject — retorno",
    "vent":   "vent — imprimir",
    "error":  "stall / redline",
    "call":   "Llamada a función",
    "pipe":   "Pipe (->)",
    "binop":  "Operación binaria",
    "num":    "Entero (torq)",
    "float":  "Decimal (venom)",
    "string": "Texto (exhaust)",
    "bool":   "Booleano (spark)",
    "name":   "Referencia variable",
    "list":   "Lista (barrel)",
    "import": "inject — import",
}


def render(root: VNode, title: str, out_path: str, dpi: int = 160):
    layout(root)

    xs: list = []; ys: list = []
    _bounds(root, xs, ys)
    px, py = 2.2, 1.4
    x_min, x_max = min(xs) - px, max(xs) + px
    y_min, y_max = min(ys) - py, max(ys) + py

    fig_w = max(16.0, (x_max - x_min) * 0.88)
    fig_h = max(9.0,  (y_max - y_min) * 1.05)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="#0F172A")
    ax.set_facecolor("#0F172A")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")

    ax.set_title(title, color="#E2E8F0", fontsize=11,
                 fontweight="bold", pad=12)

    _draw_all(ax, root)

    # Leyenda
    used: set = set()
    _used_cats(root, used)
    handles = []
    for cat in list(_CAT_NAMES.keys()):
        if cat in used and cat in PALETTE:
            bg, _, border = PALETTE[cat]
            handles.append(mpatches.Patch(
                facecolor=bg, edgecolor=border,
                label=_CAT_NAMES[cat], linewidth=1.2))
    ax.legend(handles, [h.get_label() for h in handles],
              loc="lower left", fontsize=6.5, framealpha=0.9,
              facecolor="#1E293B", edgecolor="#334155",
              labelcolor="#E2E8F0", ncol=5,
              title="Categorías de nodos", title_fontsize=7)

    ax.text(0.995, 0.005, "TORVEN Compiler  •  AST Visualizer",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=6, color="#334155")

    plt.tight_layout(pad=0.6)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[torven] → {out_path}")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def visualize(src_path: str, out_dir: Optional[str] = None) -> List[str]:
    """
    Genera varias imágenes PNG del AST de *src_path*:

      {base}_estructura.png   — estructura completa (simplificada)
      {base}_main.png         — statements del nivel principal (detallado)
      {base}_func_X.png       — árbol detallado por cada función forge
    """
    from .parser import parse

    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(src_path))

    base   = os.path.splitext(os.path.basename(src_path))[0]
    source = open(src_path, "r", encoding="utf-8").read()
    program = parse(source)

    generated: List[str] = []

    # ── 1. Árbol de ESTRUCTURA (todo el programa, simplificado) ──────────────
    simp = _conv(program, simplified=True)
    p = os.path.join(out_dir, f"{base}_estructura.png")
    render(simp,
           f"TORVEN  │  Estructura del programa  │  {os.path.basename(src_path)}",
           p, dpi=160)
    generated.append(p)

    # Separar funciones de statements principales
    forge_nodes  = [n for n in program.body if isinstance(n, ForgeStmt)]
    main_stmts   = [n for n in program.body if not isinstance(n, ForgeStmt)]

    # ── 2. Árbol de los STATEMENTS PRINCIPALES (detallado) ───────────────────
    if main_stmts:
        fake_root = VNode("main\n(statements)", "root")
        for stmt in main_stmts:
            if stmt is not None:
                fake_root.children.append(_conv(stmt, simplified=False))
                fake_root.edge_labels.append("")
        p = os.path.join(out_dir, f"{base}_main.png")
        render(fake_root,
               f"TORVEN  │  Statements principales  │  {os.path.basename(src_path)}",
               p, dpi=160)
        generated.append(p)

    # ── 3. Un árbol detallado POR CADA FUNCIÓN ────────────────────────────────
    for forge in forge_nodes:
        fn_vnode = _conv(forge, simplified=False)
        p = os.path.join(out_dir, f"{base}_func_{forge.name}.png")
        render(fn_vnode,
               f"TORVEN  │  forge {forge.name}()  │  {os.path.basename(src_path)}",
               p, dpi=160)
        generated.append(p)

    print(f"\n[torven] {len(generated)} imágenes generadas en {out_dir}")
    return generated
