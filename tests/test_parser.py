import unittest

from processador_consultas.errors import SqlSyntaxError
from processador_consultas.parser import ColumnRef, parse_query


class TestParser(unittest.TestCase):
    def test_parses_simple_select(self):
        query = parse_query("SELECT * FROM Produto")
        self.assertEqual(query.columns, "*")
        self.assertEqual(query.from_table, "Produto")
        self.assertEqual(query.joins, [])
        self.assertIsNone(query.where)

    def test_parses_column_list_with_qualified_names(self):
        query = parse_query("SELECT Produto.Nome, Preco FROM Produto")
        self.assertEqual(
            query.columns,
            [ColumnRef(table="Produto", name="Nome"), ColumnRef(table=None, name="Preco")],
        )

    def test_parses_multiple_joins(self):
        sql = (
            "SELECT * FROM Pedido "
            "JOIN Cliente ON Pedido.Cliente_idCliente = Cliente.idCliente "
            "JOIN Status ON Pedido.Status_idStatus = Status.idStatus"
        )
        query = parse_query(sql)
        self.assertEqual(len(query.joins), 2)
        self.assertEqual(query.joins[0].table, "Cliente")
        self.assertEqual(query.joins[1].table, "Status")

    def test_parses_where_with_and_and_parentheses(self):
        sql = (
            "SELECT * FROM Produto "
            "WHERE (Preco > 10 AND Preco <= 100) AND Nome <> 'x'"
        )
        query = parse_query(sql)
        self.assertIsNotNone(query.where)

    def test_is_case_insensitive_for_keywords(self):
        query = parse_query("select * from Produto where Preco > 1")
        self.assertEqual(query.from_table, "Produto")

    def test_missing_from_raises_syntax_error(self):
        with self.assertRaises(SqlSyntaxError):
            parse_query("SELECT * Produto")

    def test_incomplete_join_raises_syntax_error(self):
        with self.assertRaises(SqlSyntaxError):
            parse_query("SELECT * FROM Pedido JOIN Cliente")

    def test_dangling_and_raises_syntax_error(self):
        with self.assertRaises(SqlSyntaxError):
            parse_query("SELECT * FROM Produto WHERE Preco > 1 AND")

    def test_trailing_garbage_raises_syntax_error(self):
        with self.assertRaises(SqlSyntaxError):
            parse_query("SELECT * FROM Produto; DROP TABLE Produto")


if __name__ == "__main__":
    unittest.main()
