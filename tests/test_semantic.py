import unittest

from processador_consultas.errors import SqlSemanticError
from processador_consultas.parser import parse_query
from processador_consultas.semantic import validate


class TestSemantic(unittest.TestCase):
    def test_valid_query_passes(self):
        query = parse_query(
            "SELECT Produto.Nome, Categoria.Descricao FROM Produto "
            "JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria "
            "WHERE Produto.Preco > 100"
        )
        validate(query)  # não deve levantar

    def test_unknown_table_is_semantic_error(self):
        query = parse_query("SELECT * FROM Fornecedor")
        with self.assertRaises(SqlSemanticError):
            validate(query)

    def test_unknown_column_is_semantic_error(self):
        query = parse_query("SELECT Produto.Inexistente FROM Produto")
        with self.assertRaises(SqlSemanticError):
            validate(query)

    def test_table_not_in_from_or_join_is_semantic_error(self):
        # Cliente existe no modelo, mas não foi incluído no FROM/JOIN desta consulta.
        query = parse_query("SELECT Cliente.Nome FROM Produto")
        with self.assertRaises(SqlSemanticError):
            validate(query)

    def test_unqualified_column_resolves_when_unambiguous(self):
        query = parse_query("SELECT Nome FROM Produto")
        validate(query)  # Produto.Nome existe e é a única tabela da consulta

    def test_ambiguous_unqualified_column_is_semantic_error(self):
        # Produto e Categoria têm ambas uma coluna "Descricao".
        query = parse_query(
            "SELECT Descricao FROM Produto "
            "JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria"
        )
        with self.assertRaises(SqlSemanticError):
            validate(query)

    def test_schema_lookup_is_case_insensitive(self):
        query = parse_query("select produto.nome from produto")
        validate(query)


if __name__ == "__main__":
    unittest.main()
