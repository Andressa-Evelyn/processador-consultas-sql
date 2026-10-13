from dataclasses import dataclass, field

from .parser import Query


@dataclass
class OperatorNode:
    kind: str
    label: str
    children: list["OperatorNode"] = field(default_factory=list)


def build_operator_graph(query: Query) -> OperatorNode:
    # Começa pela tabela do FROM.
    current = OperatorNode("table", query.from_table)

    #cada join combina o resultado atual com uma nova tabela."""Monta o grafo de operadores de uma consulta SQL."""

from dataclasses import dataclass, field

from .parser import Query


@dataclass
class OperatorNode:
    """Representa uma tabela ou um operador no grafo."""

    kind: str
    label: str
    children: list["OperatorNode"] = field(default_factory=list)


def build_operator_graph(query: Query) -> OperatorNode:
    """Monta o grafo usando a consulta já interpretada pelo parser."""

    # A tabela do FROM inicia o grafo.
    current = OperatorNode("table", query.from_table)

    # Cada JOIN liga a relação atual a uma nova tabela.
    for join in query.joins:
        table = OperatorNode("table", join.table)
        current = OperatorNode(
            "join",
            "JUNÇÃO: " + str(join.condition),
            [current, table],
        )

    # A seleção aplica a condição do WHERE sobre a relação atual.
    if query.where is not None:
        current = OperatorNode(
            "selection",
            "SELEÇÃO: " + str(query.where),
            [current],
        )

    # A projeção seleciona as colunas do SELECT.
    # SELECT * mantém todas as colunas e não cria esse operador.
    if query.columns != "*":
        columns = ", ".join(str(column) for column in query.columns)
        current = OperatorNode(
            "projection",
            "PROJEÇÃO: " + columns,
            [current],
        )

    return current
    for join in query.joins:
        table = OperatorNode("table", join.table)
        current = OperatorNode(
            "join",
            "JUNÇÃO: " + str(join.condition),
            [current, table],
        )

    #where fica acima das tabelas e junções.
    if query.where is not None:
        current = OperatorNode(
            "selection",
            "SELEÇÃO: " + str(query.where),
            [current],
        )

    # Se houver colunas específicas no SELECT, a projeção fica na raiz.
    if query.columns != "*":
        columns = ", ".join(str(column) for column in query.columns)
        current = OperatorNode(
            "projection",
            "PROJEÇÃO: " + columns,
            [current],
        )

    return current