from copy import deepcopy
from dataclasses import fields, is_dataclass

from .parser import ColumnRef, Comparison, LogicalAnd
from .metadata import (
    TABLE_CARDINALITIES, COLUMN_DISTINCT_VALUES,
    DEFAULT_TABLE_CARDINALITY, PREDICATE_SELECTIVITIES,
)
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


def column_key(column: ColumnRef) -> tuple[str, str]:
    return column.table, column.name


def collect_column_refs(value) -> list[ColumnRef]:
    """Coleta referências a colunas dentro de uma expressão."""
    if isinstance(value, ColumnRef):
        return [value]

    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(collect_column_refs(item))
        return result

    if is_dataclass(value) and not isinstance(value, type):
        result = []
        for field_info in fields(value):
            result.extend(
                collect_column_refs(getattr(value, field_info.name))
            )
        return result

    return []


def collect_refs_by_key(node: OperatorNode) -> dict:
    """Mantém objetos ColumnRef para reconstruir as projeções."""
    result = {}

    def visit(current):
        for ref in collect_column_refs(current.data):
            result[column_key(ref)] = ref

        for child in current.children:
            visit(child)

    visit(node)
    return result


def optimize_projection_pushdown(
    root: OperatorNode,
) -> OperatorNode:
    refs = collect_refs_by_key(root)

    def push(node, required: set[tuple[str, str]]):
        if node.kind == OperatorKind.TABLE:
            # Conserva apenas as colunas necessárias desta tabela.
            columns = [
                refs[key]
                for key in sorted(required)
                if key[0] == node.data and key in refs
            ]

            if not columns:
                return node

            return OperatorNode(
                kind=OperatorKind.PROJECTION,
                data=columns,
                children=[node],
            )

        if node.kind == OperatorKind.PROJECTION:
            projection_keys = {
                column_key(column)
                for column in node.data
            }

            # Não descartamos colunas necessárias aos operadores abaixo.
            child_required = required | projection_keys

            return OperatorNode(
                kind=OperatorKind.PROJECTION,
                data=node.data,
                children=[
                    push(node.children[0], child_required)
                ],
            )

        if node.kind == OperatorKind.SELECTION:
            predicate_keys = {
                column_key(column)
                for column in collect_column_refs(node.data)
            }

            child_required = required | predicate_keys

            return OperatorNode(
                kind=OperatorKind.SELECTION,
                data=node.data,
                children=[
                    push(node.children[0], child_required)
                ],
            )

        if node.kind == OperatorKind.JOIN:
            join_keys = {
                column_key(column)
                for column in collect_column_refs(node.data)
            }

            all_required = required | join_keys

            left, right = node.children

            left_tables = collect_tables(left)
            right_tables = collect_tables(right)

            left_required = {
                key for key in all_required
                if key[0] in left_tables
            }

            right_required = {
                key for key in all_required
                if key[0] in right_tables
            }

            return OperatorNode(
                kind=OperatorKind.JOIN,
                data=node.data,
                children=[
                    push(left, left_required),
                    push(right, right_required),
                ],
            )

        raise ValueError(
            f"Operador não suportado: {node.kind}"
        )

    return push(root, set())


def estimate_selectivity(condition) -> float:
    """Estima a fração de linhas mantidas; AND assume independência."""
    if isinstance(condition, LogicalAnd):
        return estimate_selectivity(condition.left) * estimate_selectivity(condition.right)
    if not isinstance(condition, Comparison):
        return 1.0
    distinct_counts = [
        COLUMN_DISTINCT_VALUES[(column.table, column.name)]
        for column in collect_columns(condition)
        if (column.table, column.name) in COLUMN_DISTINCT_VALUES
    ]
    if condition.operator in ("=", "<>") and distinct_counts:
        equality = 1 / max(1, max(distinct_counts))
        return equality if condition.operator == "=" else 1 - equality
    return PREDICATE_SELECTIVITIES.get(condition.operator, 1.0)


def estimate_cardinality(node: OperatorNode) -> float:
    """Estima linhas intermediárias sem acessar um banco de dados."""
    if node.kind == OperatorKind.TABLE:
        return float(TABLE_CARDINALITIES.get(node.data, DEFAULT_TABLE_CARDINALITY))
    if node.kind == OperatorKind.JOIN:
        left, right = node.children
        return estimate_cardinality(left) * estimate_cardinality(right) * estimate_selectivity(node.data)
    rows = estimate_cardinality(node.children[0])
    if node.kind == OperatorKind.SELECTION:
        rows *= estimate_selectivity(node.data)
    return rows


def split_conjunction(condition) -> list:
    if isinstance(condition, LogicalAnd):
        return split_conjunction(condition.left) + split_conjunction(condition.right)
    return [condition]


def combine_conjunction(conditions):
    result = conditions[0]
    for condition in conditions[1:]:
        result = LogicalAnd(result, condition)
    return result


def optimize_restrictive_first(root: OperatorNode) -> OperatorNode:
    """Ordena por estimativas, sem alterar a entrada.

    Usa escolha gulosa do menor resultado intermediário em junções internas
    contíguas. Seleções e projeções delimitam os blocos de junções reordenáveis.
    As estatísticas assumem distribuição uniforme e predicados independentes;
    não representam uma busca pelo plano global de menor custo.
    """
    def reorder(node):
        if node.kind == OperatorKind.SELECTION and len(node.children) == 1:
            conditions = []
            while node.kind == OperatorKind.SELECTION and len(node.children) == 1:
                conditions.extend(split_conjunction(node.data))
                node = node.children[0]
            result = reorder(node)
            # A primeira condição executada fica mais perto das folhas.
            for condition in sorted(conditions, key=estimate_selectivity):
                result = OperatorNode(OperatorKind.SELECTION, condition, [result])
            return result

        if node.kind != OperatorKind.JOIN or len(node.children) != 2:
            node.children = [reorder(child) for child in node.children]
            return node

        relations, conditions = [], []

        def flatten(current):
            if current.kind == OperatorKind.JOIN and len(current.children) == 2:
                conditions.extend(split_conjunction(current.data))
                for child in current.children:
                    flatten(child)
            else:
                relations.append(reorder(current))

        flatten(node)
        table_sets = [collect_tables(relation) for relation in relations]
        references = [{column.table for column in collect_columns(c)} for c in conditions]
        # Sem resolução de aliases/colunas ambíguas, conservamos a ordem original.
        all_tables = set().union(*table_sets)
        if (sum(map(len, table_sets)) != len(all_tables)
                or any(None in refs or len(refs) < 2 or not refs <= all_tables
                       for refs in references)):
            node.children = [reorder(child) for child in node.children]
            return node

        pending = list(zip(conditions, references))
        while len(relations) > 1:
            candidates = []
            for i in range(len(relations)):
                for j in range(i + 1, len(relations)):
                    available = table_sets[i] | table_sets[j]
                    applicable = [c for c, refs in pending
                                  if refs <= available and refs & table_sets[i] and refs & table_sets[j]]
                    if applicable:
                        join = OperatorNode(OperatorKind.JOIN, combine_conjunction(applicable),
                                            [relations[i], relations[j]])
                        candidates.append((estimate_cardinality(join), i, j, join))
            if not candidates:
                # Não introduzimos produtos cartesianos para conectar componentes.
                node.children = [reorder(child) for child in node.children]
                return node
            _, i, j, join = min(candidates, key=lambda candidate: candidate[:3])
            available = table_sets[i] | table_sets[j]
            pending = [(c, refs) for c, refs in pending if not refs <= available]
            relations[i] = join
            table_sets[i] = available
            del relations[j]
            del table_sets[j]
        return relations[0]

    return reorder(deepcopy(root))


def optimize(node: OperatorNode) -> OperatorNode:
    all_optimizers = [
        optimize_selection_pushdown, optimize_restrictive_first,
        optimize_projection_pushdown,
    ]
    result = node
    for func in all_optimizers:
        result = func(result)

    return result
