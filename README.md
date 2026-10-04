# Processador de Consultas SQL

Trabalho da disciplina de Banco de Dados (Universidade de Fortaleza) — implementação de um
**Processador de Consultas** organizado em Histórias de Usuário (HU1 a HU5), conforme o
documento `26.2 - Projeto 2 - Processador de Consultas.pdf`.

O sistema recebe uma consulta SQL digitada pelo usuário, valida sua sintaxe e semântica,
converte para álgebra relacional, monta o grafo de operadores, aplica heurísticas de
otimização e exibe o plano de execução final.

## Status das Histórias de Usuário

| HU  | Descrição                              | Status        |
|-----|------------------------------------------|---------------|
| HU1 | Entrada e Validação da Consulta           | ✅ Implementada |
| HU2 | Conversão para Álgebra Relacional         | ⬜ Pendente     |
| HU3 | Construção do Grafo de Operadores         | ⬜ Pendente     |
| HU4 | Otimização da Consulta (heurísticas)      | ⬜ Pendente     |
| HU5 | Plano de Execução                         | ⬜ Pendente     |

## HU1 — Entrada e Validação da Consulta

> Como usuário do sistema (aluno/desenvolvedor), quero digitar uma consulta SQL na interface
> gráfica para que o sistema valide sintaxe, tabelas e atributos existentes.

### O que foi implementado

- Interface gráfica (Tkinter) com campo de texto e botão **Analisar**.
- Um **lexer** (`lexer.py`) que tokeniza a consulta (palavras-chave, identificadores,
  operadores, parênteses, números e strings).
- Um **parser recursivo descendente** (`parser.py`) que valida a gramática SQL suportada:
  `SELECT`, `FROM`, `WHERE`, `JOIN`, `ON`, operadores `=`, `>`, `<`, `<=`, `>=`, `<>`, `AND`
  e parênteses — com suporte a múltiplos `JOIN`s (0, 1, ..., N).
- Um **validador semântico** (`semantic.py`) que confere se as tabelas e colunas digitadas
  existem no modelo relacional de referência (`metadata.py`, Imagem 01 do enunciado),
  inclusive resolvendo colunas sem prefixo de tabela (ex.: `Nome` em vez de `Produto.Nome`).
- Separação clara entre **erro de sintaxe** (`SqlSyntaxError`) e **erro semântico**
  (`SqlSemanticError`), cada um exibido na interface com mensagem amigável indicando o tipo
  da falha.
- Regras de negócio da HU1: comparação de tabelas/colunas ignora maiúsculas/minúsculas e
  espaços repetidos são ignorados pelo lexer.

### Como funciona (passo a passo)

1. O usuário digita a consulta SQL na caixa de texto e clica em **Analisar**.
2. `lexer.tokenize()` transforma a string em uma lista de tokens.
3. `parser.parse_query()` consome os tokens seguindo a gramática SQL suportada e monta uma
   árvore de objetos (`Query`, `Join`, `Comparison`, `ColumnRef`, ...). Se a estrutura não
   bater com a gramática, um `SqlSyntaxError` é levantado com a posição e o motivo do erro.
4. `semantic.validate()` percorre essa árvore e confere cada tabela/coluna usada contra o
   `metadata.SCHEMA`. Se alguma não existir (ou um `JOIN`/`FROM` não incluir uma tabela que
   está sendo referenciada), um `SqlSemanticError` é levantado listando todos os problemas
   encontrados.
5. A interface mostra "✅ Consulta válida" com um resumo da consulta interpretada, ou
   "❌ Erro de Sintaxe" / "❌ Erro Semântico" com a mensagem específica.

A árvore (`Query`) retornada pelo parser é a estrutura que as próximas histórias de usuário
devem reaproveitar (HU2 a converte em álgebra relacional, HU3 a usa para montar o grafo de
operadores, etc.) — não é necessário reprocessar a string SQL original.

### Modelo relacional de referência

As tabelas e colunas aceitas pelo validador (Imagem 01 do enunciado) estão em
`processador_consultas/metadata.py`: `Categoria`, `Produto`, `TipoCliente`, `Cliente`,
`TipoEndereco`, `Endereco`, `Telefone`, `Status`, `Pedido`, `Pedido_has_Produto`.

## Estrutura do projeto

```
.
├── main.py                        # ponto de entrada (abre a interface gráfica)
├── processador_consultas/
│   ├── metadata.py                # modelo relacional de referência (Imagem 01)
│   ├── errors.py                  # SqlSyntaxError / SqlSemanticError
│   ├── lexer.py                   # tokenizador da consulta SQL
│   ├── parser.py                  # parser recursivo descendente + AST (Query, Join, ...)
│   ├── semantic.py                # validação de tabelas/colunas contra metadata.py
│   └── gui.py                     # interface gráfica (Tkinter) da HU1
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    └── test_semantic.py
```

## Como executar

Requer Python 3.10+ com o módulo `tkinter` (faz parte da instalação padrão do Python; em
distribuições Linux baseadas em Debian/Ubuntu pode precisar ser instalado à parte):

```bash
sudo apt-get install -y python3-tk   # necessário apenas no Linux, se faltar o tkinter
python3 main.py
```

### Exemplos para testar na interface

Consulta válida (com `JOIN` e `WHERE`):

```sql
SELECT Produto.Nome, Categoria.Descricao
FROM Produto
JOIN Categoria ON Produto.Categoria_idCategoria = Categoria.idCategoria
WHERE Produto.Preco > 100
```

Erro de sintaxe (falta a palavra-chave `FROM`):

```sql
SELECT * Produto
```

Erro semântico (tabela não existe no modelo):

```sql
SELECT * FROM Fornecedor
```

## Como rodar os testes

Os testes usam apenas a biblioteca padrão (`unittest`), sem dependências externas:

```bash
python3 -m unittest discover -s tests -v
```

## Como contribuir (demais HUs)

- Use `processador_consultas.parser.parse_query(sql)` para obter a árvore `Query` já validada
  sintaticamente, e `processador_consultas.semantic.validate(query)` para validá-la
  semanticamente — não é necessário reimplementar o parsing.
- A HU2 (Conversão para Álgebra Relacional) deve consumir o objeto `Query` retornado pelo
  parser (campos `columns`, `from_table`, `joins`, `where`).
- Siga o padrão de módulos já estabelecido: um módulo por responsabilidade dentro de
  `processador_consultas/`, com testes correspondentes em `tests/`.
