import unittest

from processador_consultas.parser import parse_query
from processador_consultas.relational_algebra import to_relational_algebra


class TestRelationalAlgebra(unittest.TestCase):
    def test_converts_projection(self):
        query = parse_query("SELECT Produto.Nome, Preco FROM Produto")
        self.assertEqual(
            to_relational_algebra(query),
            "π_{Produto.Nome, Preco}(Produto)",
        )

    def test_converts_selection_and_preserves_comparison_operator(self):
        query = parse_query("SELECT * FROM Produto WHERE Preco <= 10")
        self.assertEqual(
            to_relational_algebra(query),
            "σ_{Preco <= 10}(Produto)",
        )

    def test_preserves_string_literals_and_combined_conditions(self):
        query = parse_query(
            "SELECT * FROM Produto WHERE Nome = 'Caneta' AND Preco < 10"
        )
        self.assertEqual(
            to_relational_algebra(query),
            "σ_{(Nome = 'Caneta' AND Preco < 10)}(Produto)",
        )

    def test_converts_join_selection_and_projection(self):
        query = parse_query(
            "SELECT Produto.Nome, Categoria.Descricao FROM Produto "
            "JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria "
            "WHERE Produto.Preco > 100"
        )
        self.assertEqual(
            to_relational_algebra(query),
            "π_{Produto.Nome, Categoria.Descricao}("
            "σ_{Produto.Preco > 100}("
            "(Produto ⋈_{Produto.Categoria_idCategoria = "
            "Categoria.idCategoria} Categoria)))",
        )

    def test_preserves_and_conditions_and_multiple_joins(self):
        query = parse_query(
            "SELECT * FROM Pedido "
            "JOIN Cliente ON Pedido.Cliente_idCliente = Cliente.idCliente "
            "JOIN Status ON Pedido.Status_idStatus = Status.idStatus "
            "WHERE Pedido.ValorTotalPedido >= 10 AND Pedido.idPedido <> 0"
        )
        self.assertEqual(
            to_relational_algebra(query),
            "σ_{(Pedido.ValorTotalPedido >= 10 AND Pedido.idPedido <> 0)}("
            "((Pedido ⋈_{Pedido.Cliente_idCliente = Cliente.idCliente} Cliente) "
            "⋈_{Pedido.Status_idStatus = Status.idStatus} Status))",
        )

    def test_star_without_conditions_is_just_the_relation(self):
        query = parse_query("SELECT * FROM Produto")
        self.assertEqual(to_relational_algebra(query), "Produto")


if __name__ == "__main__":
    unittest.main()
