"""Lexer: transforma a string da consulta em uma lista de tokens.

A regex abaixo só reconhece "pedaços" (um número, um operador, uma palavra...).
Ela não sabe se a sequência de tokens forma uma consulta SQL válida — essa
responsabilidade é do parser (parser.py). Separar as duas etapas é o que
permite diferenciar erro de sintaxe (ordem/estrutura errada dos tokens) de
erro semântico (tokens corretos, mas tabela/coluna que não existe).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import SqlSyntaxError

# Palavras reservadas do subconjunto de SQL exigido pela HU1.
KEYWORDS = {"SELECT", "FROM", "WHERE", "JOIN", "ON", "AND"}

_TOKEN_SPEC = r"""
    (?P<STRING>'[^']*'|"[^"]*")
  | (?P<NUMBER>\d+(?:\.\d+)?)
  | (?P<LE><=)
  | (?P<GE>>=)
  | (?P<NE><>)
  | (?P<EQ>=)
  | (?P<LT><)
  | (?P<GT>>)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<COMMA>,)
  | (?P<DOT>\.)
  | (?P<STAR>\*)
  | (?P<WORD>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<WS>\s+)
  | (?P<MISMATCH>.)
"""
_MASTER_RE = re.compile(_TOKEN_SPEC, re.VERBOSE)


@dataclass
class Token:
    type: str  # ex.: "SELECT", "IDENT", "EQ", "NUMBER", "EOF"...
    value: str
    position: int  # coluna (0-based) onde o token começa, para mensagens de erro


def tokenize(sql: str) -> list[Token]:
    tokens: list[Token] = []
    for match in _MASTER_RE.finditer(sql):
        kind = match.lastgroup
        text = match.group()
        pos = match.start()

        if kind == "WS":
            continue  # regra de negócio: espaços repetidos são ignorados
        if kind == "MISMATCH":
            raise SqlSyntaxError(
                f"Caractere inválido {text!r} na posição {pos + 1}."
            )
        if kind == "WORD":
            upper = text.upper()
            kind = upper if upper in KEYWORDS else "IDENT"
        if kind == "STRING":
            text = text[1:-1]  # remove as aspas

        tokens.append(Token(type=kind, value=text, position=pos))

    tokens.append(Token(type="EOF", value="", position=len(sql)))
    return tokens
