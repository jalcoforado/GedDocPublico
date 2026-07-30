"""Catálogo de módulos, contratação por tenant e derivação de bloqueios.

O catálogo (`Modulo`, `ModuloTransacao`) é GLOBAL — sem tenant_id, por decisão
de design: módulo é do produto, não da prefeitura. A contratação
(`TenantModulo`) é por tenant e NÃO tem RLS (spec §4.1): quem escreve é o
platform admin, operando sobre outros tenants. Por isso toda leitura aqui
filtra `tenant_id` explicitamente em código — é a única barreira que existe.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Modulo, ModuloTransacao, TenantModulo, Transacao


async def slugs_contratados(db: AsyncSession, tenant_id: int) -> set[str]:
    """Slugs disponíveis ao tenant: os contratados + os não-contratáveis.

    Módulo com `contratavel = false` (hoje só `comum`) é infraestrutura, não
    produto: está sempre disponível e nunca é bloqueado.
    """
    stmt = (
        select(Modulo.slug)
        .join(TenantModulo, TenantModulo.id_modulo == Modulo.id)
        .where(
            TenantModulo.tenant_id == tenant_id,
            TenantModulo.excluido.is_(False),
            TenantModulo.ativo.is_(True),
            Modulo.ativo.is_(True),
        )
    )
    contratados = set((await db.execute(stmt)).scalars().all())

    implicitos = set((await db.execute(
        select(Modulo.slug).where(
            Modulo.contratavel.is_(False), Modulo.ativo.is_(True)
        )
    )).scalars().all())

    return contratados | implicitos


async def codigos_bloqueados(db: AsyncSession, tenant_id: int) -> set[str]:
    """Códigos de transação de módulos NÃO disponíveis ao tenant.

    Transação sem vínculo de módulo NÃO entra aqui — é fail-open deliberado
    (spec §3, D8). O teste test_toda_transacao_tem_modulo garante que o
    esquecimento apareça no CI em vez de virar tela sumida em produção.
    """
    disponiveis = await slugs_contratados(db, tenant_id)
    if not disponiveis:
        # `Modulo.slug.not_in(set())` compila para uma cláusula sempre
        # verdadeira — sem essa guarda, catálogo corrompido (ex.: 'comum'
        # inativo) faria este WHERE parar de filtrar e devolver TODOS os
        # códigos de TODOS os módulos, bloqueando todo mundo em silêncio.
        raise RuntimeError(
            "Nenhum módulo disponível para o tenant "
            f"{tenant_id} — nem os não-contratáveis. Isso indica catálogo "
            "corrompido (verifique se 'comum' existe e está ativo). Abortando "
            "em vez de bloquear todas as transações silenciosamente."
        )
    stmt = (
        select(Transacao.codigo)
        .join(ModuloTransacao, ModuloTransacao.id_transacao == Transacao.id)
        .join(Modulo, Modulo.id == ModuloTransacao.id_modulo)
        .where(Modulo.slug.not_in(disponiveis))
    )
    return set((await db.execute(stmt)).scalars().all())


async def modulos_do_tenant(db: AsyncSession, tenant_id: int) -> list[dict]:
    """Catálogo contratável com a flag de contratação do tenant. Para o admin.

    Não filtra `Modulo.ativo` na listagem nem no cálculo de `contratado`: o
    admin precisa enxergar — e poder descontratar — um módulo que o tenant
    já tinha contratado e que depois virou inativo. Por isso `contratado`
    aqui é calculado a partir do vínculo vivo em `tenant_modulo`
    diretamente, e NÃO via `slugs_contratados` — aquela função responde
    "está disponível para uso" (filtra `Modulo.ativo`, de propósito, para
    `codigos_bloqueados`); esta responde "o tenant tem contrato", que são
    perguntas diferentes. Um módulo pode estar contratado e, ao mesmo
    tempo, indisponível por ter sido desativado na plataforma.
    """
    vinculos_vivos = set((await db.execute(
        select(Modulo.slug)
        .join(TenantModulo, TenantModulo.id_modulo == Modulo.id)
        .where(
            TenantModulo.tenant_id == tenant_id,
            TenantModulo.excluido.is_(False),
            TenantModulo.ativo.is_(True),
        )
    )).scalars().all())
    modulos = (await db.execute(
        select(Modulo)
        .where(Modulo.contratavel.is_(True))
        .order_by(Modulo.ordem)
    )).scalars().all()
    return [
        {
            "id": m.id,
            "slug": m.slug,
            "nome": m.nome,
            "icone": m.icone,
            "ordem": m.ordem,
            "contratado": m.slug in vinculos_vivos,
            "ativo": m.ativo,
        }
        for m in modulos
    ]


async def contratar(db: AsyncSession, tenant_id: int, slugs: list[str]) -> None:
    """Reconcilia a contratação do tenant com a lista de slugs.

    Contrata o que falta (reaproveitando linha soft-deletada, se houver) e
    marca `excluido = True` no que saiu. Nunca apaga: descontratar suspende o
    acesso, não destrói o que o módulo produziu.

    O catálogo aqui NÃO filtra `Modulo.ativo` — descontratar precisa
    alcançar até módulo inativo (senão o vínculo fica preso, contratado
    para sempre). Só a contratação de um módulo inativo é recusada.
    """
    alvo = set(slugs)
    catalogo = {
        m.slug: m
        for m in (await db.execute(
            select(Modulo).where(Modulo.contratavel.is_(True))
        )).scalars().all()
    }
    desconhecidos = alvo - set(catalogo)
    if desconhecidos:
        raise ValueError(f"Módulo inexistente ou não contratável: {sorted(desconhecidos)}")

    inativos = {s for s in alvo if not catalogo[s].ativo}
    if inativos:
        raise ValueError(f"Módulo inativo não pode ser contratado: {sorted(inativos)}")

    vinculos = {
        v.id_modulo: v
        for v in (await db.execute(
            select(TenantModulo).where(TenantModulo.tenant_id == tenant_id)
        )).scalars().all()
    }

    for slug, modulo in catalogo.items():
        vinculo = vinculos.get(modulo.id)
        quer = slug in alvo
        if vinculo is None:
            if quer:
                db.add(TenantModulo(tenant_id=tenant_id, id_modulo=modulo.id))
        else:
            vinculo.excluido = not quer
            vinculo.ativo = quer


async def contratar_modulos_iniciais(
    db: AsyncSession, tenant_id: int, slugs: list[str] | None
) -> list[str]:
    """Contrata os módulos iniciais de um tenant recém-provisionado.

    `None` significa "todos os contratáveis e ativos" — default deliberado: o
    comportamento histórico de `provisionar_tenant` é entregar o sistema
    inteiro, e mudá-lo em silêncio quebraria quem já provisiona.

    O default filtra `ativo` porque `contratar()` recusa módulo inativo: sem o
    filtro, desativar um módulo no catálogo passaria a derrubar todo
    provisionamento novo.
    """
    if slugs is None:
        slugs = list((await db.execute(
            select(Modulo.slug).where(
                Modulo.contratavel.is_(True), Modulo.ativo.is_(True)
            )
        )).scalars().all())
    await contratar(db, tenant_id, slugs)
    return slugs
