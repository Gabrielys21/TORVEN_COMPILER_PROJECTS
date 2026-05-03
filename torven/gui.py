"""
gui.py — TORVEN IDE
Diseño replicado desde Figma:
  - Tema oscuro #0D0F14 con acento naranja #FF4500
  - Navbar con logo + botones all-caps
  - Editor izquierdo (60%) con header "EDITOR" + underline naranja
  - Panel derecho (40%) con tabs: SALIDA · BYTECODE · TOKENS · ÁRBOL AST
  - Barra inferior del editor: Líneas / Caracteres
  - Barra inferior del output: Estado del Motor + tiempo de ejecución
  - Status bar global que cambia de color (naranja → verde)
"""

from __future__ import annotations

import io
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Paleta de colores — extraída del Figma
# ─────────────────────────────────────────────────────────────────────────────

BG       = "#0D0F14"   # fondo principal
BG_ED    = "#090B10"   # fondo del editor (más oscuro)
BG_BTN   = "#13151C"   # fondo botones toolbar
BORDER   = "#1E2232"   # bordes sutiles
BORDER2  = "#2A2D3A"   # bordes botones
ORANGE   = "#FF4500"   # acento principal TORVEN
TEAL     = "#00D4AA"   # acento secundario (identificadores)
WHITE    = "#E8E8E8"   # texto principal
DIM      = "#4A5068"   # texto apagado
GREEN    = "#22C55E"   # éxito
GRAY_PIL = "#6B7280"   # pill inactivo

# Resaltado de sintaxis
SYN_KW   = "#FF4500"   # keywords TORVEN
SYN_ID   = "#00D4AA"   # identificadores / tipos
SYN_STR  = "#E5C07B"   # strings
SYN_NUM  = "#61AFEF"   # números
SYN_CMT  = "#4A5068"   # comentarios (gris apagado, italic)
SYN_OP   = "#C678DD"   # operadores especiales => ~~ !~ ^^
SYN_BOOL = "#E06C75"   # on / off

# ─────────────────────────────────────────────────────────────────────────────
# Redireccionadores de stdout / stderr
# ─────────────────────────────────────────────────────────────────────────────

class _Redir(io.TextIOBase):
    def __init__(self, q: queue.Queue, tag: str):
        self._q, self._tag = q, tag
    def write(self, text: str) -> int:
        self._q.put((self._tag, text)); return len(text)
    def flush(self): pass

# ─────────────────────────────────────────────────────────────────────────────
# Numeración de líneas
# ─────────────────────────────────────────────────────────────────────────────

class LineNumbers(tk.Canvas):
    def __init__(self, master, editor, **kw):
        super().__init__(master, width=40, bg=BG_ED,
                         highlightthickness=0, **kw)
        self._ed = editor
        for ev in ("<<Change>>", "<Configure>", "<KeyRelease>", "<MouseWheel>"):
            editor.bind(ev, self._redraw)

    def _redraw(self, _=None):
        self.delete("all")
        i = self._ed.index("@0,0")
        while True:
            dl = self._ed.dlineinfo(i)
            if dl is None: break
            ln = str(i).split(".")[0]
            self.create_text(35, dl[1] + 9, anchor="ne", text=ln,
                             fill=ORANGE, font=("Consolas", 10))
            i = self._ed.index(f"{i}+1line")
            if i == self._ed.index(f"{i}+0line"): break

# ─────────────────────────────────────────────────────────────────────────────
# Editor con resaltado de sintaxis TORVEN
# ─────────────────────────────────────────────────────────────────────────────

class CodeEditor(tk.Text):
    def __init__(self, master, **kw):
        super().__init__(
            master,
            bg=BG_ED, fg=WHITE,
            insertbackground=ORANGE,
            selectbackground="#2D3250",
            selectforeground=WHITE,
            font=("Consolas", 11),
            relief="flat", bd=0, wrap="none",
            undo=True, padx=10, pady=6,
            **kw,
        )
        self._setup_tags()
        self.bind("<KeyRelease>", self._on_key)
        self.bind("<Return>",     self._auto_indent)
        self.bind("<Tab>",        self._insert_tab)

    def _setup_tags(self):
        self.tag_configure("kw",   foreground=SYN_KW,  font=("Consolas", 11, "bold"))
        self.tag_configure("id_",  foreground=SYN_ID)
        self.tag_configure("str_", foreground=SYN_STR)
        self.tag_configure("num",  foreground=SYN_NUM)
        self.tag_configure("cmt",  foreground=SYN_CMT,  font=("Consolas", 11, "italic"))
        self.tag_configure("op",   foreground=SYN_OP,   font=("Consolas", 11, "bold"))
        self.tag_configure("bool_",foreground=SYN_BOOL)

    def _on_key(self, _=None):
        self.event_generate("<<Change>>")
        self.after(15, self._highlight)

    def _highlight(self):
        import re
        src = self.get("1.0", "end-1c")
        for tag in ("kw","id_","str_","num","cmt","op","bool_"):
            self.tag_remove(tag, "1.0", "end")

        patterns = [
            ("cmt",   r'#[^\n]*'),
            ("str_",  r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''),
            ("op",    r'=>|~~|!~|\^\^|->'),
            ("bool_", r'\b(?:on|off)\b'),
            ("id_",   r'@(?:torq|venom|exhaust|spark|barrel|chassis|void)\b'),
            ("id_",   r'\b(?:torq|venom|exhaust|spark|barrel|chassis|void)\b'),
            ("kw",    r'\b(?:forge|ignite|drift|rev|burn|inject|eject|lock|load|kill|idle|vent|stall|redline|in)\b'),
            ("id_",   r'(?<=forge\s)\w+'),
            ("num",   r'\b\d+\.?\d*\b'),
        ]
        for tag, pattern in patterns:
            for m in re.finditer(pattern, src):
                self.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def _auto_indent(self, _):
        line   = self.get("insert linestart", "insert")
        indent = len(line) - len(line.lstrip())
        extra  = 4 if line.rstrip().endswith(":") else 0
        self.insert("insert", "\n" + " " * (indent + extra))
        self._highlight()
        return "break"

    def _insert_tab(self, _):
        self.insert("insert", "    ")
        return "break"

    def set_text(self, text: str):
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self._highlight()

    def get_text(self) -> str:
        return self.get("1.0", "end-1c")

# ─────────────────────────────────────────────────────────────────────────────
# Tab bar personalizado (para control exacto del estilo)
# ─────────────────────────────────────────────────────────────────────────────

class TabBar(tk.Frame):
    """Barra de tabs con underline naranja en el tab activo."""
    def __init__(self, master, tabs: list[tuple[str,str]], on_change, **kw):
        super().__init__(master, bg=BG, **kw)
        self._frames: dict[str, tk.Frame] = {}
        self._btns:   dict[str, tk.Label] = {}
        self._lines:  dict[str, tk.Frame] = {}
        self._active  = tabs[0][0]
        self._on_change = on_change

        for key, label in tabs:
            col = tk.Frame(self, bg=BG)
            col.pack(side="left", padx=(0, 2))
            btn = tk.Label(col, text=label, bg=BG, fg=DIM,
                           font=("Segoe UI", 9, "bold"),
                           cursor="hand2", padx=12, pady=8)
            btn.pack()
            line = tk.Frame(col, bg=BG, height=2)
            line.pack(fill="x")
            btn.bind("<Button-1>", lambda e, k=key: self._select(k))
            self._btns[key]  = btn
            self._lines[key] = line

        self._select(self._active)

    def _select(self, key: str):
        for k, btn in self._btns.items():
            active = k == key
            btn.config(fg=ORANGE if active else DIM)
            self._lines[k].config(bg=ORANGE if active else BG)
        self._active = key
        self._on_change(key)

# ─────────────────────────────────────────────────────────────────────────────
# Aplicación principal
# ─────────────────────────────────────────────────────────────────────────────

class TorvenIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TORVEN IDE")
        self.geometry("1400x820")
        self.configure(bg=BG)
        self.minsize(1000, 640)

        self._filepath:   Optional[str] = None
        self._modified:   bool          = False
        self._out_q:      queue.Queue   = queue.Queue()
        self._exec_start: float         = 0.0
        self._exec_time:  float         = 0.0
        self._tree_imgs:  list          = []
        self._tree_paths: list          = []

        # Paneles de output (uno activo a la vez)
        self._out_panels: dict[str, tk.Widget] = {}
        self._active_panel = "salida"

        self._build_navbar()
        self._build_body()
        self._build_statusbar()

        self._poll_output()

        # Cargar ejemplo
        _ex = os.path.join(os.path.dirname(__file__), "examples", "hola.trv")
        if os.path.exists(_ex):
            self._load_file(_ex)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════════════════════════════ NAVBAR

    def _build_navbar(self):
        nav = tk.Frame(self, bg=BG, pady=0)
        nav.pack(side="top", fill="x")

        # Separador inferior del navbar
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(side="top", fill="x")

        # Logo
        logo_frame = tk.Frame(nav, bg=BG)
        logo_frame.pack(side="left", padx=(14, 20), pady=8)
        tk.Label(logo_frame, text="⚡", bg=BG, fg=ORANGE,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(logo_frame, text=" TORVEN", bg=BG, fg=WHITE,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(logo_frame, text="  IDE", bg=BG, fg=DIM,
                 font=("Segoe UI", 9)).pack(side="left")

        # Separador
        tk.Frame(nav, bg=BORDER2, width=1).pack(side="left", fill="y", pady=6)

        def nav_btn(text, cmd, icon="", is_primary=False):
            color  = ORANGE if is_primary else BORDER2
            fg_col = ORANGE if is_primary else WHITE
            f = tk.Frame(nav, bg=BG, padx=3, pady=6)
            f.pack(side="left")
            btn = tk.Frame(f, bg=BG_BTN,
                           highlightbackground=color,
                           highlightthickness=1)
            btn.pack()
            inner = tk.Frame(btn, bg=BG_BTN, padx=10, pady=5)
            inner.pack()
            if icon:
                tk.Label(inner, text=icon, bg=BG_BTN, fg=fg_col,
                         font=("Segoe UI", 9)).pack(side="left", padx=(0,4))
            lbl = tk.Label(inner, text=text, bg=BG_BTN, fg=fg_col,
                           font=("Segoe UI", 9, "bold"), cursor="hand2")
            lbl.pack(side="left")
            for w in (btn, inner, lbl):
                w.bind("<Button-1>", lambda e: cmd())
                w.bind("<Enter>",    lambda e, b=btn: b.config(bg="#1A1D27") or
                                     [c.config(bg="#1A1D27") for c in b.winfo_children()])
                w.bind("<Leave>",    lambda e, b=btn: b.config(bg=BG_BTN) or
                                     [c.config(bg=BG_BTN) for c in b.winfo_children()])
            return btn

        nav_btn("NUEVO",     self._new,     "📄")
        nav_btn("ABRIR",     self._open,    "📂")
        nav_btn("GUARDAR",   self._save,    "💾")

        tk.Frame(nav, bg=BORDER2, width=1).pack(side="left", fill="y", pady=6, padx=4)

        nav_btn("COMPILAR",  self._compile, "⚙")
        nav_btn("EJECUTAR",  self._exec_run,"▶", is_primary=True)
        nav_btn("COMP+EXEC", self._exec,    "⚡")

        tk.Frame(nav, bg=BORDER2, width=1).pack(side="left", fill="y", pady=6, padx=4)

        nav_btn("BYTECODE",  self._do_disasm,"〈/〉")
        nav_btn("TOKENS",    self._do_tokens,"{ }")
        nav_btn("AST",       self._do_tree,  "⊕")

        tk.Frame(nav, bg=BORDER2, width=1).pack(side="left", fill="y", pady=6, padx=4)

        nav_btn("LIMPIAR",   self._clear,   "🗑")

        # Atajos de teclado
        self.bind("<F5>",        lambda _: self._compile())
        self.bind("<F6>",        lambda _: self._exec_run())
        self.bind("<F7>",        lambda _: self._exec())
        self.bind("<Control-n>", lambda _: self._new())
        self.bind("<Control-o>", lambda _: self._open())
        self.bind("<Control-s>", lambda _: self._save())

    # ═══════════════════════════════════════════════════════════════════ BODY

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # ── Editor (izquierda ~60%) ──────────────────────────────────────────
        ed_outer = tk.Frame(body, bg=BG)
        ed_outer.pack(side="left", fill="both", expand=True)

        # Header "EDITOR" con underline naranja
        ed_hdr = tk.Frame(ed_outer, bg=BG)
        ed_hdr.pack(fill="x")
        ed_title_wrap = tk.Frame(ed_hdr, bg=BG)
        ed_title_wrap.pack(side="left", padx=14, pady=(8, 0))
        tk.Label(ed_title_wrap, text="EDITOR", bg=BG, fg=WHITE,
                 font=("Segoe UI", 9, "bold")).pack()
        tk.Frame(ed_title_wrap, bg=ORANGE, height=2).pack(fill="x")

        self._file_lbl = tk.Label(ed_hdr, text="", bg=BG, fg=DIM,
                                  font=("Segoe UI", 9))
        self._file_lbl.pack(side="left", padx=6, pady=8)

        # Área del editor
        ed_area = tk.Frame(ed_outer, bg=BG_ED)
        ed_area.pack(fill="both", expand=True)

        self._editor = CodeEditor(ed_area)
        self._lnums  = LineNumbers(ed_area, self._editor)

        vs = tk.Scrollbar(ed_area, orient="vertical",
                          command=self._editor.yview,
                          bg=BG, troughcolor=BG_ED, width=10)
        hs = tk.Scrollbar(ed_area, orient="horizontal",
                          command=self._editor.xview,
                          bg=BG, troughcolor=BG_ED, width=10)
        self._editor.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self._lnums.grid(row=0, column=0, sticky="ns")
        tk.Frame(ed_area, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns")
        self._editor.grid(row=0, column=2, sticky="nsew")
        vs.grid(row=0, column=3, sticky="ns")
        hs.grid(row=1, column=2, sticky="ew")
        ed_area.rowconfigure(0, weight=1)
        ed_area.columnconfigure(2, weight=1)

        self._editor.bind("<KeyRelease>", self._on_edit_key)
        self._editor.bind("<ButtonRelease>", self._update_ed_info)

        # Barra inferior del editor: Líneas · Caracteres
        ed_info = tk.Frame(ed_outer, bg="#0A0C12", pady=4)
        ed_info.pack(fill="x")
        self._lbl_lines = tk.Label(ed_info, text="Líneas: 0",
                                   bg="#0A0C12", fg=DIM,
                                   font=("Segoe UI", 8))
        self._lbl_lines.pack(side="left", padx=12)
        self._lbl_chars = tk.Label(ed_info, text="Caracteres: 0",
                                   bg="#0A0C12", fg=DIM,
                                   font=("Segoe UI", 8))
        self._lbl_chars.pack(side="right", padx=12)

        # Separador vertical entre paneles
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        # ── Panel de output (derecha ~40%) ───────────────────────────────────
        out_outer = tk.Frame(body, bg=BG, width=520)
        out_outer.pack(side="left", fill="both")
        out_outer.pack_propagate(False)

        # Tabs personalizados
        tab_bar = tk.Frame(out_outer, bg=BG)
        tab_bar.pack(fill="x")
        tk.Frame(out_outer, bg=BORDER, height=1).pack(fill="x")

        self._tab_content = tk.Frame(out_outer, bg=BG)
        self._tab_content.pack(fill="both", expand=True)

        tabs_def = [
            ("salida",   ">_  SALIDA"),
            ("bytecode", "〈/〉 BYTECODE"),
            ("tokens",   "{}  TOKENS"),
            ("ast",      "⊕  ÁRBOL AST"),
        ]
        self._tabbar = TabBar(tab_bar, tabs_def, self._switch_tab)
        self._tabbar.pack(side="left", padx=6, pady=2)

        # Crear paneles de contenido
        self._build_salida_panel()
        self._build_bytecode_panel()
        self._build_tokens_panel()
        self._build_ast_panel()

        # Mostrar panel inicial
        self._switch_tab("salida")

        # Barra inferior del output: Estado + tiempo
        out_info = tk.Frame(out_outer, bg="#0A0C12", pady=6)
        out_info.pack(fill="x", side="bottom")

        tk.Frame(out_info, bg=BORDER, height=1).pack(fill="x")

        bottom_row = tk.Frame(out_info, bg="#0A0C12")
        bottom_row.pack(fill="x", padx=12, pady=(6, 2))

        tk.Label(bottom_row, text="ESTADO DEL MOTOR", bg="#0A0C12", fg=DIM,
                 font=("Segoe UI", 7, "bold")).pack(side="left")

        self._motor_pill = tk.Label(bottom_row, text="INACTIVO",
                                    bg=BORDER2, fg=DIM,
                                    font=("Segoe UI", 8, "bold"),
                                    padx=8, pady=2, relief="flat")
        self._motor_pill.pack(side="left", padx=8)

        bottom_row2 = tk.Frame(out_info, bg="#0A0C12")
        bottom_row2.pack(fill="x", padx=12, pady=(2, 4))

        tk.Label(bottom_row2, text="Tiempo de ejecución:", bg="#0A0C12", fg=DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        self._lbl_time = tk.Label(bottom_row2, text="—",
                                  bg="#0A0C12", fg=WHITE,
                                  font=("Consolas", 13, "bold"))
        self._lbl_time.pack(side="left", padx=6)

        self._lbl_quote = tk.Label(out_info, text='"Como un lap time en pista"',
                                   bg="#0A0C12", fg=DIM,
                                   font=("Segoe UI", 8, "italic"))
        self._lbl_quote.pack(side="right", padx=12)

    # ─────────────────────────────────────── Paneles de contenido del output

    def _build_salida_panel(self):
        frame = tk.Frame(self._tab_content, bg=BG)

        # Título estilo terminal con borde
        title_wrap = tk.Frame(frame, bg=BG, pady=10, padx=12)
        title_wrap.pack(fill="x")
        title_box = tk.Frame(title_wrap, bg=BG,
                             highlightbackground=TEAL,
                             highlightthickness=1)
        title_box.pack(fill="x")
        self._out_title = tk.Label(title_box,
                                   text="  TORVEN IDE - Motor de Ejecución  ",
                                   bg=BG, fg=TEAL,
                                   font=("Consolas", 10, "bold"), pady=6)
        self._out_title.pack()

        # Área de texto de salida
        self._out_text = tk.Text(frame, bg=BG, fg=WHITE,
                                 font=("Consolas", 10),
                                 relief="flat", bd=0,
                                 state="disabled", wrap="word",
                                 padx=14, pady=6)
        self._out_text.tag_configure("err", foreground="#F87171")
        self._out_text.tag_configure("ok",  foreground=GREEN)
        self._out_text.tag_configure("inf", foreground=TEAL)
        self._out_text.tag_configure("dim", foreground=DIM)

        vs = tk.Scrollbar(frame, command=self._out_text.yview,
                          bg=BG, troughcolor=BG, width=8)
        self._out_text.configure(yscrollcommand=vs.set)
        self._out_text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self._out_panels["salida"] = frame

    def _build_bytecode_panel(self):
        frame = tk.Frame(self._tab_content, bg=BG)
        self._bc_text = tk.Text(frame, bg=BG, fg="#94A3B8",
                                font=("Consolas", 10),
                                relief="flat", bd=0,
                                state="disabled", wrap="none",
                                padx=14, pady=10)
        self._bc_text.tag_configure("hdr",    foreground=ORANGE,
                                    font=("Consolas", 10, "bold"))
        self._bc_text.tag_configure("opcode", foreground="#C084FC")
        self._bc_text.tag_configure("arg",    foreground=SYN_STR)
        self._bc_text.tag_configure("label_", foreground=GREEN)
        self._bc_text.tag_configure("lineno", foreground=DIM)

        vs = tk.Scrollbar(frame, command=self._bc_text.yview,
                          bg=BG, troughcolor=BG, width=8)
        hs = tk.Scrollbar(frame, orient="horizontal",
                          command=self._bc_text.xview,
                          bg=BG, troughcolor=BG, width=8)
        self._bc_text.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self._bc_text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self._out_panels["bytecode"] = frame

    def _build_tokens_panel(self):
        frame = tk.Frame(self._tab_content, bg=BG)
        self._tok_text = tk.Text(frame, bg=BG, fg="#94A3B8",
                                 font=("Consolas", 10),
                                 relief="flat", bd=0,
                                 state="disabled", wrap="none",
                                 padx=14, pady=10)
        self._tok_text.tag_configure("type_", foreground=ORANGE,
                                     font=("Consolas", 10, "bold"))
        self._tok_text.tag_configure("val_",  foreground=SYN_STR)
        self._tok_text.tag_configure("hdr_",  foreground=TEAL,
                                     font=("Consolas", 10, "bold"))

        vs = tk.Scrollbar(frame, command=self._tok_text.yview,
                          bg=BG, troughcolor=BG, width=8)
        self._tok_text.configure(yscrollcommand=vs.set)
        self._tok_text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self._out_panels["tokens"] = frame

    def _build_ast_panel(self):
        frame = tk.Frame(self._tab_content, bg=BG)

        # ── Barra de selección ────────────────────────────────────────────────
        sel = tk.Frame(frame, bg="#0A0C12", pady=5)
        sel.pack(fill="x", side="top")

        tk.Label(sel, text=" Vista:", bg="#0A0C12", fg=DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=6)

        self._tree_var   = tk.StringVar(value="(genera el árbol primero)")
        self._tree_combo = tk.OptionMenu(sel, self._tree_var, "(vacío)")
        self._tree_combo.config(
            bg=BG_BTN, fg=WHITE,
            activebackground=BORDER2, activeforeground=WHITE,
            relief="flat", highlightthickness=0,
            font=("Segoe UI", 9), bd=0, width=30,
        )
        self._tree_combo["menu"].config(
            bg=BG_BTN, fg=WHITE, activebackground=ORANGE,
            font=("Segoe UI", 9),
        )
        self._tree_combo.pack(side="left", padx=4)

        # El trace se activa cada vez que el usuario elige una opción
        self._tree_var.trace_add("write", lambda *_: self._on_tree_select())

        # ── Canvas + scrollbars en GRID (único layout que soporta ambos ejes) ─
        canv_wrap = tk.Frame(frame, bg=BG)
        canv_wrap.pack(fill="both", expand=True, side="top")
        canv_wrap.rowconfigure(0, weight=1)
        canv_wrap.columnconfigure(0, weight=1)

        self._tree_canvas = tk.Canvas(canv_wrap, bg="#080A0F",
                                      highlightthickness=0)

        vs2 = tk.Scrollbar(canv_wrap, orient="vertical",
                           command=self._tree_canvas.yview,
                           bg=BG, troughcolor="#080A0F", width=10)
        hs2 = tk.Scrollbar(canv_wrap, orient="horizontal",
                           command=self._tree_canvas.xview,
                           bg=BG, troughcolor="#080A0F", width=10)

        self._tree_canvas.configure(
            yscrollcommand=vs2.set,
            xscrollcommand=hs2.set,
        )

        # grid: canvas ocupa [0,0], scrollbar V [0,1], scrollbar H [1,0]
        self._tree_canvas.grid(row=0, column=0, sticky="nsew")
        vs2.grid(row=0, column=1, sticky="ns")
        hs2.grid(row=1, column=0, sticky="ew")

        # Scroll vertical con rueda del ratón
        self._tree_canvas.bind(
            "<MouseWheel>",
            lambda e: self._tree_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )
        # Scroll horizontal con Shift + rueda
        self._tree_canvas.bind(
            "<Shift-MouseWheel>",
            lambda e: self._tree_canvas.xview_scroll(-1 * (e.delta // 120), "units"),
        )

        # Mensaje inicial centrado
        self._tree_canvas.create_text(
            260, 120, text="Presiona  ⊕ AST  para generar los árboles",
            fill=DIM, font=("Segoe UI", 11), tags="placeholder",
        )

        self._out_panels["ast"] = frame

    def _switch_tab(self, key: str):
        for k, panel in self._out_panels.items():
            if k == key:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()
        self._active_panel = key

    # ══════════════════════════════════════════════════════════════ STATUS BAR

    def _build_statusbar(self):
        self._sb = tk.Frame(self, bg="#13151C", pady=6)
        self._sb.pack(side="bottom", fill="x")

        self._sb_icon  = tk.Label(self._sb, text="ⓘ", bg="#13151C",
                                  fg=ORANGE, font=("Segoe UI", 9, "bold"))
        self._sb_icon.pack(side="left", padx=(12, 4))

        self._sb_lbl   = tk.Label(self._sb, text="Listo",
                                  bg="#13151C", fg=WHITE,
                                  font=("Segoe UI", 9))
        self._sb_lbl.pack(side="left")

        tk.Label(self._sb, text="?", bg="#13151C", fg=DIM,
                 font=("Segoe UI", 9, "bold"), padx=10).pack(side="right")

        self._sb_cursor = tk.Label(self._sb, text="Ln 1, Col 1",
                                   bg="#13151C", fg=DIM,
                                   font=("Segoe UI", 8))
        self._sb_cursor.pack(side="right", padx=10)

    def _set_status(self, msg: str, state: str = "idle"):
        """state: 'idle' | 'running' | 'ok' | 'error'"""
        cfg = {
            "idle":    (BG,      ORANGE, "ⓘ", WHITE),
            "running": (ORANGE,  "#0D0F14","⚡", "#0D0F14"),
            "ok":      (GREEN,   "#0D0F14","✓", "#0D0F14"),
            "error":   ("#7F1D1D", "#F87171","✗", "#F87171"),
        }
        bg, icon_fg, icon, txt_fg = cfg.get(state, cfg["idle"])
        self._sb.config(bg=bg)
        self._sb_icon.config(bg=bg, fg=icon_fg, text=icon)
        self._sb_lbl.config(bg=bg, fg=txt_fg, text=msg)
        self._sb_cursor.config(bg=bg)

    def _set_motor(self, state: str, ms: float = 0):
        if state == "running":
            self._motor_pill.config(text="EJECUTANDO", bg=GREEN,   fg="#0D0F14")
            self._lbl_time.config(text="…")
        elif state == "ok":
            self._motor_pill.config(text="COMPLETADO", bg=GREEN,   fg="#0D0F14")
            self._lbl_time.config(text=f"{ms:.2f} ms")
        elif state == "error":
            self._motor_pill.config(text="ERROR",       bg="#7F1D1D", fg="#F87171")
            self._lbl_time.config(text=f"{ms:.2f} ms")
        else:
            self._motor_pill.config(text="INACTIVO",   bg=BORDER2, fg=DIM)
            self._lbl_time.config(text="—")

    # ═══════════════════════════════════════════════════════════ EDITOR EVENTS

    def _on_edit_key(self, _=None):
        self._update_ed_info()
        self._editor.event_generate("<<Change>>")
        if not self._modified:
            self._modified = True
            name = os.path.basename(self._filepath) if self._filepath else "sin título"
            self._file_lbl.config(text=f"* {name}")

    def _update_ed_info(self, _=None):
        text = self._editor.get_text()
        lines = text.count("\n") + 1
        chars = len(text)
        self._lbl_lines.config(text=f"Líneas: {lines}")
        self._lbl_chars.config(text=f"Caracteres: {chars}")
        pos = self._editor.index("insert")
        ln, col = pos.split(".")
        self._sb_cursor.config(text=f"Ln {ln}, Col {int(col)+1}")

    # ══════════════════════════════════════════════════════════ OUTPUT HELPERS

    def _poll_output(self):
        try:
            while True:
                kind, text = self._out_q.get_nowait()
                self._append_out(text, "err" if kind == "err" else "")
        except queue.Empty:
            pass
        self.after(40, self._poll_output)

    def _append_out(self, text: str, tag: str = ""):
        self._out_text.configure(state="normal")
        self._out_text.insert("end", text, tag or ())
        self._out_text.see("end")
        self._out_text.configure(state="disabled")

    def _append_bc(self, text: str, tag: str = ""):
        self._bc_text.configure(state="normal")
        self._bc_text.insert("end", text, tag or ())
        self._bc_text.configure(state="disabled")

    def _append_tok(self, text: str, tag: str = ""):
        self._tok_text.configure(state="normal")
        self._tok_text.insert("end", text, tag or ())
        self._tok_text.configure(state="disabled")

    def _clear(self):
        for w in (self._out_text, self._bc_text, self._tok_text):
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        self._set_motor("idle")
        self._set_status("Listo", "idle")

    # ══════════════════════════════════════════════════════════════ FILE OPS

    def _new(self):
        if self._modified and not messagebox.askyesno(
                "Descartar cambios", "¿Continuar sin guardar?"):
            return
        self._editor.set_text("")
        self._filepath = None
        self._modified = False
        self._file_lbl.config(text="sin título")
        self.title("TORVEN IDE")
        self._update_ed_info()

    def _open(self):
        path = filedialog.askopenfilename(
            filetypes=[("TORVEN", "*.trv"), ("All", "*.*")])
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._editor.set_text(f.read())
            self._filepath = path
            self._modified = False
            name = os.path.basename(path)
            self._file_lbl.config(text=name)
            self.title(f"TORVEN IDE — {name}")
            self._update_ed_info()
            self._set_status(f"Abierto: {name}", "idle")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _save(self):
        if self._filepath:
            self._write_file(self._filepath)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".trv",
            filetypes=[("TORVEN", "*.trv"), ("All", "*.*")])
        if path:
            self._write_file(path)

    def _write_file(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._editor.get_text())
            self._filepath = path
            self._modified = False
            name = os.path.basename(path)
            self._file_lbl.config(text=name)
            self.title(f"TORVEN IDE — {name}")
            self._set_status(f"Guardado: {name}", "idle")
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def _get_src_path(self) -> Optional[str]:
        if self._filepath and self._filepath.endswith(".trv"):
            if self._modified:
                self._save()
            return self._filepath
        tmp = tempfile.NamedTemporaryFile(suffix=".trv", delete=False,
                                          mode="w", encoding="utf-8")
        tmp.write(self._editor.get_text())
        tmp.close()
        return tmp.name

    # ══════════════════════════════════════════════════════════════ RUN OPS

    def _bg(self, fn, *args):
        """Ejecuta fn en hilo background, capturando stdout/stderr."""
        self._clear()
        self._set_status("Ejecutando código...", "running")
        self._set_motor("running")
        self._exec_start = time.time()
        self._tabbar._select("salida")

        def _worker():
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout = _Redir(self._out_q, "out")
            sys.stderr = _Redir(self._out_q, "err")
            try:
                fn(*args)
                ms = (time.time() - self._exec_start) * 1000
                self.after(0, self._on_exec_ok, ms)
            except Exception as exc:
                ms = (time.time() - self._exec_start) * 1000
                self._out_q.put(("err", f"\n[ERROR] {exc}\n"))
                self.after(0, self._on_exec_error, ms, str(exc))
            finally:
                sys.stdout, sys.stderr = old_out, old_err

        threading.Thread(target=_worker, daemon=True).start()

    def _on_exec_ok(self, ms: float):
        self._set_status(f"Ejecución completada - {ms:.2f} ms", "ok")
        self._set_motor("ok", ms)
        self.after(0, self._append_out,
                   f"\n──────────────────────────────\n"
                   f"Ejecución completada exitosamente\n"
                   f"Tiempo de vuelta: {ms:.2f} ms\n", "ok")

    def _on_exec_error(self, ms: float, _msg: str):
        self._set_status(f"Error - {ms:.2f} ms", "error")
        self._set_motor("error", ms)

    def _compile(self):
        path = self._get_src_path()
        if not path: return

        def _do():
            from torven.parser import parse
            from torven import semantic, compiler as comp
            src = open(path, "r", encoding="utf-8").read()
            print("[TORVEN] Analizando código…")
            ast  = parse(src)
            errs = semantic.analyse(ast)
            if errs:
                for e in errs: print(str(e), file=sys.stderr)
                raise RuntimeError(f"{len(errs)} error(es) semántico(s)")
            out = os.path.splitext(path)[0] + ".tvbc"
            comp.compile_to_file(ast, out)
            print(f"[TORVEN] Compilado → {os.path.basename(out)}")

        self._bg(_do)

    def _exec_run(self):
        """EJECUTAR: compila y corre en memoria."""
        path = self._get_src_path()
        if not path: return

        def _do():
            from torven.parser import parse
            from torven import semantic, compiler as comp
            from torven.vm import VM
            src  = open(path, "r", encoding="utf-8").read()
            ast  = parse(src)
            errs = semantic.analyse(ast)
            if errs:
                for e in errs: print(str(e), file=sys.stderr)
                raise RuntimeError(f"{len(errs)} error(es) semántico(s)")
            code = comp.compile_ast(ast)
            print("[TORVEN] Ejecutando…\n")
            VM().run(code)

        self._bg(_do)

    def _exec(self):
        """COMP+EXEC: compilar y ejecutar en un paso."""
        path = self._get_src_path()
        if not path: return

        def _do():
            from torven.parser import parse
            from torven import semantic, compiler as comp
            from torven.vm import VM
            src  = open(path, "r", encoding="utf-8").read()
            print("[TORVEN] Compilando…")
            ast  = parse(src)
            errs = semantic.analyse(ast)
            if errs:
                for e in errs: print(str(e), file=sys.stderr)
                raise RuntimeError(f"{len(errs)} error(es) semántico(s)")
            code = comp.compile_ast(ast)
            print("[TORVEN] Ejecutando…\n")
            VM().run(code)

        self._bg(_do)

    def _do_disasm(self):
        path = self._get_src_path()
        if not path: return
        self._clear()
        self._tabbar._select("bytecode")

        def _do():
            from torven.parser import parse
            from torven import compiler as comp
            src  = open(path, "r", encoding="utf-8").read()
            ast  = parse(src)
            code = comp.compile_ast(ast)

            def _render(co, ind=0):
                pad = "  " * ind
                self.after(0, self._append_bc,
                           f"{pad}══  {co.name}  ══\n", "hdr")
                for i, ins in enumerate(co.instructions):
                    if ins.opcode == "LABEL":
                        self.after(0, self._append_bc,
                                   f"{pad}  .{ins.arg}:\n", "label_")
                    else:
                        arg_s = repr(ins.arg) if ins.arg is not None else ""
                        self.after(0, self._append_bc, f"{pad}  {i:>4}  ")
                        self.after(0, self._append_bc,
                                   f"{ins.opcode:<18}", "opcode")
                        self.after(0, self._append_bc,
                                   f" {arg_s:<30}", "arg")
                        self.after(0, self._append_bc,
                                   f"; ln {ins.line}\n", "lineno")
                for sub in co.functions.values():
                    _render(sub, ind + 1)

            _render(code)
            self.after(0, self._set_status, "Bytecode generado ✓", "ok")

        threading.Thread(target=_do, daemon=True).start()

    def _do_tokens(self):
        path = self._get_src_path()
        if not path: return
        self._clear()
        self._tabbar._select("tokens")

        def _do():
            from torven.lexer import make_lexer
            src   = open(path, "r", encoding="utf-8").read()
            lexer = make_lexer()
            self.after(0, self._append_tok,
                       f"{'TIPO':<24}  {'VALOR':<34}  LÍNEA\n", "hdr_")
            self.after(0, self._append_tok, "─" * 68 + "\n", "hdr_")
            for tok in lexer.tokenize(src):
                self.after(0, self._append_tok, f"{tok.type:<24}  ", "type_")
                self.after(0, self._append_tok,
                           f"{str(tok.value):<34}  ", "val_")
                self.after(0, self._append_tok, f"{tok.lineno}\n")
            self.after(0, self._set_status, "Tokens generados ✓", "ok")

        threading.Thread(target=_do, daemon=True).start()

    def _do_tree(self):
        path = self._get_src_path()
        if not path: return
        self._tabbar._select("ast")
        self._set_status("Generando árboles AST…", "running")

        def _do():
            from torven.visualizer import visualize
            out_dir = os.path.dirname(os.path.abspath(path))
            paths   = visualize(path, out_dir=out_dir)
            self.after(0, self._load_tree_images, paths)
            self.after(0, self._set_status,
                       f"{len(paths)} árbol(es) generado(s) ✓", "ok")

        threading.Thread(target=_do, daemon=True).start()

    def _load_tree_images(self, paths: list):
        self._tree_paths = [p for p in paths if os.path.exists(p)]
        if not self._tree_paths:
            return
        names = [os.path.basename(p) for p in self._tree_paths]

        # Reconstruir el menú del OptionMenu
        menu = self._tree_combo["menu"]
        menu.delete(0, "end")
        for n in names:
            menu.add_command(
                label=n,
                command=lambda v=n: self._tree_var.set(v),
            )

        # Mostrar la primera imagen directamente (sin depender del trace)
        self._tree_var.set(names[0])
        self._show_tree_img(self._tree_paths[0])

    def _on_tree_select(self):
        val = self._tree_var.get()
        if not hasattr(self, "_tree_paths"):
            return
        for p in self._tree_paths:
            if os.path.basename(p) == val:
                self._show_tree_img(p)
                return

    def _show_tree_img(self, path: str):
        if not os.path.exists(path):
            return
        try:
            from PIL import Image, ImageTk as ITk
        except ImportError:
            self._tree_canvas.delete("all")
            self._tree_canvas.create_text(
                10, 20, anchor="nw",
                text="Instala Pillow para ver imágenes:\n  pip install Pillow",
                fill=ORANGE, font=("Consolas", 10),
            )
            return

        img   = Image.open(path)
        photo = ITk.PhotoImage(img)

        self._tree_canvas.delete("all")
        self._tree_canvas.create_image(0, 0, anchor="nw", image=photo)

        # scrollregion con padding para que se vea completo
        self._tree_canvas.configure(
            scrollregion=(0, 0, img.width + 20, img.height + 20),
        )
        # Volver al origen al cambiar de imagen
        self._tree_canvas.xview_moveto(0)
        self._tree_canvas.yview_moveto(0)

        # CRÍTICO: guardar referencia fuera del scope para evitar GC
        self._tree_imgs = [photo]

    # ══════════════════════════════════════════════════════════════════ CLOSE

    def _on_close(self):
        if self._modified and not messagebox.askyesno(
                "Salir", "¿Salir sin guardar?"):
            return
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────

def launch():
    app = TorvenIDE()
    app.mainloop()


if __name__ == "__main__":
    launch()
