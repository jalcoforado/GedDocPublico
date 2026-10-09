"""Rotas do módulo Contratos (G1). Só HTTP — as decisões estão em
`services/contratos.py`.

Spec: docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md

Gate: toda rota exige a transação `contrato`. A contratação do módulo não
precisa de dependência própria aqui — transação de módulo não contratado é
bloqueada dentro de `require_permission`, ANTES do bypass de super-usuário
(mesmo arranjo de frota e pagamentos).

ORDEM IMPORTA: as rotas de segmento literal (`/resumo`, `/catalogos`,
`/fornecedores`) vêm antes
de `/{contrato_id}`. Declaradas depois, a paramétrica as engole e a requisição
morre em 422 — `tests/test_guarda_ordem_rotas.py` reprova.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.common import Paginated
from ..schemas.contratos import (
    TIPOS_ADITIVO,
    TIPOS_OBJETO,
    AditivoAnular,
    AditivoCreate,
    AditivoOut,
    AditivoUpdate,
    ApostilaCreate,
    ApostilaOut,
    ContratoCatalogosOut,
    ContratoCreate,
    ContratoEncerrar,
    ContratoOut,
    ContratoRescindir,
    ContratoResumoOut,
    ContratosPainelOut,
    ContratoUpdate,
    FornecedorContratoCreate,
    FornecedorContratoOut,
    SituacaoContratoLit,
    TipoOpcaoOut,
)
from ..schemas.pagamentos import FornecedorCreate
from ..services import contratos as svc
from ..services import pagamentos_cadastros as cadastros_svc

TRANSACAO = "contrato"

router = APIRouter(prefix="/contratos", tags=["contratos"])


async def _detalhe(db: AsyncSession, tenant_id: int, contrato_id: int, usuario: Usuario) -> ContratoOut:
    return ContratoOut.model_validate(
        await svc.detalhar(db, tenant_id=tenant_id, contrato_id=contrato_id, usuario=usuario),
        from_attributes=True)


# ---------- coleção e rotas literais ------------------------------------------

@router.get("", response_model=Paginated[ContratoResumoOut])
async def list_contratos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    situacao: SituacaoContratoLit | None = None,
    id_unidade: int | None = None,
    id_fornecedor: int | None = None,
    exercicio: int | None = None,
    q: str | None = None,
    vence_ate: date | None = None,
    _: Usuario = Depends(require_permission(TRANSACAO)),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[ContratoResumoOut]:
    itens, total = await svc.listar(
        db, tenant_id=tenant_id, page=page, page_size=page_size, situacao=situacao,
        id_unidade=id_unidade, id_fornecedor=id_fornecedor, exercicio=exercicio, q=q,
        vence_ate=vence_ate)
    return Paginated(
        items=[ContratoResumoOut.model_validate(i) for i in itens],
        total=total, page=page, page_size=page_size)


@router.get("/resumo", response_model=ContratosPainelOut)
async def resumo_contratos(
    _: Usuario = Depends(require_permission(TRANSACAO)),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratosPainelOut:
    return ContratosPainelOut.model_validate(await svc.painel(db, tenant_id=tenant_id))


@router.get("/catalogos", response_model=ContratoCatalogosOut)
async def catalogos_contratos(
    _: Usuario = Depends(require_permission(TRANSACAO)),
) -> ContratoCatalogosOut:
    return ContratoCatalogosOut(
        tipos_objeto=[TipoOpcaoOut(codigo=c, rotulo=r) for c, r in TIPOS_OBJETO.items()],
        tipos_aditivo=[TipoOpcaoOut(codigo=c, rotulo=r) for c, r in TIPOS_ADITIVO.items()],
    )


# Fornecedor é cadastro do módulo de pagamentos (`pagamentos.fornecedor`, sob a
# transação `pagamento_cadastro`). Um município que contrata só `contratos` tem
# essa transação BLOQUEADA e ficaria sem como escolher o contratado. Estas duas
# rotas dão ao módulo o mínimo — identificação, sem dado bancário — sob a
# transação `contrato` (decisão Q2 do spec). Promover fornecedor a cadastro
# transversal é fatia própria.
@router.get("/fornecedores", response_model=list[FornecedorContratoOut])
async def list_fornecedores_do_contrato(
    q: str | None = None,
    _: Usuario = Depends(require_permission(TRANSACAO)),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[FornecedorContratoOut]:
    rows = await cadastros_svc.listar_fornecedores(db, tenant_id=tenant_id, q=q)
    return [FornecedorContratoOut.model_validate(r) for r in rows]


@router.post("/fornecedores", response_model=FornecedorContratoOut,
             status_code=status.HTTP_201_CREATED)
async def create_fornecedor_do_contrato(
    payload: FornecedorContratoCreate,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> FornecedorContratoOut:
    criado = await cadastros_svc.criar_fornecedor(
        db, tenant_id=tenant_id, usuario_id=usuario.id,
        payload=FornecedorCreate(**payload.model_dump()))
    return FornecedorContratoOut.model_validate(criado)


@router.post("", response_model=ContratoOut, status_code=status.HTTP_201_CREATED)
async def create_contrato(
    payload: ContratoCreate,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    c = await svc.criar(db, tenant_id=tenant_id, usuario=usuario, payload=payload)
    return await _detalhe(db, tenant_id, c.id, usuario)


# ---------- um contrato --------------------------------------------------------

@router.get("/{contrato_id}", response_model=ContratoOut)
async def get_contrato(
    contrato_id: int,
    usuario: Usuario = Depends(require_permission(TRANSACAO)),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    return await _detalhe(db, tenant_id, contrato_id, usuario)


@router.put("/{contrato_id}", response_model=ContratoOut)
async def update_contrato(
    contrato_id: int,
    payload: ContratoUpdate,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    await svc.atualizar(
        db, tenant_id=tenant_id, contrato_id=contrato_id, usuario=usuario, payload=payload)
    return await _detalhe(db, tenant_id, contrato_id, usuario)


@router.delete("/{contrato_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contrato(
    contrato_id: int,
    _: Usuario = Depends(require_permission(TRANSACAO, "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await svc.excluir(db, tenant_id=tenant_id, contrato_id=contrato_id)


@router.post("/{contrato_id}/assinar", response_model=ContratoOut)
async def assinar_contrato(
    contrato_id: int,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    await svc.assinar(db, tenant_id=tenant_id, contrato_id=contrato_id)
    return await _detalhe(db, tenant_id, contrato_id, usuario)


@router.post("/{contrato_id}/encerrar", response_model=ContratoOut)
async def encerrar_contrato(
    contrato_id: int,
    payload: ContratoEncerrar,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    await svc.encerrar(
        db, tenant_id=tenant_id, contrato_id=contrato_id,
        data_encerramento=payload.data_encerramento)
    return await _detalhe(db, tenant_id, contrato_id, usuario)


@router.post("/{contrato_id}/rescindir", response_model=ContratoOut)
async def rescindir_contrato(
    contrato_id: int,
    payload: ContratoRescindir,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ContratoOut:
    await svc.rescindir(
        db, tenant_id=tenant_id, contrato_id=contrato_id,
        data_encerramento=payload.data_encerramento, motivo=payload.motivo)
    return await _detalhe(db, tenant_id, contrato_id, usuario)


# ---------- aditivos -----------------------------------------------------------

@router.post("/{contrato_id}/aditivos", response_model=AditivoOut,
             status_code=status.HTTP_201_CREATED)
async def create_aditivo(
    contrato_id: int,
    payload: AditivoCreate,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AditivoOut:
    return AditivoOut.model_validate(await svc.criar_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, usuario_id=usuario.id,
        payload=payload))


@router.put("/{contrato_id}/aditivos/{aditivo_id}", response_model=AditivoOut)
async def update_aditivo(
    contrato_id: int,
    aditivo_id: int,
    payload: AditivoUpdate,
    _: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AditivoOut:
    return AditivoOut.model_validate(await svc.atualizar_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id,
        payload=payload))


@router.delete("/{contrato_id}/aditivos/{aditivo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_aditivo(
    contrato_id: int,
    aditivo_id: int,
    _: Usuario = Depends(require_permission(TRANSACAO, "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await svc.excluir_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id)


@router.post("/{contrato_id}/aditivos/{aditivo_id}/assinar", response_model=AditivoOut)
async def assinar_aditivo(
    contrato_id: int,
    aditivo_id: int,
    _: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AditivoOut:
    return AditivoOut.model_validate(await svc.assinar_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id))


@router.post("/{contrato_id}/aditivos/{aditivo_id}/anular", response_model=AditivoOut)
async def anular_aditivo(
    contrato_id: int,
    aditivo_id: int,
    payload: AditivoAnular,
    _: Usuario = Depends(require_permission(TRANSACAO, "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AditivoOut:
    return AditivoOut.model_validate(await svc.anular_aditivo(
        db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo_id,
        motivo=payload.motivo))


# ---------- apostilas ----------------------------------------------------------

@router.post("/{contrato_id}/apostilas", response_model=ApostilaOut,
             status_code=status.HTTP_201_CREATED)
async def create_apostila(
    contrato_id: int,
    payload: ApostilaCreate,
    usuario: Usuario = Depends(require_permission(TRANSACAO, "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ApostilaOut:
    return ApostilaOut.model_validate(await svc.criar_apostila(
        db, tenant_id=tenant_id, contrato_id=contrato_id, usuario_id=usuario.id,
        payload=payload))


@router.delete("/{contrato_id}/apostilas/{apostila_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_apostila(
    contrato_id: int,
    apostila_id: int,
    _: Usuario = Depends(require_permission(TRANSACAO, "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    await svc.excluir_apostila(
        db, tenant_id=tenant_id, contrato_id=contrato_id, apostila_id=apostila_id)
