"""Painel admin de plataforma — gestão de tenants.

Fronteira **cross-tenant**. Desde SEC-01A (ADR-016) as oito rotas mutáveis e de
leitura de tenant são protegidas por `require_platform_admin`
(`app/auth/plataforma.py`): token administrativo RS256 do IdP dedicado, com
`iss`/`aud` próprios, mais um principal ativo em
`aprimora_py.platform_principal`. Nenhuma credencial municipal — e-mail,
`usuario.id`, cookie ou token — participa da decisão.

E elas **não usam `get_db`**: recebem `get_platform_db`, uma sessão do papel
`aprimora_platform` (`NOBYPASSRLS`, grants cross-tenant enumerados na migration
0076) que nunca herda `app.tenant_id` do `TenantMiddleware`. O tenant alvo vem
do path da operação, sempre.

Uma exceção, deliberada e delimitada: `POST /admin/tenants`. O provisionamento
escreve nas tabelas de NEGÓCIO do tenant (`utils.usuario`, `utils.grupo`,
`protocolos.tipo_manifestante`, ...), às quais o ADR §2.3 nega acesso ao papel
de plataforma. Partir `provisionar_tenant` em "ato de plataforma" (criar a linha
do tenant) e "ato municipal" (semear o cadastro) é item já decidido e registrado
para `SEC-RLS-00B`; antecipá-lo aqui derrubaria o onboarding dentro de um PR de
segurança. Até lá essa rota continua na sessão municipal, com o gate novo.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user_no_password_gate
from ..auth.plataforma import require_platform_admin
from ..config import modulos_do_plano
from ..database import get_db
from ..database_plataforma import get_platform_db
from ..models import PlatformPrincipal, Tenant, Usuario
from ..schemas.admin_tenant import (
    AdminMeOut,
    AdminTenantCreate,
    AdminTenantCreated,
    AdminTenantOut,
    AdminTenantUpdate,
)
from ..schemas.modulo import ContratacaoIn, ModuloAdminOut
from ..services.modulos import contratar, modulos_do_tenant
from ..services.plataforma_auditoria import registrar_no_tenant, registrar_operacao
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


def _correlacao(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _auditar(
    db: AsyncSession,
    request: Request,
    principal: PlatformPrincipal,
    *,
    tenant_alvo_id: int,
    acao: str,
    detalhe: dict,
) -> None:
    """Decisão **D-a**: as duas trilhas, nesta ordem.

    A autoritativa entra na transação da operação (rollback da operação leva a
    trilha junto). A visível ao município é gravada **depois** do commit, em
    transação própria com `SET LOCAL app.tenant_id = <alvo>` — gravá-la antes
    registraria no tenant uma mudança que ainda pode não acontecer.
    """
    correlacao = _correlacao(request)
    await registrar_operacao(
        db,
        principal=principal,
        acao=acao,
        tenant_alvo_id=tenant_alvo_id,
        detalhe=detalhe,
        correlation_id=correlacao,
    )
    await db.commit()
    await registrar_no_tenant(
        tenant_alvo_id=tenant_alvo_id,
        acao=acao,
        entidade="tenant",
        id_entidade=tenant_alvo_id,
        payload=detalhe,
        correlation_id=correlacao,
    )


@router.get("/admin/me", response_model=AdminMeOut)
async def admin_me(
    current: Usuario = Depends(get_current_user_no_password_gate),
) -> AdminMeOut:
    """O que o frontend municipal usa para decidir se mostra o link do painel.

    `is_platform_admin` é **constante `false`** desde SEC-01A (decisão D-b), e
    isso não é gambiarra: depois deste PR é literalmente verdade que **nenhuma
    sessão municipal é identidade de plataforma**. Esta rota responde a partir
    de um `utils.usuario` do tenant do `Host`; o operador de plataforma vive em
    outro realm, com outro token e outro principal, e não tem como aparecer
    aqui. O efeito é o correto e fail-closed: o link some para todo mundo.

    Consequência conhecida e aceita: entre `SEC-01A` e `SEC-01B` o console de
    plataforma fica inalcançável pela UI. O campo permanece no schema para não
    quebrar os três pontos de consumo do frontend; quem o devolve para a vida é
    o console próprio de `SEC-01B`.

    SEC-1 whitelist: sem o gate de `must_change_password`, porque o frontend a
    chama na inicialização.
    """
    return AdminMeOut(email=current.email, is_platform_admin=False)


@router.get("/admin/tenants", response_model=list[AdminTenantOut])
async def listar_tenants(
    q: str | None = None,
    ativo: bool | None = None,
    plano: str | None = None,
    _: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
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
    request: Request,
    principal: PlatformPrincipal = Depends(require_platform_admin),
    # SESSÃO MUNICIPAL, e a única rota de plataforma que a usa. Ver o cabeçalho
    # do módulo: `provisionar_tenant` semeia o cadastro do tenant e o papel
    # `aprimora_platform` não tem — nem deve ter — DML em `utils.*`. Partir o
    # provisionamento é item de `SEC-RLS-00B`.
    db_municipal: AsyncSession = Depends(get_db),
    db_plataforma: AsyncSession = Depends(get_platform_db),
) -> AdminTenantCreated:
    try:
        tenant, senha = await provisionar_tenant(
            db_municipal,
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
            # `ator_usuario_id` é FK para `utils.usuario.id`. O operador de
            # plataforma não é um usuário municipal; a autoria fica na trilha
            # de plataforma, abaixo, que sabe representá-la.
            ator_usuario_id=None,
        )
    except SlugIndisponivelError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ProvisioningError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await registrar_operacao(
        db_plataforma,
        principal=principal,
        acao="tenant.provisionado",
        tenant_alvo_id=tenant.id,
        detalhe={"slug": tenant.slug, "plano": tenant.plano},
        correlation_id=_correlacao(request),
    )
    await db_plataforma.commit()
    return AdminTenantCreated(tenant=_to_out(tenant), admin_email=payload.admin_email, senha_temporaria=senha)


@router.get("/admin/tenants/{tenant_id}", response_model=AdminTenantOut)
async def detalhe_tenant(
    tenant_id: int,
    _: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> AdminTenantOut:
    return _to_out(await _get_tenant(db, tenant_id))


@router.put("/admin/tenants/{tenant_id}", response_model=AdminTenantOut)
async def editar_tenant(
    tenant_id: int,
    payload: AdminTenantUpdate,
    request: Request,
    principal: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> AdminTenantOut:
    t = await _get_tenant(db, tenant_id)
    dados = payload.model_dump(exclude_unset=True)  # slug nunca está aqui (imutável)
    for campo, valor in dados.items():
        setattr(t, campo, valor)
    t.atualizado_em = datetime.utcnow()
    await _auditar(
        db, request, principal,
        tenant_alvo_id=t.id, acao="tenant.editado",
        detalhe={"campos": sorted(dados.keys())},
    )
    await db.refresh(t)
    return _to_out(t)


async def _set_ativo(
    db: AsyncSession,
    request: Request,
    principal: PlatformPrincipal,
    tenant_id: int,
    ativo: bool,
) -> Tenant:
    t = await _get_tenant(db, tenant_id)
    t.ativo = ativo
    t.atualizado_em = datetime.utcnow()
    await _auditar(
        db, request, principal,
        tenant_alvo_id=t.id,
        acao="tenant.ativado" if ativo else "tenant.desativado",
        detalhe={"ativo": ativo},
    )
    await db.refresh(t)
    return t


@router.post("/admin/tenants/{tenant_id}/ativar", response_model=AdminTenantOut)
async def ativar_tenant(
    tenant_id: int,
    request: Request,
    principal: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> AdminTenantOut:
    return _to_out(await _set_ativo(db, request, principal, tenant_id, True))


@router.post("/admin/tenants/{tenant_id}/desativar", response_model=AdminTenantOut)
async def desativar_tenant(
    tenant_id: int,
    request: Request,
    principal: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> AdminTenantOut:
    return _to_out(await _set_ativo(db, request, principal, tenant_id, False))


@router.get("/admin/tenants/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def listar_modulos(
    tenant_id: int,
    _: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> list[ModuloAdminOut]:
    await _get_tenant(db, tenant_id)  # 404 antes de expor catálogo de tenant inexistente
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]


@router.put("/admin/tenants/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def definir_modulos(
    tenant_id: int,
    payload: ContratacaoIn,
    request: Request,
    principal: PlatformPrincipal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_platform_db),
) -> list[ModuloAdminOut]:
    await _get_tenant(db, tenant_id)  # 404 antes de gravar TenantModulo órfão (violaria a FK)
    try:
        await contratar(db, tenant_id, payload.slugs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _auditar(
        db, request, principal,
        tenant_alvo_id=tenant_id, acao="tenant.modulos_definidos",
        detalhe={"slugs": sorted(payload.slugs)},
    )
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]
