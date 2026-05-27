"""Service de Apensamento — Fase P6.

Apensar = juntar um processo (filho/apensado) a outro (principal). A partir
daí o pai "carrega" o filho no histórico e na tramitação documental.

Validações críticas:
- Mesmo tenant (RLS garante, mas validamos com erro amigável).
- Processos distintos (CHECK constraint do schema também garante).
- Filho não pode estar com apensamento ATIVO já (parcial unique também garante).
- Não pode criar ciclo: pai não pode ser descendente do filho.
- Ambos processos devem estar ativos e não excluídos.

Cancela-se via `desapensar()` — não deleta o registro; preserva auditoria.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Processo, ProcessoApensamento
from .audit import log as audit_log


class ApensamentoError(Exception):
    pass


async def _get_processo_ativo(
    db: AsyncSession, processo_id: int, tenant_id: int, *, rotulo: str = "Processo"
) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise ApensamentoError(f"{rotulo} {processo_id} não encontrado")
    if not p.ativo:
        raise ApensamentoError(f"{rotulo} {processo_id} está inativo")
    return p


async def _validar_sem_ciclo(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_filho: int,
    id_pai: int,
) -> None:
    """Garante que id_pai NÃO é descendente de id_filho.

    Walk descendente a partir de id_filho via `id_processo_pai` reversa.
    Se id_pai aparecer entre descendentes, é ciclo.
    """
    # Subir a partir do pai candidato — se chegarmos no filho, é ciclo.
    cur: int | None = id_pai
    visitados: set[int] = set()
    while cur is not None and cur not in visitados:
        visitados.add(cur)
        if cur == id_filho:
            raise ApensamentoError(
                "Apensamento criaria ciclo: o processo pai é descendente do filho."
            )
        row = await db.execute(
            select(Processo.id_processo_pai).where(
                Processo.id == cur,
                Processo.tenant_id == tenant_id,
            )
        )
        cur = row.scalar_one_or_none()


async def apensar(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    id_processo_apensado: int,
    id_processo_principal: int,
    motivo: str,
) -> ProcessoApensamento:
    if id_processo_apensado == id_processo_principal:
        raise ApensamentoError("Um processo não pode ser apensado a si mesmo")

    filho = await _get_processo_ativo(
        db, id_processo_apensado, tenant_id, rotulo="Processo a apensar"
    )
    pai = await _get_processo_ativo(
        db, id_processo_principal, tenant_id, rotulo="Processo principal"
    )

    if filho.id_processo_pai is not None:
        raise ApensamentoError(
            "Processo já está apensado. Desapense antes de apensar a outro."
        )

    await _validar_sem_ciclo(
        db, tenant_id=tenant_id, id_filho=filho.id, id_pai=pai.id
    )

    now = datetime.now()
    apens = ProcessoApensamento(
        tenant_id=tenant_id,
        id_processo_apensado=filho.id,
        id_processo_principal=pai.id,
        id_usuario=usuario_id,
        motivo=motivo,
        criado_em=now,
    )
    db.add(apens)
    await db.flush()

    # Atualiza ponteiro denormalizado pra leituras rápidas
    filho.id_processo_pai = pai.id

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.apensado",
        entidade="processo",
        id_entidade=filho.id,
        payload={
            "id_processo_principal": pai.id,
            "numero_processo_apensado": filho.numero_processo,
            "numero_processo_principal": pai.numero_processo,
            "motivo": motivo,
        },
    )

    await db.commit()
    await db.refresh(apens)
    return apens


async def desapensar(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    id_processo_apensado: int,
    motivo: str,
) -> ProcessoApensamento:
    filho = await _get_processo_ativo(
        db, id_processo_apensado, tenant_id, rotulo="Processo apensado"
    )
    if filho.id_processo_pai is None:
        raise ApensamentoError("Processo não está apensado")

    # Busca o registro ativo de apensamento
    apens = (
        await db.execute(
            select(ProcessoApensamento).where(
                ProcessoApensamento.id_processo_apensado == filho.id,
                ProcessoApensamento.tenant_id == tenant_id,
                ProcessoApensamento.desapensado_em.is_(None),
            )
        )
    ).scalar_one_or_none()
    if apens is None:
        # Estado inconsistente: id_processo_pai existe mas sem registro ativo.
        # Limpa o ponteiro pra normalizar.
        filho.id_processo_pai = None
        await db.commit()
        raise ApensamentoError(
            "Estado inconsistente — ponteiro id_processo_pai existia sem registro "
            "ativo. Limpamos o ponteiro; tente novamente."
        )

    now = datetime.now()
    apens.desapensado_em = now
    apens.id_usuario_desapensamento = usuario_id
    apens.motivo_desapensamento = motivo
    filho.id_processo_pai = None

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.desapensado",
        entidade="processo",
        id_entidade=filho.id,
        payload={
            "id_processo_principal": apens.id_processo_principal,
            "numero_processo_apensado": filho.numero_processo,
            "motivo": motivo,
            "id_apensamento": apens.id,
        },
    )

    await db.commit()
    await db.refresh(apens)
    return apens
