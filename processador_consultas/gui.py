"""Interface gráfica da HU1 e HU2: validação e álgebra relacional.

Fluxo do botão "Analisar":
    texto digitado -> parse_query() (sintaxe) -> validate() (semântica)
    -> conversão para álgebra relacional -> mensagem de sucesso ou erro.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext
from tkinter import ttk

from processador_consultas.operator_graph import OperatorNode, build_operator_graph

from .errors import SqlSemanticError, SqlSyntaxError
from .parser import Query, parse_query
from .relational_algebra import to_relational_algebra
from .semantic import validate


EXAMPLE_QUERY = (
    "SELECT Produto.Nome, Categoria.Descricao\n"
    "FROM Produto\n"
    "JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria\n"
    "WHERE Produto.Preco > 100"
)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Processador de Consultas SQL — HU1 e HU2")
        self.geometry("860x600")
        self.minsize(640, 480)

        # Último AST validado com sucesso, disponível para as próximas
        # histórias de usuário (HU2: álgebra relacional, HU3: grafo...).
        self.last_query: Query | None = None

        self._build_widgets()

    def _build_widgets(self) -> None:
        mono = tkfont.Font(family="Courier New", size=11)

        tk.Label(
            self, text="Consulta SQL", anchor="w", font=("Helvetica", 11, "bold")
        ).pack(fill="x", padx=12, pady=(12, 0))

        self.input_box = scrolledtext.ScrolledText(
            self, height=8, font=mono, wrap="word", undo=True
        )
        self.input_box.pack(fill="x", padx=12, pady=6)
        self.input_box.insert("1.0", EXAMPLE_QUERY)

        button_bar = tk.Frame(self)
        button_bar.pack(fill="x", padx=12)
        tk.Button(
            button_bar, text="Analisar", command=self.analyze, width=14
        ).pack(side="left")
        tk.Button(
            button_bar, text="Limpar", command=self._clear_all, width=10
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            self, text="Resultado", anchor="w", font=("Helvetica", 11, "bold")
        ).pack(fill="x", padx=12, pady=(12, 0))

        self.output_box = scrolledtext.ScrolledText(
        self, height=7, font=mono, wrap="word", state="disabled"
        )
        self.output_box.pack(fill="x", padx=12, pady=(6, 6))

        tk.Label(
            self,
            text="Grafo de Operadores (original)",
            anchor="w",
            font=("Helvetica", 11, "bold"),
        ).pack(fill="x", padx=12, pady=(6, 0))

        self.graph_tree = ttk.Treeview(self, show="tree", height=8)
        self.graph_tree.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.output_box.tag_config("ok", foreground="#1a7f37")
        self.output_box.tag_config("err", foreground="#c0392b")
        self.output_box.tag_config("bold", font=("Courier New", 11, "bold"))

    def _clear_all(self) -> None:
        self.input_box.delete("1.0", tk.END)
        self._clear_graph()
        self._write("", tag=None)

    def _write(self, text: str, tag: str | None) -> None:
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", tk.END)
        if text:
            self.output_box.insert("1.0", text, (tag,) if tag else ())
        self.output_box.configure(state="disabled")

    def analyze(self) -> None:
        self._clear_graph()
        sql = self.input_box.get("1.0", tk.END).strip()
        if not sql:
            self._write("Digite uma consulta SQL antes de analisar.", "err")
            return

        try:
            query = parse_query(sql)
        except SqlSyntaxError as exc:
            self._write(f"❌ Erro de Sintaxe\n\n{exc}", "err")
            return

        try:
            validate(query)
        except SqlSemanticError as exc:
            self._write(f"❌ Erro Semântico\n\n{exc}", "err")
            return

        self.last_query = query
        algebra = to_relational_algebra(query)
        self._write(
            f"✅ Consulta válida!\n\n{_describe(query)}\n\n"
            f"Álgebra Relacional:\n{algebra}",
            "ok",
        )
        graph = build_operator_graph(query)
        self._show_operator_graph(graph)

    def _clear_graph(self) -> None:
        self.graph_tree.delete(*self.graph_tree.get_children())


    def _show_operator_graph(self, node: OperatorNode, parent: str = "") -> None:
        item = self.graph_tree.insert(parent, "end", text=node.label, open=True)

        for child in node.children:
            self._show_operator_graph(child, item)


def _describe(query: Query) -> str:
    lines = []
    columns = "*" if query.columns == "*" else ", ".join(str(c) for c in query.columns)
    lines.append(f"Colunas selecionadas : {columns}")
    lines.append(f"Tabela principal     : {query.from_table}")
    if query.joins:
        lines.append("Junções (JOIN)       :")
        for join in query.joins:
            lines.append(f"  - {join.table}  ON  {join.condition}")
    else:
        lines.append("Junções (JOIN)       : nenhuma")
    lines.append(f"Condição (WHERE)     : {query.where if query.where else 'nenhuma'}")
    return "\n".join(lines)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
