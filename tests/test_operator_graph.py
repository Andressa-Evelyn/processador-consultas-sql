import unittest

from processador_consultas.operator_graph import build_operator_graph
from processador_consultas.parser import parse_query


class TestOperatorGraph(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()