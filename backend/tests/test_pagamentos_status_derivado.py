"""O `status` legado é FUNÇÃO das três dimensões — nunca o contrário.

Este é o teste que segura a premissa nº 1 da spec: manter a coluna legada
derivada durante F1–F4 é seguro. Se ele ficar vermelho, a resposta não é
remendar o mapa: é acelerar a F5 e apagar a coluna.
"""
import pytest
from sqlalchemy import select

from app.models import Debito
from app.services import pagamentos_estados as est
from app.services import pagamentos_debitos as svc


def test_sincronizar_status_legado_e_pura_derivacao():
    d = Debito(situacao_tramitacao="AUTORIZADA", situacao_fila="ELEGIVEL",
               situacao_pagamento="NAO_INICIADA", status="LIXO")
    svc._sincronizar_status_legado(d)
    assert d.status == "AUTORIZADO"

    d.situacao_pagamento = "PAGA"
    d.situacao_fila = "CONCLUIDA"
    svc._sincronizar_status_legado(d)
    assert d.status == "PAGO"


def test_toda_transicao_do_novo_fluxo_produz_status_legado_valido():
    """Percorre o grafo inteiro e confere o legado em cada nó alcançável."""
    from app.schemas.pagamentos import StatusDebito
    validos = set(StatusDebito.__args__)
    for origem, destinos in est.TRANSICOES_TRAMITACAO.items():
        for destino in destinos:
            d = Debito(situacao_tramitacao=destino, situacao_fila="NAO_REGISTRADA",
                       situacao_pagamento="NAO_INICIADA", status="")
            svc._sincronizar_status_legado(d)
            assert d.status in validos, f"{origem} -> {destino} deu '{d.status}'"
