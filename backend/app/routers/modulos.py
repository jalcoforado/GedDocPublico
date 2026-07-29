"""Módulos disponíveis ao usuário logado.

Regra (spec §3, D1): módulo aparece se o TENANT o contratou E o usuário tem
alguma transação dele. As tabelas legadas do PHP (public.modulos,
public.configuracoes_modulos) não são mais lidas — saem do ORM na fatia F4.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Modulo, ModuloTransacao, Transacao, Usuario
from ..schemas.modulo import ModuloOut, ModulosMeResponse
from ..services.modulos import slugs_contratados
from ..services.permissoes import load_permissions

router = APIRouter(prefix="/modulos", tags=["modulos"])


@router.get("/me", response_model=ModulosMeResponse)
async def me(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ModulosMeResponse:
    disponiveis = await slugs_contratados(db, tenant_id)
    perms = await load_permissions(db, user.id, tenant_id=tenant_id)
    codigos = {p.codigo for p in perms.items}

    # Slug -> códigos de transação daquele módulo.
    linhas = (await db.execute(
        select(Modulo, Transacao.codigo)
        .join(ModuloTransacao, ModuloTransacao.id_modulo == Modulo.id)
        .join(Transacao, Transacao.id == ModuloTransacao.id_transacao)
        .where(Modulo.contratavel.is_(True), Modulo.ativo.is_(True))
        .order_by(Modulo.ordem)
    )).all()

    vistos: dict[str, Modulo] = {}
    for modulo, codigo in linhas:
        if modulo.slug not in disponiveis:
            continue
        if codigo in codigos and modulo.slug not in vistos:
            vistos[modulo.slug] = modulo

    itens = [
        ModuloOut(slug=m.slug, nome=m.nome, icone=m.icone, ordem=m.ordem)
        for m in sorted(vistos.values(), key=lambda m: m.ordem)
    ]
    return ModulosMeResponse(itens=itens)
