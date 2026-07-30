"""Endpoints de workflow — Fases 19-21.

CRUD básico de WorkflowDefinition + endpoint pra testar expressão de
condição (19). Engine de transições (20a). Integração com Processo (20b).
SLA + alertas (21).

Versionamento: PUT cria NOVA versão (versao = max+1) e desativa as anteriores
do mesmo slug. Quem já estiver executando a versão anterior continua na
mesma — protegido por instância apontando para `workflow_definition.id`.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import (
    Processo,
    TipoProcessoWorkflow,
    Usuario,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowSlaAlerta,
)
from ..schemas.workflow import (
    EvaluateExprRequest,
    EvaluateExprResponse,
    TipoProcessoWorkflowOut,
    TipoProcessoWorkflowSet,
    TransicaoDisponivel,
    WorkflowDefinitionCreate,
    WorkflowDefinitionListItem,
    WorkflowDefinitionOut,
    WorkflowDefinitionUpdate,
    WorkflowInstanceCreate,
    WorkflowInstanceDetail,
    WorkflowInstanceOut,
    WorkflowSlaAlertaDetail,
    WorkflowSlaAlertaOut,
    WorkflowSlaAlertaResolve,
    WorkflowTransicaoExec,
    WorkflowTransicaoLogOut,
)
from ..services.workflow_dsl import WorkflowExprError, evaluate_expr
from ..services.workflow_engine import (
    WorkflowEngineError,
    carregar_log,
    executar_transicao,
    iniciar,
    migrar_instance,
    transicoes_disponiveis,
)

router = APIRouter(prefix="/workflow-definitions", tags=["workflow"])


@router.get("", response_model=list[WorkflowDefinitionListItem])
async def list_workflow_definitions(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    apenas_ativos: bool = True,
):
    stmt = select(WorkflowDefinition)
    stmt = tenant_filter(stmt, WorkflowDefinition, tenant_id)
    if apenas_ativos:
        stmt = stmt.where(WorkflowDefinition.ativo.is_(True))
    stmt = stmt.order_by(WorkflowDefinition.slug, WorkflowDefinition.versao.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [WorkflowDefinitionListItem.model_validate(r) for r in rows]


@router.get("/{wf_id}", response_model=WorkflowDefinitionOut)
async def get_workflow_definition(
    wf_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == wf_id,
                WorkflowDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não encontrado"
        )
    return WorkflowDefinitionOut.model_validate(wf)


@router.post(
    "", response_model=WorkflowDefinitionOut, status_code=status.HTTP_201_CREATED
)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    current: Usuario = Depends(require_permission("workflow", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Primeira versão? Próxima? Desativa as anteriores se for nova versão de
    # slug existente.
    max_versao = (
        await db.execute(
            select(func.coalesce(func.max(WorkflowDefinition.versao), 0)).where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == payload.slug,
            )
        )
    ).scalar_one()
    proxima_versao = max_versao + 1

    if proxima_versao > 1:
        # Desativa versões anteriores do mesmo slug
        await db.execute(
            update(WorkflowDefinition)
            .where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == payload.slug,
            )
            .values(ativo=False)
        )

    wf = WorkflowDefinition(
        tenant_id=tenant_id,
        slug=payload.slug,
        nome=payload.nome,
        descricao=payload.descricao,
        versao=proxima_versao,
        ativo=True,
        dsl=payload.dsl.model_dump(),
        criado_em=datetime.utcnow(),
        id_usuario_criador=current.id,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return WorkflowDefinitionOut.model_validate(wf)


@router.put("/{wf_id}", response_model=WorkflowDefinitionOut)
async def update_workflow_definition(
    wf_id: int,
    payload: WorkflowDefinitionUpdate,
    current: Usuario = Depends(require_permission("workflow", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Update do workflow.

    Se `dsl` for enviado → cria NOVA VERSÃO (instâncias ativas continuam na
    versão antiga, que é desativada). Só `nome`/`descricao`/`ativo` atualiza
    in-place sem bumpar versão.
    """
    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == wf_id,
                WorkflowDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não encontrado"
        )

    data = payload.model_dump(exclude_unset=True)
    dsl_dado = "dsl" in data and data["dsl"] is not None

    if dsl_dado:
        # Fase 22b — cria nova versão. Desativa todas as versões do mesmo slug
        # (incluindo a apontada por wf_id, que pode não ser a mais recente) e
        # insere uma nova row com `versao = max+1`.
        max_versao = (
            await db.execute(
                select(func.coalesce(func.max(WorkflowDefinition.versao), 0)).where(
                    WorkflowDefinition.tenant_id == tenant_id,
                    WorkflowDefinition.slug == wf.slug,
                )
            )
        ).scalar_one()
        await db.execute(
            update(WorkflowDefinition)
            .where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == wf.slug,
            )
            .values(ativo=False)
        )
        nova = WorkflowDefinition(
            tenant_id=tenant_id,
            slug=wf.slug,
            nome=data.get("nome") or wf.nome,
            descricao=data["descricao"] if "descricao" in data else wf.descricao,
            versao=max_versao + 1,
            ativo=True,
            dsl=payload.dsl.model_dump() if payload.dsl else wf.dsl,
            criado_em=datetime.utcnow(),
            id_usuario_criador=current.id,
        )
        db.add(nova)
        await db.commit()
        await db.refresh(nova)
        return WorkflowDefinitionOut.model_validate(nova)

    # Sem DSL → update in-place
    if "nome" in data and data["nome"] is not None:
        wf.nome = data["nome"]
    if "descricao" in data:
        wf.descricao = data["descricao"]
    if "ativo" in data and data["ativo"] is not None:
        wf.ativo = data["ativo"]
    wf.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(wf)
    return WorkflowDefinitionOut.model_validate(wf)


@router.delete("/{wf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_definition(
    wf_id: int,
    _: Usuario = Depends(require_permission("workflow", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete via `ativo=false`. Não removemos a row pra preservar
    auditoria de workflows historicamente executados."""
    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == wf_id,
                WorkflowDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não encontrado"
        )
    wf.ativo = False
    wf.atualizado_em = datetime.utcnow()
    await db.commit()


@router.get("/{wf_id}/versoes")
async def list_versoes_mesmo_slug(
    wf_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas as versões do mesmo slug deste WF (ativas e inativas).
    + Conta instances ativas em cada versão. Usado pela UI de migração (22c).
    """
    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == wf_id,
                WorkflowDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não encontrado"
        )

    versoes = (
        await db.execute(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == wf.slug,
            )
            .order_by(WorkflowDefinition.versao.desc())
        )
    ).scalars().all()

    # Conta instances ativas por id_workflow_definition
    cnt_rows = (
        await db.execute(
            select(
                WorkflowInstance.id_workflow_definition,
                func.count(WorkflowInstance.id),
            )
            .where(
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.ativa.is_(True),
                WorkflowInstance.id_workflow_definition.in_([v.id for v in versoes]),
            )
            .group_by(WorkflowInstance.id_workflow_definition)
        )
    ).all()
    cnt_por_id = {wid: int(cnt) for wid, cnt in cnt_rows}

    return [
        {
            "id": v.id,
            "slug": v.slug,
            "nome": v.nome,
            "versao": v.versao,
            "ativo": v.ativo,
            "criado_em": v.criado_em.isoformat(),
            "instances_ativas": cnt_por_id.get(v.id, 0),
        }
        for v in versoes
    ]


@router.post("/test-expr", response_model=EvaluateExprResponse)
async def test_expr(
    payload: EvaluateExprRequest,
    # Ferramenta do desenhista de workflow (mesmo público do CRUD de
    # definition, que já é gateado). Não tem efeito colateral: leitura basta.
    _: Usuario = Depends(require_permission("workflow")),
):
    """Avalia uma expressão SAFE contra um contexto arbitrário. Não exige
    tenant (mas exige login). Use na UI para testar condições antes de
    gravar o workflow.
    """
    try:
        resultado = evaluate_expr(payload.expressao, payload.contexto)
        return EvaluateExprResponse(resultado=resultado, truthy=bool(resultado))
    except WorkflowExprError as e:
        return EvaluateExprResponse(resultado=None, truthy=False, erro=str(e))


# ===== Workflow Instances (Fase 20a) =====

instances_router = APIRouter(prefix="/workflow-instances", tags=["workflow"])


async def _get_instance_or_404(
    db: AsyncSession, instance_id: int, tenant_id: int
) -> WorkflowInstance:
    inst = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.id == instance_id,
                WorkflowInstance.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if inst is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="WorkflowInstance não encontrada"
        )
    return inst


@instances_router.get("", response_model=list[WorkflowInstanceOut])
async def list_workflow_instances(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    id_processo: int | None = Query(None),
    apenas_ativas: bool = Query(True),
):
    stmt = select(WorkflowInstance).where(WorkflowInstance.tenant_id == tenant_id)
    if id_processo is not None:
        stmt = stmt.where(WorkflowInstance.id_processo == id_processo)
    if apenas_ativas:
        stmt = stmt.where(WorkflowInstance.ativa.is_(True))
    stmt = stmt.order_by(WorkflowInstance.iniciada_em.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [WorkflowInstanceOut.model_validate(r) for r in rows]


@instances_router.get("/{instance_id}", response_model=WorkflowInstanceDetail)
async def get_workflow_instance(
    instance_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    inst = await _get_instance_or_404(db, instance_id, tenant_id)
    disponiveis, contexto = await transicoes_disponiveis(db, inst, usuario=current)
    log = await carregar_log(db, instance_id, tenant_id)
    return WorkflowInstanceDetail(
        **WorkflowInstanceOut.model_validate(inst).model_dump(),
        transicoes_disponiveis=[
            TransicaoDisponivel(
                de=t["de"],
                para=t["para"],
                label=t["label"],
                descricao=t.get("descricao"),
                grupos_permitidos=t.get("grupos_permitidos", []),
            )
            for t in disponiveis
        ],
        log=[WorkflowTransicaoLogOut.model_validate(le) for le in log],
        contexto_atual=contexto,
    )


@instances_router.post(
    "", response_model=WorkflowInstanceOut, status_code=status.HTTP_201_CREATED
)
async def create_workflow_instance(
    payload: WorkflowInstanceCreate,
    # Instanciar um workflow é ato de configuração do fluxo, não de
    # tramitação — alinha com o `inserir` do CRUD de definition.
    current: Usuario = Depends(require_permission("workflow", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        inst = await iniciar(
            db,
            tenant_id=tenant_id,
            id_workflow_definition=payload.id_workflow_definition,
            id_processo=payload.id_processo,
            usuario_id=current.id,
        )
    except WorkflowEngineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WorkflowInstanceOut.model_validate(inst)


@instances_router.post("/{instance_id}/migrar", response_model=WorkflowInstanceOut)
async def migrar(
    instance_id: int,
    payload: dict,  # {id_workflow_definition_destino: int, mapa_estados: dict[str,str] | None}
    # Troca a definição sob uma instância viva — operação de manutenção do
    # desenho do fluxo, não de tramitação.
    current: Usuario = Depends(require_permission("workflow", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Migra instance ativa pra outra versão do mesmo slug (Fase 22c).

    Body:
    - `id_workflow_definition_destino` (int, obrigatório)
    - `mapa_estados` (dict opcional) — chave=estado atual da instance, valor=estado no destino.
      Se omitido, usa identidade (estado_atual precisa existir no destino).
    """
    destino = payload.get("id_workflow_definition_destino")
    if not isinstance(destino, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`id_workflow_definition_destino` obrigatório (int)",
        )
    mapa = payload.get("mapa_estados")
    if mapa is not None and not isinstance(mapa, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`mapa_estados` deve ser dict[str,str] ou null",
        )
    inst = await _get_instance_or_404(db, instance_id, tenant_id)
    try:
        inst = await migrar_instance(
            db,
            inst,
            id_workflow_definition_destino=destino,
            mapa_estados=mapa,
            usuario_id=current.id,
        )
    except WorkflowEngineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WorkflowInstanceOut.model_validate(inst)


@instances_router.post(
    "/{instance_id}/transicao", response_model=WorkflowInstanceDetail
)
async def transicionar(
    instance_id: int,
    payload: WorkflowTransicaoExec,
    # Quem transiciona é o servidor que trabalha o processo (a UI chama daqui:
    # components/ProcessoWorkflowPanel.tsx), não o desenhista do fluxo — por
    # isso o código é `processo`, e não `workflow`. Ambos caem no módulo
    # protocolo, então o enforcement de módulo é o mesmo.
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    inst = await _get_instance_or_404(db, instance_id, tenant_id)
    try:
        inst = await executar_transicao(
            db,
            inst,
            para=payload.para,
            usuario_id=current.id,
            contexto_extra=payload.contexto_extra,
        )
    except WorkflowEngineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Retorna detail completo (com transições disponíveis do novo estado)
    disponiveis, contexto = await transicoes_disponiveis(db, inst, usuario=current)
    log = await carregar_log(db, instance_id, tenant_id)
    return WorkflowInstanceDetail(
        **WorkflowInstanceOut.model_validate(inst).model_dump(),
        transicoes_disponiveis=[
            TransicaoDisponivel(
                de=t["de"],
                para=t["para"],
                label=t["label"],
                descricao=t.get("descricao"),
                grupos_permitidos=t.get("grupos_permitidos", []),
            )
            for t in disponiveis
        ],
        log=[WorkflowTransicaoLogOut.model_validate(le) for le in log],
        contexto_atual=contexto,
    )


# ===== Mapeamento tipo_processo → workflow (Fase 20b) =====

mapeamento_router = APIRouter(prefix="/tipo-processo-workflow", tags=["workflow"])


@mapeamento_router.get("", response_model=list[TipoProcessoWorkflowOut])
async def list_mapeamentos(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(TipoProcessoWorkflow)
            .where(TipoProcessoWorkflow.tenant_id == tenant_id)
            .order_by(TipoProcessoWorkflow.id_tipo_processo)
        )
    ).scalars().all()
    return [TipoProcessoWorkflowOut.model_validate(r) for r in rows]


@mapeamento_router.put(
    "/{id_tipo_processo}", response_model=TipoProcessoWorkflowOut | None
)
async def set_mapeamento(
    id_tipo_processo: int,
    payload: TipoProcessoWorkflowSet,
    _: Usuario = Depends(require_permission("workflow", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Configura (ou remove) o workflow associado a um tipo_processo.

    - `slug_workflow=null` remove o mapeamento.
    - Verifica que o workflow_definition com aquele slug existe e está ativo.
    """
    existente = (
        await db.execute(
            select(TipoProcessoWorkflow).where(
                TipoProcessoWorkflow.tenant_id == tenant_id,
                TipoProcessoWorkflow.id_tipo_processo == id_tipo_processo,
            )
        )
    ).scalar_one_or_none()

    if payload.slug_workflow is None:
        if existente is not None:
            await db.delete(existente)
            await db.commit()
        return None

    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.slug == payload.slug_workflow,
                WorkflowDefinition.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow ativo com slug='{payload.slug_workflow}' não encontrado",
        )

    if existente is None:
        existente = TipoProcessoWorkflow(
            tenant_id=tenant_id,
            id_tipo_processo=id_tipo_processo,
            slug_workflow=payload.slug_workflow,
            criado_em=datetime.utcnow(),
        )
        db.add(existente)
    else:
        existente.slug_workflow = payload.slug_workflow
        existente.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(existente)
    return TipoProcessoWorkflowOut.model_validate(existente)


# ===== SLA alertas (Fase 21) =====

alertas_router = APIRouter(prefix="/workflow-alertas", tags=["workflow"])


@alertas_router.get("", response_model=list[WorkflowSlaAlertaDetail])
async def list_alertas(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    apenas_pendentes: bool = Query(True),
    id_processo: int | None = Query(None),
):
    """Lista alertas de SLA. Por padrão só os pendentes (não resolvidos).

    Junta dados do processo associado pra UI montar a linha sem chamada extra.
    """
    stmt = (
        select(
            WorkflowSlaAlerta,
            WorkflowInstance.id_processo,
            WorkflowInstance.estado_atual,
            WorkflowInstance.ativa,
            Processo.numero_processo,
        )
        .join(
            WorkflowInstance,
            WorkflowInstance.id == WorkflowSlaAlerta.id_workflow_instance,
        )
        .join(Processo, Processo.id == WorkflowInstance.id_processo)
        .where(WorkflowSlaAlerta.tenant_id == tenant_id)
    )
    if apenas_pendentes:
        stmt = stmt.where(WorkflowSlaAlerta.resolvido_em.is_(None))
    if id_processo is not None:
        stmt = stmt.where(WorkflowInstance.id_processo == id_processo)
    stmt = stmt.order_by(WorkflowSlaAlerta.criado_em.desc())

    rows = (await db.execute(stmt)).all()
    return [
        WorkflowSlaAlertaDetail(
            **WorkflowSlaAlertaOut.model_validate(alerta).model_dump(),
            id_processo=id_processo_proc,
            numero_processo=numero,
            estado_atual=estado_atual,
            instance_ativa=ativa,
        )
        for alerta, id_processo_proc, estado_atual, ativa, numero in rows
    ]


@alertas_router.post("/{alerta_id}/resolver", response_model=WorkflowSlaAlertaOut)
async def resolver_alerta(
    alerta_id: int,
    payload: WorkflowSlaAlertaResolve,
    # Alerta de SLA é artefato do workflow; resolvê-lo altera o artefato.
    _: Usuario = Depends(require_permission("workflow", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Resolve manualmente um alerta de SLA (ex: "ciente", "escalado")."""
    alerta = (
        await db.execute(
            select(WorkflowSlaAlerta).where(
                WorkflowSlaAlerta.id == alerta_id,
                WorkflowSlaAlerta.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if alerta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado"
        )
    if alerta.resolvido_em is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alerta já resolvido",
        )
    alerta.resolvido_em = datetime.utcnow()
    alerta.resolucao = payload.resolucao
    await db.commit()
    await db.refresh(alerta)
    return WorkflowSlaAlertaOut.model_validate(alerta)


@alertas_router.post("/verificar-agora", status_code=status.HTTP_202_ACCEPTED)
async def verificar_agora(
    # Dispara varredura de SLA no tenant e grava alertas — escrita, não leitura.
    _: Usuario = Depends(require_permission("workflow", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
):
    """Dispara a varredura de SLA imediatamente para o tenant atual.

    Útil para teste/debug e para "atualizar agora" na UI sem esperar o
    beat. Roda async via Celery → retorna 202 + task_id.
    """
    from ..tasks.verificar_sla_workflows import run as task_sla

    async_result = task_sla.delay(tenant_id=tenant_id)
    return {"task_id": async_result.id, "tenant_id": tenant_id}


# ===== Atalho: workflow do processo =====

processos_workflow_router = APIRouter(tags=["workflow"])


@processos_workflow_router.get(
    "/processos/{processo_id}/workflow", response_model=WorkflowInstanceDetail | None
)
async def get_workflow_do_processo(
    processo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna a WorkflowInstance ATIVA do processo (ou None se não há)."""
    inst = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.id_processo == processo_id,
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.ativa.is_(True),
            )
        )
    ).scalar_one_or_none()
    if inst is None:
        return None
    disponiveis, contexto = await transicoes_disponiveis(db, inst, usuario=current)
    log = await carregar_log(db, inst.id, tenant_id)
    return WorkflowInstanceDetail(
        **WorkflowInstanceOut.model_validate(inst).model_dump(),
        transicoes_disponiveis=[
            TransicaoDisponivel(
                de=t["de"],
                para=t["para"],
                label=t["label"],
                descricao=t.get("descricao"),
                grupos_permitidos=t.get("grupos_permitidos", []),
            )
            for t in disponiveis
        ],
        log=[WorkflowTransicaoLogOut.model_validate(le) for le in log],
        contexto_atual=contexto,
    )
