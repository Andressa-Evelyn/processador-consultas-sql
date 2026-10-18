import unittest
from copy import deepcopy
from unittest.mock import patch

from processador_consultas import metadata

from processador_consultas.operator_graph import OperatorKind, OperatorNode
from processador_consultas.optimizer import (
    collect_tables, estimate_cardinality, estimate_selectivity,
    optimize, optimize_restrictive_first, optimize_selection_pushdown,
    split_conjunction,
)
from processador_consultas.parser import ColumnRef, Comparison, Literal, LogicalAnd


def table(name):
    return OperatorNode(OperatorKind.TABLE, name)


def predicate(table_name, column="value", operator=">", value="10"):
    return Comparison(
        ColumnRef(table_name, column), operator, Literal(value, "number")
    )


def selection(condition, child):
    return OperatorNode(OperatorKind.SELECTION, condition, [child])


def make_join(left, right):
    return OperatorNode(
        OperatorKind.JOIN,
        Comparison(ColumnRef("A", "id"), "=", ColumnRef("B", "a_id")),
        [left, right],
    )


class TestOptimizeSelectionPushdown(unittest.TestCase):
    def setUp(self):
        self.join = make_join(table("A"), table("B"))

    def test_moves_selection_to_each_side_of_join(self):
        for name, index in (("A", 0), ("B", 1)):
            with self.subTest(table=name):
                condition = predicate(name)
                expected = deepcopy(self.join)
                expected.children[index] = selection(condition, table(name))

                result = optimize_selection_pushdown(selection(condition, self.join))

                self.assertEqual(expected, result)

    def test_splits_and_and_pushes_each_selection_to_its_table_below_projection(self):
        product_condition = predicate("Produto", "Preco", ">", "100")
        category_condition = predicate("Categoria", "idCategoria", "<", "100")
        join_condition = Comparison(
            ColumnRef("Produto", "Categoria_idCategoria"),
            "=",
            ColumnRef("Categoria", "idCategoria"),
        )
        columns = [
            ColumnRef("Produto", "Nome"),
            ColumnRef("Categoria", "Descricao"),
        ]
        original = OperatorNode(
            OperatorKind.PROJECTION,
            columns,
            [
                selection(
                    LogicalAnd(product_condition, category_condition),
                    OperatorNode(
                        OperatorKind.JOIN,
                        join_condition,
                        [table("Produto"), table("Categoria")],
                    ),
                )
            ],
        )
        snapshot = deepcopy(original)
        expected = OperatorNode(
            OperatorKind.PROJECTION,
            columns,
            [
                OperatorNode(
                    OperatorKind.JOIN,
                    join_condition,
                    [
                        selection(product_condition, table("Produto")),
                        selection(category_condition, table("Categoria")),
                    ],
                )
            ],
        )

        result = optimize_selection_pushdown(original)

        self.assertEqual(snapshot, original)
        self.assertEqual(expected, result)

    def test_moves_entire_nested_and_when_all_conditions_reference_same_table(self):
        for name, index in (("A", 0), ("B", 1)):
            with self.subTest(table=name):
                condition = LogicalAnd(
                    LogicalAnd(predicate(name), predicate(name, "price", "<", "100")),
                    LogicalAnd(predicate(name, "stock"), predicate(name, "age")),
                )
                expected = deepcopy(self.join)
                expected.children[index] = selection(condition, table(name))

                result = optimize_selection_pushdown(selection(condition, self.join))

                self.assertEqual(expected, result)

    def test_splits_and_with_one_condition_per_table(self):
        for names in (("A", "B"), ("B", "A")):
            with self.subTest(order=names):
                condition = LogicalAnd(predicate(names[0]), predicate(names[1]))
                original = selection(condition, self.join)

                expected = make_join(
                    selection(predicate("A"), table("A")),
                    selection(predicate("B"), table("B")),
                )
                self.assertEqual(expected, optimize_selection_pushdown(original))

    def test_pushes_larger_and_to_each_of_four_tables(self):
        join = make_join(make_join(table("A"), table("B")),
                      make_join(table("C"), table("D")))
        conditions = [predicate(name) for name in ("A", "B", "C", "D")]
        groupings = [
            LogicalAnd(LogicalAnd(LogicalAnd(*conditions[:2]), conditions[2]), conditions[3]),
            LogicalAnd(LogicalAnd(*conditions[:2]), LogicalAnd(*conditions[2:])),
            LogicalAnd(conditions[0], LogicalAnd(conditions[1], LogicalAnd(*conditions[2:]))),
        ]
        for condition in groupings:
            with self.subTest(condition=str(condition)):
                original = selection(condition, join)
                expected = make_join(
                    make_join(
                        selection(conditions[0], table("A")),
                        selection(conditions[1], table("B")),
                    ),
                    make_join(
                        selection(conditions[2], table("C")),
                        selection(conditions[3], table("D")),
                    ),
                )
                self.assertEqual(expected, optimize_selection_pushdown(original))

    def test_moves_and_from_different_tables_in_same_branch(self):
        branch = make_join(table("A"), table("B"))
        condition = LogicalAnd(predicate("A"), predicate("B"))
        for index in (0, 1):
            with self.subTest(branch=index):
                join = make_join(branch, table("C")) if index == 0 else make_join(table("C"), branch)
                expected = deepcopy(join)
                expected.children[index] = make_join(
                    selection(predicate("A"), table("A")),
                    selection(predicate("B"), table("B")),
                )

                result = optimize_selection_pushdown(selection(condition, join))

                self.assertEqual(expected, result)

    def test_keeps_comparison_between_columns_from_both_branches(self):
        condition = Comparison(ColumnRef("A", "value"), ">", ColumnRef("B", "value"))
        original = selection(condition, self.join)

        self.assertEqual(original, optimize_selection_pushdown(original))

    def test_does_not_move_predicates_without_identifiable_table(self):
        conditions = [
            Comparison(Literal("1", "number"), "=", Literal("1", "number")),
            predicate(None),
            predicate("Unknown"),
        ]
        for condition in conditions:
            with self.subTest(condition=str(condition)):
                original = selection(condition, self.join)
                self.assertEqual(original, optimize_selection_pushdown(original))

    def test_keeps_remaining_conditions_above_join_and_pushes_local_condition(self):
        cross_table_condition = Comparison(
            ColumnRef("A", "value"), ">", ColumnRef("B", "value")
        )
        remaining_conditions = [
            cross_table_condition,
            predicate(None),
            predicate("Unknown"),
            Comparison(Literal("1", "number"), "=", Literal("1", "number")),
        ]
        for remaining in remaining_conditions:
            with self.subTest(remaining=str(remaining)):
                original = selection(
                    LogicalAnd(predicate("A"), remaining), self.join
                )
                expected = selection(
                    remaining,
                    make_join(selection(predicate("A"), table("A")), table("B")),
                )

                self.assertEqual(expected, optimize_selection_pushdown(original))

    def test_optimizes_selection_below_projection(self):
        condition = predicate("A")
        original = OperatorNode(
            OperatorKind.PROJECTION, [ColumnRef("A", "value")],
            [selection(condition, self.join)],
        )
        expected = OperatorNode(
            OperatorKind.PROJECTION, [ColumnRef("A", "value")],
            [make_join(selection(condition, table("A")), table("B"))],
        )

        self.assertEqual(expected, optimize_selection_pushdown(original))

    def test_groups_interleaved_conditions_by_branch_and_preserves_remaining_and(self):
        first_left = predicate("A", "price")
        second_left = predicate("A", "stock")
        right_condition = predicate("B", "value")
        cross_table = Comparison(ColumnRef("A", "id"), "<", ColumnRef("B", "id"))
        unknown = predicate("Unknown")
        condition = LogicalAnd(
            LogicalAnd(first_left, cross_table),
            LogicalAnd(right_condition, LogicalAnd(second_left, unknown)),
        )
        original = selection(condition, self.join)
        snapshot = deepcopy(original)
        expected = selection(
            LogicalAnd(cross_table, unknown),
            make_join(
                selection(LogicalAnd(first_left, second_left), table("A")),
                selection(right_condition, table("B")),
            ),
        )

        result = optimize_selection_pushdown(original)

        self.assertEqual(expected, result)
        self.assertEqual(snapshot, original)

    def test_moves_comparisons_with_column_on_right_or_both_operands(self):
        for name, index in (("A", 0), ("B", 1)):
            conditions = [
                Comparison(Literal("100", "number"), "<", ColumnRef(name, "price")),
                Comparison(ColumnRef(name, "price"), ">", ColumnRef(name, "cost")),
            ]
            for condition in conditions:
                with self.subTest(table=name, condition=str(condition)):
                    expected = deepcopy(self.join)
                    expected.children[index] = selection(condition, table(name))

                    result = optimize_selection_pushdown(selection(condition, self.join))

                    self.assertEqual(expected, result)

    def test_moves_cross_table_condition_to_lowest_join_containing_both_tables(self):
        cross_table = Comparison(
            ColumnRef("A", "price"), ">", ColumnRef("B", "price")
        )
        local_condition = predicate("C")
        branch = make_join(table("A"), table("B"))
        for index in (0, 1):
            with self.subTest(branch=index):
                children = [branch, table("C")] if index == 0 else [table("C"), branch]
                original = selection(
                    LogicalAnd(cross_table, local_condition), make_join(*children)
                )
                expected_children = [
                    selection(cross_table, branch),
                    selection(local_condition, table("C")),
                ]
                if index == 1:
                    expected_children.reverse()
                expected = make_join(*expected_children)

                result = optimize_selection_pushdown(original)

                self.assertEqual(expected, result)
                self.assertEqual(result, optimize_selection_pushdown(result))

    def test_preserves_trees_without_join_directly_below_selection(self):
        cases = [table("A"), self.join, selection(predicate("A"), table("A"))]
        for original in cases:
            with self.subTest(kind=original.kind):
                self.assertEqual(original, optimize_selection_pushdown(original))

    def test_preserves_original_tree_and_does_not_share_mutable_nodes(self):
        condition = LogicalAnd(predicate("A"), predicate("A", "price"))
        original = selection(condition, self.join)
        snapshot = deepcopy(original)

        result = optimize_selection_pushdown(original)

        self.assertEqual(snapshot, original)
        self.assertIsNot(original, result)
        self.assertIsNot(condition, result.children[0].data)
        result.children[0].children[0].data = "Changed"
        result.children[1].children.append(table("Extra"))
        result.children[0].data.left = predicate("Other")
        self.assertEqual(snapshot, original)


def join(left, right, first, second):
    return OperatorNode(
        OperatorKind.JOIN,
        Comparison(ColumnRef(first, "id"), "=", ColumnRef(second, "id")),
        [left, right],
    )


class TestRestrictiveFirst(unittest.TestCase):
    def test_metadata_covers_all_tables(self):
        self.assertEqual(set(metadata.SCHEMA), set(metadata.TABLE_CARDINALITIES))
        for (name, column), count in metadata.COLUMN_DISTINCT_VALUES.items():
            self.assertIn(column, metadata.SCHEMA[name])
            self.assertGreater(count, 0)
            self.assertLessEqual(count, metadata.TABLE_CARDINALITIES[name])

    def test_estimates_equality_range_and_conjunction(self):
        equality = Comparison(ColumnRef("Produto", "idProduto"), "=", Literal("1", "number"))
        inequality = Comparison(equality.left, "<>", equality.right)
        range_condition = Comparison(equality.left, ">", equality.right)
        self.assertAlmostEqual(0.0001, estimate_selectivity(equality))
        self.assertAlmostEqual(0.9999, estimate_selectivity(inequality))
        self.assertAlmostEqual(1 / 3, estimate_selectivity(range_condition))
        self.assertAlmostEqual(0.0001 / 3, estimate_selectivity(LogicalAnd(equality, range_condition)))
        self.assertEqual(metadata.DEFAULT_TABLE_CARDINALITY, estimate_cardinality(table("Unknown")))

    def test_orders_combined_and_stacked_selections_nearest_table_first(self):
        equality = Comparison(ColumnRef("Produto", "idProduto"), "=", Literal("1", "number"))
        range_condition = Comparison(ColumnRef("Produto", "Preco"), ">", Literal("100", "number"))
        for original in (
            OperatorNode(OperatorKind.SELECTION, LogicalAnd(range_condition, equality), [table("Produto")]),
            OperatorNode(OperatorKind.SELECTION, equality, [
                OperatorNode(OperatorKind.SELECTION, range_condition, [table("Produto")])
            ]),
        ):
            with self.subTest(original=original):
                snapshot = deepcopy(original)
                result = optimize_restrictive_first(original)
                self.assertEqual(range_condition, result.data)
                self.assertEqual(equality, result.children[0].data)
                self.assertEqual(table("Produto"), result.children[0].children[0])
                self.assertEqual(snapshot, original)

    def test_joins_smallest_estimated_result_first_and_preserves_predicates(self):
        original = join(join(table("A"), table("B"), "A", "B"), table("C"), "B", "C")
        snapshot = deepcopy(original)
        with patch.dict(metadata.TABLE_CARDINALITIES, {"A": 10000, "B": 100, "C": 10}):
            result = optimize_restrictive_first(original)
        inner = next(child for child in result.children if child.kind == OperatorKind.JOIN)
        self.assertEqual({"B", "C"}, collect_tables(inner))
        self.assertCountEqual(
            [original.data, original.children[0].data], [result.data, inner.data]
        )
        self.assertEqual(snapshot, original)

    def test_uses_filtered_cardinality_when_choosing_join(self):
        condition = Comparison(ColumnRef("A", "id"), "=", Literal("1", "number"))
        filtered = OperatorNode(OperatorKind.SELECTION, condition, [table("A")])
        original = join(join(filtered, table("B"), "A", "B"), table("C"), "B", "C")
        with patch.dict(metadata.TABLE_CARDINALITIES, {"A": 10000, "B": 100, "C": 10}), \
                patch.dict(metadata.COLUMN_DISTINCT_VALUES, {("A", "id"): 10000}):
            result = optimize_restrictive_first(original)
        inner = next(child for child in result.children if child.kind == OperatorKind.JOIN)
        self.assertEqual({"A", "B"}, collect_tables(inner))

    def test_preserves_cyclic_join_predicates_and_projection(self):
        original = join(join(table("A"), table("B"), "A", "B"), table("C"), "B", "C")
        extra = Comparison(ColumnRef("A", "id"), "=", ColumnRef("C", "id"))
        original.data = LogicalAnd(original.data, extra)
        columns = [ColumnRef("A", "id")]
        result = optimize_restrictive_first(OperatorNode(OperatorKind.PROJECTION, columns, [original]))
        self.assertEqual(columns, result.data)
        predicates = []

        def visit(node):
            if node.kind == OperatorKind.JOIN:
                predicates.extend(split_conjunction(node.data))
            for child in node.children:
                visit(child)

        visit(result)
        self.assertCountEqual(
            split_conjunction(original.data) + [original.children[0].data], predicates
        )

    def test_preserves_join_with_unqualified_columns(self):
        original = join(table("A"), table("B"), "A", "B")
        original.data = Comparison(ColumnRef(None, "id"), "=", ColumnRef("B", "id"))
        self.assertEqual(original, optimize_restrictive_first(original))

    def test_does_not_create_cartesian_join_when_conditions_cannot_connect_all_tables(self):
        original = join(join(table("A"), table("B"), "A", "B"), table("C"), "A", "B")
        snapshot = deepcopy(original)

        result = optimize_restrictive_first(original)

        self.assertEqual(snapshot, result)
        self.assertEqual(snapshot, original)

    def test_full_pipeline_applies_restrictive_first(self):
        equality = Comparison(ColumnRef("Produto", "idProduto"), "=", Literal("1", "number"))
        range_condition = Comparison(ColumnRef("Produto", "Preco"), ">", Literal("100", "number"))
        original = OperatorNode(OperatorKind.SELECTION, LogicalAnd(range_condition, equality), [table("Produto")])
        result = optimize(original)
        self.assertEqual(range_condition, result.data)
        self.assertEqual(equality, result.children[0].data)


if __name__ == "__main__":
    unittest.main()
