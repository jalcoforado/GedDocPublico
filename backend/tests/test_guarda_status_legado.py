"""Guarda de Status Legado — Debito.status é sempre derivado, nunca escrito direto."""

import ast
import inspect


def _find_parent_function(tree, target_node):
    """Encontra a função parent de um nó AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target_node:
                    return node
    return None


def test_debito_status_nao_escrito_direto():
    """
    Verifica que nenhum código em pagamentos_debitos escreve
    Debito.status direto. A única escrita legítima é via
    _sincronizar_status_legado().
    """
    from app.services import pagamentos_debitos as svc

    source = inspect.getsource(svc)
    tree = ast.parse(source)

    # Única função permitida escrever em .status
    permitidos = {"_sincronizar_status_legado"}

    # Procure por d.status = ... ou debito.status = ...
    erros = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                # Atribuição a atributo: obj.attr = ...
                if isinstance(target, ast.Attribute) and target.attr == "status":
                    # Encontrou escrita em .status
                    parent_func = _find_parent_function(tree, node)
                    if not parent_func:
                        erros.append(
                            f"Linha {node.lineno}: escrita a .status fora de função "
                            f"(inválido em contexto global)"
                        )
                    elif parent_func.name not in permitidos:
                        erros.append(
                            f"Linha {node.lineno} em {parent_func.name}(): "
                            f"escrita direta a .status (deve usar _sincronizar_status_legado())"
                        )

    assert not erros, (
        "Guarda de status legado violada — Debito.status deve ser derivado, "
        "nunca escrito direto. Erros:\n" + "\n".join(erros)
    )


def test_sincronizar_status_legado_existe():
    """Valida que _sincronizar_status_legado existe e é chamável."""
    from app.services.pagamentos_debitos import _sincronizar_status_legado
    assert callable(_sincronizar_status_legado)
