"""Engine de transições de workflow — Fase 20a.

Funções puras sobre a definição (DSL) + acesso ao banco para
WorkflowInstance e WorkflowTransicaoLog. Sem integração com o Processo
real (movimentação) — isso é responsabilidade da Fase 20b.

Pontos importantes:
- `id_workflow_definition` é a VERSÃO EXATA — instância não migra se a
  definição evoluir (POST cria nova versão e desativa antigas, mas
  instâncias ativas continuam apontando para a versão velha).
- Estado final encerra a instance (ativa=false + finalizada_em).
- Cada transição é registrada em `workflow_transicao_log` com snapshot
  do contexto avaliado — útil pra debug/auditoria depois.
- Condições avaliadas pelo simpleeval (workflow_dsl.evaluate_expr).
- Contexto automático carrega dados do processo associado +
  `estado_anterior` (último estado_de no log).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Acao,
    Encaminhamento,
    Movimentacao,
    Processo,
    Usuario,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowSlaAlerta,
    WorkflowTransicaoLog,
)
from .workflow_dsl import WorkflowExprError, evaluate_expr


class WorkflowEngineError(Exception):
    """Erro de uso do engine — origem inválida, condição falsa, etc."""


async def _load_definition(
    db: AsyncSession, definition_id: int, tenant_id: int
) -> WorkflowDefinition:
    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == definition_id,
                WorkflowDefinition.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise WorkflowEngineError("WorkflowDefinition não encontrada")
    return wf


async def _load_instance(
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
        raise WorkflowEngineError("WorkflowInstance não encontrada")
    return inst


async def _load_processo(
    db: AsyncSession, processo_id: int, tenant_id: int
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
        raise WorkflowEngineError("Processo não encontrado")
    return p


async def compute_contexto(
    db: AsyncSession,
    instance: WorkflowInstance,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Constrói o contexto disponível para as expressões SAFE.

    Variáveis automáticas:
      - dias_aberto, numero_processo, id_assunto, id_manifestante,
        id_unidade_atual, id_unidade_proprietaria, externo, publico,
        estado_atual, estado_anterior
    Variáveis em `extra` SOBRESCREVEM auto.
    """
    processo = await _load_processo(db, instance.id_processo, instance.tenant_id)
    now = datetime.utcnow()
    dias_aberto = max(0, (now - processo.data_hora_abertura).days)

    # Último estado_de no log (estado anterior)
    ultimo_log = (
        await db.execute(
            select(WorkflowTransicaoLog)
            .where(
                WorkflowTransicaoLog.id_workflow_instance == instance.id,
                WorkflowTransicaoLog.tenant_id == instance.tenant_id,
            )
            .order_by(WorkflowTransicaoLog.executada_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    estado_anterior = ultimo_log.estado_de if ultimo_log else None

    auto: dict[str, Any] = {
        "dias_aberto": dias_aberto,
        "numero_processo": processo.numero_processo,
        "id_assunto": processo.id_assunto,
        "id_manifestante": processo.id_manifestante,
        "id_unidade_atual": processo.id_local_atual or processo.id_unidade_proprietaria,
        "id_unidade_proprietaria": processo.id_unidade_proprietaria,
        "externo": bool(processo.externo),
        "publico": bool(processo.publico),
        "estado_atual": instance.estado_atual,
        "estado_anterior": estado_anterior,
    }
    if extra:
        auto.update(extra)
    return auto


def _transicoes_do_estado(
    dsl: dict[str, Any], estado: str, contexto: dict[str, Any]
) -> list[dict[str, Any]]:
    """Filtra transições saindo de `estado` cujas condições são truthy.
    Transições com condicao malformada são EXCLUÍDAS (defesa em camadas)."""
    out: list[dict[str, Any]] = []
    for t in dsl.get("transicoes", []):
        if t.get("de") != estado:
            continue
        cond = t.get("condicao")
        if cond is None or not str(cond).strip():
            out.append(t)
            continue
        try:
            if bool(evaluate_expr(cond, contexto)):
                out.append(t)
        except WorkflowExprError:
            continue
    return out


def _estado_obj(dsl: dict[str, Any], slug: str) -> dict[str, Any] | None:
    for e in dsl.get("estados", []):
        if e.get("slug") == slug:
            return e
    return None


async def iniciar(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_workflow_definition: int,
    id_processo: int,
    usuario_id: int | None,
) -> WorkflowInstance:
    """Cria uma WorkflowInstance no estado_inicial da definition.

    Falha se já existir instance ATIVA para o mesmo processo (regra de
    negócio + enforcer no índice parcial criado na migration).
    """
    wf = await _load_definition(db, id_workflow_definition, tenant_id)
    if not wf.ativo:
        raise WorkflowEngineError(
            "WorkflowDefinition inativa — instanciar versão ativa"
        )
    # Confirma que processo existe no tenant
    await _load_processo(db, id_processo, tenant_id)

    # Verifica conflito com instance ativa (mensagem amigável; o unique
    # parcial garante invariante mesmo sob concorrência).
    existente = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.id_processo == id_processo,
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.ativa.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existente is not None:
        raise WorkflowEngineError(
            f"Processo {id_processo} já tem WorkflowInstance ativa (#{existente.id})"
        )

    estado_inicial = wf.dsl.get("estado_inicial")
    if not estado_inicial:
        raise WorkflowEngineError("DSL sem estado_inicial")

    inst = WorkflowInstance(
        tenant_id=tenant_id,
        id_workflow_definition=wf.id,
        id_processo=id_processo,
        estado_atual=estado_inicial,
        ativa=True,
        iniciada_em=datetime.utcnow(),
        id_usuario_inicio=usuario_id,
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


async def transicoes_disponiveis(
    db: AsyncSession,
    instance: WorkflowInstance,
    contexto_extra: dict[str, Any] | None = None,
    usuario: Usuario | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Devolve `(transicoes, contexto)` — útil para a UI mostrar opções.

    Se `usuario` for passado, filtra transições cujo estado destino tem
    `id_unidade_responsavel` setado e o usuário não pertence a essa unidade.
    Sem `usuario` retorna tudo (back-compat).
    """
    if not instance.ativa:
        return [], {}
    wf = await _load_definition(db, instance.id_workflow_definition, instance.tenant_id)
    contexto = await compute_contexto(db, instance, contexto_extra)
    candidatas = _transicoes_do_estado(wf.dsl, instance.estado_atual, contexto)
    if usuario is not None:
        filtradas: list[dict[str, Any]] = []
        for t in candidatas:
            dest = _estado_obj(wf.dsl, t.get("para", ""))
            unid = dest.get("id_unidade_responsavel") if dest else None
            if _usuario_pode_ver_transicao(unid, usuario):
                filtradas.append(t)
        return filtradas, contexto
    return candidatas, contexto


async def executar_transicao(
    db: AsyncSession,
    instance: WorkflowInstance,
    *,
    para: str,
    usuario_id: int | None,
    contexto_extra: dict[str, Any] | None = None,
) -> WorkflowInstance:
    """Executa transição do estado atual para `para`. Valida origem,
    condição e referência. Cria log + atualiza instance + encerra se
    `para` é estado final.
    """
    if not instance.ativa:
        raise WorkflowEngineError("Instance já finalizada")

    wf = await _load_definition(db, instance.id_workflow_definition, instance.tenant_id)
    contexto = await compute_contexto(db, instance, contexto_extra)

    # Procura a transição: estado_atual → para, condição satisfeita
    candidatas = _transicoes_do_estado(wf.dsl, instance.estado_atual, contexto)
    selecionada = next((t for t in candidatas if t.get("para") == para), None)
    if selecionada is None:
        # Verifica se a transição existe mas a condição rejeita
        bruta = next(
            (
                t for t in wf.dsl.get("transicoes", [])
                if t.get("de") == instance.estado_atual and t.get("para") == para
            ),
            None,
        )
        if bruta is None:
            raise WorkflowEngineError(
                f"Transição {instance.estado_atual!r} → {para!r} não existe"
            )
        raise WorkflowEngineError(
            f"Transição {instance.estado_atual!r} → {para!r} bloqueada pela condição: "
            f"{bruta.get('condicao')}"
        )

    estado_de = instance.estado_atual
    transicao_label = selecionada.get("label", f"{estado_de}->{para}")

    # Log
    log = WorkflowTransicaoLog(
        tenant_id=instance.tenant_id,
        id_workflow_instance=instance.id,
        estado_de=estado_de,
        estado_para=para,
        transicao_label=transicao_label,
        id_usuario=usuario_id,
        contexto_snapshot=contexto,
        executada_em=datetime.utcnow(),
    )
    db.add(log)

    # Atualiza instance
    instance.estado_atual = para
    destino = _estado_obj(wf.dsl, para)
    if destino is not None and destino.get("final"):
        instance.ativa = False
        instance.finalizada_em = datetime.utcnow()

    # Auto-resolve alertas pendentes do estado que estamos deixando.
    # Fase 21: alerta dura enquanto a instance está parada no estado.
    await db.execute(
        update(WorkflowSlaAlerta)
        .where(
            WorkflowSlaAlerta.id_workflow_instance == instance.id,
            WorkflowSlaAlerta.tenant_id == instance.tenant_id,
            WorkflowSlaAlerta.estado == estado_de,
            WorkflowSlaAlerta.resolvido_em.is_(None),
        )
        .values(resolvido_em=datetime.utcnow(), resolucao="transitado")
    )

    # Workflow↔Org fix: se o estado destino tem unidade responsável diferente
    # do local atual, faz auto-encaminhamento (sem prioridade/prazo — o usuário
    # pode encaminhar manualmente depois se precisar especificar).
    unid_resp = destino.get("id_unidade_responsavel") if destino else None
    if unid_resp is not None:
        processo = await _load_processo(db, instance.id_processo, instance.tenant_id)
        local_atual = processo.id_local_atual or processo.id_unidade_proprietaria
        if int(unid_resp) != int(local_atual):
            await _auto_encaminhar(
                db,
                processo=processo,
                tenant_id=instance.tenant_id,
                id_unidade_destino=int(unid_resp),
                usuario_id=usuario_id,
            )

    await db.commit()
    await db.refresh(instance)
    return instance


async def _auto_encaminhar(
    db: AsyncSession,
    *,
    processo: Processo,
    tenant_id: int,
    id_unidade_destino: int,
    usuario_id: int | None,
) -> None:
    """Encaminhamento programático disparado pelo engine quando uma transição
    entra num estado com `id_unidade_responsavel`. Idempotente em relação a
    encaminhamento pendente: se já há um pendente PARA o mesmo destino, pula;
    se há pendente pra outro destino, cancela antes (auto-cancelamento).

    Cria Movimentacao + Encaminhamento + atualiza `processo.id_local_atual`.
    Sem prioridade explícita (pega prioridade 1 — "normal"). Sem despacho.
    """
    from datetime import datetime as _dt

    now = _dt.utcnow()
    origem = processo.id_local_atual or processo.id_unidade_proprietaria

    # Pega encaminhamentos pendentes (não recebido, não cancelado)
    pendentes = (
        await db.execute(
            select(Encaminhamento).where(
                Encaminhamento.id_processo == processo.id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.excluido.is_(False),
                Encaminhamento.recebido.is_(False),
                Encaminhamento.cancelado.is_(False),
            )
        )
    ).scalars().all()

    for p in pendentes:
        if p.id_unidade_destino == id_unidade_destino:
            # Já tem pra mesmo destino — nada a fazer
            return
        # Cancela o velho — o workflow está sobrescrevendo a direção
        p.cancelado = True

    # Resolve ação ENCAMINHAMENTO
    acao = (
        await db.execute(
            select(Acao).where(Acao.flag == "ENCAMINHAMENTO", Acao.ativo.is_(True))
        )
    ).scalar_one_or_none()
    if acao is None:
        raise WorkflowEngineError(
            "Ação 'ENCAMINHAMENTO' não encontrada — não é possível auto-encaminhar"
        )

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo.id,
        id_unidade_responsavel=origem,
        id_acao=acao.id,
        id_usuario=usuario_id,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()

    encaminhamento = Encaminhamento(
        tenant_id=tenant_id,
        id_processo=processo.id,
        id_unidade_origem=origem,
        id_unidade_destino=id_unidade_destino,
        id_prioridade=1,  # "normal" — convenção
        quantidade_folhas=0,
        data_prazo=None,
        externo=False,
        recebido=False,
        cancelado=False,
        id_usuario=usuario_id,
        id_movimentacao=movimentacao.id,
        ativo=True,
        excluido=False,
    )
    db.add(encaminhamento)
    processo.id_local_atual = id_unidade_destino
    processo.id_ultima_movimentacao = movimentacao.id


def _usuario_pode_ver_transicao(
    estado_destino_unid: int | None, usuario: Usuario | None
) -> bool:
    """Decide se o usuário enxerga uma transição em `transicoes_disponiveis`.

    Regras:
    - Sem `usuario` (chamada do engine sem contexto): mostra tudo (back-compat)
    - Usuário sem `id_unidade_trabalho`: mostra tudo (admins/coordenadores
      sem lotação fixa).
    - Estado destino sem `id_unidade_responsavel`: mostra (transição livre).
    - Caso normal: estado destino com `id_unidade_responsavel` exige usuário
      lotado nessa unidade.
    """
    if usuario is None:
        return True
    if usuario.id_unidade_trabalho is None:
        return True
    if estado_destino_unid is None:
        return True
    return int(usuario.id_unidade_trabalho) == int(estado_destino_unid)


async def migrar_instance(
    db: AsyncSession,
    instance: WorkflowInstance,
    *,
    id_workflow_definition_destino: int,
    mapa_estados: dict[str, str] | None,
    usuario_id: int | None,
) -> WorkflowInstance:
    """Migra uma WorkflowInstance ativa para outra versão do MESMO slug.

    Regras:
    - Instance precisa estar ativa
    - Destino deve ser do mesmo `slug` que a versão atual (não migra cross-WF)
    - Destino deve ter um estado que mapeie do `estado_atual` da instance.
      Se `mapa_estados` não vier, tenta mapa identidade (estado_atual existe
      no destino). Senão erra.
    - Cria entry em `workflow_transicao_log` marcando a migração
      (estado_de=anterior, estado_para=novo no destino, label="MIGRAÇÃO v→v")
      pra rastreabilidade. NÃO encerra alertas SLA (eles continuam válidos no
      novo estado se o mapa preservou).
    """
    if not instance.ativa:
        raise WorkflowEngineError("Instance já finalizada — não pode ser migrada")

    wf_atual = await _load_definition(
        db, instance.id_workflow_definition, instance.tenant_id
    )
    wf_destino = await _load_definition(
        db, id_workflow_definition_destino, instance.tenant_id
    )
    if wf_destino.slug != wf_atual.slug:
        raise WorkflowEngineError(
            f"Destino é de slug diferente ({wf_destino.slug!r} ≠ {wf_atual.slug!r})"
        )
    if wf_destino.id == wf_atual.id:
        raise WorkflowEngineError("Destino é a mesma versão atual da instance")
    if not wf_destino.ativo:
        raise WorkflowEngineError("Destino está inativo")

    # Resolve estado de destino
    estado_atual = instance.estado_atual
    destino_slugs = {e.get("slug") for e in wf_destino.dsl.get("estados", [])}
    if mapa_estados:
        novo_estado = mapa_estados.get(estado_atual)
        if not novo_estado:
            raise WorkflowEngineError(
                f"Mapa não cobre o estado atual {estado_atual!r}"
            )
    else:
        novo_estado = estado_atual  # mapa identidade
    if novo_estado not in destino_slugs:
        raise WorkflowEngineError(
            f"Estado destino {novo_estado!r} não existe na versão "
            f"v{wf_destino.versao}"
        )

    # Log
    log = WorkflowTransicaoLog(
        tenant_id=instance.tenant_id,
        id_workflow_instance=instance.id,
        estado_de=estado_atual,
        estado_para=novo_estado,
        transicao_label=f"MIGRAÇÃO v{wf_atual.versao} → v{wf_destino.versao}",
        id_usuario=usuario_id,
        contexto_snapshot={
            "migracao": True,
            "wf_de": wf_atual.id,
            "wf_para": wf_destino.id,
            "versao_de": wf_atual.versao,
            "versao_para": wf_destino.versao,
            "mapa_estados": mapa_estados or {},
        },
        executada_em=datetime.utcnow(),
    )
    db.add(log)

    # Atualiza instance
    instance.id_workflow_definition = wf_destino.id
    instance.estado_atual = novo_estado

    # Se o novo estado já é final, encerra
    novo_estado_obj = _estado_obj(wf_destino.dsl, novo_estado)
    if novo_estado_obj is not None and novo_estado_obj.get("final"):
        instance.ativa = False
        instance.finalizada_em = datetime.utcnow()

    await db.commit()
    await db.refresh(instance)
    return instance


async def carregar_log(
    db: AsyncSession, instance_id: int, tenant_id: int
) -> list[WorkflowTransicaoLog]:
    rows = (
        await db.execute(
            select(WorkflowTransicaoLog)
            .where(
                WorkflowTransicaoLog.id_workflow_instance == instance_id,
                WorkflowTransicaoLog.tenant_id == tenant_id,
            )
            .order_by(WorkflowTransicaoLog.executada_em.asc())
        )
    ).scalars().all()
    return list(rows)


async def compute_dias_no_estado(
    db: AsyncSession, instance: WorkflowInstance
) -> int:
    """Dias decorridos desde a entrada da instance no estado atual.

    Se já houve transição, conta a partir da última (`executada_em`).
    Se nunca transicionou, conta a partir de `iniciada_em`.
    """
    ultimo_log = (
        await db.execute(
            select(WorkflowTransicaoLog)
            .where(
                WorkflowTransicaoLog.id_workflow_instance == instance.id,
                WorkflowTransicaoLog.tenant_id == instance.tenant_id,
                WorkflowTransicaoLog.estado_para == instance.estado_atual,
            )
            .order_by(WorkflowTransicaoLog.executada_em.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    entrada = ultimo_log.executada_em if ultimo_log else instance.iniciada_em
    return max(0, (datetime.utcnow() - entrada).days)
