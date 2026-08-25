"""Anexos de débito (F2, Task 5).

Reaproveita o storage de anexos de protocolo (`protocolos.anexo`, o mesmo
diretório por tenant, a mesma lista de extensões) através de um vínculo
próprio, `pagamentos.anexo_debito` (Task 1, migration 0105) — soft-delete,
versionado por `versao_debito` e, opcionalmente, amarrado a um
`PedidoAjuste` (documento enviado EM RESPOSTA a um pedido específico).

Não cria `AnexoProcesso`: débito não é processo, e o núcleo compartilhado
`_persistir_arquivo` (extraído de `services/anexos.py` nesta mesma fatia) só
cuida de gravar o arquivo e criar a linha `Anexo` — nada de vínculo.

Autorização (`get_anexo_debito_path_autorizado`): débito não tem
`nivel_sigilo` (isso é dimensão de PROCESSO, ver `services/sigilo.py`), então
aqui não há checagem de sigilo — a barreira é o vínculo `anexo_debito` ATIVO
pertencer ao tenant do caller. A ordem continua a mesma do padrão de
processo: autoriza ANTES de resolver o caminho no disco, para que um arquivo
ausente não vire canal de diferenciar "não encontrado" de "sem permissão".
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Anexo
from ..models.pagamentos import AnexoDebito, Debito, PedidoAjuste
from . import pagamentos_estados as est
from .anexos import ALLOWED_EXTS, AnexoError, _ext_of, _persistir_arquivo, get_anexo_path


def _utcnow() -> datetime:
    return datetime.utcnow()


class AnexoDebitoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_404_NOT_FOUND):
        super().__init__(status_code=code, detail=detail)


async def _obter_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> Debito:
    d = (
        await db.execute(
            select(Debito).where(
                Debito.id == debito_id,
                Debito.tenant_id == tenant_id,
                Debito.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise AnexoDebitoError("Débito não encontrado")
    return d


async def anexar_ao_debito(
    db: AsyncSession,
    *,
    tenant_id: int,
    tenant_slug: str,
    debito_id: int,
    usuario_id: int | None,
    file: UploadFile,
    descricao: str | None,
    id_pedido_ajuste: int | None = None,
) -> AnexoDebito:
    """Upload de um anexo de débito. NÃO comita — o caller (router) grava a
    auditoria e comita, no mesmo padrão de `pagamentos_ajustes.criar_pedido`."""
    debito = await _obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if debito.situacao_tramitacao in est.TERMINAIS:
        raise AnexoDebitoError(
            f"Débito em situação terminal ('{debito.situacao_tramitacao}') não aceita anexos.",
            status.HTTP_409_CONFLICT,
        )

    if id_pedido_ajuste is not None:
        pedido = (
            await db.execute(
                select(PedidoAjuste).where(
                    PedidoAjuste.id == id_pedido_ajuste,
                    PedidoAjuste.tenant_id == tenant_id,
                    PedidoAjuste.id_debito == debito_id,
                )
            )
        ).scalar_one_or_none()
        if pedido is None:
            raise AnexoDebitoError(
                "Pedido de ajuste não encontrado para este débito.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    if not file.filename:
        raise AnexoDebitoError("Arquivo sem nome", status.HTTP_400_BAD_REQUEST)
    ext = _ext_of(file.filename)
    if ext not in ALLOWED_EXTS:
        raise AnexoDebitoError(f"Extensão '.{ext}' não permitida", status.HTTP_400_BAD_REQUEST)

    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AnexoDebitoError(
            f"Arquivo excede {settings.max_upload_size_mb} MB", status.HTTP_400_BAD_REQUEST
        )

    anexo = await _persistir_arquivo(
        db,
        content=content,
        filename=file.filename,
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        descricao=descricao,
        id_tipo_anexo=None,
        publico=False,
        usuario_id=usuario_id,
    )

    vinculo = AnexoDebito(
        tenant_id=tenant_id,
        id_debito=debito_id,
        id_anexo=anexo.id,
        id_usuario=usuario_id,
        versao_debito=debito.versao,
        id_pedido_ajuste=id_pedido_ajuste,
        criado_em=_utcnow(),
        excluido=False,
    )
    db.add(vinculo)
    await db.flush()
    return vinculo


async def listar_anexos_debito(
    db: AsyncSession, *, tenant_id: int, debito_id: int
) -> list[AnexoDebito]:
    rows = (
        await db.execute(
            select(AnexoDebito)
            .where(
                AnexoDebito.tenant_id == tenant_id,
                AnexoDebito.id_debito == debito_id,
                AnexoDebito.excluido.is_(False),
            )
            .order_by(AnexoDebito.id)
        )
    ).scalars()
    return list(rows)


async def get_anexo_debito_path_autorizado(
    db: AsyncSession,
    *,
    tenant_id: int,
    tenant_slug: str,
    anexo_debito_id: int,
) -> tuple[Path, Anexo]:
    """1º: vínculo ATIVO do tenant (404 se não) — autorização ANTES de
    resolver o caminho. `tenant_slug` não está no esboço original da
    interface porque é indispensável para localizar o arquivo no storage por
    tenant (mesmo padrão de `services/anexos.get_anexo_path_autorizado`)."""
    vinculo = (
        await db.execute(
            select(AnexoDebito).where(
                AnexoDebito.id == anexo_debito_id,
                AnexoDebito.tenant_id == tenant_id,
                AnexoDebito.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if vinculo is None:
        raise AnexoDebitoError("Anexo não encontrado")

    try:
        anexo, path = await get_anexo_path(
            db, vinculo.id_anexo, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
    except AnexoError as e:
        raise AnexoDebitoError(str(e))
    return path, anexo


async def remover_anexo_debito(
    db: AsyncSession,
    *,
    tenant_id: int,
    debito_id: int,
    anexo_debito_id: int,
    usuario_id: int | None,
) -> None:
    """Soft-delete do vínculo. NÃO apaga o arquivo físico (mesmo padrão de
    `services/anexos.delete_anexo`) e NÃO comita — router grava auditoria e
    comita."""
    vinculo = (
        await db.execute(
            select(AnexoDebito).where(
                AnexoDebito.id == anexo_debito_id,
                AnexoDebito.tenant_id == tenant_id,
                AnexoDebito.id_debito == debito_id,
                AnexoDebito.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if vinculo is None:
        raise AnexoDebitoError("Anexo não encontrado")
    vinculo.excluido = True
    await db.flush()
