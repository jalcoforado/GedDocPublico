"""Lógica de abertura de processo.

Espelha o fluxo do PHP Processo::abrir (em aprimora/app/services/Processo.php):
1. Cria o processo (numero_processo via função PG `gerar_numero_processo_string()`).
2. Cria movimentação inicial com ação ABERTURA, vinculada ao processo + usuário + unidade proprietária.
3. Atualiza id_ultima_movimentacao e id_local_atual do processo.
4. Tudo em uma única transação.
"""
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Acao, Movimentacao, Processo
from ..schemas.processo import ProcessoCreate


class AberturaError(Exception):
    pass


async def abrir_processo(
    db: AsyncSession,
    payload: ProcessoCreate,
    *,
    usuario_id: int,
) -> Processo:
    # 1. Gera número de processo via função PG (mesma lógica do PHP).
    numero_row = (
        await db.execute(text("SELECT protocolos.gerar_numero_processo_string() AS num"))
    ).first()
    if numero_row is None or not numero_row.num:
        raise AberturaError("Falha ao gerar número de processo")
    numero_processo = numero_row.num

    # 2. Localiza ação de abertura (flag = 'ABERTURA').
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

    # 3. Cria processo.
    processo = Processo(
        id_assunto=payload.id_assunto,
        id_manifestante=payload.id_manifestante,
        id_unidade_proprietaria=payload.id_unidade_proprietaria,
        observacao=payload.observacao,
        corpo=payload.corpo,
        numero_origem=payload.numero_origem,
        numero_processo=numero_processo,
        publico=payload.publico,
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

    await db.commit()
    await db.refresh(processo)
    return processo
