"""Guardas estruturais da regra central da F1 de pagamentos.

A validação financeira é uma conferência vinculada: valida ou solicita
ajuste. Ela nunca encerra a solicitação.
"""
from app.main import app
from app.services import pagamentos_debitos as svc


def test_servico_nao_expoe_decisoes_genericas_do_rito_antigo():
    assert not hasattr(svc, "rejeitar")
    assert not hasattr(svc, "devolver")
    assert not hasattr(svc, "encaminhar")
    assert not hasattr(svc, "suspender")
    assert not hasattr(svc, "reativar")


def test_rotas_antigas_nao_executam_regra_de_negocio():
    por_caminho = {
        route.path: route
        for route in app.routes
        if hasattr(route, "path")
    }
    for sufixo in ("devolver", "rejeitar", "suspender", "reativar", "encaminhar"):
        rota = por_caminho[f"/api/v2/pagamentos/debitos/{{debito_id}}/{sufixo}"]
        assert 410 in rota.responses or rota.status_code == 410


def test_validacao_so_tem_validar_e_solicitar_ajuste():
    caminhos = {
        route.path
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith("/api/v2/pagamentos/debitos/")
    }
    assert "/api/v2/pagamentos/debitos/{debito_id}/validar" in caminhos
    assert "/api/v2/pagamentos/debitos/{debito_id}/solicitar-ajuste" in caminhos
    assert "/api/v2/pagamentos/debitos/{debito_id}/validacao-rejeitar" not in caminhos
