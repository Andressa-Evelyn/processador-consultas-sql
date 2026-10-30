"""Interface gráfica da HU1 e HU2: validação e álgebra relacional.

Fluxo do botão "Analisar":
    texto digitado -> parse_query() (sintaxe) -> validate() (semântica)
    -> conversão para álgebra relacional -> mensagem de sucesso ou erro.
"""

from __future__ import annotations

import tkinter as tk
from collections import defaultdict
from tkinter import font as tkfont
from tkinter import scrolledtext, StringVar, ttk
from collections.abc import Callable

from processador_consultas.operator_graph import OperatorNode, build_operator_graph

from .errors import SqlSemanticError, SqlSyntaxError
from .parser import Query, parse_query
from .relational_algebra import to_relational_algebra, node_to_relational_algebra
from .semantic import validate
from .optimizer import optimize
from .metadata import SCHEMA, TABLE_CARDINALITIES, COLUMN_DISTINCT_VALUES
from .execution_plan import build_execution_plan


EXAMPLE_QUERY = (
    "SELECT Produto.Nome, Categoria.Descricao\n"
    "FROM Produto\n"
    "JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria\n"
    "WHERE Produto.Preco > 100"
)


class AppViewModel:
    def __init__(self):
        self.sql_text = StringVar(value=EXAMPLE_QUERY)
        self.output_text = StringVar(value=EXAMPLE_QUERY)
        self._original_graph = None
        self._optimized_graph = None
        self._listeners: dict[str, list] = defaultdict(list)

    def add_notify(self, key: str, func: Callable[[OperatorNode], None]):
        self._listeners[key].append(func)

    def notify(self, key):
        value = self.original_graph if key == 'original' else self.optimized_graph
        for listener in self._listeners[key]:
            listener(value)

    @property
    def original_graph(self):
        return self._original_graph

    @original_graph.setter
    def original_graph(self, value):
        self._original_graph = value
        self.notify('original')

    @property
    def optimized_graph(self):
        return self._optimized_graph

    @optimized_graph.setter
    def optimized_graph(self, value):
        self._optimized_graph = value
        self.notify('optimized')

    def analyze(self, sql: str):
        self.original_graph = None
        self.optimized_graph = None

        if not sql:
            self.output_text.set("Digite uma consulta SQL antes de analisar.")
            return

        try:
            query = parse_query(sql)
        except SqlSyntaxError as exc:
            self.output_text.set(f"❌ Erro de Sintaxe\n\n{exc}")
            return

        try:
            validate(query)
        except SqlSemanticError as exc:
            self.output_text.set(f"❌ Erro Semântico\n\n{exc}")
            return

        # self.last_query = query
        algebra = to_relational_algebra(query)
        self.original_graph = build_operator_graph(query)
        self.optimized_graph = optimize(self.original_graph)
        algebra_optimized = node_to_relational_algebra(self.optimized_graph)
        self.output_text.set(
            f"✅ Consulta válida!\n\n{_describe(query)}\n\n"
            f"Álgebra Relacional:\n{algebra}\n\n"
            f"Álgebra Relacional otimizada:\n{algebra_optimized}\n"
        )
        print(f'{self.original_graph=}')
        print(f'{self.optimized_graph=}')

    def clear(self):
        self.output_text.set('')
        self.sql_text.set('')
        self.original_graph = None
        self.optimized_graph = None


def button_bar(master: tk.Misc, analyze, clear_all):
    content = tk.Frame(master)
    content.pack(fill="x", padx=12)
    ttk.Button(
        content, text="Analisar", command=analyze, width=14
    ).pack(side="left")
    ttk.Button(
        content, text="Limpar", command=clear_all, width=10
    ).pack(side="left", padx=(8, 0))

    return content


def TreeMetadata(master: tk.Misc):
    frame = ttk.Frame(master)
    ttk.Label(frame, text="Metadados (estimativas)").pack(side="top", fill="x")
    tree = ttk.Treeview(
        frame, columns=("cardinality", "distinct_values"),
        show="tree headings", height=8,
    )
    tree.heading("#0", text="Tabela / Coluna")
    tree.heading("cardinality", text="Cardinalidade")
    tree.heading("distinct_values", text="Valores distintos")
    tree.column("#0", width=190, minwidth=120)
    tree.column("cardinality", width=95, minwidth=90, anchor="e")
    tree.column("distinct_values", width=110, minwidth=100, anchor="e")

    for table_name, columns in SCHEMA.items():
        cardinality = TABLE_CARDINALITIES.get(table_name, "Não informado")
        table_item = tree.insert(
            "", "end", text=table_name, values=(cardinality, "")
        )
        for column_name in columns:
            distinct_values = COLUMN_DISTINCT_VALUES.get(
                (table_name, column_name), "Não informado"
            )
            tree.insert(
                table_item, "end", text=column_name, values=("", distinct_values)
            )

    tree.pack(fill="both", expand=True)

    return frame


class QueryFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, view_model: AppViewModel, **kwargs):
        super().__init__(master, **kwargs)
        self.view_model = view_model
        self.input_box: scrolledtext.ScrolledText | None = None
        self.build()
        self.view_model.sql_text.trace_add('write', self.attach)

    def build(self):
        tk.Label(
            self, text="Consulta SQL", anchor="w", font=("Helvetica", 11, "bold")
        ).pack(fill="x", padx=12, pady=(12, 0))

        frame = ttk.Frame(self)

        self.input_box: scrolledtext.ScrolledText = scrolledtext.ScrolledText(
            frame, height=8, font=tkfont.Font(family="Courier New", size=11),
            wrap="word", undo=True
        )
        self.input_box.pack(fill="x", side="left", padx=12, pady=6)
        self.input_box.insert("1.0", EXAMPLE_QUERY)

        tree = TreeMetadata(frame)
        tree.pack(side="left", padx=12, pady=6)

        frame.pack(fill="x")

        button_bar(self, analyze=self.analyze, clear_all=self.clear_all)

    def analyze(self):
        sql = self.input_box.get("1.0", tk.END).strip()
        self.view_model.analyze(sql)

    def clear_all(self) -> None:
        self.view_model.clear()

    def attach(self, *_):
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", self.view_model.sql_text.get())


class OutputFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, view_model: AppViewModel, **kwargs):
        super().__init__(master, **kwargs)
        self.view_model = view_model
        self.output_box: scrolledtext.ScrolledText | None = None
        self.build()
        self.view_model.output_text.trace_add("write", self.update_output)

    def build(self) -> None:
        tk.Label(
            self, text="Resultado", anchor="w", font=("Helvetica", 11, "bold")
        ).pack(fill="x", padx=12, pady=(12, 0))

        self.output_box = scrolledtext.ScrolledText(
            self, height=7, font=tkfont.Font(family="Courier New", size=11), wrap="word", state="disabled"
        )
        self.output_box.pack(fill="x", padx=12, pady=(6, 6))
        self.output_box.tag_config("ok", foreground="#1a7f37")
        self.output_box.tag_config("err", foreground="#c0392b")
        self.output_box.tag_config("bold", font=("Courier New", 11, "bold"))

    def get_tag(self):
        value = self.view_model.output_text.get()
        if value.startswith("✅"):
            return "ok"
        if value.startswith("❌"):
            return "err"
        return None

    def update_output(self, *_):
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", tk.END)
        tag = self.get_tag()
        value = self.view_model.output_text.get()
        self.output_box.insert("1.0", value, (tag,) if tag else ())
        self.output_box.configure(state="disabled")


class GraphFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc, observer: Callable[Callable[[OperatorNode], None], None], **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.graph_tree = ttk.Treeview(self, show="tree", height=8)
        self.graph_tree.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        observer(self.update_graph)

    def update_graph(self, value: OperatorNode):
        self.clear_graph()
        if value:
            self.show_operator_graph(value)

    def clear_graph(self) -> None:
        self.graph_tree.delete(*self.graph_tree.get_children())

    def show_operator_graph(self, node: OperatorNode, parent: str = "") -> None:
        item = self.graph_tree.insert(parent, "end", text=node.label, open=True)

        for child in node.children:
            self.show_operator_graph(child, item)



class ExecutionPlanFrame(ttk.Frame):
    """Exibe o plano lógico ordenado e a justificativa de cada operação."""
    def __init__(self, parent: tk.Misc, observer, **kwargs):
        super().__init__(parent, **kwargs)
        ttk.Label(self, text="Plano de Execução (grafo otimizado)").pack(
            side="top", fill="x", padx=8, pady=(8, 2)
        )
        self.tree = ttk.Treeview(
            self, columns=("operation", "heuristic", "rationale"),
            show="headings", height=10
        )
        self.tree.heading("operation", text="Etapa / operação")
        self.tree.heading("heuristic", text="Heurística")
        self.tree.heading("rationale", text="Justificativa / efeito")
        self.tree.column("operation", width=220, minwidth=150)
        self.tree.column("heuristic", width=240, minwidth=170)
        self.tree.column("rationale", width=420, minwidth=220)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        observer(self.update_plan)

    def update_plan(self, root):
        self.tree.delete(*self.tree.get_children())
        if root is None:
            return
        for step in build_execution_plan(root):
            self.tree.insert("", "end", values=(
                f"{step.number}. {step.operation}", step.heuristic, step.rationale
            ))

def GraphTabs(master: tk.Misc, view_model: AppViewModel, **kwargs):
    frame = ttk.Frame(master)
    tk.Label(
        frame,
        text="Grafo de Operadores",
        anchor="w",
        font=("Helvetica", 11, "bold"),
    ).pack(fill="x", pady=(6, 0))

    tabs = ttk.Notebook(frame)
    tabs.add(GraphFrame(tabs, lambda func: view_model.add_notify("original", func)), text="Sem otimização")
    tabs.add(GraphFrame(tabs, lambda func: view_model.add_notify("optimized", func)), text="Com otimização")
    tabs.add(ExecutionPlanFrame(tabs, lambda func: view_model.add_notify("optimized", func)), text="Plano de Execução")
    tabs.pack(fill="both", expand=True)
    return frame


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Processador de Consultas SQL — HU1 a HU5")
        self.geometry("860x600")
        self.minsize(640, 480)
        self.view_model = AppViewModel()

        # Último AST validado com sucesso, disponível para as próximas
        # histórias de usuário (HU2: álgebra relacional, HU3: grafo...).
        self.last_query: Query | None = None

        self._build_widgets()

    def _build_widgets(self) -> None:
        query_frame = QueryFrame(self, self.view_model)
        query_frame.pack(fill="x")

        output_frame = OutputFrame(self, self.view_model)
        output_frame.pack(fill="x")

        tabs = GraphTabs(self, self.view_model)
        tabs.pack(fill="x", padx=12, pady=(6, 0))


def _describe(query: Query) -> str:
    lines = []
    columns = "*" if query.columns == "*" else ", ".join(str(c) for c in query.columns)
    lines.append(f"Colunas selecionadas : {columns}")
    lines.append(f"Tabela principal     : {query.from_table}")
    if query.joins:
        lines.append("Junções (JOIN)       :")
        for join in query.joins:
            if join.condition is None:
                lines.append(f"  - {join.table} (produto cartesiano)")
            else:
                lines.append(f"  - {join.table}  ON  {join.condition}")
    else:
        lines.append("Junções (JOIN)       : nenhuma")
    lines.append(f"Condição (WHERE)     : {query.where if query.where else 'nenhuma'}")
    return "\n".join(lines)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
