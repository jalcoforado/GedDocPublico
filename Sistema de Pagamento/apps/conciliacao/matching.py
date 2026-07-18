"""
Motor de correspondência (RF40/RF41) entre lançamentos de extrato e pedidos
autorizados. A baixa automática só ocorre para correspondência exata —
mesmo valor, credor identificável no histórico e data dentro de uma janela
razoável — nunca por aproximação de valores (regra de negócio explícita
do módulo M7).
"""

JANELA_DIAS = 10


def encontrar_correspondencia_exata(lancamento, candidatos):
    for pedido in candidatos:
        if pedido.valor != lancamento.valor:
            continue
        primeiro_nome_credor = (pedido.credor.nome or '').split()[0].upper() if pedido.credor.nome else ''
        if primeiro_nome_credor and primeiro_nome_credor not in lancamento.historico.upper():
            continue
        referencia = pedido.vencimento
        if abs((lancamento.data - referencia).days) > JANELA_DIAS:
            continue
        return pedido
    return None
