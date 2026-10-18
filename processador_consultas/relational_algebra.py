"""Converte uma consulta SQL interpretada para álgebra relacional."""

from __future__ import annotations

from .parser import Query


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
