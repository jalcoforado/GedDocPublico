"""Service de Volumes — Fase P6.

Volume físico de processo grande (vol 1/3, 2/3, 3/3). Em arquivamento
documental, quando um processo passa de N páginas (regra geralmente ~200),
ele é fisicamente dividido em volumes encadernados separados.

Numeração unique por (tenant, processo). Range de páginas é informativo;
não há validação cruzada entre volumes (responsabilidade do arquivista).
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Processo, ProcessoVolume
from ..schemas.apensamento import VolumeCreate, VolumeUpdate
from .audit import log as audit_log


class VolumeError(Exception):
    pass


async def _check_processo(db: AsyncSession, processo_id: int, tenant_id: int) -> Processo:
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
        raise VolumeError(f"Processo {processo_id} não encontrado")
    return p


async def criar_volume(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    processo_id: int,
    payload: VolumeCreate,
) -> ProcessoVolume:
    await _check_processo(db, processo_id, tenant_id)

    # Duplicidade (numero já existe pra esse processo)
    existing = (
        await db.execute(
            select(ProcessoVolume).where(
                ProcessoVolume.tenant_id == tenant_id,
                ProcessoVolume.id_processo == processo_id,
                ProcessoVolume.numero == payload.numero,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise VolumeError(f"Volume {payload.numero} já existe neste processo")

    # Validação pagina_final >= pagina_inicial (também há CHECK no DB)
    if (
        payload.pagina_inicial is not None
        and payload.pagina_final is not None
        and payload.pagina_final < payload.pagina_inicial
    ):
        raise VolumeError("pagina_final deve ser >= pagina_inicial")

    now = datetime.now()
    vol = ProcessoVolume(
        tenant_id=tenant_id,
        id_processo=processo_id,
        numero=payload.numero,
        pagina_inicial=payload.pagina_inicial,
        pagina_final=payload.pagina_final,
        observacao=payload.observacao,
        id_usuario=usuario_id,
        criado_em=now,
    )
    db.add(vol)
    await db.flush()

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.volume_criado",
        entidade="processo",
        id_entidade=processo_id,
        payload={
            "id_volume": vol.id,
            "numero": vol.numero,
            "pagina_inicial": vol.pagina_inicial,
            "pagina_final": vol.pagina_final,
        },
    )

    await db.commit()
    await db.refresh(vol)
    return vol


async def atualizar_volume(
    db: AsyncSession,
    *,
    tenant_id: int,
    volume_id: int,
    payload: VolumeUpdate,
) -> ProcessoVolume:
    vol = (
        await db.execute(
            select(ProcessoVolume).where(
                ProcessoVolume.id == volume_id,
                ProcessoVolume.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if vol is None:
        raise VolumeError(f"Volume {volume_id} não encontrado")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(vol, k, v)

    if (
        vol.pagina_inicial is not None
        and vol.pagina_final is not None
        and vol.pagina_final < vol.pagina_inicial
    ):
        raise VolumeError("pagina_final deve ser >= pagina_inicial")

    await db.commit()
    await db.refresh(vol)
    return vol


async def deletar_volume(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    volume_id: int,
) -> None:
    """Hard-delete (volumes raramente são errôneos e quando são, somem mesmo)."""
    vol = (
        await db.execute(
            select(ProcessoVolume).where(
                ProcessoVolume.id == volume_id,
                ProcessoVolume.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if vol is None:
        raise VolumeError(f"Volume {volume_id} não encontrado")

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.volume_excluido",
        entidade="processo",
        id_entidade=vol.id_processo,
        payload={"id_volume": vol.id, "numero": vol.numero},
    )

    await db.delete(vol)
    await db.commit()
