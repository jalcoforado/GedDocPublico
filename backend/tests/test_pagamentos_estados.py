"""Domínio das três dimensões de situação do débito (spec §4.1).

Testes puros — não tocam banco. O que eles travam é a propriedade que a F1
inteira depende: as três dimensões são independentes, e o `status` legado é
função delas, não o contrário.
"""
from app.services import pagamentos_estados as est


def test_as_tres_dimensoes_nao_compartilham_valor():
    """Valor repetido entre dimensões faria o status legado ficar ambíguo."""
    assert not (est.TRAMITACAO & est.FILA)
    assert not (est.FILA & est.PAGAMENTO)
    # TRAMITACAO e PAGAMENTO compartilham 'CANCELADA' de propósito: cancelar a
    # solicitação cancela a execução. É o único par permitido.
    assert (est.TRAMITACAO & est.PAGAMENTO) == {"CANCELADA"}


def test_toda_tramitacao_tem_etapa_no_stepper():
    assert set(est.ETAPA_POR_TRAMITACAO) == est.TRAMITACAO


def test_terminais_nao_tem_saida():
    for t in est.TERMINAIS:
        assert est.TRANSICOES_TRAMITACAO[t] == frozenset()


def test_validacao_nao_alcanca_nenhum_terminal():
    """A regra central da fatia (spec §3.1): a validação financeira não encerra."""
    saidas = est.TRANSICOES_TRAMITACAO["AGUARDANDO_VALIDACAO"]
    assert saidas & est.TERMINAIS == frozenset()
    assert saidas == frozenset({"AGUARDANDO_AUTORIDADE", "AJUSTE_VALIDACAO"})


def test_gestor_alcanca_rejeicao_e_autoridade_alcanca_indeferimento():
    assert "REJEITADA_GESTOR" in est.TRANSICOES_TRAMITACAO["AGUARDANDO_GESTOR"]
    assert "INDEFERIDA_AUTORIDADE" in est.TRANSICOES_TRAMITACAO["AGUARDANDO_AUTORIDADE"]


def test_status_legado_cobre_toda_combinacao_alcancavel():
    """Nenhuma combinação atingível pode cair no fallback silencioso."""
    for tram in est.TRAMITACAO:
        for fila in est.FILA:
            for pag in est.PAGAMENTO:
                assert status_valido(est.status_legado(tram, fila, pag))


def status_valido(s: str) -> bool:
    return s in {
        "RASCUNHO", "EM_VALIDACAO", "DEVOLVIDO", "VALIDADO", "ENVIADO_SECRETARIO",
        "AGUARDANDO_AUTORIZACAO", "AUTORIZADO", "ENVIADO_TESOURARIA",
        "EM_PROCESSAMENTO", "PAGO_PARCIAL", "PAGO", "CONCILIADO", "REJEITADO",
        "SUSPENSO", "CANCELADO", "ESTORNADO",
    }


def test_status_legado_prioriza_execucao_sobre_tramitacao():
    """Autorizada e paga → PAGO. A execução, quando começou, manda no legado."""
    assert est.status_legado("AUTORIZADA", "CONCLUIDA", "PAGA") == "PAGO"
    assert est.status_legado("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL") == "PAGO_PARCIAL"
    assert est.status_legado("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA") == "AUTORIZADO"


def test_status_legado_das_etapas_pre_autorizacao():
    assert est.status_legado("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA") == "RASCUNHO"
    assert est.status_legado("AGUARDANDO_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "EM_VALIDACAO"
    assert est.status_legado("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA") == "EM_VALIDACAO"
    assert est.status_legado("AJUSTE_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "DEVOLVIDO"
    assert est.status_legado("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA") == "ENVIADO_SECRETARIO"
    assert est.status_legado("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "REJEITADO"
    assert est.status_legado("INDEFERIDA_AUTORIDADE", "NAO_REGISTRADA", "NAO_INICIADA") == "REJEITADO"
    assert est.status_legado("CANCELADA", "RETIRADA", "CANCELADA") == "CANCELADO"


def test_transicao_permitida():
    assert est.transicao_permitida("RASCUNHO", "AGUARDANDO_GESTOR")
    assert not est.transicao_permitida("RASCUNHO", "AGUARDANDO_AUTORIDADE")
    assert not est.transicao_permitida("AGUARDANDO_VALIDACAO", "REJEITADA_GESTOR")
