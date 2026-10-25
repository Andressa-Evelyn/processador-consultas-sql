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
| HU2 | Conversão para Álgebra Relacional         | ✅ Implementada |
| HU3 | Construção do Grafo de Operadores         | ✅ Implementada |
| HU4 | Otimização da Consulta (heurísticas)      | ✅ Implementada |
| HU5 | Plano de Execução                         | ✅ Implementada |

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

## HU2 — Conversão para Álgebra Relacional

Após validar a consulta, a interface também exibe sua expressão equivalente em álgebra
relacional. O módulo `processador_consultas/relational_algebra.py` consome diretamente a AST
retornada por `parse_query()`:

- `SELECT` com lista de colunas é representado por projeção (`π`).
- `WHERE` é representado por seleção (`σ`).
- Cada `JOIN ... ON` é representado por uma junção theta (`⋈`) com sua condição.
- Tabelas separadas por vírgula no `FROM` são representadas por produto cartesiano (`×`).
- Consultas sem uma dessas operações omitem o operador correspondente; `SELECT *` não
  acrescenta uma projeção artificial.

Por exemplo, a consulta padrão da interface gera uma expressão equivalente a:

```text
π_{Produto.Nome, Categoria.Descricao}(σ_{Produto.Preco > 100}((Produto ⋈_{Produto.Categoria_idCategoria = Categoria.idCategoria} Categoria)))
```

A árvore (`Query`) retornada pelo parser é a estrutura que as próximas histórias de usuário
devem reaproveitar (HU2 a converte em álgebra relacional, HU3 a usa para montar o grafo de
operadores, etc.) — não é necessário reprocessar a string SQL original.

### Modelo relacional de referência

As tabelas e colunas aceitas pelo validador (Imagem 01 do enunciado) estão em
`processador_consultas/metadata.py`: `Categoria`, `Produto`, `TipoCliente`, `Cliente`,
`TipoEndereco`, `Endereco`, `Telefone`, `Status`, `Pedido`, `Pedido_has_Produto`.

## HU3 — Construção do Grafo de Operadores

> Como aluno, quero que o sistema construa um grafo de operadores, para visualizar a
> estratégia de execução da consulta.

Implementada em `processador_consultas/operator_graph.py`, pela função
`build_operator_graph(query)`, que utiliza a AST retornada pelo parser.

- A interface exibe a árvore original na aba **Sem otimização**.
- As folhas representam as tabelas; os nós intermediários representam seleções (`σ`),
  junções (`⋈`), produtos cartesianos (`×`) e projeções (`π`).
- As ligações entre pais e filhos representam o fluxo dos resultados intermediários:
  os filhos fornecem os dados consumidos pelo operador pai.
- A raiz representa a projeção final quando o `SELECT` lista colunas. Para `SELECT *`,
  essa projeção é omitida, pois todas as colunas são mantidas.
- A árvore respeita as dependências lógicas da consulta: tabelas alimentam as junções
  ou produtos cartesianos, seguidos pelo filtro do `WHERE` e pela projeção final.
  `JOIN` tem precedência sobre as vírgulas no `FROM`.

## HU4 — Otimização da Consulta Raiz

> Como aluno, quero que a álgebra relacional seja otimizada conforme heurísticas,
> para reduzir o custo de execução.

Implementada em `processador_consultas/optimizer.py`. A função `optimize(node)` aplica
as heurísticas sobre o grafo de operadores, preservando a árvore original. A interface
exibe o resultado na aba **Com otimização**, permitindo comparar as duas estratégias.

As heurísticas implementadas são:

- **Antecipação de seleções** (`optimize_selection_pushdown`): divide condições ligadas
  por `AND` e move os filtros para os ramos das tabelas correspondentes, reduzindo as
  tuplas antes das junções. Condições que dependem de ambos os ramos permanecem acima.
- **Antecipação de projeções** (`optimize_projection_pushdown`): mantém perto das tabelas
  apenas os atributos necessários à saída, aos filtros e às condições de junção.
- **Operações mais restritivas primeiro** (`optimize_restrictive_first`): ordena seleções
  pela seletividade estimada e reordena blocos de junções internas para priorizar os
  menores resultados intermediários.
- **Eliminação de produtos cartesianos evitáveis** (`avoid_cartesian_product`): transforma
  uma seleção com comparação entre colunas dos dois ramos de um produto cartesiano em
  uma junção com a mesma condição. Produtos sem condição de ligação são preservados.

A ordem das etapas em `optimize` considera as dependências entre as regras:

1. Antecipar as seleções.
2. Ordenar e separar os predicados das seleções.
3. Converter produtos cartesianos elegíveis em junções.
4. Reordenar as operações, incluindo as junções recém-criadas.
5. Antecipar as projeções, preservando os atributos exigidos pelos demais operadores.

As estimativas usam `TABLE_CARDINALITIES` (linhas por tabela), `COLUMN_DISTINCT_VALUES`
(valores distintos por coluna) e `PREDICATE_SELECTIVITIES` (seletividades padrão), em
`metadata.py`. São estatísticas ilustrativas e editáveis, sem coleta em um banco real.
A interface mostra as cardinalidades e os valores distintos na árvore **Metadados**.
O cálculo assume distribuição uniforme e independência entre predicados; a escolha das
junções é gulosa e não garante o plano global de menor custo.

Os testes em `tests/test_operator_graph.py` e `tests/test_optimizer.py` cobrem a construção
dos grafos, as transformações, a preservação da árvore original e o fluxo de otimização.

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
│   ├── relational_algebra.py      # conversão da AST para álgebra relacional (HU2)
│   ├── operator_graph.py          # construção do grafo de operadores (HU3)
│   ├── optimizer.py               # heurísticas de otimização do grafo (HU4)
│   ├── execution_plan.py          # plano lógico ordenado (HU5)
│   └── gui.py                     # interface gráfica (Tkinter) das HU1 a HU5
└── tests/
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_semantic.py
    ├── test_relational_algebra.py
    ├── test_operator_graph.py
    └── test_optimizer.py
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
- A HU2 (Conversão para Álgebra Relacional) consome o objeto `Query` retornado pelo parser
  (campos `columns`, `from_table`, `joins`, `where`).
- Siga o padrão de módulos já estabelecido: um módulo por responsabilidade dentro de
  `processador_consultas/`, com testes correspondentes em `tests/`.
