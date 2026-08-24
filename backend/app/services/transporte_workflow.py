"""Providers de contexto do workflow para as entidades de transporte — P8 D1
(Task 2). Fachadas (`iniciar_workflow_de_ocorrencia` etc.) entram nas Tasks
3–5; este módulo cobre só o registro dos providers de `compute_contexto`.

Cada provider recebe `(db, instance)` e devolve o dicionário de variáveis
disponíveis para as condições do DSL — `estado_atual`/`estado_anterior` são
comuns a todo tipo e acrescentados pelo engine depois do provider (não
duplicar aqui, ver `workflow_engine.compute_contexto`).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ocorrencia, OcorrenciaAndamento, WorkflowDefinition, WorkflowInstance
from ..models.transporte_regulado import Alvara
from .transporte_regulado import (
    estado_do_checklist,
    obter_convocacao,
    situacao_vistorias,
    titular_tem_convocacao_suspensa,
)
from . import workflow_engine as engine
from .workflow_engine import WorkflowEngineError, register_context_provider


async def _contexto_ocorrencia(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    oc = (
        await db.execute(
            select(Ocorrencia).where(
                Ocorrencia.id == instance.entidade_id,
                Ocorrencia.tenant_id == instance.tenant_id,
                Ocorrencia.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if oc is None:
        raise WorkflowEngineError("Ocorrência não encontrada")

    dias_aberta = max(0, (datetime.utcnow() - oc.criado_em).days)
    qtd_andamentos = (
        await db.execute(
            select(func.count(OcorrenciaAndamento.id)).where(
                OcorrenciaAndamento.id_ocorrencia == oc.id,
                OcorrenciaAndamento.tenant_id == instance.tenant_id,
                OcorrenciaAndamento.excluido.is_(False),
            )
        )
    ).scalar_one() or 0

    return {
        "dias_aberta": dias_aberta,
        "origem": oc.origem,
        "id_tipo": oc.id_tipo,
        "tem_alvo": bool(oc.id_permissionario or oc.id_empresa or oc.id_veiculo),
        "qtd_andamentos": int(qtd_andamentos),
        "situacao_atual": oc.situacao,
    }


async def _contexto_alvara(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    alv = (
        await db.execute(
            select(Alvara).where(
                Alvara.id == instance.entidade_id,
                Alvara.tenant_id == instance.tenant_id,
                Alvara.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if alv is None:
        raise WorkflowEngineError("Alvará não encontrado")

    if alv.data_validade is None:
        # Sem validade cadastrada não é "vence amanhã" — 9999 sinaliza ao DSL
        # que não há prazo a vigiar, em vez de um número pequeno arbitrário.
        dias_para_vencer = 9999
    else:
        dias_para_vencer = (alv.data_validade - date.today()).days

    titular_suspenso = await titular_tem_convocacao_suspensa(
        db,
        tenant_id=instance.tenant_id,
        id_permissionario=alv.id_permissionario,
        id_empresa=alv.id_empresa,
    )

    return {
        "dias_para_vencer": dias_para_vencer,
        "tipo_servico": alv.tipo_servico,
        "eh_renovacao": alv.renovado_de is not None,
        "titular_suspenso": titular_suspenso,
    }


async def _contexto_convocacao(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    conv = await obter_convocacao(
        db, tenant_id=instance.tenant_id, convocacao_id=instance.entidade_id
    )
    dias_para_prazo = (conv.prazo - date.today()).days

    itens = await estado_do_checklist(
        db, tenant_id=instance.tenant_id, convocacao_id=conv.id
    )
    checklist_completo = all(
        i["marcado"] is True for i in itens if i["obrigatorio"]
    )

    vistorias = await situacao_vistorias(db, tenant_id=instance.tenant_id, conv=conv)

    return {
        "dias_para_prazo": dias_para_prazo,
        "situacao_atual": conv.situacao,
        "checklist_completo": checklist_completo,
        # `condicional` não conta — só `situacao_vistorias` (que exige
        # `resultado == "aprovado"`) decide isso; nada aqui reimplementa.
        "tem_vistoria_aprovada": bool(vistorias["satisfeita"]),
    }


# ============================================================================
# Sementes de DSL — Task 3 (piloto: ocorrências). `obter_definicao` cria a
# `WorkflowDefinition` do tenant lazy a partir daqui na primeira vez que uma
# fachada precisa dela; edições do tenant DEPOIS disso nunca são
# sobrescritas — a semente só serve de ponto de partida.
# ============================================================================

SEMENTES: dict[str, dict] = {
    "transporte-ocorrencia": {
        "estado_inicial": "registrada",
        "estados": [
            {"slug": "registrada", "label": "Registrada"},
            {"slug": "em_apuracao", "label": "Em apuração"},
            {"slug": "procedente", "label": "Procedente", "final": True},
            {"slug": "improcedente", "label": "Improcedente", "final": True},
            {"slug": "arquivada", "label": "Arquivada", "final": True},
        ],
        "transicoes": [
            {"de": "registrada", "para": "em_apuracao", "label": "iniciar_apuracao"},
            {"de": "em_apuracao", "para": "procedente", "label": "decidir_procedente"},
            {"de": "em_apuracao", "para": "improcedente", "label": "decidir_improcedente"},
            {"de": "em_apuracao", "para": "arquivada", "label": "arquivar"},
        ],
    },
    # P8 D2 (Task 4). A condição `not titular_suspenso` é ESPELHO do gate da
    # Fase C (`titular_tem_convocacao_suspensa`, checado em `renovar_alvara`
    # ANTES da transição) — nunca a fonte do 409 daquela rota; o 409 da Fase C
    # continua vindo do gate de serviço, intacto.
    "transporte-alvara": {
        "estado_inicial": "vigente",
        "estados": [
            {"slug": "vigente", "label": "Vigente"},
            {"slug": "renovado", "label": "Renovado", "final": True},
            {"slug": "revogado", "label": "Revogado", "final": True},
        ],
        "transicoes": [
            {"de": "vigente", "para": "renovado", "label": "renovar",
             "condicao": "not titular_suspenso"},
            {"de": "vigente", "para": "revogado", "label": "revogar"},
        ],
    },
    # P8 D3 (Task 5). `estado_anterior` (injetado pelo engine a partir do
    # último log) é o que permite `reativar`/`reativar_analise` devolverem a
    # convocação para onde ela estava ANTES da suspensão — diferente da P5.3
    # (`reativar_convocacao` sempre voltava para `convocado`). `suspender`/
    # `suspender_analise` têm o mesmo `para` ("suspenso") de propósito: quem
    # transiciona não precisa escolher o label, o engine casa pelo `de` ==
    # `estado_atual` sozinho.
    "transporte-recadastramento": {
        "estado_inicial": "convocado",
        "estados": [
            {"slug": "convocado", "label": "Convocado"},
            {"slug": "em_analise", "label": "Em análise"},
            {"slug": "suspenso", "label": "Suspenso"},
            {"slug": "deferido", "label": "Deferido", "final": True},
            {"slug": "indeferido", "label": "Indeferido", "final": True},
        ],
        "transicoes": [
            {"de": "convocado", "para": "em_analise", "label": "iniciar_analise"},
            {"de": "em_analise", "para": "deferido", "label": "deferir",
             "condicao": "checklist_completo"},
            {"de": "em_analise", "para": "indeferido", "label": "indeferir"},
            {"de": "convocado", "para": "suspenso", "label": "suspender"},
            {"de": "em_analise", "para": "suspenso", "label": "suspender_analise"},
            {"de": "suspenso", "para": "convocado", "label": "reativar",
             "condicao": "estado_anterior == 'convocado'"},
            {"de": "suspenso", "para": "em_analise", "label": "reativar_analise",
             "condicao": "estado_anterior == 'em_analise'"},
        ],
    },
}


async def obter_definicao(
    db: AsyncSession, *, tenant_id: int, slug: str
) -> WorkflowDefinition:
    """Devolve a `WorkflowDefinition` ativa de `slug` para o tenant.

    Se não existir NENHUMA (nem ativa nem inativa) para esse par
    `(tenant_id, slug)`, cria — lazy — a partir de `SEMENTES[slug]`
    (`versao=1`, `ativo=True`) e dá `flush` na sessão corrente (não
    `commit`: quem chama decide quando persistir, geralmente dentro da
    mesma transação de `engine.iniciar`). Depois de criada, edição do
    tenant sobre essa linha nunca é sobrescrita — esta função só cria
    quando não existe nenhuma.
    """
    wf = (
        await db.execute(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == slug,
                WorkflowDefinition.ativo.is_(True),
            )
            .order_by(WorkflowDefinition.versao.desc())
        )
    ).scalars().first()
    if wf is not None:
        return wf

    if slug not in SEMENTES:
        raise WorkflowEngineError(f"Sem semente de workflow para slug={slug!r}")

    wf = WorkflowDefinition(
        tenant_id=tenant_id,
        slug=slug,
        nome=slug.replace("-", " ").title(),
        versao=1,
        ativo=True,
        dsl=SEMENTES[slug],
        criado_em=datetime.utcnow(),
    )
    db.add(wf)
    await db.flush()
    return wf


async def obter_ou_criar_instancia(
    db: AsyncSession, *, tenant_id: int, slug: str, entidade_tipo: str,
    entidade_id: int, situacao_atual: str, usuario_id: int | None,
) -> WorkflowInstance:
    """Devolve a `WorkflowInstance` ativa de `(entidade_tipo, entidade_id)` —
    ou a cria lazy no `situacao_atual` da entidade (não no `estado_inicial`
    do DSL: uma entidade que já existia antes do P8, ou que ganha workflow
    numa situação que não é a inicial, nasce onde já está).

    ATENÇÃO: `engine.iniciar` COMMITA internamente. Chame esta função ANTES
    de mutar a entidade — se a criação falhar, nada foi tocado ainda."""
    inst = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.entidade_tipo == entidade_tipo,
                WorkflowInstance.entidade_id == entidade_id,
                WorkflowInstance.ativa.is_(True),
            )
        )
    ).scalar_one_or_none()
    if inst is not None:
        return inst

    wf = await obter_definicao(db, tenant_id=tenant_id, slug=slug)
    return await engine.iniciar(
        db,
        tenant_id=tenant_id,
        id_workflow_definition=wf.id,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        usuario_id=usuario_id,
        estado_inicial=situacao_atual,
    )


async def transicionar(
    db: AsyncSession, *, instancia: WorkflowInstance, para: str,
    usuario_id: int | None, entidade: Any, slug: str,
    contexto_extra: dict[str, Any] | None = None,
) -> None:
    """Muta `entidade.situacao = para` e chama `engine.executar_transicao`.

    `contexto_extra`, quando passado, entra no `contexto_snapshot` do log da
    transição (ex.: `revogar_alvara` grava o motivo ali) — repassado direto
    para `engine.executar_transicao`, que já o funde ao contexto automático.

    `engine.executar_transicao` COMMITA internamente — a mutação da
    entidade e a transição da instância são persistidas juntas nesse mesmo
    commit. Se a transição falhar (não existe ou condição bloqueia), NADA
    foi commitado: a mutação em memória fica pendente e o caller (router
    dentro de `db.begin()`, ou teste) é quem desfaz com o rollback da
    transação — o 409 responde sem efeito no banco.

    `WorkflowEngineError` vira `HTTPException(409, ...)`: mensagem própria
    (citando slug/estado destino/estado de origem) quando a transição não
    existe no DSL; a mensagem do engine (que já descreve a condição) quando
    a transição existe mas está bloqueada.
    """
    entidade.situacao = para
    try:
        await engine.executar_transicao(
            db, instancia, para=para, usuario_id=usuario_id,
            contexto_extra=contexto_extra,
        )
    except WorkflowEngineError as exc:
        msg = str(exc)
        if "bloqueada pela condição" in msg:
            raise HTTPException(status.HTTP_409_CONFLICT, msg) from exc
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"O workflow {slug!r} não permite {para!r} a partir de "
            f"{instancia.estado_atual!r}",
        ) from exc


async def transicionar_tentando(
    db: AsyncSession, *, instancia: WorkflowInstance, usuario_id: int | None,
    entidade: Any, slug: str, tentativas: list[str],
) -> str:
    """Tenta cada `para` de `tentativas`, NA ORDEM, e usa a primeira que o
    engine aceitar — caso de uso: `reativar_convocacao` (P8 D3), onde o
    destino certo depende de `estado_anterior` (condição do DSL) e não do
    caller, que só sabe que a instância está em `suspenso`.

    Propaga o 409 da ÚLTIMA tentativa se todas forem recusadas — mensagem
    plausível o bastante (a condição da última tentativa é a mais específica:
    normalmente a mais "provável" veio primeiro).
    """
    se_ultimo_erro: HTTPException | None = None
    for para in tentativas:
        try:
            await transicionar(
                db, instancia=instancia, para=para, usuario_id=usuario_id,
                entidade=entidade, slug=slug,
            )
            return para
        except HTTPException as exc:
            se_ultimo_erro = exc
    assert se_ultimo_erro is not None  # `tentativas` não pode ser vazia
    raise se_ultimo_erro


def registrar_providers() -> None:
    """Registra os providers de `ocorrencia`/`alvara`/`convocacao` no engine.

    Idempotente (reatribuição de chave de dict) — seguro chamar mais de uma
    vez, inclusive no import deste módulo (linha abaixo) e de novo em
    `main.py`, se algum dia for explicitado lá.
    """
    register_context_provider("ocorrencia", _contexto_ocorrencia)
    register_context_provider("alvara", _contexto_alvara)
    register_context_provider("convocacao", _contexto_convocacao)


# Registro no import — é o "padrão mais simples que funciona com o teste":
# qualquer teste/rota que importe este módulo (direta ou indiretamente via
# `app.main`) já enxerga os três providers em `CONTEXT_PROVIDERS`.
registrar_providers()
