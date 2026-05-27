"""Service de Desentranhamento — Fase P6.

Desentranhar = remover formalmente um anexo de um processo já formado.
Não deleta o arquivo nem o registro `Anexo` — marca o vínculo
``AnexoProcesso.desentranhado_em`` + motivo + autoridade.

Listagens de anexos do processo passam a filtrar ``desentranhado_em IS NULL``.
O termo de desentranhamento (PDF) é gerado sob demanda a partir do registro
marcado — preserva auditoria mesmo após N anos.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Anexo, AnexoProcesso, Processo
from .audit import log as audit_log


class DesentranhamentoError(Exception):
    pass


async def desentranhar_anexo(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    processo_id: int,
    anexo_processo_id: int,
    motivo: str,
    autoridade: str,
) -> AnexoProcesso:
    """Marca o anexo como desentranhado do processo.

    Atenção: `anexo_processo_id` é o id da tabela JOIN, NÃO do `Anexo`. Isso
    permite o mesmo anexo estar em outros processos (raro, mas possível).
    """
    # Garante que o processo é do tenant e está ativo (não permite operar em
    # processo arquivado/excluído).
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
        raise DesentranhamentoError(f"Processo {processo_id} não encontrado")

    ap = (
        await db.execute(
            select(AnexoProcesso).where(
                AnexoProcesso.id == anexo_processo_id,
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ap is None:
        raise DesentranhamentoError(
            f"Anexo {anexo_processo_id} não vinculado ao processo {processo_id}"
        )
    if ap.desentranhado_em is not None:
        raise DesentranhamentoError("Anexo já foi desentranhado deste processo")

    # Carrega o anexo pra capturar descrição no audit
    anexo = (
        await db.execute(select(Anexo).where(Anexo.id == ap.id_anexo))
    ).scalar_one_or_none()
    descricao = anexo.descricao if anexo else None

    now = datetime.now()
    ap.desentranhado_em = now
    ap.id_usuario_desentranhamento = usuario_id
    ap.motivo_desentranhamento = motivo
    ap.autoridade_desentranhamento = autoridade

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.anexo_desentranhado",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_anexo_processo": ap.id,
            "id_anexo": ap.id_anexo,
            "descricao_anexo": descricao,
            "motivo": motivo,
            "autoridade": autoridade,
        },
    )

    await db.commit()
    await db.refresh(ap)
    return ap
