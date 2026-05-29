"""Provisionamento de tenant — serviço ÚNICO (PR 3a).

Fonte única usada **tanto pela CLI** (`app/cli/tenant.py`) **quanto pela API
admin** (`routers/admin_tenants.py`). Cria o registro do tenant + o bootstrap
mínimo (admin super-usuário, grupo SU, unidade, catálogos) de forma
**transacional** e **tenant-safe sob RLS**.

Pontos críticos:
- O registro em `aprimora_py.tenant` é cross-tenant (a tabela não tem RLS).
- **Antes** de inserir qualquer dado tenant-scoped, fazemos
  `SET LOCAL app.tenant_id = <novo_id>` — sem isso, sob a role de produção
  (`aprimora_app`, NOBYPASSRLS) as policies bloqueiam os inserts. Não dependemos
  do superuser de dev.
- Atomicidade: tudo numa transação; falha → rollback (sem tenant parcial).
- Senha do admin: **gerada**, retornada **uma vez**; persistimos só bcrypt
  (`senha` MD5 fica vazio — caminho legado desabilitado).
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from .audit import log as audit_log
from ..models import (
    Grupo,
    Nivel,
    Sistema,
    Tenant,
    TipoManifestante,
    TipoUnidadeTrabalho,
    UnidadeTrabalho,
    Usuario,
    UsuarioGrupo,
)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
SLUGS_RESERVADOS = frozenset(
    {"www", "api", "admin", "app", "mail", "static", "assets", "plataforma"}
)


class ProvisioningError(Exception):
    """Erro de provisionamento — mapeado para 400 na API."""


class SlugIndisponivelError(ProvisioningError):
    """Slug já existe — mapeado para 409 na API."""


def validar_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not SLUG_RE.match(s):
        raise ProvisioningError(
            "Slug inválido: use 3–50 caracteres [a-z0-9-], sem hífen nas pontas."
        )
    if s in SLUGS_RESERVADOS:
        raise ProvisioningError(f"Slug reservado: {s!r}.")
    return s


async def provisionar_tenant(
    db: AsyncSession,
    *,
    slug: str,
    nome: str,
    admin_email: str,
    admin_nome: str,
    admin_cpf: str,
    cnpj: str | None = None,
    id_cidade: int | None = None,
    plano: str = "basico",
    cor_primaria: str | None = None,
    logo_url: str | None = None,
    limite_usuarios: int | None = None,
    limite_armazenamento_mb: int | None = None,
    senha: str | None = None,
    ator_usuario_id: int | None = None,
) -> tuple[Tenant, str]:
    """Cria tenant + bootstrap mínimo. Retorna (tenant, senha_temporaria).
    Transacional: comita no fim; exceção → caller faz rollback."""
    slug = validar_slug(slug)

    if (
        await db.execute(select(Tenant.id).where(Tenant.slug == slug))
    ).scalar_one_or_none() is not None:
        raise SlugIndisponivelError(f"Slug '{slug}' já existe.")

    now = datetime.utcnow()
    tenant = Tenant(
        slug=slug,
        nome=nome,
        cnpj=cnpj,
        id_cidade=id_cidade,
        plano=plano,
        cor_primaria=cor_primaria,
        logo_url=logo_url,
        limite_usuarios=limite_usuarios,
        limite_armazenamento_mb=limite_armazenamento_mb,
        ativo=True,
        criado_em=now,
    )
    db.add(tenant)
    await db.flush()  # obtém tenant.id (aprimora_py.tenant — sem RLS)

    # CRÍTICO: a partir daqui os inserts são tenant-scoped (tabelas com RLS).
    # SET não aceita bind params no Postgres → interpolar o int (seguro).
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant.id)}"))

    # Pré-requisitos globais (SU precisa de nível valor=0 + sistema 'sistemas').
    nivel_su = (
        await db.execute(select(Nivel).where(Nivel.valor == 0).limit(1))
    ).scalar_one_or_none()
    sistema_app = (
        await db.execute(select(Sistema).where(Sistema.app == "sistemas").limit(1))
    ).scalar_one_or_none()
    if nivel_su is None or sistema_app is None:
        raise ProvisioningError(
            "Pré-requisitos globais ausentes (nível valor=0 ou sistema 'sistemas')."
        )

    tu = TipoUnidadeTrabalho(
        tenant_id=tenant.id, tipo_unidade_trabalho="Secretaria", codigo="SEC"
    )
    db.add(tu)
    await db.flush()
    unidade = UnidadeTrabalho(
        tenant_id=tenant.id,
        unidade_trabalho="Protocolo Geral",
        sigla="PG",
        id_tipo_unidade_trabalho=tu.id,
    )
    db.add(unidade)
    await db.flush()

    db.add(
        TipoManifestante(
            tenant_id=tenant.id,
            tipo_manifestante="Pessoa Física",
            id_categoria=1,
            ativo=True,
        )
    )

    senha_temp = senha or secrets.token_urlsafe(12)
    usuario = Usuario(
        tenant_id=tenant.id,
        nome=admin_nome,
        email=admin_email,
        cpf=admin_cpf,
        senha="",  # sem MD5 — só bcrypt (caminho legado desabilitado)
        senha_bcrypt=hash_password(senha_temp),
        id_unidade_trabalho=unidade.id,
        ativo=True,
        excluido=False,
        cargo="Administrador",
        app="sistemas",
    )
    db.add(usuario)
    await db.flush()

    grupo_su = Grupo(
        tenant_id=tenant.id,
        id_nivel=nivel_su.id,
        id_sistema=sistema_app.id,
        grupo="Super Usuário",
        excluido=False,
    )
    db.add(grupo_su)
    await db.flush()
    db.add(
        UsuarioGrupo(
            tenant_id=tenant.id,
            id_usuario=usuario.id,
            id_grupo=grupo_su.id,
            ativo=True,
            excluido=False,
            app="sistemas",
        )
    )

    await audit_log(
        db,
        tenant_id=tenant.id,
        id_usuario=ator_usuario_id,
        acao="tenant.provisionado",
        entidade="tenant",
        id_entidade=tenant.id,
        payload={"slug": tenant.slug, "admin_email": admin_email, "plano": plano},
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant, senha_temp
