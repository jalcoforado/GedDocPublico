"""Rascunho de processo: editar, abrir (dar número) e excluir. SI-16.

O rascunho nasce em `abertura_processo.abrir_processo` com
`situacao='rascunho'` e sem número (E3). Até aqui ele não podia ser editado, e
o número só nascia como efeito colateral do primeiro encaminhamento — nada na
tela dizia isso. Decisões de produto de 2026-11-05:

- **Rascunho é de quem o criou.** Só o autor edita, abre ou exclui, e para os
  outros ele não existe (404). Vale também para super-usuário: é autoria, não
  grau de acesso. A regra de leitura mora em `sigilo.assert_acesso_processo` e
  em `processos.list_processos`/`get_processo_detail`; aqui ela é conferida de
  novo, porque estes atos escrevem.
- **"Abrir processo" é um ato próprio.** Dá o número e o processo fica na
  unidade de quem abriu. Encaminhar um rascunho continua dando o número
  (`acoes_processo.encaminhar`), e os dois caminhos usam `emitir_numero`.
- **Excluir é lógico** (`excluido=True`) e só vale para rascunho. Processo
  aberto não se exclui.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Acao, Assunto, Manifestante, Movimentacao, Processo, Tenant, UnidadeTrabalho
from ..schemas.processo import RascunhoUpdate


class RascunhoError(Exception):
    """Pedido inválido (400): referência que não existe nesta prefeitura."""


class RascunhoNaoEncontradoError(RascunhoError):
    """404: não existe, foi excluído, ou é rascunho de outra pessoa."""


class RascunhoJaAbertoError(RascunhoError):
    """409: o processo já tem número — não é mais rascunho."""


async def _carregar_rascunho(
    db: AsyncSession, processo_id: int, *, tenant_id: int, usuario_id: int
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
    # Rascunho alheio responde igual a inexistente: 409 confirmaria que existe.
    if p is None or (p.situacao == "rascunho" and p.id_usuario != usuario_id):
        raise RascunhoNaoEncontradoError("Processo não encontrado")
    if p.situacao != "rascunho":
        raise RascunhoJaAbertoError(
            "Este processo já foi aberto e tem número: não é mais rascunho."
        )
    return p


async def _assert_do_tenant(db: AsyncSession, modelo, id_: int, *, tenant_id: int, nome: str):
    """FK "soft" quanto ao tenant: a FK do Postgres aceitaria o id de outra
    prefeitura. 400 com o nome do campo, como um valor inválido de formulário."""
    existe = (
        await db.execute(
            select(modelo.id).where(
                modelo.id == id_,
                modelo.tenant_id == tenant_id,
                modelo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existe is None:
        raise RascunhoError(f"{nome} não encontrado(a).")


async def editar_rascunho(
    db: AsyncSession,
    processo_id: int,
    payload: RascunhoUpdate,
    *,
    tenant_id: int,
    usuario_id: int,
) -> Processo:
    p = await _carregar_rascunho(db, processo_id, tenant_id=tenant_id, usuario_id=usuario_id)

    await _assert_do_tenant(db, Assunto, payload.id_assunto, tenant_id=tenant_id, nome="Assunto")
    await _assert_do_tenant(
        db, Manifestante, payload.id_manifestante, tenant_id=tenant_id, nome="Manifestante"
    )
    await _assert_do_tenant(
        db, UnidadeTrabalho, payload.id_unidade_proprietaria,
        tenant_id=tenant_id, nome="Unidade proprietária",
    )

    from .sigilo import SigiloError, resolver_nivel_criacao

    try:
        nivel_sigilo = resolver_nivel_criacao(payload.nivel_sigilo, payload.publico)
    except SigiloError as e:
        raise RascunhoError(str(e)) from e

    antes = {
        "id_assunto": p.id_assunto,
        "id_manifestante": p.id_manifestante,
        "id_unidade_proprietaria": p.id_unidade_proprietaria,
        "nivel_sigilo": p.nivel_sigilo,
    }

    # Rascunho nunca tramitou (tramitar o numera), então ele está onde nasceu:
    # trocar a unidade proprietária troca também onde ele está e a unidade da
    # movimentação de abertura — senão a linha do tempo diria que ele foi
    # aberto num setor que não é mais o dele.
    if payload.id_unidade_proprietaria != p.id_unidade_proprietaria:
        abertura = (
            await db.execute(
                select(Movimentacao)
                .join(Acao, Acao.id == Movimentacao.id_acao)
                .where(
                    Movimentacao.id_processo == p.id,
                    Movimentacao.tenant_id == tenant_id,
                    Movimentacao.excluido.is_(False),
                    Acao.flag == "ABERTURA",
                )
            )
        ).scalar_one_or_none()
        if abertura is not None:
            abertura.id_unidade_responsavel = payload.id_unidade_proprietaria
        p.id_local_atual = payload.id_unidade_proprietaria

    p.id_assunto = payload.id_assunto
    p.id_manifestante = payload.id_manifestante
    p.id_unidade_proprietaria = payload.id_unidade_proprietaria
    p.observacao = payload.observacao
    p.corpo = payload.corpo
    p.numero_origem = payload.numero_origem
    p.nivel_sigilo = nivel_sigilo
    p.externo = payload.externo
    p.canal_entrada = payload.canal_entrada

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.rascunho_editado",
        entidade="processo",
        id_entidade=p.id,
        payload={
            "antes": antes,
            "depois": {
                "id_assunto": p.id_assunto,
                "id_manifestante": p.id_manifestante,
                "id_unidade_proprietaria": p.id_unidade_proprietaria,
                "nivel_sigilo": nivel_sigilo,
            },
        },
    )
    await db.commit()
    await db.refresh(p)
    return p


async def abrir_rascunho(
    db: AsyncSession, processo_id: int, *, tenant_id: int, usuario_id: int
) -> Processo:
    """Dá o número (e o NUP, se a prefeitura usa) e o processo passa a valer.

    Ele fica onde está — na unidade de quem abriu —, e o workflow, se o tipo
    tiver um, nasce agora, como na abertura direta.
    """
    p = await _carregar_rascunho(db, processo_id, tenant_id=tenant_id, usuario_id=usuario_id)
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise RascunhoNaoEncontradoError("Processo não encontrado")

    from .numeracao_processo import emitir_numero

    await emitir_numero(db, p, tenant=tenant, usuario_id=usuario_id, now=datetime.now())
    p.situacao = "protocolado"

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.aberto_do_rascunho",
        entidade="processo",
        id_entidade=p.id,
        payload={"numero_processo": p.numero_processo, "nup": p.nup},
    )
    await db.commit()
    await db.refresh(p)

    from .workflow_integration import auto_iniciar_workflow_se_aplicavel

    await auto_iniciar_workflow_se_aplicavel(db, p, usuario_id)
    return p


async def excluir_rascunho(
    db: AsyncSession, processo_id: int, *, tenant_id: int, usuario_id: int
) -> None:
    """Exclusão lógica. Some de toda listagem e de todo acesso por id, que já
    filtram `excluido`; a linha fica no banco, com a trilha de auditoria."""
    p = await _carregar_rascunho(db, processo_id, tenant_id=tenant_id, usuario_id=usuario_id)
    p.excluido = True

    from .audit import log as audit_log

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="processo.rascunho_excluido",
        entidade="processo",
        id_entidade=p.id,
        payload={"id_assunto": p.id_assunto, "id_manifestante": p.id_manifestante},
    )
    await db.commit()
