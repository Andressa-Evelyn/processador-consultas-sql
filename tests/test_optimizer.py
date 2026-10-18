import unittest
from copy import deepcopy

from processador_consultas.operator_graph import OperatorKind, OperatorNode
from processador_consultas.optimizer import optimize_selection_pushdown
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


if __name__ == "__main__":
    unittest.main()
