"""Modelo relacional de referência (Imagem 01 do enunciado do Projeto 2).

Este é o "dicionário de dados" usado pela validação semântica da HU1: toda
tabela e toda coluna digitadas pelo usuário precisam existir aqui.
"""

from __future__ import annotations

# Nome da tabela -> lista de colunas, exatamente como descrito no enunciado.
SCHEMA: dict[str, list[str]] = {
    "Categoria": ["idCategoria", "Descricao"],
    "Produto": [
        "idProduto",
        "Nome",
        "Descricao",
        "Preco",
        "QuantEstoque",
        "Categoria_idCategoria",
    ],
    "TipoCliente": ["idTipoCliente", "Descricao"],
    "Cliente": [
        "idCliente",
        "Nome",
        "Email",
        "Nascimento",
        "Senha",
        "TipoCliente_idTipoCliente",
        "DataRegistro",
    ],
    "TipoEndereco": ["idTipoEndereco", "Descricao"],
    "Endereco": [
        "idEndereco",
        "EnderecoPadrao",
        "Logradouro",
        "Numero",
        "Complemento",
        "Bairro",
        "Cidade",
        "UF",
        "CEP",
        "TipoEndereco_idTipoEndereco",
        "Cliente_idCliente",
    ],
    "Telefone": ["Numero", "Cliente_idCliente"],
    "Status": ["idStatus", "Descricao"],
    "Pedido": [
        "idPedido",
        "Status_idStatus",
        "DataPedido",
        "ValorTotalPedido",
        "Cliente_idCliente",
    ],
    "Pedido_has_Produto": [
        "idPedidoProduto",
        "Pedido_idPedido",
        "Produto_idProduto",
        "Quantidade",
        "PrecoUnitario",
    ],
}


# Estatísticas ilustrativas, não coletadas de um banco real.
TABLE_CARDINALITIES: dict[str, int] = {
    "Categoria": 50,
    "Produto": 10000,
    "TipoCliente": 5,
    "Cliente": 20000,
    "TipoEndereco": 5,
    "Endereco": 30000,
    "Telefone": 25000,
    "Status": 6,
    "Pedido": 100000,
    "Pedido_has_Produto": 300000,
}

# Quantidade estimada de valores distintos (NDV) por coluna.
COLUMN_DISTINCT_VALUES: dict[tuple[str, str], int] = {
    ("Categoria", "idCategoria"): 50,
    ("Produto", "idProduto"): 10000,
    ("Produto", "Categoria_idCategoria"): 50,
    ("Produto", "Preco"): 1000,
    ("Cliente", "idCliente"): 20000,
    ("Cliente", "TipoCliente_idTipoCliente"): 5,
    ("TipoCliente", "idTipoCliente"): 5,
    ("TipoEndereco", "idTipoEndereco"): 5,
    ("Endereco", "idEndereco"): 30000,
    ("Endereco", "Cliente_idCliente"): 20000,
    ("Endereco", "TipoEndereco_idTipoEndereco"): 5,
    ("Telefone", "Cliente_idCliente"): 20000,
    ("Status", "idStatus"): 6,
    ("Pedido", "idPedido"): 100000,
    ("Pedido", "Cliente_idCliente"): 20000,
    ("Pedido", "Status_idStatus"): 6,
    ("Pedido_has_Produto", "idPedidoProduto"): 300000,
    ("Pedido_has_Produto", "Pedido_idPedido"): 100000,
    ("Pedido_has_Produto", "Produto_idProduto"): 10000,
}

# Fração estimada de linhas mantidas quando não há estatísticas da coluna.
DEFAULT_TABLE_CARDINALITY = 1000
PREDICATE_SELECTIVITIES: dict[str, float] = {
    "=": 0.1, "<>": 0.9,
    "<": 1 / 3, ">": 1 / 3, "<=": 1 / 3, ">=": 1 / 3,
}


def find_table(name: str) -> str | None:
    """Retorna o nome canônico da tabela (como está no SCHEMA) ou None.

    A comparação ignora maiúsculas/minúsculas, conforme regra de negócio da HU1.
    """
    for table_name in SCHEMA:
        if table_name.lower() == name.lower():
            return table_name
    return None


def find_column(table_name: str, column_name: str) -> str | None:
    """Retorna o nome canônico da coluna dentro de uma tabela já validada, ou None."""
    for col in SCHEMA.get(table_name, []):
        if col.lower() == column_name.lower():
            return col
    return None
