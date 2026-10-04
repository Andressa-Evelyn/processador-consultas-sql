import unittest

from processador_consultas.errors import SqlSyntaxError
from processador_consultas.lexer import tokenize


class TestLexer(unittest.TestCase):
    def test_tokenizes_keywords_and_identifiers(self):
        tokens = tokenize("select Nome from Produto")
        types = [t.type for t in tokens]
        self.assertEqual(types, ["SELECT", "IDENT", "FROM", "IDENT", "EOF"])

    def test_collapses_repeated_whitespace(self):
        tokens = tokenize("SELECT   *    FROM   Produto")
        types = [t.type for t in tokens]
        self.assertEqual(types, ["SELECT", "STAR", "FROM", "IDENT", "EOF"])

    def test_multi_char_operators_are_not_split(self):
        tokens = tokenize("WHERE Preco <= 10")
        types = [t.type for t in tokens]
        self.assertIn("LE", types)
        self.assertNotIn("LT", types)

    def test_string_and_number_literals(self):
        tokens = tokenize("WHERE Nome = 'Caneta' AND Preco > 9.9")
        values = {t.type: t.value for t in tokens}
        self.assertEqual(values["STRING"], "Caneta")
        self.assertEqual(values["NUMBER"], "9.9")

    def test_invalid_character_raises_syntax_error(self):
        with self.assertRaises(SqlSyntaxError):
            tokenize("SELECT * FROM Produto WHERE Preco # 10")


if __name__ == "__main__":
    unittest.main()
