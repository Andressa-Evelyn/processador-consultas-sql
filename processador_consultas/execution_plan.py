"""Geração de um plano de execução didático a partir do grafo otimizado."""
from dataclasses import dataclass

from .operator_graph import OperatorKind, OperatorNode


@dataclass(frozen=True)
class ExecutionStep:
    number: int
    operation: str
    heuristic: str
    rationale: str


def build_execution_plan(root: OperatorNode) -> list[ExecutionStep]:
    """Retorna operações em pós-ordem: filhos primeiro, operador consumidor depois.

    A ordem respeita as dependências expressas pelo grafo otimizado. Esta aplicação
    apresenta um plano lógico, não um plano físico de um SGBD real.
    """
    ordered: list[OperatorNode] = []

    def visit(node: OperatorNode) -> None:
        for child in node.children:
            visit(child)
        ordered.append(node)

    visit(root)
    steps = []
    for index, node in enumerate(ordered, start=1):
        if node.kind == OperatorKind.TABLE:
            operation = f"Ler tabela {node.data}"
            heuristic = "Acesso às relações de origem"
            rationale = "Disponibiliza a relação de entrada para os operadores seguintes."
        elif node.kind == OperatorKind.SELECTION:
            operation = f"Aplicar seleção σ ({node.data})"
            heuristic = "Antecipação de seleções, quando possível"
            rationale = "Filtra tuplas que não satisfazem o predicado antes de entregar o resultado ao operador pai."
        elif node.kind == OperatorKind.PROJECTION:
            columns = ", ".join(map(str, node.data))
            operation = f"Aplicar projeção π ({columns})"
            heuristic = "Empurrar projeções / eliminar colunas desnecessárias"
            rationale = "Mantém as colunas requeridas pela consulta, reduzindo o volume de dados intermediários."
        elif node.kind == OperatorKind.JOIN:
            operation = f"Executar junção ⋈ ({node.data})"
            heuristic = "Substituição de produto cartesiano por junção e ordenação de junções"
            rationale = "Combina as relações usando a condição indicada; a posição no grafo otimizado define quando ela ocorre."
        elif node.kind == OperatorKind.CROSS_PRODUCT:
            operation = "Executar produto cartesiano ×"
            heuristic = "Produto cartesiano residual"
            rationale = "Combina cada tupla de uma entrada com cada tupla da outra; tende a ser caro e deve ser evitado quando há predicado de junção aplicável."
        else:
            operation = node.label
            heuristic = "Nenhuma heurística identificada"
            rationale = "Operação representada no grafo otimizado."
        steps.append(ExecutionStep(index, operation, heuristic, rationale))
    return steps
