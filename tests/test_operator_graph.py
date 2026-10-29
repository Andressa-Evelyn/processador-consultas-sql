import unittest

from processador_consultas.operator_graph import OperatorKind, OperatorNode, build_operator_graph
from processador_consultas.errors import SqlSemanticError, SqlSyntaxError
from processador_consultas.metadata import TABLE_CARDINALITIES
from processador_consultas.optimizer import estimate_cardinality, optimize
from processador_consultas.parser import parse_query
from processador_consultas.relational_algebra import to_relational_algebra
from processador_consultas.semantic import validate


class TestOperatorGraph(unittest.TestCase):
    def test_builds_cross_product_from_comma_separated_tables(self):
        query = parse_query("SELECT * FROM Produto, Categoria")
        validate(query)

        graph = build_operator_graph(query)

        self.assertIsNone(query.joins[0].condition)
        self.assertEqual(OperatorNode(
            OperatorKind.CROSS_PRODUCT, None,
            [OperatorNode(OperatorKind.TABLE, "Produto"),
             OperatorNode(OperatorKind.TABLE, "Categoria")],
        ), graph)
        self.assertEqual("PRODUTO CARTESIANO", graph.label)
        self.assertEqual("(Produto × Categoria)", to_relational_algebra(query))
        self.assertEqual(
            TABLE_CARDINALITIES["Produto"] * TABLE_CARDINALITIES["Categoria"],
            estimate_cardinality(graph),
        )

    def test_builds_multiple_cross_products(self):
        query = parse_query("SELECT * FROM Produto, Categoria, Cliente")
        graph = build_operator_graph(query)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, graph.kind)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, graph.children[0].kind)
        self.assertEqual("Cliente", graph.children[1].data)
        self.assertEqual("((Produto × Categoria) × Cliente)", to_relational_algebra(query))

    def test_join_has_precedence_over_comma(self):
        query = parse_query(
            "SELECT * FROM Categoria, Produto "
            "JOIN Pedido_has_Produto ON Produto.idProduto = Pedido_has_Produto.Produto_idProduto"
        )
        graph = build_operator_graph(query)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, graph.kind)
        self.assertEqual("Categoria", graph.children[0].data)
        self.assertEqual(OperatorKind.JOIN, graph.children[1].kind)
        self.assertEqual(
            "(Categoria × (Produto ⋈_{Produto.idProduto = Pedido_has_Produto.Produto_idProduto} Pedido_has_Produto))",
            to_relational_algebra(query),
        )

    def test_comma_after_join_preserves_join_group(self):
        query = parse_query(
            "SELECT * FROM Produto JOIN Categoria "
            "ON Produto.Categoria_idCategoria = Categoria.idCategoria, Cliente"
        )
        graph = build_operator_graph(query)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, graph.kind)
        self.assertEqual(OperatorKind.JOIN, graph.children[0].kind)
        self.assertEqual("Cliente", graph.children[1].data)

    def test_cross_product_preserves_projection_and_selection_in_pipeline(self):
        query = parse_query(
            "SELECT Produto.Nome, Categoria.Descricao FROM Produto, Categoria "
            "WHERE Produto.Preco > 100"
        )
        validate(query)
        graph = build_operator_graph(query)
        self.assertEqual(OperatorKind.PROJECTION, graph.kind)
        self.assertEqual(OperatorKind.SELECTION, graph.children[0].kind)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, graph.children[0].children[0].kind)
        result = optimize(graph)
        self.assertEqual(OperatorKind.PROJECTION, result.kind)
        self.assertEqual(OperatorKind.CROSS_PRODUCT, result.children[0].kind)
        projected = result.children[0].children[0]
        self.assertEqual(OperatorKind.PROJECTION, projected.kind)
        filtered = projected.children[0]
        self.assertEqual(OperatorKind.SELECTION, filtered.kind)
        self.assertEqual(OperatorKind.TABLE, filtered.children[0].kind)
        self.assertEqual(
            "π_{Produto.Nome, Categoria.Descricao}(σ_{Produto.Preco > 100}((Produto × Categoria)))",
            to_relational_algebra(query),
        )

    def test_rejects_missing_table_after_comma(self):
        for sql in ("SELECT * FROM Produto,", "SELECT * FROM Produto,, Categoria"):
            with self.subTest(sql=sql), self.assertRaises(SqlSyntaxError):
                parse_query(sql)

    def test_validates_tables_and_ambiguous_columns_in_cross_product(self):
        for sql in (
            "SELECT * FROM Produto, Unknown",
            "SELECT Descricao FROM Produto, Categoria",
            "SELECT Categoria.Unknown FROM Produto, Categoria",
        ):
            with self.subTest(sql=sql), self.assertRaises(SqlSemanticError):
                validate(parse_query(sql))

    def test_monta_tabelas_join_where_e_projecao(self):
        sql = """
        SELECT Produto.Nome, Categoria.Descricao
        FROM Produto
        JOIN Categoria
            ON Produto.Categoria_idCategoria = Categoria.idCategoria
        WHERE Produto.Preco > 100
        """

        graph = build_operator_graph(parse_query(sql))

        # A projeção fica na raiz.
        self.assertEqual("projection", graph.kind)

        # Abaixo dela vem a seleção do WHERE.
        selection = graph.children[0]
        self.assertEqual("selection", selection.kind)

        # Abaixo da seleção vem a junção.
        join = selection.children[0]
        self.assertEqual("join", join.kind)

        # A junção recebe as duas tabelas.
        self.assertEqual(
            ["Produto", "Categoria"],
            [node.label for node in join.children],
        )

    def test_select_asterisco_nao_cria_projecao(self):
        graph = build_operator_graph(parse_query("SELECT * FROM Produto"))

        self.assertEqual("table", graph.kind)
        self.assertEqual("Produto", graph.label)
        self.assertEqual([], graph.children)

    def test_monta_grafo_com_multiplos_joins(self):
      """Verifica que cada JOIN acrescenta uma tabela ao grafo."""
      sql = """
      SELECT Produto.Nome
      FROM Produto
      JOIN Categoria
          ON Produto.Categoria_idCategoria = Categoria.idCategoria
      JOIN Pedido_has_Produto
          ON Produto.idProduto = Pedido_has_Produto.Produto_idProduto
      """

      graph = build_operator_graph(parse_query(sql))

      # O primeiro JOIN fica dentro do segundo JOIN.
      second_join = graph.children[0]
      self.assertEqual("join", second_join.kind)
      self.assertEqual("Pedido_has_Produto", second_join.children[1].label)

      first_join = second_join.children[0]
      self.assertEqual("join", first_join.kind)
      self.assertEqual(
          ["Produto", "Categoria"],
          [node.label for node in first_join.children],
      )


if __name__ == "__main__":
    unittest.main()
