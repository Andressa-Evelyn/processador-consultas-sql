from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from .parser import Query


class OperatorKind(str, Enum):
    TABLE = "table"
    JOIN = "join"
    SELECTION = "selection"
    PROJECTION = "projection"


@dataclass
class OperatorNode:
    """Representa uma tabela ou um operador no grafo."""

    kind: OperatorKind
    data: Any
    children: list[OperatorNode] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == OperatorKind.TABLE:
            return f'{self.data}'
        if self.kind == OperatorKind.JOIN:
            return f'JUNÇÃO: {self.data}'
        if self.kind == OperatorKind.SELECTION:
            return f'SELEÇÃO: {self.data}'
        if self.kind == OperatorKind.PROJECTION:
            content = ", ".join(str(column) for column in self.data)
            return f'PROJEÇÃO: {content}'

        raise ValueError('kind não suportado')


def build_operator_graph(query: Query) -> OperatorNode:
    """Monta o grafo usando a consulta já interpretada pelo parser."""

    # A tabela do FROM inicia o grafo.
    current = OperatorNode(OperatorKind.TABLE, query.from_table)

    # Cada JOIN liga a relação atual a uma nova tabela.
    for join in query.joins:
        table = OperatorNode(OperatorKind.TABLE, join.table)
        current = OperatorNode(
            OperatorKind.JOIN,
            join.condition,
            [current, table],
        )

    # A seleção aplica a condição do WHERE sobre a relação atual.
    if query.where is not None:
        current = OperatorNode(
            OperatorKind.SELECTION,
            query.where,
            [current],
        )

    # A projeção seleciona as colunas do SELECT.
    # SELECT * mantém todas as colunas e não cria esse operador.
    if query.columns != "*":
        current = OperatorNode(
            OperatorKind.PROJECTION,
            query.columns,
            [current],
        )

    return current
