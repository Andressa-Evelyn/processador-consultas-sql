"""Converte uma consulta SQL interpretada para álgebra relacional."""

from __future__ import annotations

from .parser import Query
from .operator_graph import OperatorNode, OperatorKind


def to_relational_algebra(query: Query) -> str:
    """Converte FROM, JOIN, WHERE e SELECT em relações e operadores."""
    expression = query.from_table

    # JOIN tem precedência sobre os produtos cartesianos do FROM.
    groups = []
    for join in query.joins:
        if join.condition is None:
            groups.append(expression)
            expression = join.table
        else:
            expression = f"({expression} ⋈_{{{join.condition}}} {join.table})"
    groups.append(expression)
    expression = groups[0]
    for group in groups[1:]:
        expression = f"({expression} × {group})"

    # WHERE vira seleção (σ).
    if query.where is not None:
        expression = f"σ_{{{query.where}}}({expression})"

    # SELECT com colunas vira projeção (π); SELECT * mantém todas.
    if query.columns != "*":
        columns = ", ".join(str(column) for column in query.columns)
        expression = f"π_{{{columns}}}({expression})"

    return expression


def node_to_relational_algebra(node: OperatorNode) -> str:
    """Converte OperatorNode em relações e operadores."""
    if node.kind == OperatorKind.TABLE:
        return str(node.data)

    if node.kind in (OperatorKind.JOIN, OperatorKind.CROSS_PRODUCT):
        left, right = node.children
        left_expression = node_to_relational_algebra(left)
        right_expression = node_to_relational_algebra(right)
        operator = f"⋈_{{{node.data}}}" if node.kind == OperatorKind.JOIN else "×"
        return f"({left_expression} {operator} {right_expression})"

    if node.kind in (OperatorKind.SELECTION, OperatorKind.PROJECTION):
        child, = node.children
        expression = node_to_relational_algebra(child)
        if node.kind == OperatorKind.SELECTION:
            return f"σ_{{{node.data}}}({expression})"
        columns = ", ".join(str(column) for column in node.data)
        return f"π_{{{columns}}}({expression})"

    raise ValueError(f"Operador não suportado: {node.kind}")
