"""Rotas dos cadastros de Pagamentos (PAG-1) — só Credor por enquanto."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    CredorCreate, CredorDadosBancariosOut, CredorOut, CredorUpdate,
    FonteCreate, FonteOut, FonteUpdate, NaturezaCreate, NaturezaOut, NaturezaUpdate,
)
from ..services import pagamentos_cadastros as svc

credores_router = APIRouter(prefix="/pagamentos/credores", tags=["pagamentos-cadastros"])


@credores_router.get("", response_model=list[CredorOut])
async def list_credores(q: str | None = None,
                        _: Usuario = Depends(require_permission("pagamento_cadastro")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    rows = await svc.listar_credores(db, tenant_id=tenant_id, q=q)
    return [CredorOut.model_validate(svc.credor_out(r)) for r in rows]


@credores_router.get("/{credor_id}", response_model=CredorOut)
async def get_credor(credor_id: int,
                     _: Usuario = Depends(require_permission("pagamento_cadastro")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    c = await svc.obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.get("/{credor_id}/dados-bancarios", response_model=CredorDadosBancariosOut)
async def get_dados_bancarios(credor_id: int,
                              _: Usuario = Depends(require_permission("pagamento_cadastro")),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    return await svc.dados_bancarios_credor(db, tenant_id=tenant_id, credor_id=credor_id)


@credores_router.post("", response_model=CredorOut, status_code=status.HTTP_201_CREATED)
async def create_credor(payload: CredorCreate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    c = await svc.criar_credor(db, tenant_id=tenant_id, payload=payload)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.put("/{credor_id}", response_model=CredorOut)
async def update_credor(credor_id: int, payload: CredorUpdate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    c = await svc.atualizar_credor(db, tenant_id=tenant_id, credor_id=credor_id, payload=payload)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.delete("/{credor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credor(credor_id: int,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    await svc.excluir_credor(db, tenant_id=tenant_id, credor_id=credor_id)


naturezas_router = APIRouter(prefix="/pagamentos/naturezas", tags=["pagamentos-cadastros"])


@naturezas_router.get("", response_model=list[NaturezaOut])
async def list_naturezas(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return [NaturezaOut.model_validate(r) for r in await svc.listar_naturezas(db, tenant_id=tenant_id)]


@naturezas_router.get("/{natureza_id}", response_model=NaturezaOut)
async def get_natureza(natureza_id: int,
                       _: Usuario = Depends(require_permission("pagamento_cadastro")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return NaturezaOut.model_validate(
        await svc.obter_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id))


@naturezas_router.post("", response_model=NaturezaOut, status_code=status.HTTP_201_CREATED)
async def create_natureza(payload: NaturezaCreate,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return NaturezaOut.model_validate(
        await svc.criar_natureza(db, tenant_id=tenant_id, payload=payload))


@naturezas_router.put("/{natureza_id}", response_model=NaturezaOut)
async def update_natureza(natureza_id: int, payload: NaturezaUpdate,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return NaturezaOut.model_validate(
        await svc.atualizar_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id, payload=payload))


@naturezas_router.delete("/{natureza_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_natureza(natureza_id: int,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    await svc.excluir_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)


fontes_router = APIRouter(prefix="/pagamentos/fontes", tags=["pagamentos-cadastros"])


@fontes_router.get("", response_model=list[FonteOut])
async def list_fontes(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return [FonteOut.model_validate(r) for r in await svc.listar_fontes(db, tenant_id=tenant_id)]


@fontes_router.get("/{fonte_id}", response_model=FonteOut)
async def get_fonte(fonte_id: int,
                    _: Usuario = Depends(require_permission("pagamento_cadastro")),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    return FonteOut.model_validate(await svc.obter_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id))


@fontes_router.post("", response_model=FonteOut, status_code=status.HTTP_201_CREATED)
async def create_fonte(payload: FonteCreate,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return FonteOut.model_validate(await svc.criar_fonte(db, tenant_id=tenant_id, payload=payload))


@fontes_router.put("/{fonte_id}", response_model=FonteOut)
async def update_fonte(fonte_id: int, payload: FonteUpdate,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return FonteOut.model_validate(
        await svc.atualizar_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id, payload=payload))


@fontes_router.delete("/{fonte_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fonte(fonte_id: int,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    await svc.excluir_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id)
