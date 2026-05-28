"""Lógica de abertura de processo.

Espelha o fluxo do PHP Processo::abrir (em aprimora/app/services/Processo.php):
1. Cria o processo (numero_processo via função PG `gerar_numero_processo_string()`).
2. Cria movimentação inicial com ação ABERTURA, vinculada ao processo + usuário + unidade proprietária.
3. Atualiza id_ultima_movimentacao e id_local_atual do processo.
4. Tudo em uma única transação.

Fase 13a: recebe `tenant_id` e propaga em Processo + Movimentacao.
"""
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Acao, Movimentacao, Processo, Tenant
from ..schemas.processo import ProcessoCreate


class AberturaError(Exception):
    pass


async def abrir_processo(
    db: AsyncSession,
    payload: ProcessoCreate,
    *,
    tenant_id: int,
    usuario_id: int,
) -> Processo:
    # 1. Gera número de processo via função PG (mesma lógica do PHP).
    numero_row = (
        await db.execute(text("SELECT protocolos.gerar_numero_processo_string() AS num"))
    ).first()
    if numero_row is None or not numero_row.num:
        raise AberturaError("Falha ao gerar número de processo")
    numero_processo = numero_row.num

    # 2. Localiza ação de abertura (flag = 'ABERTURA'). Acao é catálogo global.
    acao_abertura = (
        await db.execute(
            select(Acao).where(
                Acao.flag == "ABERTURA",
                Acao.excluido.is_(False),
                Acao.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if acao_abertura is None:
        raise AberturaError(
            "Ação 'ABERTURA' não cadastrada em protocolos.acao — execute o seed."
        )

    now = datetime.now()

    # Sigilo gradual — resolve ostensivo/interno (publico é coluna gerada).
    from .sigilo import SigiloError, resolver_nivel_criacao

    try:
        nivel_sigilo = resolver_nivel_criacao(payload.nivel_sigilo, payload.publico)
    except SigiloError as e:
        raise AberturaError(str(e)) from e

    # 3. Cria processo.
    processo = Processo(
        tenant_id=tenant_id,
        id_assunto=payload.id_assunto,
        id_manifestante=payload.id_manifestante,
        id_unidade_proprietaria=payload.id_unidade_proprietaria,
        observacao=payload.observacao,
        corpo=payload.corpo,
        numero_origem=payload.numero_origem,
        numero_processo=numero_processo,
        nivel_sigilo=nivel_sigilo,
        externo=payload.externo,
        virtual=payload.virtual,
        data_hora_abertura=now,
        id_local_atual=payload.id_unidade_proprietaria,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        migrado=False,
    )
    db.add(processo)
    await db.flush()  # popula processo.id

    # 4. Cria movimentação de abertura.
    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo.id,
        id_unidade_responsavel=payload.id_unidade_proprietaria,
        id_acao=acao_abertura.id,
        id_usuario=usuario_id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    # 5. Aponta id_ultima_movimentacao no processo.
    processo.id_ultima_movimentacao = movimentacao.id

    # Audit (Fase 24)
    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.aberto",
        entidade="processo",
        id_entidade=processo.id,
        payload={
            "numero_processo": processo.numero_processo,
            "id_assunto": processo.id_assunto,
            "id_manifestante": processo.id_manifestante,
            "id_unidade_proprietaria": processo.id_unidade_proprietaria,
            "externo": processo.externo,
            "nivel_sigilo": nivel_sigilo,
        },
    )

    # Fase P2 — NUP federal (opt-in por tenant). Gera ANTES do commit pra
    # que sequencial e nup fiquem na mesma transação do processo.
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant and tenant.usar_nup_federal and tenant.codigo_orgao_nup:
        from .nup import NupError, gerar_nup

        try:
            nup_str, sequencial = await gerar_nup(db, tenant=tenant, ano=now.year)
            processo.nup = nup_str
            processo.numero_sequencial_orgao = sequencial
        except NupError as e:
            # Falha de geração de NUP NÃO bloqueia abertura — registra audit
            # como warning. Operador pode reemitir manualmente depois.
            from .audit import log as audit_log_warn

            await audit_log_warn(
                db,
                tenant_id=tenant_id,
                id_usuario=usuario_id,
                acao="processo.nup_falhou",
                entidade="processo",
                id_entidade=processo.id,
                payload={"erro": str(e)},
            )

    await db.commit()
    await db.refresh(processo)

    # 6. (Fase 20b) Auto-instancia workflow se tipo_processo tem mapeamento.
    # Falha silenciosamente — workflow é opt-in.
    from .workflow_integration import auto_iniciar_workflow_se_aplicavel

    await auto_iniciar_workflow_se_aplicavel(db, processo, usuario_id)

    return processo
