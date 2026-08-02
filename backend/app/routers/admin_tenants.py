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

**O `TenantMiddleware` ainda roda na frente destas rotas, e isso é uma bomba de
efeito retardado para `SEC-01B`.** Hoje `STRICT_TENANT_RESOLUTION=false`, então
todo `Host` que não seja subdomínio de tenant cai silenciosamente no
`default_tenant_slug` e a requisição chega ao gate. Com a resolução estrita —
que é a configuração pretendida para produção — esse mesmo `Host` recebe **404
antes** de `require_platform_admin`. Como o console de operador vai para origem
própria (Q-3), cujo `Host` nunca será slug de tenant, ligar
`STRICT_TENANT_RESOLUTION` derrubaria `/api/v2/admin/*` inteiro sem que nada no
gate fosse tocado. A separação que este módulo descreve é verdadeira do gate
para dentro; o middleware, na frente, ainda a contradiz. Correção é `SEC-01B`
(bypass por prefixo de path); registrado também no runbook §1.

`POST /admin/tenants` é a única rota com **duas** sessões, e desde
`SEC-RLS-00C` isso é a fronteira funcionando, não uma exceção pendente: o
provisionamento foi partido em ato de PLATAFORMA (criar o tenant e a contratação
inicial — `db_plataforma`) e ato MUNICIPAL (semear `utils.*`/`protocolos.*` —
`db_municipal`), porque o ADR §2.3 nega DML de entitlement ao papel municipal e
DML de negócio ao papel de plataforma. Cada ato roda no seu papel; nenhum papel
faz os dois. O modo de falha do provisionamento parcial está descrito em
`services/provisioning_tenant.py`.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user_no_password_gate
from ..auth.plataforma import exigir_tenant_alvo, require_platform_admin
from ..config import modulos_do_plano
from ..database import get_db
from ..database_plataforma import get_platform_db
from ..models.plataforma import PlatformPrincipal
from ..models.tenant import Tenant
from ..models.usuario import Usuario
from ..schemas.admin_tenant import (
    AdminMeOut,
    AdminTenantCreate,
    AdminTenantCreated,
    AdminTenantOut,
    AdminTenantUpdate,
)
from ..schemas.modulo import ContratacaoIn, ModuloAdminOut
from ..services.modulos import contratar, modulos_do_tenant
from ..services.plataforma_auditoria import (
    registrar_falha_de_projecao,
    registrar_no_tenant,
    registrar_operacao,
)
from ..services.provisioning_tenant import (
    ProvisionamentoIncompletoError,
    ProvisioningError,
    SlugIndisponivelError,
    provisionar_tenant,
)

logger = logging.getLogger("plataforma")

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


async def _get_tenant(db: AsyncSession, tenant_id: int | None) -> Tenant:
    """Carrega o tenant alvo. **Chokepoint** por onde passam todas as rotas com
    alvo — é por isso que `exigir_tenant_alvo` mora aqui e não em cada rota.

    Hoje as 8 rotas recebem `tenant_id` como path param obrigatório, então o
    `None` é inalcançável pela borda HTTP e o cenário 19 da matriz está
    satisfeito **estruturalmente**. A guarda é cinto e suspensório, e vale para
    a rota futura que receba o alvo do corpo — onde `None` deixa de ser
    impossível e vira o caso comum de payload malformado.
    """
    tenant_id = exigir_tenant_alvo(tenant_id)
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

    E, depois do commit, a falha da projeção municipal **não vira 500**. A essa
    altura a alteração já está aplicada: propagar a exceção não desfaz nada,
    mente sobre o resultado e convida o operador a repetir a operação. A falha é
    registrada — `logger.error` com o `correlation_id` e uma linha na trilha
    autoritativa — e a resposta é o sucesso que de fato ocorreu.

    Isto **não** é o `except Exception` de `services/audit.py` que este PR
    critica. Lá a trilha engolida é a única, e a operação fica sem rastro
    nenhum. Aqui a autoritativa já está gravada e íntegra; o que se perde é uma
    projeção secundária, cuja perda é ela própria auditada. O critério é
    estreito — depois do commit, e só havendo outra trilha dizendo o que
    aconteceu. Não estender.
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
    try:
        await registrar_no_tenant(
            tenant_alvo_id=tenant_alvo_id,
            acao=acao,
            entidade="tenant",
            id_entidade=tenant_alvo_id,
            payload=detalhe,
            correlation_id=correlacao,
        )
    except Exception as exc:  # noqa: BLE001 — ver docstring: depois do commit
        logger.error(
            "plataforma_projecao_municipal_falhou",
            extra={
                "correlation_id": correlacao,
                "tenant_alvo_id": tenant_alvo_id,
                "acao": acao,
                "erro": str(exc),
            },
        )
        await registrar_falha_de_projecao(
            db,
            principal=principal,
            tenant_alvo_id=tenant_alvo_id,
            acao=acao,
            erro=str(exc),
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
    # DUAS sessões, uma por ato (SEC-RLS-00C). A municipal semeia `utils.*` e
    # `protocolos.*`, onde `aprimora_platform` não tem — nem deve ter — DML; a
    # de plataforma cria o tenant e a contratação, onde `aprimora_app` não tem
    # mais INSERT (migration 0079). Ver o cabeçalho do módulo.
    db_municipal: AsyncSession = Depends(get_db),
    db_plataforma: AsyncSession = Depends(get_platform_db),
) -> AdminTenantCreated:
    try:
        tenant, senha = await provisionar_tenant(
            db_municipal,
            db_plataforma=db_plataforma,
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
    except ProvisionamentoIncompletoError as e:
        # ORDEM IMPORTA: esta cláusula tem de vir ANTES da de `ProvisioningError`,
        # de quem herda — senão o `500` vira `400` e o operador conclui que
        # mandou um payload ruim, quando o tenant já existe no banco.
        #
        # Não é 400: o pedido estava correto e o ato de plataforma já comitou. O
        # tenant ficou INATIVO (não resolve por subdomínio, ninguém entra) e é
        # retomável — a mensagem traz o comando. Nada é apagado aqui: apagar
        # tenant não é operação de runtime nenhum.
        logger.error(
            "plataforma_provisionamento_incompleto",
            extra={
                "correlation_id": _correlacao(request),
                "tenant_alvo_id": e.tenant_id,
                "slug": e.slug,
                "erro": str(e.causa),
            },
        )
        # O ato 1 comitou nesta sessão; se a falha veio do ato 3, ela pode estar
        # com transação suja. Rollback antes de gravar a trilha (no-op quando
        # limpa) para que o registro do incidente não morra junto com ele.
        await db_plataforma.rollback()
        await registrar_operacao(
            db_plataforma,
            principal=principal,
            acao="tenant.provisionamento_incompleto",
            tenant_alvo_id=e.tenant_id,
            detalhe={"slug": e.slug, "erro": str(e.causa)},
            correlation_id=_correlacao(request),
        )
        await db_plataforma.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
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
