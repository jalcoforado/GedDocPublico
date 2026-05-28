"""Serviço do módulo de Protocolo — Fase P1 (Balcão).

`abrir_protocolo_balcao` reaproveita `abertura_processo.abrir_processo` e
em seguida carimba os 3 campos novos (id_especie_documental, canal_entrada,
data_recepcao) no Processo já criado, na mesma transação lógica.

Reaproveitar é mais seguro do que duplicar — garante que comportamento auto:
auto-instanciação de workflow + audit log de `processo.aberto` + numeração PG
permanecem idênticos pra processo interno e protocolo de balcão.

Audit adicional `processo.protocolado_balcao` registra origem (espécie +
recepção) explicitamente, separado do `processo.aberto`.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import EspecieDocumental, Processo
from ..schemas.processo import ProcessoCreate
from ..schemas.protocolo import ProtocoloBalcaoRequest
from .abertura_processo import AberturaError, abrir_processo
from .audit import log as audit_log


class ProtocoloError(Exception):
    pass


async def abrir_protocolo_balcao(
    db: AsyncSession,
    payload: ProtocoloBalcaoRequest,
    *,
    tenant_id: int,
    usuario_id: int,
) -> Processo:
    # 1. Valida espécie documental (existe + ativa + tenant correto).
    especie = (
        await db.execute(
            select(EspecieDocumental).where(
                EspecieDocumental.id == payload.id_especie_documental,
                EspecieDocumental.tenant_id == tenant_id,
                EspecieDocumental.excluido.is_(False),
                EspecieDocumental.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if especie is None:
        raise ProtocoloError(
            f"Espécie documental {payload.id_especie_documental} não encontrada ou inativa"
        )

    # 2. Reusa o abridor padrão de processo (numeração PG + movimentação + audit + WF).
    processo_create = ProcessoCreate(
        id_assunto=payload.id_assunto,
        id_manifestante=payload.id_manifestante,
        id_unidade_proprietaria=payload.id_unidade_proprietaria,
        observacao=payload.observacao,
        corpo=None,
        numero_origem=payload.numero_origem,
        publico=payload.publico,
        nivel_sigilo=payload.nivel_sigilo,
        externo=True,  # protocolo de balcão é sempre origem externa
        virtual=False,  # documento físico recebido
    )
    try:
        processo = await abrir_processo(
            db, processo_create, tenant_id=tenant_id, usuario_id=usuario_id
        )
    except AberturaError as e:
        raise ProtocoloError(str(e)) from e

    # 3. Carimba os campos novos.
    processo.id_especie_documental = payload.id_especie_documental
    processo.canal_entrada = payload.canal_entrada
    processo.data_recepcao = payload.data_recepcao or datetime.now()
    # Fase P4 — classe CCD (opcional)
    if payload.id_ccd_classe is not None:
        processo.id_ccd_classe = payload.id_ccd_classe

    # 4. Audit adicional (acima do `processo.aberto` já feito).
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.protocolado_balcao",
        entidade="processo",
        id_entidade=processo.id,
        payload={
            "numero_processo": processo.numero_processo,
            "id_especie_documental": especie.id,
            "especie_flag": especie.flag,
            "canal_entrada": payload.canal_entrada,
            "data_recepcao": processo.data_recepcao.isoformat(),
            "id_ccd_classe": payload.id_ccd_classe,
        },
    )

    await db.commit()
    await db.refresh(processo)
    return processo
