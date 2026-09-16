"""Cálculo de permanência: espera, análise e o agregado do processo.

Sem banco e sem app — `services/permanencia.py` é função pura sobre instantes,
e é justamente por isso que estes testes conseguem enumerar os casos de borda
que um teste de rota nunca alcançaria (relógio fora de ordem, empate de
carimbo, processo arquivado e parado).

O que NÃO está aqui: a costura router↔service. Ela tem teste próprio em
`test_processos_permanencia_http.py`, porque é onde o `Depends` some e onde os
defeitos desta casa historicamente moram.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.permanencia import No, calcular

BASE = datetime(2026, 3, 2, 9, 0, 0)


def _no(id_: int, minutos: int, status: str) -> No:
    return No(id=id_, momento=BASE + timedelta(minutes=minutos), status_movimentacao=status)


def test_espera_e_analise_saem_dos_nos_vizinhos():
    """O coração da fatia: o que separa fila de trabalho é a ação do nó.

    Abertura às 9h, encaminhado às 9h30, recebido às 11h, encaminhado de novo
    às 11h15. Logo: 30 min com quem abriu (análise), 90 min na fila do
    destino (espera), 15 min com quem recebeu (análise).
    """
    nos = [
        _no(1, 0, "inicial"),
        _no(2, 30, "encaminhado"),
        _no(3, 120, "recebido"),
        _no(4, 135, "encaminhado"),
    ]
    por_id, resumo = calcular(nos, agora=BASE + timedelta(minutes=135))

    assert por_id[1].natureza == "analise"
    assert por_id[1].segundos == 30 * 60
    assert por_id[2].natureza == "espera"
    assert por_id[2].segundos == 90 * 60
    assert por_id[3].natureza == "analise"
    assert por_id[3].segundos == 15 * 60

    assert resumo.espera_segundos == 90 * 60
    assert resumo.analise_segundos == (30 + 15) * 60
    assert resumo.total_ativo_segundos == 135 * 60
    assert resumo.tramitacoes == 2


def test_no_aberto_conta_ate_agora():
    """Sem nó posterior, o tempo do último nó ainda está correndo."""
    nos = [_no(1, 0, "inicial"), _no(2, 10, "encaminhado")]
    agora = BASE + timedelta(minutes=70)

    por_id, resumo = calcular(nos, agora=agora)

    assert por_id[2].aberto is True
    assert por_id[2].segundos == 60 * 60
    assert por_id[1].aberto is False
    assert resumo.em_curso is True


def test_processo_com_uma_so_movimentacao():
    """Abertura e mais nada: um nó aberto, nenhuma tramitação."""
    por_id, resumo = calcular(
        [_no(1, 0, "inicial")], agora=BASE + timedelta(minutes=45)
    )

    assert por_id[1].segundos == 45 * 60
    assert por_id[1].aberto is True
    assert resumo.tramitacoes == 0
    assert resumo.espera_segundos == 0
    assert resumo.analise_segundos == 45 * 60
    assert resumo.em_curso is True


def test_relogio_fora_de_ordem_nao_vira_permanencia_negativa():
    """Carimbo posterior ANTES do anterior não pode virar número negativo.

    Não é hipótese: `acoes_processo` grava com `datetime.now()` e
    `workflow_engine` grava a mesma coluna com `datetime.utcnow()`. Hoje
    coincidem porque o container roda em UTC; definir `TZ` faz divergirem em
    3 h. Processo migrado e seed produzem o mesmo efeito por outros caminhos.

    A ordenação interna já resolve a maior parte — por isso o caso que importa
    é o do ÚLTIMO nó contra `agora`, onde não há vizinho para reordenar.
    """
    nos = [_no(1, 0, "inicial"), _no(2, 180, "encaminhado")]

    # `agora` atrás do último carimbo: 3 h de fuso, exatamente o cenário do TZ.
    por_id, _ = calcular(nos, agora=BASE)

    assert por_id[2].segundos == 0
    assert por_id[2].segundos >= 0


def test_ordem_de_entrada_nao_importa():
    """A timeline do detalhe vem em ordem DECRESCENTE; o resultado é o mesmo.

    Parear por índice em vez de por id seria um defeito silencioso: os números
    apareceriam trocados entre as linhas, todos plausíveis, nenhum correto.
    """
    nos = [_no(1, 0, "inicial"), _no(2, 30, "encaminhado"), _no(3, 90, "recebido")]
    agora = BASE + timedelta(minutes=90)

    crescente, resumo_c = calcular(nos, agora=agora)
    decrescente, resumo_d = calcular(list(reversed(nos)), agora=agora)

    assert crescente == decrescente
    assert resumo_c == resumo_d


def test_empate_de_carimbo_tem_ordem_estavel():
    """Receber grava o MESMO instante em duas linhas (movimentação e enc.).

    Com carimbos iguais o desempate é o id, que é crescente por inserção. Sem
    isso a ordenação seria arbitrária e a permanência saltaria entre execuções
    sem nada ter mudado no banco.
    """
    nos = [_no(1, 0, "encaminhado"), _no(2, 0, "recebido")]
    por_id, resumo = calcular(nos, agora=BASE + timedelta(minutes=20))

    assert por_id[1].segundos == 0
    assert por_id[1].natureza == "espera"
    assert por_id[2].segundos == 20 * 60
    assert por_id[2].aberto is True
    assert resumo.espera_segundos == 0


def test_arquivado_e_parado_nao_acumula_tempo():
    """Depois do arquivamento o relógio anda, mas ninguém está segurando nada.

    Somar esse trecho faria um processo arquivado há dois anos parecer o mais
    lento da casa — e a lista "mais demorados" viraria a lista "mais antigos".
    """
    nos = [_no(1, 0, "inicial"), _no(2, 60, "final")]
    # Um ano depois do arquivamento.
    por_id, resumo = calcular(nos, agora=BASE + timedelta(days=365))

    assert por_id[2].segundos == 0
    assert resumo.total_ativo_segundos == 60 * 60
    assert resumo.em_curso is False


def test_arquivamento_seguido_de_movimentacao_conta_o_intervalo():
    """Arquivado e depois movimentado de novo: o intervalo é real e fica.

    Diferente do caso acima — ali o tempo não acabou, aqui acabou. Mas ele não
    entra em espera nem em análise: não era fila de ninguém nem trabalho de
    ninguém, e por isso `total_ativo` o exclui.
    """
    nos = [
        _no(1, 0, "inicial"),
        _no(2, 60, "final"),
        _no(3, 120, "encaminhado"),
    ]
    por_id, resumo = calcular(nos, agora=BASE + timedelta(minutes=150))

    assert por_id[2].natureza == "encerrado"
    assert por_id[2].segundos == 60 * 60
    assert resumo.espera_segundos == 30 * 60
    assert resumo.analise_segundos == 60 * 60
    assert resumo.total_ativo_segundos == 90 * 60  # o trecho arquivado ficou fora
    assert resumo.em_curso is True


def test_status_desconhecido_cai_em_analise():
    """Ação cadastrada depois não pode sumir da soma.

    O catálogo `protocolos.acao` é editável, e uma ação nova traz um
    `status_movimentacao` que este módulo não conhece. O padrão seguro é contar
    como tempo de alguém: some a menos e o total mente para baixo, que é o erro
    mais difícil de perceber.
    """
    nos = [_no(1, 0, "juntada_de_documento"), _no(2, 25, "recebido")]
    _, resumo = calcular(nos, agora=BASE + timedelta(minutes=25))

    assert resumo.analise_segundos == 25 * 60
    assert resumo.total_ativo_segundos == 25 * 60


def test_sem_movimentacao_nenhuma():
    """Lista vazia não estoura e não inventa tempo."""
    por_id, resumo = calcular([], agora=BASE)

    assert por_id == {}
    assert resumo.total_ativo_segundos == 0
    assert resumo.tramitacoes == 0
    assert resumo.em_curso is False
