from copy import deepcopy
from dataclasses import fields, is_dataclass

from .parser import ColumnRef, LogicalAnd
from .operator_graph import OperatorNode, OperatorKind


def collect_tables(node: OperatorNode) -> set[str]:
    """Retorna todas as tabelas presentes em uma subárvore."""
    if node.kind == OperatorKind.TABLE:
        return {node.data}

    tables = set()

    for child in node.children:
        tables.update(collect_tables(child))

    return tables


def collect_columns(value) -> set[ColumnRef]:
    """Extrai as referências a colunas de uma expressão."""
    if isinstance(value, ColumnRef):
        return {value}

    if isinstance(value, (list, tuple)):
        columns = set()

        for item in value:
            columns.update(collect_columns(item))

        return columns

    if is_dataclass(value) and not isinstance(value, type):
        columns = set()

        for field_info in fields(value):
            columns.update(
                collect_columns(getattr(value, field_info.name))
            )

        return columns

    return set()


def optimize_selection_pushdown(
    node: OperatorNode,
) -> OperatorNode:
    """Aplica a heurística de antecipação de seleções."""
    # Trabalhamos em uma cópia para preservar a árvore original.
    node = deepcopy(node)

    # Primeiro, otimizamos recursivamente os filhos.
    node.children = [
        optimize_selection_pushdown(child)
        for child in node.children
    ]

    # A regra exige uma seleção diretamente acima de uma junção.
    if (
        node.kind != OperatorKind.SELECTION
        or len(node.children) != 1
    ):
        return node

    join = node.children[0]

    if (
        join.kind != OperatorKind.JOIN
        or len(join.children) != 2
    ):
        return node

    left, right = join.children
    left_tables = collect_tables(left)
    right_tables = collect_tables(right)

    def combine(first, second):
        if first is None:
            return second
        if second is None:
            return first
        return LogicalAnd(first, second)

    def partition(condition):
        if isinstance(condition, LogicalAnd):
            first = partition(condition.left)
            second = partition(condition.right)
            return tuple(combine(a, b) for a, b in zip(first, second))
        referenced_tables = {column.table for column in collect_columns(condition)}
        if referenced_tables and referenced_tables <= left_tables:
            return condition, None, None
        if referenced_tables and referenced_tables <= right_tables:
            return None, condition, None
        # Predicados entre ramos, constantes e colunas sem tabela ficam acima.
        return None, None, condition

    left_condition, right_condition, remaining = partition(node.data)
    if left_condition is None and right_condition is None:
        return node

    if left_condition is not None:
        left = optimize_selection_pushdown(OperatorNode(
            OperatorKind.SELECTION, left_condition, [left]
        ))
    if right_condition is not None:
        right = optimize_selection_pushdown(OperatorNode(
            OperatorKind.SELECTION, right_condition, [right]
        ))

    join.children = [left, right]
    if remaining is not None:
        node.data = remaining
        return node
    return join


def optimize(node: OperatorNode) -> OperatorNode:
    all_optimizers = [optimize_selection_pushdown]
    result = node
    for func in all_optimizers:
        result = func(node)

    return result
