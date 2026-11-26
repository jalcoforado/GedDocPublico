"""Notificações do rito de pagamentos.

O rito inteiro (unidade → gestor → validação → autoridade → tesouraria) andava
em silêncio: quem tinha de decidir só descobria abrindo a própria fila, e o
solicitante só sabia do desfecho indo olhar. Aqui cada mudança de etapa avisa
quem passa a ter a vez, e o solicitante quando a solicitação volta ou anda.

Três decisões que valem ler antes de mexer:

1. **Só `in_app`.** O sino do sistema, sem e-mail nem WhatsApp. O padrão de
   preferência do e-mail é LIGADO (`notificacoes.DEFAULT_PREFS`): pedir o canal
   aqui faria cada passo do rito disparar e-mail para todo o grupo da etapa.
   Ligar e-mail é decisão de produto, não efeito colateral desta fatia.

2. **Quem recebe "chegou para você" é quem tem a transação da etapa concedida
   a um grupo NÃO super-usuário.** Super-usuário passa por toda permissão, e
   avisá-lo de cada etapa de cada solicitação seria ruído, não aviso. Enquanto
   o município só tiver grupos super-usuário, ninguém recebe esses avisos — o
   solicitante continua recebendo os dele, que não dependem de grupo.

3. **Nunca desfaz o ato.** `notificacoes.enviar` comita por conta própria, então
   isto roda DEPOIS do commit do ato, e qualquer falha vira log
   (`apos_transicao` engole a exceção). Notificação é cortesia; a decisão já
   está gravada.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import (
    Debito, Grupo, GrupoTransacao, Nivel, Sistema, Transacao, Usuario, UsuarioGrupo,
)
from . import notificacoes
from . import pagamentos_estados as est
from .notificacoes import Destinatario

logger = logging.getLogger(__name__)

# Tipos de notificação (= eventos de preferência, `notificacoes.EVENTOS_NOTIFICACAO`).
PENDENTE = "pagamento_pendente"      # chegou para a pessoa decidir
DEVOLVIDO = "pagamento_devolvido"    # voltou para o solicitante (ajuste ou encerramento)
ANDAMENTO = "pagamento_andamento"    # o solicitante é informado de que andou

CANAIS = ("in_app",)

# Etapa que passa a ter a vez → transação de quem decide nela, e como dizer.
_VEZ_DE: dict[str, tuple[str, str]] = {
    est.AGUARDANDO_GESTOR: ("pagamento_gerir", "aguarda a sua decisão como gestor da pasta"),
    est.AGUARDANDO_VALIDACAO: ("pagamento_validar", "aguarda a sua validação financeira"),
    est.AGUARDANDO_AUTORIDADE: ("pagamento_autorizar", "aguarda a sua autorização"),
}

# Etapa em que a solicitação volta para o solicitante → (título, frase).
_VOLTOU: dict[str, tuple[str, str]] = {
    est.AJUSTE_GESTOR: ("Ajuste pedido pelo gestor", "foi devolvida pelo gestor para ajuste"),
    est.AJUSTE_VALIDACAO: (
        "Ajuste pedido pela validação", "foi devolvida pela validação financeira para ajuste"),
    est.AJUSTE_AUTORIDADE: (
        "Ajuste pedido pela autoridade", "foi devolvida pela autoridade para ajuste"),
    est.REJEITADA_GESTOR: ("Solicitação rejeitada", "foi rejeitada pelo gestor da pasta"),
    est.INDEFERIDA_AUTORIDADE: (
        "Solicitação indeferida", "foi indeferida pela autoridade competente"),
}


async def usuarios_com_transacao(db: AsyncSession, *, tenant_id: int, codigo: str) -> set[int]:
    """Usuários ativos do tenant que têm `codigo` concedido por um grupo NÃO
    super-usuário (ver decisão 2 no topo). Vínculo global ou por lotação conta
    igual: o aviso é "pode ser com você", não uma checagem de acesso."""
    app = get_settings().app_name
    rows = (await db.execute(
        select(UsuarioGrupo.id_usuario).distinct()
        .join(Grupo, Grupo.id == UsuarioGrupo.id_grupo)
        .join(Nivel, Nivel.id == Grupo.id_nivel)
        .join(Sistema, Sistema.id == Grupo.id_sistema)
        .join(GrupoTransacao, GrupoTransacao.id_grupo == Grupo.id)
        .join(Transacao, Transacao.id == GrupoTransacao.id_transacao)
        .join(Usuario, Usuario.id == UsuarioGrupo.id_usuario)
        .where(
            UsuarioGrupo.tenant_id == tenant_id, UsuarioGrupo.excluido.is_(False),
            UsuarioGrupo.ativo.is_(True),
            Grupo.tenant_id == tenant_id, Grupo.excluido.is_(False),
            Nivel.valor != 0,
            Sistema.excluido.is_(False), Sistema.app == app,
            GrupoTransacao.tenant_id == tenant_id, GrupoTransacao.excluido.is_(False),
            Transacao.excluido.is_(False), Transacao.codigo == codigo,
            Usuario.tenant_id == tenant_id, Usuario.excluido.is_(False),
            Usuario.ativo.is_(True),
        ))).scalars().all()
    return set(rows)


async def _enviar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuarios: set[int],
                  tipo: str, titulo: str, mensagem: str) -> int:
    if not usuarios:
        return 0
    criadas = await notificacoes.enviar(
        db, tenant_id=tenant_id,
        destinatarios=[Destinatario(id_usuario=u) for u in sorted(usuarios)],
        canais=CANAIS, tipo=tipo, titulo=titulo, mensagem=mensagem,
        link_url=f"/m/pagamentos/solicitacoes/{debito_id}",
        payload={"id_debito": debito_id},
    )
    return len(criadas)


async def notificar_transicao(db: AsyncSession, *, tenant_id: int, debito: Debito,
                              ator_id: int | None, nome_fornecedor: str | None = None) -> int:
    """Avisa quem deve saber do estado em que o débito ACABOU de entrar.

    Lê só `debito.situacao_tramitacao` — o chamador é quem garante que houve
    transição. Quem praticou o ato (`ator_id`) nunca é avisado dele mesmo.
    Devolve quantas notificações criou.
    """
    # Lido antes de qualquer commit: `enviar` comita, e atributo expirado numa
    # sessão assíncrona não recarrega sozinho.
    debito_id, tramitacao = debito.id, debito.situacao_tramitacao
    solicitante = debito.id_usuario_solicitante
    de_quem = f" — {nome_fornecedor}" if nome_fornecedor else ""
    ref = f"A solicitação de pagamento #{debito_id}{de_quem}"

    if tramitacao in _VEZ_DE:
        codigo, frase = _VEZ_DE[tramitacao]
        quem = await usuarios_com_transacao(db, tenant_id=tenant_id, codigo=codigo)
        # Segregação de funções: o solicitante não decide a própria solicitação.
        quem -= {ator_id, solicitante}
        return await _enviar(
            db, tenant_id=tenant_id, debito_id=debito_id, usuarios=quem, tipo=PENDENTE,
            titulo="Solicitação de pagamento na sua fila", mensagem=f"{ref} {frase}.")

    if tramitacao in _VOLTOU:
        titulo, frase = _VOLTOU[tramitacao]
        return await _enviar(
            db, tenant_id=tenant_id, debito_id=debito_id, usuarios={solicitante} - {ator_id},
            tipo=DEVOLVIDO, titulo=titulo, mensagem=f"{ref} {frase}.")

    if tramitacao == est.AUTORIZADA:
        return await _enviar(
            db, tenant_id=tenant_id, debito_id=debito_id, usuarios={solicitante} - {ator_id},
            tipo=ANDAMENTO, titulo="Pagamento autorizado",
            mensagem=f"{ref} foi autorizada e segue para a tesouraria.")

    return 0


async def notificar_pagamento(db: AsyncSession, *, tenant_id: int, debito: Debito,
                              ator_id: int | None) -> int:
    """Avisa o solicitante quando a solicitação termina de ser paga."""
    if debito.situacao_pagamento != est.PAGA:
        return 0
    debito_id, solicitante = debito.id, debito.id_usuario_solicitante
    return await _enviar(
        db, tenant_id=tenant_id, debito_id=debito_id, usuarios={solicitante} - {ator_id},
        tipo=ANDAMENTO, titulo="Pagamento realizado",
        mensagem=f"A solicitação de pagamento #{debito_id} foi paga.")


async def notificar_liberacao(db: AsyncSession, *, tenant_id: int, qtd_parcelas: int,
                              ator_id: int | None) -> int:
    """Avisa a tesouraria de que há parcelas liberadas para pagar.

    UM aviso por liberação, não um por parcela: a autoridade libera em lote, e
    vinte avisos iguais ensinariam a tesouraria a ignorar o sino. O link vai
    para a Central da tesouraria, que é onde a fila está.
    """
    if qtd_parcelas <= 0:
        return 0
    quem = await usuarios_com_transacao(db, tenant_id=tenant_id, codigo="pagamento_pagar")
    quem -= {ator_id}
    if not quem:
        return 0
    quantas = "1 parcela foi liberada" if qtd_parcelas == 1 else (
        f"{qtd_parcelas} parcelas foram liberadas")
    criadas = await notificacoes.enviar(
        db, tenant_id=tenant_id,
        destinatarios=[Destinatario(id_usuario=u) for u in sorted(quem)],
        canais=CANAIS, tipo=PENDENTE, titulo="Parcelas liberadas para pagamento",
        mensagem=f"{quantas} para pagamento e aguarda a tesouraria.",
        link_url="/m/pagamentos/tesouraria",
        payload={"qtd_parcelas": qtd_parcelas},
    )
    return len(criadas)


async def apos_liberacao(db: AsyncSession, *, tenant_id: int, qtd_parcelas: int,
                         ator_id: int | None) -> None:
    try:
        await notificar_liberacao(db, tenant_id=tenant_id, qtd_parcelas=qtd_parcelas,
                                  ator_id=ator_id)
    except Exception:  # noqa: BLE001
        logger.exception("pagamento_notificacao_falhou", extra={"tenant_id": tenant_id})
        await db.rollback()


async def apos_transicao(db: AsyncSession, *, tenant_id: int, debito: Debito,
                         ator_id: int | None, nome_fornecedor: str | None = None) -> None:
    """`notificar_transicao` para ser chamada pelo router DEPOIS do ato: nunca
    levanta. Falha de notificação não pode virar 500 de um ato já gravado."""
    try:
        await notificar_transicao(db, tenant_id=tenant_id, debito=debito, ator_id=ator_id,
                                  nome_fornecedor=nome_fornecedor)
    except Exception:  # noqa: BLE001
        logger.exception("pagamento_notificacao_falhou",
                         extra={"tenant_id": tenant_id, "id_debito": getattr(debito, "id", None)})
        await db.rollback()


async def apos_pagamento(db: AsyncSession, *, tenant_id: int, debito: Debito,
                         ator_id: int | None) -> None:
    try:
        await notificar_pagamento(db, tenant_id=tenant_id, debito=debito, ator_id=ator_id)
    except Exception:  # noqa: BLE001
        logger.exception("pagamento_notificacao_falhou",
                         extra={"tenant_id": tenant_id, "id_debito": getattr(debito, "id", None)})
        await db.rollback()
