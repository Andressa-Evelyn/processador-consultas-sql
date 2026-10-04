"""Validação semântica: confere tabelas e colunas contra o modelo relacional.

Roda depois que o parser já confirmou que a consulta é gramaticalmente válida
(ver parser.py). Aqui o problema não é mais "a consulta está bem formada?",
e sim "as tabelas/colunas que o usuário digitou existem de fato?".
"""

from __future__ import annotations

from . import metadata
from .errors import SqlSemanticError
from .parser import ColumnRef, Comparison, Condition, Literal, LogicalAnd, Query


def _iter_column_refs(condition: Condition):
    if isinstance(condition, Comparison):
        for operand in (condition.left, condition.right):
            if isinstance(operand, ColumnRef):
                yield operand
    elif isinstance(condition, LogicalAnd):
        yield from _iter_column_refs(condition.left)
        yield from _iter_column_refs(condition.right)


def validate(query: Query) -> None:
    """Levanta SqlSemanticError (com todos os problemas encontrados) ou retorna None."""

    errors: list[str] = []

    # 1) tabelas usadas na consulta (FROM + JOINs) precisam existir no modelo.
    used_tables: dict[str, str] = {}  # nome digitado (lower) -> nome canônico
    table_entries = [("FROM", query.from_table)] + [
        ("JOIN", join.table) for join in query.joins
    ]
    for clause, typed_name in table_entries:
        canonical = metadata.find_table(typed_name)
        if canonical is None:
            errors.append(
                f"Tabela '{typed_name}' (usada em {clause}) não existe no modelo relacional."
            )
        else:
            used_tables[typed_name.lower()] = canonical

    # Sem tabelas válidas não há como resolver colunas: reporta e para por aqui.
    if not used_tables:
        raise SqlSemanticError("\n".join(errors))

    def resolve_column(ref: ColumnRef) -> None:
        if ref.table is not None:
            canonical_table = used_tables.get(ref.table.lower())
            if canonical_table is None:
                if metadata.find_table(ref.table) is None:
                    errors.append(
                        f"Tabela '{ref.table}' (em '{ref}') não existe no modelo relacional."
                    )
                else:
                    errors.append(
                        f"Tabela '{ref.table}' (em '{ref}') não faz parte do FROM/JOIN desta consulta."
                    )
                return
            if metadata.find_column(canonical_table, ref.name) is None:
                errors.append(
                    f"Coluna '{ref.name}' não existe na tabela '{canonical_table}' (em '{ref}')."
                )
            return

        # Coluna sem prefixo: procura em todas as tabelas usadas na consulta.
        matches = [
            table
            for table in used_tables.values()
            if metadata.find_column(table, ref.name) is not None
        ]
        if not matches:
            errors.append(
                f"Coluna '{ref.name}' não existe em nenhuma das tabelas da consulta "
                f"({', '.join(sorted(set(used_tables.values())))})."
            )
        elif len(matches) > 1:
            errors.append(
                f"Coluna '{ref.name}' é ambígua: existe em mais de uma tabela da "
                f"consulta ({', '.join(sorted(matches))}); use o prefixo tabela.coluna."
            )

    # 2) colunas do SELECT.
    if query.columns != "*":
        for column in query.columns:
            resolve_column(column)

    # 3) colunas usadas nas condições de JOIN (ON ...).
    for join in query.joins:
        for ref in _iter_column_refs(join.condition):
            resolve_column(ref)

    # 4) colunas usadas no WHERE.
    if query.where is not None:
        for ref in _iter_column_refs(query.where):
            resolve_column(ref)

    if errors:
        raise SqlSemanticError("\n".join(errors))
