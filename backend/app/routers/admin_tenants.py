"""Painel admin de plataforma — gestão de tenants (PR3a).

Rotas cross-tenant: NÃO usam require_tenant_id. Protegidas por
`require_platform_admin` (allowlist via env). Operam sobre `aprimora_py.tenant`
(sem RLS); a criação delega ao serviço único `provisioning_tenant`.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import (
    get_current_user_no_password_gate,
    require_platform_admin,
)
from ..config import is_platform_admin, modulos_do_plano
from ..database import get_db
from ..models import Tenant, Usuario
from ..schemas.admin_tenant import (
    AdminMeOut,
    AdminTenantCreate,
    AdminTenantCreated,
    AdminTenantOut,
    AdminTenantUpdate,
)
from ..schemas.modulo import ContratacaoIn, ModuloAdminOut
from ..services.audit import log as audit_log
from ..services.modulos import contratar, modulos_do_tenant
from ..services.provisioning_tenant import (
    ProvisioningError,
    SlugIndisponivelError,
    provisionar_tenant,
)

router = APIRouter(tags=["admin-plataforma"])


def _to_out(t: Tenant) -> AdminTenantOut:
    return AdminTenantOut(
        id=t.id,
        slug=t.slug,
        nome=t.nome,
        cnpj=t.cnpj,
        id_cidade=t.id_cidade,
        ativo=t.ativo,
        plano=t.plano,
        cor_primaria=t.cor_primaria,
        logo_url=t.logo_url,
        codigo_orgao_nup=t.codigo_orgao_nup,
        usar_nup_federal=t.usar_nup_federal,
        limite_usuarios=t.limite_usuarios,
        limite_armazenamento_mb=t.limite_armazenamento_mb,
        criado_em=t.criado_em,
        atualizado_em=t.atualizado_em,
        modulos=modulos_do_plano(t.plano),
    )


async def _get_tenant(db: AsyncSession, tenant_id: int) -> Tenant:
    t = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")
    return t


@router.get("/admin/me", response_model=AdminMeOut)
async def admin_me(
    current: Usuario = Depends(get_current_user_no_password_gate),
) -> AdminMeOut:
    """Para o frontend decidir se mostra o painel de plataforma. Qualquer usuário
    autenticado pode chamar; só reporta se ele é admin de plataforma.

    SEC-1 whitelist: o frontend chama /admin/me na inicialização para decidir
    se mostra o link do painel de plataforma — não pode ser bloqueado pelo gate
    de must_change_password. As rotas de mutação do painel
    (`/admin/tenants/...`) continuam protegidas via `require_platform_admin`,
    que por sua vez passa por `get_current_user` e portanto herda o gate."""
    return AdminMeOut(email=current.email, is_platform_admin=is_platform_admin(current.email))


@router.get("/admin/tenants", response_model=list[AdminTenantOut])
async def listar_tenants(
    q: str | None = None,
    ativo: bool | None = None,
    plano: str | None = None,
    _: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminTenantOut]:
    stmt = select(Tenant).order_by(Tenant.id)
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func, or_
        stmt = stmt.where(or_(func.lower(Tenant.slug).like(like), func.lower(Tenant.nome).like(like)))
    if ativo is not None:
        stmt = stmt.where(Tenant.ativo.is_(ativo))
    if plano:
        stmt = stmt.where(Tenant.plano == plano)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_out(t) for t in rows]


@router.post("/admin/tenants", response_model=AdminTenantCreated, status_code=status.HTTP_201_CREATED)
async def criar_tenant(
    payload: AdminTenantCreate,
    current: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantCreated:
    try:
        tenant, senha = await provisionar_tenant(
            db,
            slug=payload.slug,
            nome=payload.nome,
            admin_email=payload.admin_email,
            admin_nome=payload.admin_nome,
            admin_cpf=payload.admin_cpf,
            cnpj=payload.cnpj,
            id_cidade=payload.id_cidade,
            plano=payload.plano,
            cor_primaria=payload.cor_primaria,
            logo_url=payload.logo_url,
            limite_usuarios=payload.limite_usuarios,
            limite_armazenamento_mb=payload.limite_armazenamento_mb,
            ator_usuario_id=current.id,
        )
    except SlugIndisponivelError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ProvisioningError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AdminTenantCreated(tenant=_to_out(tenant), admin_email=payload.admin_email, senha_temporaria=senha)


@router.get("/admin/tenants/{tenant_id}", response_model=AdminTenantOut)
async def detalhe_tenant(
    tenant_id: int,
    _: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantOut:
    return _to_out(await _get_tenant(db, tenant_id))


@router.put("/admin/tenants/{tenant_id}", response_model=AdminTenantOut)
async def editar_tenant(
    tenant_id: int,
    payload: AdminTenantUpdate,
    current: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantOut:
    t = await _get_tenant(db, tenant_id)
    dados = payload.model_dump(exclude_unset=True)  # slug nunca está aqui (imutável)
    for campo, valor in dados.items():
        setattr(t, campo, valor)
    t.atualizado_em = datetime.utcnow()
    await audit_log(
        db, tenant_id=t.id, id_usuario=current.id, acao="tenant.editado",
        entidade="tenant", id_entidade=t.id, payload={"campos": sorted(dados.keys())},
    )
    await db.commit()
    await db.refresh(t)
    return _to_out(t)


async def _set_ativo(db: AsyncSession, tenant_id: int, ativo: bool, ator: int) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.ativo = ativo
    t.atualizado_em = datetime.utcnow()
    await audit_log(
        db, tenant_id=t.id, id_usuario=ator,
        acao="tenant.ativado" if ativo else "tenant.desativado",
        entidade="tenant", id_entidade=t.id, payload={"ativo": ativo},
    )
    await db.commit()
    await db.refresh(t)
    return t


@router.post("/admin/tenants/{tenant_id}/ativar", response_model=AdminTenantOut)
async def ativar_tenant(
    tenant_id: int,
    current: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantOut:
    return _to_out(await _set_ativo(db, tenant_id, True, current.id))


@router.post("/admin/tenants/{tenant_id}/desativar", response_model=AdminTenantOut)
async def desativar_tenant(
    tenant_id: int,
    current: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTenantOut:
    return _to_out(await _set_ativo(db, tenant_id, False, current.id))


@router.get("/admin/tenants/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def listar_modulos(
    tenant_id: int,
    _: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ModuloAdminOut]:
    await _get_tenant(db, tenant_id)  # 404 antes de expor catálogo de tenant inexistente
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]


@router.put("/admin/tenants/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def definir_modulos(
    tenant_id: int,
    payload: ContratacaoIn,
    current: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ModuloAdminOut]:
    await _get_tenant(db, tenant_id)  # 404 antes de gravar TenantModulo órfão (violaria a FK)
    try:
        await contratar(db, tenant_id, payload.slugs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await audit_log(
        db, tenant_id=tenant_id, id_usuario=current.id, acao="tenant.modulos_definidos",
        entidade="tenant", id_entidade=tenant_id, payload={"slugs": sorted(payload.slugs)},
    )
    await db.commit()
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]
