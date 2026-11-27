"""Pedido de avaliação e decisão por documento (SI-73, RF-04 V2).

Quem tramita o processo pede a um servidor do município que avalie um ou mais
documentos; o avaliador aprova ou devolve CADA um. Regras e motivos em
`docs/avaliacao-de-documentos.md`. Resumo:

- a avaliação aponta para a VERSÃO EXATA do documento (SI-72); a aprovação da
  versão 1 não vale para a 2;
- só o avaliador designado decide (e precisa da transação
  `documento_avaliar`, no router); devolução exige justificativa;
- devolvido é corrigido com versão nova (SI-72) e REENVIADO: item novo no
  mesmo pedido, ligado ao devolvido;
- enquanto aguarda avaliação o documento não recebe versão nova, e documento
  com avaliação registrada não pode ser excluído (`services/anexos.py`);
- avaliar não é assinar: nada aqui toca `assinatura_anexo`.

O sigilo do processo é conferido aqui em TODA operação por id de pedido (o id
do processo não está na URL) e, nas rotas com `processo_id`, no router, antes
de resolver qualquer recurso.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Anexo, AvaliacaoDocumento, AvaliacaoPedido, Processo, Usuario
from ..schemas.avaliacao import (
    AvaliacaoDecisoes,
    AvaliacaoItemOut,
    AvaliacaoPedidoCreate,
    AvaliacaoPedidoOut,
)
from ..schemas.common import Paginated
from .sigilo import SigiloAcessoError, assert_acesso_processo, niveis_permitidos, pode_acessar

log = logging.getLogger(__name__)

TRANSACAO = "documento_avaliar"


class AvaliacaoError(Exception):
    """400 genérico."""


class AvaliacaoNaoEncontrada(AvaliacaoError):
    """404 — inclusive pedido de processo que o usuário não pode ver."""


class AvaliacaoConflito(AvaliacaoError):
    """409 — estado não permite (já decidido, substituído, arquivado…)."""


class AvaliacaoInvalida(AvaliacaoError):
    """422 — dado do pedido inaceitável (avaliador, prazo)."""


class AvaliacaoProibida(AvaliacaoError):
    """403 — vê o pedido, mas não é o avaliador designado."""


# ---------------------------------------------------------------------------
# Situação dos documentos (também para a trava do fluxo, SI-75)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendenciasAvaliacao:
    aguardando: int
    devolvidos_sem_reenvio: int

    @property
    def livre(self) -> bool:
        return self.aguardando == 0 and self.devolvidos_sem_reenvio == 0


async def pendencias_do_processo(
    db: AsyncSession, processo_id: int, *, tenant_id: int
) -> PendenciasAvaliacao:
    """Quantos documentos aguardam decisão e quantos foram devolvidos e ainda
    não reenviados. É a pergunta da condição "exige aprovação documental"."""
    reenvio = AvaliacaoDocumento.__table__.alias("reenvio")
    base = (
        select(func.count())
        .select_from(AvaliacaoDocumento)
        .join(AvaliacaoPedido, AvaliacaoPedido.id == AvaliacaoDocumento.id_pedido)
        .where(
            AvaliacaoPedido.id_processo == processo_id,
            AvaliacaoPedido.tenant_id == tenant_id,
            AvaliacaoPedido.excluido.is_(False),
            AvaliacaoDocumento.tenant_id == tenant_id,
        )
    )
    aguardando = (
        await db.execute(base.where(AvaliacaoDocumento.resultado.is_(None)))
    ).scalar_one()
    devolvidos = (
        await db.execute(
            base.where(
                AvaliacaoDocumento.resultado == "devolvido",
                ~select(reenvio.c.id)
                .where(reenvio.c.id_avaliacao_anterior == AvaliacaoDocumento.id)
                .exists(),
            )
        )
    ).scalar_one()
    return PendenciasAvaliacao(aguardando=aguardando, devolvidos_sem_reenvio=devolvidos)


async def anexo_aguarda_avaliacao(db: AsyncSession, anexo_id: int, *, tenant_id: int) -> bool:
    return (
        await db.execute(
            select(AvaliacaoDocumento.id).where(
                AvaliacaoDocumento.id_anexo == anexo_id,
                AvaliacaoDocumento.tenant_id == tenant_id,
                AvaliacaoDocumento.resultado.is_(None),
            ).limit(1)
        )
    ).first() is not None


async def anexo_tem_avaliacao(db: AsyncSession, anexo_id: int, *, tenant_id: int) -> bool:
    return (
        await db.execute(
            select(AvaliacaoDocumento.id).where(
                AvaliacaoDocumento.id_anexo == anexo_id,
                AvaliacaoDocumento.tenant_id == tenant_id,
            ).limit(1)
        )
    ).first() is not None


# ---------------------------------------------------------------------------
# Pedido
# ---------------------------------------------------------------------------


async def _validar_avaliador(
    db: AsyncSession, id_avaliador: int, processo: Processo, *, tenant_id: int, solicitante_id: int
) -> Usuario:
    """Servidor ATIVO do mesmo município, com a transação e a credencial de
    sigilo do processo. Não precisa ser da unidade do processo (regra do card).
    A FK não confere município: a consulta filtra o tenant."""
    from .permissoes import load_permissions  # lazy: evita ciclo de import

    if id_avaliador == solicitante_id:
        raise AvaliacaoInvalida("Quem pede a avaliação não pode ser o avaliador.")
    avaliador = (
        await db.execute(
            select(Usuario).where(
                Usuario.id == id_avaliador,
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if avaliador is None:
        raise AvaliacaoInvalida("Avaliador não encontrado entre os servidores do município.")
    perms = await load_permissions(db, avaliador.id, tenant_id=tenant_id)
    if TRANSACAO in perms.codigos_bloqueados:
        raise AvaliacaoInvalida("Avaliação de documento indisponível: módulo não contratado.")
    if not perms.is_super_usuario and not any(p.codigo == TRANSACAO for p in perms.items):
        raise AvaliacaoInvalida(
            f"{avaliador.nome} não tem permissão para avaliar documentos."
        )
    if not pode_acessar(
        avaliador.nivel_acesso_sigilo, processo.nivel_sigilo, is_super=perms.is_super_usuario
    ):
        raise AvaliacaoInvalida(
            f"{avaliador.nome} não tem credencial de acesso para o sigilo deste processo."
        )
    return avaliador


async def criar_pedido(
    db: AsyncSession,
    processo_id: int,
    dados: AvaliacaoPedidoCreate,
    *,
    tenant_id: int,
    usuario: Usuario,
) -> AvaliacaoPedidoOut:
    from .anexos import AnexoConflito, AnexoNaoEncontrado, alvo_de_versao  # lazy
    from .audit import log as audit_log

    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise AvaliacaoNaoEncontrada("Processo não encontrado")
    if processo.situacao == "rascunho":
        raise AvaliacaoConflito("Processo em rascunho: protocole-o antes de pedir avaliação.")
    if dados.prazo is not None and dados.prazo < date.today():
        raise AvaliacaoInvalida("O prazo não pode ser uma data passada.")

    avaliador = await _validar_avaliador(
        db, dados.id_avaliador, processo, tenant_id=tenant_id, solicitante_id=usuario.id
    )

    # Documento avaliável = o que pode ser corrigido se for devolvido (vigente,
    # do próprio processo, não herdado nem peça de despacho, processo não
    # arquivado) e que não está aguardando outra avaliação. É exatamente o
    # alvo de versão nova do SI-72 — FOR UPDATE contra pedido simultâneo.
    anexos: list[Anexo] = []
    for anexo_id in dados.id_anexos:
        try:
            anexos.append(
                await alvo_de_versao(db, processo_id, anexo_id, tenant_id=tenant_id, travar=True)
            )
        except AnexoNaoEncontrado:
            raise AvaliacaoNaoEncontrada(f"Documento #{anexo_id} não encontrado neste processo")
        except AnexoConflito as e:
            raise AvaliacaoConflito(f"Documento #{anexo_id}: {e}")

    pedido = AvaliacaoPedido(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_usuario_solicitante=usuario.id,
        id_usuario_avaliador=avaliador.id,
        orientacao=dados.orientacao,
        prazo=dados.prazo,
        situacao="pendente",
        criado_em=datetime.now(),
        excluido=False,
    )
    db.add(pedido)
    await db.flush()
    for a in anexos:
        db.add(AvaliacaoDocumento(tenant_id=tenant_id, id_pedido=pedido.id, id_anexo=a.id))
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="processo.avaliacao_solicitada",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_pedido": pedido.id,
            "id_avaliador": avaliador.id,
            "id_anexos": [a.id for a in anexos],
            "prazo": dados.prazo.isoformat() if dados.prazo else None,
        },
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AvaliacaoConflito("Um dos documentos já aguarda avaliação.")

    # A resposta sai antes do aviso: se a notificação falhar, o rollback dela
    # expira os objetos da sessão, e o pedido já está gravado.
    out = await obter_pedido(db, pedido.id, tenant_id=tenant_id, usuario=usuario)
    prazo = f" Prazo: {dados.prazo.strftime('%d/%m/%Y')}." if dados.prazo else ""
    await _avisar(
        db,
        tenant_id=tenant_id,
        destinatario=avaliador.id,
        tipo="avaliacao_solicitada",
        titulo="Documentos para avaliar",
        mensagem=(
            f"{usuario.nome} pediu a sua avaliação de {len(anexos)} documento(s) do "
            f"processo {out.numero_processo or f'#{processo_id}'}.{prazo}"
        ),
        processo_id=processo_id,
        pedido_id=out.id,
    )
    return out


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


async def _pedido_autorizado(
    db: AsyncSession, pedido_id: int, *, tenant_id: int, usuario: Usuario, travar: bool = False
) -> AvaliacaoPedido:
    """O pedido, se o usuário pode ver o processo dele; senão 404 — a mesma
    resposta para "não existe" e "não pode ver"."""
    stmt = select(AvaliacaoPedido).where(
        AvaliacaoPedido.id == pedido_id,
        AvaliacaoPedido.tenant_id == tenant_id,
        AvaliacaoPedido.excluido.is_(False),
    )
    if travar:
        stmt = stmt.with_for_update()
    pedido = (await db.execute(stmt)).scalar_one_or_none()
    if pedido is None:
        raise AvaliacaoNaoEncontrada("Pedido de avaliação não encontrado")
    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=pedido.id_processo, usuario=usuario
        )
    except SigiloAcessoError:
        raise AvaliacaoNaoEncontrada("Pedido de avaliação não encontrado")
    return pedido


async def obter_pedido(
    db: AsyncSession, pedido_id: int, *, tenant_id: int, usuario: Usuario
) -> AvaliacaoPedidoOut:
    pedido = await _pedido_autorizado(db, pedido_id, tenant_id=tenant_id, usuario=usuario)
    return (await _montar(db, [pedido], tenant_id=tenant_id))[0]


async def listar_do_processo(
    db: AsyncSession, processo_id: int, *, tenant_id: int
) -> list[AvaliacaoPedidoOut]:
    """Todos os pedidos do processo, do mais novo ao mais antigo. O sigilo é
    conferido no router, antes."""
    pedidos = (
        await db.execute(
            select(AvaliacaoPedido)
            .where(
                AvaliacaoPedido.id_processo == processo_id,
                AvaliacaoPedido.tenant_id == tenant_id,
                AvaliacaoPedido.excluido.is_(False),
            )
            .order_by(AvaliacaoPedido.id.desc())
        )
    ).scalars().all()
    return await _montar(db, list(pedidos), tenant_id=tenant_id)


async def listar_meus(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario: Usuario,
    papel: str,
    situacao: str | None,
    page: int,
    page_size: int,
) -> Paginated[AvaliacaoPedidoOut]:
    """Caixas "Para avaliar" (`papel=avaliador`) e "Avaliações solicitadas"
    (`papel=solicitante`). Só pedidos do próprio usuário e de processos que a
    credencial dele alcança hoje (ela pode ter baixado depois do pedido)."""
    from .permissoes import load_permissions

    coluna = (
        AvaliacaoPedido.id_usuario_avaliador
        if papel == "avaliador"
        else AvaliacaoPedido.id_usuario_solicitante
    )
    filtro = [
        coluna == usuario.id,
        AvaliacaoPedido.tenant_id == tenant_id,
        AvaliacaoPedido.excluido.is_(False),
        Processo.tenant_id == tenant_id,
    ]
    if situacao is not None:
        filtro.append(AvaliacaoPedido.situacao == situacao)
    perms = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    if not perms.is_super_usuario:
        filtro.append(Processo.nivel_sigilo.in_(niveis_permitidos(usuario.nivel_acesso_sigilo)))

    base = select(AvaliacaoPedido).join(Processo, Processo.id == AvaliacaoPedido.id_processo)
    total = (
        await db.execute(select(func.count()).select_from(base.where(*filtro).subquery()))
    ).scalar_one()
    # Pendente primeiro, prazo mais próximo primeiro; depois o mais novo.
    pedidos = (
        await db.execute(
            base.where(*filtro)
            .order_by(
                (AvaliacaoPedido.situacao != "pendente"),
                AvaliacaoPedido.prazo.asc().nulls_last(),
                AvaliacaoPedido.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return Paginated[AvaliacaoPedidoOut](
        items=await _montar(db, list(pedidos), tenant_id=tenant_id),
        total=total,
        page=page,
        page_size=page_size,
    )


async def _vigente_de(db: AsyncSession, anexo_id: int, *, tenant_id: int) -> int:
    """A versão vigente da cadeia que começa em `anexo_id` (ele mesmo, se não
    foi substituído)."""
    from .anexos import sucessora_de

    atual = anexo_id
    for _ in range(100):  # cadeia de versões é curta; o teto evita laço em dado ruim
        prox = await sucessora_de(db, atual, tenant_id=tenant_id)
        if prox is None:
            return atual
        atual = prox
    return atual


async def _montar(
    db: AsyncSession, pedidos: list[AvaliacaoPedido], *, tenant_id: int
) -> list[AvaliacaoPedidoOut]:
    if not pedidos:
        return []
    ids = [p.id for p in pedidos]
    itens = (
        await db.execute(
            select(AvaliacaoDocumento, Anexo.descricao, Anexo.versao)
            .join(Anexo, Anexo.id == AvaliacaoDocumento.id_anexo)
            .where(
                AvaliacaoDocumento.id_pedido.in_(ids),
                AvaliacaoDocumento.tenant_id == tenant_id,
            )
            .order_by(AvaliacaoDocumento.id)
        )
    ).all()
    reenvio_de = {
        i.id_avaliacao_anterior: i.id for i, _, _ in itens if i.id_avaliacao_anterior is not None
    }
    uids = {p.id_usuario_solicitante for p in pedidos} | {p.id_usuario_avaliador for p in pedidos}
    nomes = dict(
        (await db.execute(
            select(Usuario.id, Usuario.nome).where(
                Usuario.id.in_(uids), Usuario.tenant_id == tenant_id
            )
        )).all()
    )
    numeros = dict(
        (await db.execute(
            select(Processo.id, Processo.numero_processo).where(
                Processo.id.in_({p.id_processo for p in pedidos}),
                Processo.tenant_id == tenant_id,
            )
        )).all()
    )

    por_pedido: dict[int, list[AvaliacaoItemOut]] = {p.id: [] for p in pedidos}
    for item, descricao, versao in itens:
        reenviado = reenvio_de.get(item.id)
        pode = False
        if item.resultado == "devolvido" and reenviado is None:
            pode = await _vigente_de(db, item.id_anexo, tenant_id=tenant_id) != item.id_anexo
        por_pedido[item.id_pedido].append(
            AvaliacaoItemOut(
                id=item.id,
                id_anexo=item.id_anexo,
                descricao_anexo=descricao,
                versao=versao,
                situacao=item.resultado or "aguardando",
                justificativa=item.justificativa,
                id_usuario_decisao=item.id_usuario_decisao,
                decidido_em=item.decidido_em,
                id_avaliacao_anterior=item.id_avaliacao_anterior,
                id_avaliacao_reenvio=reenviado,
                pode_reenviar=pode,
            )
        )
    return [
        AvaliacaoPedidoOut(
            id=p.id,
            id_processo=p.id_processo,
            numero_processo=numeros.get(p.id_processo),
            id_usuario_solicitante=p.id_usuario_solicitante,
            nome_solicitante=nomes.get(p.id_usuario_solicitante),
            id_usuario_avaliador=p.id_usuario_avaliador,
            nome_avaliador=nomes.get(p.id_usuario_avaliador),
            orientacao=p.orientacao,
            prazo=p.prazo,
            situacao=p.situacao,
            criado_em=p.criado_em,
            concluido_em=p.concluido_em,
            itens=por_pedido[p.id],
        )
        for p in pedidos
    ]


# ---------------------------------------------------------------------------
# Decisão e reenvio
# ---------------------------------------------------------------------------


async def _atualizar_situacao(db: AsyncSession, pedido: AvaliacaoPedido) -> None:
    await db.flush()
    resta = (
        await db.execute(
            select(AvaliacaoDocumento.id).where(
                AvaliacaoDocumento.id_pedido == pedido.id,
                AvaliacaoDocumento.tenant_id == pedido.tenant_id,
                AvaliacaoDocumento.resultado.is_(None),
            ).limit(1)
        )
    ).first()
    if resta is None:
        pedido.situacao = "concluida"
        pedido.concluido_em = datetime.now()
    else:
        pedido.situacao = "pendente"
        pedido.concluido_em = None


async def decidir(
    db: AsyncSession,
    pedido_id: int,
    dados: AvaliacaoDecisoes,
    *,
    tenant_id: int,
    usuario: Usuario,
) -> AvaliacaoPedidoOut:
    """Aprova ou devolve documentos do pedido, todos na mesma transação. Só o
    avaliador designado (AC-04): ter a transação não basta."""
    from .anexos import sucessora_de
    from .audit import log as audit_log

    pedido = await _pedido_autorizado(
        db, pedido_id, tenant_id=tenant_id, usuario=usuario, travar=True
    )
    if pedido.id_usuario_avaliador != usuario.id:
        raise AvaliacaoProibida("Só o avaliador designado pode decidir este pedido.")

    ids = [d.id_item for d in dados.decisoes]
    itens = {
        i.id: i
        for i in (
            await db.execute(
                select(AvaliacaoDocumento).where(
                    AvaliacaoDocumento.id.in_(ids),
                    AvaliacaoDocumento.id_pedido == pedido.id,
                    AvaliacaoDocumento.tenant_id == tenant_id,
                ).with_for_update()
            )
        ).scalars().all()
    }
    agora = datetime.now()
    for d in dados.decisoes:
        item = itens.get(d.id_item)
        if item is None:
            raise AvaliacaoNaoEncontrada(f"Documento #{d.id_item} não faz parte deste pedido")
        if item.resultado is not None:
            raise AvaliacaoConflito(f"O documento #{item.id_anexo} já foi decidido.")
        if await sucessora_de(db, item.id_anexo, tenant_id=tenant_id) is not None:
            raise AvaliacaoConflito(
                f"O documento #{item.id_anexo} foi substituído por versão posterior."
            )
        item.resultado = d.resultado
        item.justificativa = d.justificativa
        item.id_usuario_decisao = usuario.id
        item.decidido_em = agora
    await _atualizar_situacao(db, pedido)
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="processo.avaliacao_decidida",
        entidade="processo",
        id_entidade=pedido.id_processo,
        payload={
            "id_pedido": pedido.id,
            "decisoes": [
                {
                    "id_anexo": itens[d.id_item].id_anexo,
                    "resultado": d.resultado,
                    "justificativa": d.justificativa,
                }
                for d in dados.decisoes
            ],
        },
    )
    await db.commit()

    aprovados = sum(1 for d in dados.decisoes if d.resultado == "aprovado")
    devolvidos = len(dados.decisoes) - aprovados
    partes = []
    if aprovados:
        partes.append(f"{aprovados} aprovado(s)")
    if devolvidos:
        partes.append(f"{devolvidos} devolvido(s) para correção")
    out = await obter_pedido(db, pedido_id, tenant_id=tenant_id, usuario=usuario)
    await _avisar(
        db,
        tenant_id=tenant_id,
        destinatario=out.id_usuario_solicitante,
        tipo="avaliacao_decidida",
        titulo="Avaliação de documentos",
        mensagem=(
            f"{usuario.nome} avaliou documentos do processo "
            f"{out.numero_processo or f'#{out.id_processo}'}: {' e '.join(partes)}."
        ),
        processo_id=out.id_processo,
        pedido_id=out.id,
    )
    return out


async def reenviar(
    db: AsyncSession,
    pedido_id: int,
    item_id: int,
    *,
    tenant_id: int,
    usuario: Usuario,
) -> AvaliacaoPedidoOut:
    """Devolve ao avaliador a versão corrigida de um documento devolvido.

    A correção é a versão nova do SI-72, enviada antes; aqui ela só volta para
    avaliação, como item novo do mesmo pedido apontando para o devolvido."""
    from .anexos import AnexoConflito, AnexoNaoEncontrado, alvo_de_versao
    from .audit import log as audit_log

    pedido = await _pedido_autorizado(
        db, pedido_id, tenant_id=tenant_id, usuario=usuario, travar=True
    )
    item = (
        await db.execute(
            select(AvaliacaoDocumento).where(
                AvaliacaoDocumento.id == item_id,
                AvaliacaoDocumento.id_pedido == pedido.id,
                AvaliacaoDocumento.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise AvaliacaoNaoEncontrada("Documento não faz parte deste pedido")
    if item.resultado != "devolvido":
        raise AvaliacaoConflito("Só documento devolvido é reenviado.")
    ja = (
        await db.execute(
            select(AvaliacaoDocumento.id).where(
                AvaliacaoDocumento.id_avaliacao_anterior == item.id,
                AvaliacaoDocumento.tenant_id == tenant_id,
            )
        )
    ).first()
    if ja is not None:
        raise AvaliacaoConflito("Este documento já foi reenviado.")
    vigente = await _vigente_de(db, item.id_anexo, tenant_id=tenant_id)
    if vigente == item.id_anexo:
        raise AvaliacaoConflito(
            "Envie primeiro a versão corrigida do documento; depois reenvie para avaliação."
        )
    try:
        await alvo_de_versao(db, pedido.id_processo, vigente, tenant_id=tenant_id, travar=True)
    except AnexoNaoEncontrado:
        raise AvaliacaoNaoEncontrada("A versão corrigida não está mais no processo.")
    except AnexoConflito as e:
        raise AvaliacaoConflito(str(e))

    novo = AvaliacaoDocumento(
        tenant_id=tenant_id,
        id_pedido=pedido.id,
        id_anexo=vigente,
        id_avaliacao_anterior=item.id,
    )
    db.add(novo)
    await _atualizar_situacao(db, pedido)
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="processo.avaliacao_reenviada",
        entidade="processo",
        id_entidade=pedido.id_processo,
        payload={"id_pedido": pedido.id, "id_anexo_devolvido": item.id_anexo, "id_anexo": vigente},
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AvaliacaoConflito("Este documento já foi reenviado ou já aguarda avaliação.")

    out = await obter_pedido(db, pedido_id, tenant_id=tenant_id, usuario=usuario)
    await _avisar(
        db,
        tenant_id=tenant_id,
        destinatario=out.id_usuario_avaliador,
        tipo="avaliacao_reenviada",
        titulo="Documento corrigido para avaliar",
        mensagem=(
            f"{usuario.nome} reenviou para avaliação a versão corrigida de um documento "
            f"do processo {out.numero_processo or f'#{out.id_processo}'}."
        ),
        processo_id=out.id_processo,
        pedido_id=out.id,
    )
    return out


# ---------------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------------


async def _avisar(
    db: AsyncSession,
    *,
    tenant_id: int,
    destinatario: int,
    tipo: str,
    titulo: str,
    mensagem: str,
    processo_id: int,
    pedido_id: int,
) -> None:
    """Notificação in-app. Roda DEPOIS do commit e nunca desfaz o ato (mesmo
    contrato de `acoes_processo.avisar_cancelamento_recebimento`)."""
    from . import notificacoes
    from .notificacoes import Destinatario

    try:
        await notificacoes.enviar(
            db,
            tenant_id=tenant_id,
            destinatarios=[Destinatario(id_usuario=destinatario)],
            canais=("in_app",),
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem[:500],
            link_url=f"/m/protocolo/processos/{processo_id}",
            payload={"id_processo": processo_id, "id_pedido": pedido_id},
        )
    except Exception:  # noqa: BLE001 — notificação é cortesia
        await db.rollback()
        log.exception("falha ao notificar %s do pedido de avaliação %s", tipo, pedido_id)
