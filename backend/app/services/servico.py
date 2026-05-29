"""Catálogo de Serviços — serviço de domínio (PR 4a).

Tudo tenant-scoped. Pontos críticos de segurança:
- `tenant_id` vem sempre do caller (`request.state.tenant_id`), nunca do payload.
- Carga por id filtra `tenant_id` (404 cross-tenant).
- `slug` único por tenant (409).
- Defaults (unidade/tipo/assunto/espécie) validados **same-tenant** — a FK do
  Postgres garante integridade mas NÃO filtra por tenant (igual PR 3b).
- Desativar = soft-delete via `ativo=false`; público só vê `ativo & não excluído`.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    EspecieDocumental,
    Servico,
    TipoProcesso,
    UnidadeTrabalho,
)
from ..schemas.servico import (
    ServicoCreate,
    ServicoPublicOut,
    ServicoUpdate,
)


async def _validar_slug_unico(
    db: AsyncSession, *, tenant_id: int, slug: str, excluir_id: int | None = None
) -> None:
    stmt = select(Servico.id).where(
        Servico.tenant_id == tenant_id, Servico.slug == slug
    )
    if excluir_id is not None:
        stmt = stmt.where(Servico.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um serviço com o slug '{slug}' neste tenant.",
        )


async def _existe_no_tenant(db: AsyncSession, model, id_: int, tenant_id: int) -> bool:
    row = (
        await db.execute(
            select(model.id).where(
                model.id == id_,
                model.tenant_id == tenant_id,
                model.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def _validar_defaults(db: AsyncSession, *, tenant_id: int, dados: dict) -> None:
    """Cada default não nulo deve existir, ser do tenant e não estar excluído."""
    checagens = [
        ("id_unidade_responsavel", UnidadeTrabalho, "Unidade responsável"),
        ("id_tipo_processo_padrao", TipoProcesso, "Tipo de processo padrão"),
        ("id_assunto_padrao", Assunto, "Assunto padrão"),
        ("id_especie_documental_padrao", EspecieDocumental, "Espécie documental padrão"),
    ]
    for campo, model, rotulo in checagens:
        valor = dados.get(campo)
        if valor is not None and not await _existe_no_tenant(db, model, int(valor), tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{rotulo} inválido(a): não existe, não é deste tenant ou está inativo(a).",
            )


async def obter_servico(db: AsyncSession, *, tenant_id: int, servico_id: int) -> Servico:
    servico = (
        await db.execute(
            select(Servico).where(
                Servico.id == servico_id,
                Servico.tenant_id == tenant_id,
                Servico.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if servico is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado"
        )
    return servico


async def listar_servicos(
    db: AsyncSession, *, tenant_id: int, incluir_inativos: bool
) -> list[Servico]:
    stmt = select(Servico).where(
        Servico.tenant_id == tenant_id, Servico.excluido.is_(False)
    )
    if not incluir_inativos:
        stmt = stmt.where(Servico.ativo.is_(True))
    stmt = stmt.order_by(
        Servico.destaque.desc(), Servico.ordem_exibicao, Servico.nome
    )
    return list((await db.execute(stmt)).scalars().all())


async def criar_servico(
    db: AsyncSession, *, tenant_id: int, payload: ServicoCreate
) -> Servico:
    dados = payload.model_dump()  # documentos_exigidos -> list[dict] | None
    await _validar_slug_unico(db, tenant_id=tenant_id, slug=dados["slug"])
    await _validar_defaults(db, tenant_id=tenant_id, dados=dados)

    servico = Servico(tenant_id=tenant_id, criado_em=datetime.utcnow(), **dados)
    db.add(servico)
    await db.commit()
    await db.refresh(servico)
    return servico


async def atualizar_servico(
    db: AsyncSession, *, tenant_id: int, servico_id: int, payload: ServicoUpdate
) -> Servico:
    servico = await obter_servico(db, tenant_id=tenant_id, servico_id=servico_id)
    dados = payload.model_dump(exclude_unset=True)

    if "slug" in dados:
        await _validar_slug_unico(
            db, tenant_id=tenant_id, slug=dados["slug"], excluir_id=servico_id
        )
    await _validar_defaults(db, tenant_id=tenant_id, dados=dados)

    for campo, valor in dados.items():
        setattr(servico, campo, valor)
    servico.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(servico)
    return servico


async def set_ativo(
    db: AsyncSession, *, tenant_id: int, servico_id: int, ativo: bool
) -> Servico:
    servico = await obter_servico(db, tenant_id=tenant_id, servico_id=servico_id)
    servico.ativo = ativo
    servico.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(servico)
    return servico


def _to_public(servico: Servico, unidade_nome: str | None) -> ServicoPublicOut:
    return ServicoPublicOut(
        nome=servico.nome,
        slug=servico.slug,
        descricao_curta=servico.descricao_curta,
        descricao_detalhada=servico.descricao_detalhada,
        publico_alvo=servico.publico_alvo,
        instrucoes_cidadao=servico.instrucoes_cidadao,
        prazo_estimado_dias=servico.prazo_estimado_dias,
        unidade_responsavel=unidade_nome,
        documentos_exigidos=servico.documentos_exigidos,
        categoria=servico.categoria,
        destaque=servico.destaque,
        ordem_exibicao=servico.ordem_exibicao,
        solicitar_habilitado=False,
    )


async def listar_publico(db: AsyncSession, *, tenant_id: int) -> list[ServicoPublicOut]:
    stmt = (
        select(Servico, UnidadeTrabalho.unidade_trabalho)
        .outerjoin(
            UnidadeTrabalho, UnidadeTrabalho.id == Servico.id_unidade_responsavel
        )
        .where(
            Servico.tenant_id == tenant_id,
            Servico.ativo.is_(True),
            Servico.excluido.is_(False),
        )
        .order_by(Servico.destaque.desc(), Servico.ordem_exibicao, Servico.nome)
    )
    rows = (await db.execute(stmt)).all()
    return [_to_public(s, unidade_nome) for s, unidade_nome in rows]


async def obter_publico(
    db: AsyncSession, *, tenant_id: int, slug: str
) -> ServicoPublicOut:
    row = (
        await db.execute(
            select(Servico, UnidadeTrabalho.unidade_trabalho)
            .outerjoin(
                UnidadeTrabalho, UnidadeTrabalho.id == Servico.id_unidade_responsavel
            )
            .where(
                Servico.tenant_id == tenant_id,
                Servico.slug == slug,
                Servico.ativo.is_(True),
                Servico.excluido.is_(False),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado"
        )
    servico, unidade_nome = row
    return _to_public(servico, unidade_nome)
