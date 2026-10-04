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
