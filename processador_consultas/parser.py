"""Parser recursivo descendente para o subconjunto de SQL da HU1.

Gramática implementada (maiúsculas = palavras-chave fixas):

    query        := SELECT select_list FROM IDENT join* [WHERE condition]
    select_list  := '*' | column_ref (',' column_ref)*
    join         := JOIN IDENT ON condition
    condition    := and_expr
    and_expr     := predicate (AND predicate)*
    predicate    := '(' condition ')' | comparison
    comparison   := operand operator operand
    operand      := column_ref | NUMBER | STRING
    column_ref   := IDENT ['.' IDENT]
    operator     := '=' | '>' | '<' | '<=' | '>=' | '<>'

O resultado é uma árvore de objetos (Query/Join/Comparison/...) que as
próximas histórias de usuário (HU2: álgebra relacional, HU3: grafo de
operadores...) podem percorrer sem precisar reinterpretar a string SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from .errors import SqlSyntaxError
from .lexer import Token, tokenize

COMPARISON_OPERATORS = {
    "EQ": "=",
    "GT": ">",
    "LT": "<",
    "LE": "<=",
    "GE": ">=",
    "NE": "<>",
}


# --------------------------------------------------------------------------
# AST (Abstract Syntax Tree)
# --------------------------------------------------------------------------


@dataclass
class ColumnRef:
    """Referência a uma coluna, ex.: `Produto.Nome` ou apenas `Nome`."""

    table: str | None
    name: str

    def __str__(self) -> str:
        return f"{self.table}.{self.name}" if self.table else self.name


@dataclass
class Literal:
    """Valor literal usado em uma comparação (número ou string)."""

    value: str
    kind: str  # "number" | "string"

    def __str__(self) -> str:
        return self.value if self.kind == "number" else f"'{self.value}'"


Operand = Union[ColumnRef, Literal]


@dataclass
class Comparison:
    left: Operand
    operator: str  # um de '=', '>', '<', '<=', '>=', '<>'
    right: Operand

    def __str__(self) -> str:
        return f"{self.left} {self.operator} {self.right}"


@dataclass
class LogicalAnd:
    left: "Condition"
    right: "Condition"

    def __str__(self) -> str:
        return f"({self.left} AND {self.right})"


Condition = Union[Comparison, LogicalAnd]


@dataclass
class Join:
    table: str
    condition: Condition


@dataclass
class Query:
    columns: str | list[ColumnRef]  # '*' ou lista de colunas
    from_table: str
    joins: list[Join] = field(default_factory=list)
    where: Condition | None = None


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    # -- utilidades -------------------------------------------------------

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        if token.type != "EOF":
            self._pos += 1
        return token

    def _expect(self, token_type: str, description: str) -> Token:
        token = self._current()
        if token.type != token_type:
            found = "o fim da consulta" if token.type == "EOF" else repr(token.value)
            raise SqlSyntaxError(
                f"Erro de sintaxe: esperado {description} na posição "
                f"{token.position + 1}, mas foi encontrado {found}."
            )
        return self._advance()

    # -- regras da gramática -----------------------------------------------

    def parse_query(self) -> Query:
        self._expect("SELECT", "a palavra-chave 'SELECT' no início da consulta")
        columns = self._parse_select_list()

        self._expect("FROM", "a palavra-chave 'FROM'")
        from_table = self._expect("IDENT", "o nome de uma tabela após 'FROM'").value

        joins: list[Join] = []
        while self._current().type == "JOIN":
            joins.append(self._parse_join())

        where: Condition | None = None
        if self._current().type == "WHERE":
            self._advance()
            where = self._parse_condition()

        if self._current().type != "EOF":
            token = self._current()
            raise SqlSyntaxError(
                f"Erro de sintaxe: token inesperado {token.value!r} na posição "
                f"{token.position + 1} após o fim da consulta."
            )

        return Query(columns=columns, from_table=from_table, joins=joins, where=where)

    def _parse_select_list(self) -> str | list[ColumnRef]:
        if self._current().type == "STAR":
            self._advance()
            return "*"

        columns = [self._parse_column_ref()]
        while self._current().type == "COMMA":
            self._advance()
            columns.append(self._parse_column_ref())
        return columns

    def _parse_column_ref(self) -> ColumnRef:
        first = self._expect("IDENT", "o nome de uma coluna ou tabela").value
        if self._current().type == "DOT":
            self._advance()
            column = self._expect(
                "IDENT", f"o nome da coluna após '{first}.'"
            ).value
            return ColumnRef(table=first, name=column)
        return ColumnRef(table=None, name=first)

    def _parse_join(self) -> Join:
        self._advance()  # consome 'JOIN'
        table = self._expect("IDENT", "o nome de uma tabela após 'JOIN'").value
        self._expect("ON", "a palavra-chave 'ON' após a tabela do JOIN")
        condition = self._parse_condition()
        return Join(table=table, condition=condition)

    def _parse_condition(self) -> Condition:
        return self._parse_and_expr()

    def _parse_and_expr(self) -> Condition:
        left = self._parse_predicate()
        while self._current().type == "AND":
            self._advance()
            right = self._parse_predicate()
            left = LogicalAnd(left=left, right=right)
        return left

    def _parse_predicate(self) -> Condition:
        if self._current().type == "LPAREN":
            self._advance()
            condition = self._parse_condition()
            self._expect("RPAREN", "o fechamento ')' do grupo de condições")
            return condition
        return self._parse_comparison()

    def _parse_comparison(self) -> Comparison:
        left = self._parse_operand()
        operator_token = self._current()
        if operator_token.type not in COMPARISON_OPERATORS:
            raise SqlSyntaxError(
                "Erro de sintaxe: esperado um operador de comparação "
                "(=, >, <, <=, >=, <>) na posição "
                f"{operator_token.position + 1}, mas foi encontrado "
                f"{operator_token.value!r}."
            )
        self._advance()
        right = self._parse_operand()
        return Comparison(
            left=left, operator=COMPARISON_OPERATORS[operator_token.type], right=right
        )

    def _parse_operand(self) -> Operand:
        token = self._current()
        if token.type == "IDENT":
            return self._parse_column_ref()
        if token.type == "NUMBER":
            self._advance()
            return Literal(value=token.value, kind="number")
        if token.type == "STRING":
            self._advance()
            return Literal(value=token.value, kind="string")
        found = "o fim da consulta" if token.type == "EOF" else repr(token.value)
        raise SqlSyntaxError(
            "Erro de sintaxe: esperado uma coluna, número ou texto na posição "
            f"{token.position + 1}, mas foi encontrado {found}."
        )


def parse_query(sql: str) -> Query:
    """Função de conveniência: tokeniza e faz o parsing de `sql`.

    Levanta SqlSyntaxError quando a consulta não segue a gramática suportada.
    Não faz validação semântica — isso é responsabilidade de `semantic.validate`.
    """
    tokens = tokenize(sql)
    parser = Parser(tokens)
    return parser.parse_query()
