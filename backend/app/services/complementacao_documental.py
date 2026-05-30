"""Service layer de complementação documental (PR 4d).

Implementa solicitar / responder / cancelar / listar / obter_aberta /
montar_out. `ComplementacaoError(status_code, detail)` é mapeada para
HTTPException nos routers.

Decisões fechadas que valem aqui:

- D-CONCORRENCIA: 1 `aberta` viva por processo (verificação + índice único
  parcial na migration 0027 + **transição atômica** via
  `UPDATE ... WHERE status='aberta' RETURNING *` em responder/cancelar —
  PR 4d-fix).
- D-RESPOSTA: cidadão responde via ação explícita; **não** exige docs
  completos.
- D-AUDIT: mensagem/motivo nunca vão pro audit (ficam só na tabela, sob RLS).

LGPD — decisão sobre `documentos_solicitados_keys` no audit (PR 4d-fix):
mantida no payload do evento `complementacao.solicitada`. Justificativa:
são *slugs técnicos estáveis* (gerados de `slugify(nome)` em `servico.py`,
PR 4a/4c), não descrições livres nem dados do cidadão. Não é registrado:
CPF, nome do cidadão, mensagem do servidor, motivo de cancelamento, nome
de arquivo, conteúdo. Se no futuro as keys passarem a derivar de algo
sensível, trocar por contagem ou hash.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Anexo,
    AnexoProcesso,
    ComplementacaoDocumental,
    Processo,
    Servico,
    Usuario,
)
from ..schemas.complementacao_documental import (
    ComplementacaoDocSolicitadoOut,
    ComplementacaoOut,
)
from .audit import log as audit_log


class ComplementacaoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _now() -> datetime:
    return datetime.utcnow()


async def _carregar_processo(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> Processo:
    proc = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if proc is None:
        raise ComplementacaoError(404, "Processo não encontrado")
    return proc


async def _carregar_keys_validas(
    db: AsyncSession, *, tenant_id: int, processo: Processo
) -> set[str]:
    """Lê documentos_exigidos do serviço vinculado ao processo e devolve o
    conjunto de keys válidas. Levanta 400 se processo não tem serviço ou se o
    serviço não tem docs exigidos."""
    if processo.id_servico is None:
        raise ComplementacaoError(
            400,
            "Processo sem serviço — não há documentos exigidos para complementação.",
        )
    servico = (
        await db.execute(
            select(Servico).where(
                Servico.id == processo.id_servico,
                Servico.tenant_id == tenant_id,
                Servico.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    docs = (servico.documentos_exigidos if servico else None) or []
    keys = {
        d["key"]
        for d in docs
        if isinstance(d, dict) and d.get("key")
    }
    if not keys:
        raise ComplementacaoError(400, "Serviço sem documentos exigidos.")
    return keys


async def _carregar_docs_servico_indexados(
    db: AsyncSession, *, tenant_id: int, processo: Processo
) -> dict[str, dict[str, Any]]:
    """Versão "rica" do _carregar_keys_validas: devolve dict key → item completo
    (nome, descricao, ...) para o serializador montar `documentos_solicitados`
    com `nome` legível. Devolve {} se processo não tem serviço."""
    if processo.id_servico is None:
        return {}
    servico = (
        await db.execute(
            select(Servico).where(
                Servico.id == processo.id_servico,
                Servico.tenant_id == tenant_id,
                Servico.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    docs = (servico.documentos_exigidos if servico else None) or []
    out: dict[str, dict[str, Any]] = {}
    for d in docs:
        if isinstance(d, dict) and d.get("key"):
            out[d["key"]] = d
    return out


async def _carregar_anexos_por_key(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> set[str]:
    """Conjunto de `documento_exigido_key` que têm pelo menos um anexo vivo
    no processo. Reusa a mesma lógica do checklist (PR 4c)."""
    anexos = (
        await db.execute(
            select(Anexo.documento_exigido_key)
            .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
            .where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalars().all()
    return {k for k in anexos if k}


async def _existe_aberta(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> bool:
    row = (
        await db.execute(
            select(ComplementacaoDocumental.id).where(
                ComplementacaoDocumental.tenant_id == tenant_id,
                ComplementacaoDocumental.id_processo == processo_id,
                ComplementacaoDocumental.status == "aberta",
                ComplementacaoDocumental.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def solicitar(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    id_usuario_solicitante: int,
    mensagem: str,
    documentos_solicitados_keys: list[str],
) -> ComplementacaoDocumental:
    """Servidor abre nova complementação. Valida processo + serviço + keys +
    concorrência (1 aberta por processo)."""
    proc = await _carregar_processo(db, tenant_id=tenant_id, processo_id=processo_id)
    keys_validas = await _carregar_keys_validas(
        db, tenant_id=tenant_id, processo=proc
    )

    # Dedup preservando ordem.
    solicitadas: list[str] = list(dict.fromkeys(documentos_solicitados_keys))
    if not solicitadas:
        raise ComplementacaoError(400, "Selecione ao menos um documento.")
    invalidas = [k for k in solicitadas if k not in keys_validas]
    if invalidas:
        raise ComplementacaoError(
            400, f"Documento(s) inválido(s) para este serviço: {invalidas}"
        )

    if await _existe_aberta(db, tenant_id=tenant_id, processo_id=processo_id):
        raise ComplementacaoError(
            409, "Já existe complementação aberta para este processo."
        )

    now = _now()
    comp = ComplementacaoDocumental(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_usuario_solicitante=id_usuario_solicitante,
        status="aberta",
        mensagem=mensagem,
        documentos_solicitados=[{"key": k} for k in solicitadas],
        criado_em=now,
        atualizado_em=None,
        respondido_em=None,
        cancelado_em=None,
        excluido=False,
    )
    db.add(comp)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ComplementacaoError(
            409, "Já existe complementação aberta para este processo."
        ) from exc

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=id_usuario_solicitante,
        acao="complementacao.solicitada",
        entidade="complementacao_documental",
        id_entidade=comp.id,
        payload={
            "id_processo": processo_id,
            "id_complementacao": comp.id,
            "documentos_solicitados_keys": solicitadas,
            "canal": "interno",
            "id_usuario_responsavel": id_usuario_solicitante,
        },
    )
    return comp


async def responder(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    complementacao_id: int,
) -> ComplementacaoDocumental:
    """Cidadão marca complementação como respondida.

    Não valida quantidade de anexos — D-RESPOSTA: cidadão decide quando
    fechar; servidor avalia suficiência depois.

    Transição **atômica** via `UPDATE ... WHERE status='aberta' RETURNING *`:
    se duas transações concorrentes tentarem responder/cancelar a mesma
    complementação, apenas a primeira faz o UPDATE; a segunda recebe 0
    linhas e levanta 409 — sem emitir audit_log fantasma (PR 4d-fix).
    """
    now = _now()
    stmt = (
        update(ComplementacaoDocumental)
        .where(
            ComplementacaoDocumental.id == complementacao_id,
            ComplementacaoDocumental.id_processo == processo_id,
            ComplementacaoDocumental.tenant_id == tenant_id,
            ComplementacaoDocumental.excluido.is_(False),
            ComplementacaoDocumental.status == "aberta",
        )
        .values(
            status="respondida",
            respondido_em=now,
            atualizado_em=now,
        )
        .returning(ComplementacaoDocumental)
        .execution_options(synchronize_session="fetch")
    )
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if comp is None:
        # 0 linhas alteradas: ou a linha não existe (404), ou existe mas o
        # status já não é "aberta" / está excluída (409). Diagnostica.
        existente = (
            await db.execute(
                select(ComplementacaoDocumental.id).where(
                    ComplementacaoDocumental.id == complementacao_id,
                    ComplementacaoDocumental.id_processo == processo_id,
                    ComplementacaoDocumental.tenant_id == tenant_id,
                    ComplementacaoDocumental.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existente is None:
            raise ComplementacaoError(404, "Complementação não encontrada")
        raise ComplementacaoError(409, "Complementação não está aberta.")

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=None,
        acao="complementacao.respondida",
        entidade="complementacao_documental",
        id_entidade=comp.id,
        payload={
            "id_processo": processo_id,
            "id_complementacao": comp.id,
            "canal": "portal",
        },
    )
    return comp


async def cancelar(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    complementacao_id: int,
    id_usuario_responsavel: int,
    motivo: str | None,
) -> ComplementacaoDocumental:
    """Servidor cancela complementação aberta.

    Transição **atômica** via `UPDATE ... WHERE status='aberta' RETURNING *`
    (mesma garantia de `responder`): se duas transações concorrentes
    tentarem responder/cancelar a mesma complementação, apenas a primeira
    faz o UPDATE; a segunda recebe 0 linhas e levanta 409 — sem audit_log
    fantasma (PR 4d-fix).
    """
    now = _now()
    stmt = (
        update(ComplementacaoDocumental)
        .where(
            ComplementacaoDocumental.id == complementacao_id,
            ComplementacaoDocumental.id_processo == processo_id,
            ComplementacaoDocumental.tenant_id == tenant_id,
            ComplementacaoDocumental.excluido.is_(False),
            ComplementacaoDocumental.status == "aberta",
        )
        .values(
            status="cancelada",
            cancelado_em=now,
            atualizado_em=now,
            motivo_cancelamento=motivo,
        )
        .returning(ComplementacaoDocumental)
        .execution_options(synchronize_session="fetch")
    )
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if comp is None:
        existente = (
            await db.execute(
                select(ComplementacaoDocumental.id).where(
                    ComplementacaoDocumental.id == complementacao_id,
                    ComplementacaoDocumental.id_processo == processo_id,
                    ComplementacaoDocumental.tenant_id == tenant_id,
                    ComplementacaoDocumental.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existente is None:
            raise ComplementacaoError(404, "Complementação não encontrada")
        raise ComplementacaoError(409, "Complementação não está aberta.")

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=id_usuario_responsavel,
        acao="complementacao.cancelada",
        entidade="complementacao_documental",
        id_entidade=comp.id,
        payload={
            "id_processo": processo_id,
            "id_complementacao": comp.id,
            "canal": "interno",
            "id_usuario_responsavel": id_usuario_responsavel,
        },
    )
    return comp


async def listar(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> list[ComplementacaoDocumental]:
    rows = (
        await db.execute(
            select(ComplementacaoDocumental)
            .where(
                ComplementacaoDocumental.tenant_id == tenant_id,
                ComplementacaoDocumental.id_processo == processo_id,
                ComplementacaoDocumental.excluido.is_(False),
            )
            .order_by(ComplementacaoDocumental.criado_em.desc())
        )
    ).scalars().all()
    return list(rows)


async def obter_aberta(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> ComplementacaoDocumental | None:
    return (
        await db.execute(
            select(ComplementacaoDocumental)
            .where(
                ComplementacaoDocumental.tenant_id == tenant_id,
                ComplementacaoDocumental.id_processo == processo_id,
                ComplementacaoDocumental.status == "aberta",
                ComplementacaoDocumental.excluido.is_(False),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def montar_out(
    db: AsyncSession,
    comp: ComplementacaoDocumental,
    *,
    docs_servico_idx: dict[str, dict[str, Any]] | None = None,
    keys_enviadas: set[str] | None = None,
) -> ComplementacaoOut:
    """Serializa `Comp` cruzando com docs do serviço (para `nome`/`descricao`)
    e com anexos (para `enviado`). Carrega `nome_solicitante` se necessário.

    `docs_servico_idx` e `keys_enviadas` são caches que o caller pode passar
    para evitar refetch. Quando omitidos, o helper resolve sozinho.
    """
    # Carregamentos preguiçosos só se o caller não passou.
    if docs_servico_idx is None:
        proc = await _carregar_processo(
            db, tenant_id=comp.tenant_id, processo_id=comp.id_processo
        )
        docs_servico_idx = await _carregar_docs_servico_indexados(
            db, tenant_id=comp.tenant_id, processo=proc
        )
    if keys_enviadas is None:
        keys_enviadas = await _carregar_anexos_por_key(
            db, tenant_id=comp.tenant_id, processo_id=comp.id_processo
        )

    nome_solicitante: str | None = None
    if comp.id_usuario_solicitante:
        nome_solicitante = (
            await db.execute(
                select(Usuario.nome).where(Usuario.id == comp.id_usuario_solicitante)
            )
        ).scalar_one_or_none()

    itens: list[ComplementacaoDocSolicitadoOut] = []
    for d in comp.documentos_solicitados or []:
        if not isinstance(d, dict) or not d.get("key"):
            continue
        k = d["key"]
        meta = docs_servico_idx.get(k, {})
        itens.append(
            ComplementacaoDocSolicitadoOut(
                key=k,
                nome=str(meta.get("nome") or k),
                descricao=meta.get("descricao"),
                enviado=k in keys_enviadas,
            )
        )

    return ComplementacaoOut(
        id=comp.id,
        status=comp.status,  # type: ignore[arg-type]
        mensagem=comp.mensagem,
        documentos_solicitados=itens,
        id_usuario_solicitante=comp.id_usuario_solicitante,
        nome_solicitante=nome_solicitante,
        criado_em=comp.criado_em,
        atualizado_em=comp.atualizado_em,
        respondido_em=comp.respondido_em,
        cancelado_em=comp.cancelado_em,
        motivo_cancelamento=comp.motivo_cancelamento,
    )


async def listar_out(
    db: AsyncSession, *, tenant_id: int, processo_id: int
) -> list[ComplementacaoOut]:
    """Lista complementações já serializadas, reaproveitando caches por processo."""
    rows = await listar(db, tenant_id=tenant_id, processo_id=processo_id)
    proc = await _carregar_processo(db, tenant_id=tenant_id, processo_id=processo_id)
    docs_idx = await _carregar_docs_servico_indexados(
        db, tenant_id=tenant_id, processo=proc
    )
    keys_env = await _carregar_anexos_por_key(
        db, tenant_id=tenant_id, processo_id=processo_id
    )
    return [
        await montar_out(db, r, docs_servico_idx=docs_idx, keys_enviadas=keys_env)
        for r in rows
    ]
