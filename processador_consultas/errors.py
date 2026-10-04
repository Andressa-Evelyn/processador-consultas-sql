"""Erros do processador de consultas.

Duas classes separadas (em vez de uma só) é o que permite à interface
distinguir, como pede a HU1, entre erro de gramática SQL e erro semântico.
"""


class SqlSyntaxError(Exception):
    """Consulta mal formada: palavra-chave faltando, JOIN incompleto, etc."""


class SqlSemanticError(Exception):
    """Consulta gramaticalmente correta, mas referencia tabela/coluna inexistente."""
