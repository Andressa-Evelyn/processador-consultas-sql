"""Processador de Consultas SQL — pacote principal.

HU1 (Entrada e Validação da Consulta) está implementada nos módulos:
    lexer.py     - tokenização da string SQL
    parser.py    - análise sintática (gramática) e construção da AST
    semantic.py  - validação de tabelas/colunas contra metadata.py
    metadata.py  - modelo relacional de referência (Imagem 01 do enunciado)
    gui.py       - interface gráfica (campo de texto + botão "Analisar")

O resultado do parsing (processador_consultas.parser.Query) é a estrutura
que as próximas histórias de usuário devem consumir, em vez de reprocessar
a string SQL original.
"""
