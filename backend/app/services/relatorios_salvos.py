"""Relatórios salvos (SI-35) — os "meus relatórios" de cada pessoa.

Toda carga filtra `tenant_id` E `id_usuario`: o relatório de outra pessoa (ou
de outra prefeitura) é 404, nunca 403 — 403 confirmaria que existe. É o erro
que o download de jobs tem hoje (card à parte); aqui nasce com teste.

O que se guarda é só a definição. Ela é validada ao salvar (schema fechado) e
de novo ao abrir (`relatorios_montado.normalizar_definicao`), porque o
catálogo de colunas pode mudar entre um e outro.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RelatorioSalvo
from ..schemas.relatorio_montado import (
    RelatorioSalvoAtualizar,
    RelatorioSalvoCriar,
    RelatorioSalvoOut,
    RelatorioSalvoResumo,
)
from ..utils.relogio import agora_utc
from .relatorios_comum import hora_local
from .relatorios_montado import normalizar_definicao

MAX_POR_PESSOA = 50


def _nao_encontrado() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relatório não encontrado.")


async def _carregar(db: AsyncSession, id_: int, *, tenant_id: int, id_usuario: int) -> RelatorioSalvo:
    r = (
        await db.execute(
            select(RelatorioSalvo).where(
                RelatorioSalvo.id == id_,
                RelatorioSalvo.tenant_id == tenant_id,
                RelatorioSalvo.id_usuario == id_usuario,
            )
        )
    ).scalar_one_or_none()
    if r is None:
        raise _nao_encontrado()
    return r


async def _nome_livre(
    db: AsyncSession, nome: str, *, tenant_id: int, id_usuario: int, exceto: int | None = None
) -> None:
    stmt = select(RelatorioSalvo.id).where(
        RelatorioSalvo.tenant_id == tenant_id,
        RelatorioSalvo.id_usuario == id_usuario,
        func.lower(RelatorioSalvo.nome) == nome.lower(),
    )
    if exceto is not None:
        stmt = stmt.where(RelatorioSalvo.id != exceto)
    if (await db.execute(stmt)).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Você já tem um relatório chamado "{nome}". Escolha outro nome.',
        )


def _resumo(r: RelatorioSalvo) -> RelatorioSalvoResumo:
    return RelatorioSalvoResumo(
        id=r.id, nome=r.nome,
        criado_em=hora_local(r.criado_em), atualizado_em=hora_local(r.atualizado_em),
    )


def _out(r: RelatorioSalvo) -> RelatorioSalvoOut:
    definicao, avisos = normalizar_definicao(r.definicao)
    if definicao is None:
        # Não dá para abrir; a pessoa remonta. 409: o recurso existe, mas o
        # estado dele não permite a operação.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=" ".join(avisos))
    return RelatorioSalvoOut(**_resumo(r).model_dump(), definicao=definicao, avisos=avisos)


async def listar(db: AsyncSession, *, tenant_id: int, id_usuario: int) -> list[RelatorioSalvoResumo]:
    rows = (
        await db.execute(
            select(RelatorioSalvo)
            .where(RelatorioSalvo.tenant_id == tenant_id, RelatorioSalvo.id_usuario == id_usuario)
            .order_by(func.lower(RelatorioSalvo.nome), RelatorioSalvo.id)
        )
    ).scalars().all()
    return [_resumo(r) for r in rows]


async def obter(db: AsyncSession, id_: int, *, tenant_id: int, id_usuario: int) -> RelatorioSalvoOut:
    return _out(await _carregar(db, id_, tenant_id=tenant_id, id_usuario=id_usuario))


async def criar(
    db: AsyncSession, dados: RelatorioSalvoCriar, *, tenant_id: int, id_usuario: int
) -> RelatorioSalvoOut:
    qtd = (
        await db.execute(
            select(func.count()).where(
                RelatorioSalvo.tenant_id == tenant_id, RelatorioSalvo.id_usuario == id_usuario
            )
        )
    ).scalar_one()
    if qtd >= MAX_POR_PESSOA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Você já tem {MAX_POR_PESSOA} relatórios salvos. Exclua algum para salvar outro.",
        )
    await _nome_livre(db, dados.nome, tenant_id=tenant_id, id_usuario=id_usuario)
    agora = agora_utc()
    r = RelatorioSalvo(
        tenant_id=tenant_id,
        id_usuario=id_usuario,
        nome=dados.nome,
        definicao=dados.definicao.model_dump(mode="json"),
        criado_em=agora,
        atualizado_em=agora,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _out(r)


async def atualizar(
    db: AsyncSession, id_: int, dados: RelatorioSalvoAtualizar, *, tenant_id: int, id_usuario: int
) -> RelatorioSalvoOut:
    r = await _carregar(db, id_, tenant_id=tenant_id, id_usuario=id_usuario)
    if dados.nome is not None and dados.nome != r.nome:
        await _nome_livre(db, dados.nome, tenant_id=tenant_id, id_usuario=id_usuario, exceto=r.id)
        r.nome = dados.nome
    if dados.definicao is not None:
        r.definicao = dados.definicao.model_dump(mode="json")
    r.atualizado_em = agora_utc()
    await db.commit()
    await db.refresh(r)
    return _out(r)


async def excluir(db: AsyncSession, id_: int, *, tenant_id: int, id_usuario: int) -> None:
    r = await _carregar(db, id_, tenant_id=tenant_id, id_usuario=id_usuario)
    await db.delete(r)
    await db.commit()
