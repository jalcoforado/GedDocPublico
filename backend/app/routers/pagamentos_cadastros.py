"""Rotas dos cadastros de Pagamentos (PAG-1) — só Credor por enquanto."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    AlcadaCreate, AlcadaOut, AlcadaUpdate,
    ContaCreate, ContaOut, ContaUpdate,
    ContratoCreate, ContratoOut, ContratoUpdate,
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


contas_router = APIRouter(prefix="/pagamentos/contas", tags=["pagamentos-cadastros"])


@contas_router.get("", response_model=list[ContaOut])
async def list_contas(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return [ContaOut.model_validate(r) for r in await svc.listar_contas(db, tenant_id=tenant_id)]


@contas_router.get("/{conta_id}", response_model=ContaOut)
async def get_conta(conta_id: int,
                    _: Usuario = Depends(require_permission("pagamento_cadastro")),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    return ContaOut.model_validate(await svc.obter_conta(db, tenant_id=tenant_id, conta_id=conta_id))


@contas_router.post("", response_model=ContaOut, status_code=status.HTTP_201_CREATED)
async def create_conta(payload: ContaCreate,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return ContaOut.model_validate(await svc.criar_conta(db, tenant_id=tenant_id, payload=payload))


@contas_router.put("/{conta_id}", response_model=ContaOut)
async def update_conta(conta_id: int, payload: ContaUpdate,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return ContaOut.model_validate(
        await svc.atualizar_conta(db, tenant_id=tenant_id, conta_id=conta_id, payload=payload))


@contas_router.delete("/{conta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conta(conta_id: int,
                       _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    await svc.excluir_conta(db, tenant_id=tenant_id, conta_id=conta_id)


contratos_router = APIRouter(prefix="/pagamentos/contratos", tags=["pagamentos-cadastros"])


@contratos_router.get("", response_model=list[ContratoOut])
async def list_contratos(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return [ContratoOut.model_validate(r) for r in await svc.listar_contratos(db, tenant_id=tenant_id)]


@contratos_router.get("/{contrato_id}", response_model=ContratoOut)
async def get_contrato(contrato_id: int,
                       _: Usuario = Depends(require_permission("pagamento_cadastro")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return ContratoOut.model_validate(
        await svc.obter_contrato(db, tenant_id=tenant_id, contrato_id=contrato_id))


@contratos_router.post("", response_model=ContratoOut, status_code=status.HTTP_201_CREATED)
async def create_contrato(payload: ContratoCreate,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return ContratoOut.model_validate(await svc.criar_contrato(db, tenant_id=tenant_id, payload=payload))


@contratos_router.put("/{contrato_id}", response_model=ContratoOut)
async def update_contrato(contrato_id: int, payload: ContratoUpdate,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return ContratoOut.model_validate(
        await svc.atualizar_contrato(db, tenant_id=tenant_id, contrato_id=contrato_id, payload=payload))


@contratos_router.delete("/{contrato_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contrato(contrato_id: int,
                          _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    await svc.excluir_contrato(db, tenant_id=tenant_id, contrato_id=contrato_id)


alcadas_router = APIRouter(prefix="/pagamentos/alcadas", tags=["pagamentos-cadastros"])


@alcadas_router.get("", response_model=list[AlcadaOut])
async def list_alcadas(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    return [AlcadaOut.model_validate(r) for r in await svc.listar_alcadas(db, tenant_id=tenant_id)]


@alcadas_router.get("/{alcada_id}", response_model=AlcadaOut)
async def get_alcada(alcada_id: int,
                     _: Usuario = Depends(require_permission("pagamento_cadastro")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    return AlcadaOut.model_validate(await svc.obter_alcada(db, tenant_id=tenant_id, alcada_id=alcada_id))


@alcadas_router.post("", response_model=AlcadaOut, status_code=status.HTTP_201_CREATED)
async def create_alcada(payload: AlcadaCreate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    return AlcadaOut.model_validate(await svc.criar_alcada(db, tenant_id=tenant_id, payload=payload))


@alcadas_router.put("/{alcada_id}", response_model=AlcadaOut)
async def update_alcada(alcada_id: int, payload: AlcadaUpdate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    return AlcadaOut.model_validate(
        await svc.atualizar_alcada(db, tenant_id=tenant_id, alcada_id=alcada_id, payload=payload))


@alcadas_router.delete("/{alcada_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alcada(alcada_id: int,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    await svc.excluir_alcada(db, tenant_id=tenant_id, alcada_id=alcada_id)


enums_router = APIRouter(prefix="/pagamentos/enums", tags=["pagamentos-cadastros"])


@enums_router.get("")
async def get_enums(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                    __: int = Depends(require_tenant_id)):
    from ..models import Criticidade, GrupoDespesa
    return {"criticidade": [e.value for e in Criticidade], "grupo_despesa": [e.value for e in GrupoDespesa]}
