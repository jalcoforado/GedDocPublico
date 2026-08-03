"""Configuração inicial do tenant (PR 3b).

Duas responsabilidades, ambas tenant-scoped:

- ``atualizar_config_institucional`` — aplica a whitelist de campos
  institucionais sobre ``aprimora_py.tenant`` filtrando **explicitamente** por
  ``tenant_id`` (a tabela não tem RLS). Valida ``id_unidade_padrao`` contra
  unidades **do próprio tenant** e **ativas** (não excluídas).
- ``calcular_onboarding`` — checklist calculado a partir do estado real do
  tenant (contagens tenant-scoped). Nenhum dado sensível; tudo do tenant.

Desde o ``SEC-RLS-00D`` (migration 0080) este módulo hospeda também
``COLUNAS_MUNICIPAIS_DE_TENANT``, a fonte única das colunas de
``aprimora_py.tenant`` graváveis pelo papel ``aprimora_app``. Ela é maior do que
a whitelist deste serviço, porque existe um segundo caminho municipal de escrita
(``routers/tenant.py::update_nup_config``) que não passa por aqui.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import modulos_do_plano
from ..models import (
    Assunto,
    EspecieDocumental,
    Grupo,
    Tenant,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from ..schemas.tenant import OnboardingItem, OnboardingResponse, TenantInstitucionalUpdate

# Campos do modelo Tenant que o admin municipal pode editar pela interface.
# Espelha a whitelist do schema; nenhum campo de plataforma entra aqui.
_CAMPOS_INSTITUCIONAIS = frozenset(
    {
        "nome",
        "sigla",
        "email_institucional",
        "telefone_institucional",
        "endereco",
        "site_oficial",
        "horario_atendimento",
        "texto_boas_vindas_portal",
        "logo_url",
        "cor_primaria",
        "id_unidade_padrao",
    }
)

# Campos NUP federal (Fase P2). NÃO passam por este serviço — quem os grava é
# `routers/tenant.py::update_nup_config`, por `PUT /tenants/me/nup-config`. Estão
# aqui, e não lá, porque a constante abaixo precisa dos dois conjuntos no mesmo
# lugar; o router é a única coisa que os escreve.
_CAMPOS_NUP_FEDERAL = frozenset({"codigo_orgao_nup", "usar_nup_federal"})

# SEC-RLS-00D — **fonte única** das colunas de `aprimora_py.tenant` que o papel
# municipal (`aprimora_app`) pode gravar. A migration `0080` concede
# `UPDATE (<estas colunas>)` e revoga o `UPDATE` de tabela inteira; a tabela não
# tem RLS, então o grant é a única barreira de banco que existe ali.
#
# Isto não é documentação: `tests/test_grant_por_coluna_tenant.py` compara este
# conjunto com o que o banco concede de fato e reprova a divergência. Campo novo
# aqui **exige coluna nova no grant, por migration** — senão o endpoint passa a
# devolver 500 com `permission denied for table tenant`, e o rastro aponta para
# o service, não para o grant.
COLUNAS_MUNICIPAIS_DE_TENANT = _CAMPOS_INSTITUCIONAIS | _CAMPOS_NUP_FEDERAL


async def _validar_unidade_padrao(
    db: AsyncSession, *, id_unidade: int, tenant_id: int
) -> None:
    """Exige que a unidade exista, seja do tenant e esteja ativa (não excluída).

    `UnidadeTrabalho` só tem `excluido` (sem coluna `ativo`): "ativa" = não
    excluída. Filtra por `tenant_id` para barrar unidade de outro tenant.
    """
    unidade = (
        await db.execute(
            select(UnidadeTrabalho.id).where(
                UnidadeTrabalho.id == id_unidade,
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if unidade is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unidade padrão inválida: não existe, não é deste tenant ou está inativa.",
        )


async def atualizar_config_institucional(
    db: AsyncSession,
    *,
    tenant_id: int,
    payload: TenantInstitucionalUpdate,
) -> Tenant:
    """Atualiza só campos institucionais do tenant `tenant_id`. Comita."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado"
        )

    dados = payload.model_dump(exclude_unset=True)
    # Defesa adicional: só campos da whitelist são aplicados (o schema já barra
    # extras, mas garantimos que nada fora da lista chegue ao modelo).
    dados = {k: v for k, v in dados.items() if k in _CAMPOS_INSTITUCIONAIS}

    if dados.get("id_unidade_padrao") is not None:
        await _validar_unidade_padrao(
            db, id_unidade=int(dados["id_unidade_padrao"]), tenant_id=tenant_id
        )

    for campo, valor in dados.items():
        setattr(tenant, campo, valor)

    # NÃO acrescente aqui o `atualizado_em = datetime.utcnow()` que o resto do
    # repositório usa depois do `setattr`: essa coluna está FORA do
    # `GRANT UPDATE (...)` da 0080, e o ORM emite um `UPDATE` só com todas as
    # colunas sujas — uma delas fora do grant derruba a instrução inteira.
    # Guardado por `tests/test_pr3b_config_inicial.py`
    # ::test_config_institucional_grava_pelo_orm_sob_aprimora_app.
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def _contar(db: AsyncSession, model, tenant_id: int) -> int:
    stmt = select(func.count()).select_from(model).where(
        model.tenant_id == tenant_id, model.excluido.is_(False)
    )
    return int((await db.execute(stmt)).scalar_one())


async def calcular_onboarding(
    db: AsyncSession, *, tenant_id: int, tenant: Tenant
) -> OnboardingResponse:
    """Checklist de onboarding a partir do estado real do tenant."""
    n_unidades = await _contar(db, UnidadeTrabalho, tenant_id)
    n_grupos = await _contar(db, Grupo, tenant_id)
    n_assuntos = await _contar(db, Assunto, tenant_id)
    n_tipos = await _contar(db, TipoProcesso, tenant_id)
    n_especies = await _contar(db, EspecieDocumental, tenant_id)
    n_usuarios_ativos = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Usuario)
                .where(
                    Usuario.tenant_id == tenant_id,
                    Usuario.excluido.is_(False),
                    Usuario.ativo.is_(True),
                )
            )
        ).scalar_one()
    )

    dados_ok = bool(
        (tenant.email_institucional or "").strip()
        and (tenant.telefone_institucional or "").strip()
    )
    portal_ok = bool((tenant.texto_boas_vindas_portal or "").strip())
    assinatura_ok = "assinatura" in modulos_do_plano(tenant.plano)

    itens = [
        OnboardingItem(chave="dados_institucionais", rotulo="Dados institucionais preenchidos", concluido=dados_ok),
        OnboardingItem(chave="unidade_padrao", rotulo="Unidade padrão definida", concluido=tenant.id_unidade_padrao is not None),
        OnboardingItem(chave="unidades", rotulo="Unidade de trabalho cadastrada", concluido=n_unidades >= 1),
        # "Além do admin inicial": exige ≥ 2 usuários ativos.
        OnboardingItem(chave="usuarios", rotulo="Equipe de usuários cadastrada", concluido=n_usuarios_ativos >= 2),
        OnboardingItem(chave="grupos", rotulo="Grupos de acesso configurados", concluido=n_grupos >= 1),
        OnboardingItem(chave="assuntos", rotulo="Assuntos cadastrados", concluido=n_assuntos >= 1),
        OnboardingItem(chave="tipos_processo", rotulo="Tipos de processo cadastrados", concluido=n_tipos >= 1),
        OnboardingItem(chave="especies_documentais", rotulo="Espécies documentais cadastradas", concluido=n_especies >= 1),
        # Placeholder honesto: hoje "módulo habilitado", não "assinatura operacional".
        OnboardingItem(chave="assinatura", rotulo="Módulo de assinatura habilitado", concluido=assinatura_ok),
        OnboardingItem(chave="portal_cidadao", rotulo="Mensagem de boas-vindas do portal", concluido=portal_ok),
    ]

    concluidos = sum(1 for i in itens if i.concluido is True)
    total = len(itens)
    return OnboardingResponse(
        itens=itens,
        total=total,
        concluidos=concluidos,
        pendentes=total - concluidos,
    )
