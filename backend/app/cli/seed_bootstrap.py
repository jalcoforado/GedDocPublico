"""Seed mínimo de bootstrap — sistema logável com todos os módulos.

Idempotente. Cria (get_or_create):
  1. Catálogo global: utils.sistema(app=settings.app_name) + utils.nivel(valor=0)
  2. Tenant piloto (aprimora_py.tenant, id=1, slug "sobral") — 0003 é pulada pelo baseline 0020
  3. Admin super-usuário admin@local.test (senha dev admin123)
  4. utils.grupo (nível 0, sistema do app_name) + utils.usuario_grupo (tenant 1)
  5. Segredo KEY_LOGIN_GLOBAL_JWT em utils.sistema_constante
  6. Catálogo global protocolos.acao (ABERTURA/ENCAMINHAMENTO/RECEBIMENTO) —
     sem ele não se abre nem tramita processo
  7. Contratação inicial de módulos do tenant (aprimora_py.tenant_modulo) —
     só se o tenant não tiver NENHUMA linha ainda; não ressuscita
     descontratação deliberada do platform admin (ver
     garantir_contratacao_inicial)

Uso: docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..config import get_settings
# SEC-RLS-00B: operação ADMINISTRATIVA, não de runtime. A conexão vem de
# `MIGRATOR_DATABASE_URL` (papel `aprimora_migrator`) quando definida, e de
# `DATABASE_URL` enquanto não estiver — ver `app/database_admin.py`.
from ..database_admin import AdminSessionLocal as SessionLocal
from ..models import (
    Grupo,
    Modulo,
    ModuloTransacao,
    Nivel,
    Sistema,
    SistemaTransacao,
    Tenant,
    TenantModulo,
    Transacao,
    Usuario,
    UsuarioGrupo,
    WorkflowDefinition,
)
from ..services.modulos import contratar_modulos_iniciais

APP = get_settings().app_name

ADMIN_EMAIL = "admin@local.test"
ADMIN_SENHA = "admin123"
TENANT_SLUG = "sobral"


async def _set_local_tenant(db: AsyncSession, tenant_id: int) -> None:
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))


# Mapa módulo -> códigos de transação. Ponto de partida; a autoridade é o teste
# test_toda_transacao_tem_modulo (tests/test_guarda_modularizacao.py), que
# reprova o PR se sobrar transação do nosso sistema fora daqui.
MODULO_TRANSACOES: dict[str, tuple[str, ...]] = {
    "protocolo": (
        "processo", "catalogo", "assunto", "manifestante", "servico",
        "minuta_template", "cidade", "endereco", "workflow",
    ),
    "pagamentos": (
        "pagamento_cadastro", "pagamento_solicitar", "pagamento_autorizar",
        "pagamento_pagar", "pagamento_validar", "pagamento_auditar", "pagamento_gerir",
    ),
    "frota": ("frota",),
    "transporte": ("transporte_regulado",),
    # `auditoria` (migration 0090, item 1.0.8) fica em administração: a trilha
    # atravessa todos os módulos, mas quem a lê é quem administra o município.
    "administracao": ("usuario", "unidadeTrabalho", "configuracao", "auditoria"),
    "comum": ("dashboard",),
}


async def garantir_sistema_transacao(db: AsyncSession) -> int:
    """Liga ao sistema do app toda transação que os módulos declaram.

    Sem esse vínculo o ramo de super-usuário do `load_permissions` devolve
    lista vazia — ele consulta `sistema_transacao`, não `transacao`. Só as
    transações declaradas em MODULO_TRANSACOES são ligadas: `utils.transacao`
    pode conter códigos do PHP legado que não são nossos.
    """
    sistema = (
        await db.execute(select(Sistema).where(Sistema.app == APP, Sistema.excluido.is_(False)))
    ).scalars().first()
    if sistema is None:
        raise RuntimeError(f"Nenhum utils.sistema com app='{APP}' — o seed roda fora de ordem.")

    declarados = {c for codigos in MODULO_TRANSACOES.values() for c in codigos}
    transacoes = {
        t.codigo: t.id
        for t in (await db.execute(
            select(Transacao).where(
                Transacao.excluido.is_(False), Transacao.codigo.in_(declarados)
            )
        )).scalars().all()
    }
    ja_ligadas = set((await db.execute(
        select(SistemaTransacao.id_transacao).where(
            SistemaTransacao.id_sistema == sistema.id,
            SistemaTransacao.excluido.is_(False),
        )
    )).scalars().all())

    criados = 0
    for id_transacao in transacoes.values():
        if id_transacao in ja_ligadas:
            continue
        db.add(SistemaTransacao(
            id_sistema=sistema.id, id_transacao=id_transacao, excluido=False
        ))
        criados += 1
    return criados


async def semear_modulos(db: AsyncSession) -> dict:
    """Garante o catálogo de módulos e os vínculos com as transações.

    Idempotente: roda a cada deploy. Código de transação que ainda não existe
    em `utils.transacao` é ignorado em silêncio — o vínculo entra no próximo
    deploy, depois que a transação for criada.
    """
    modulos = {
        m.slug: m
        for m in (await db.execute(select(Modulo))).scalars().all()
    }
    if not modulos:
        raise RuntimeError(
            "aprimora_py.modulo está vazia — rode `alembic upgrade head` "
            "antes do seed (a migration 0073 popula o catálogo)."
        )

    transacoes = {
        t.codigo: t.id
        for t in (await db.execute(
            select(Transacao).where(Transacao.excluido.is_(False))
        )).scalars().all()
    }

    existentes = {
        (row[0], row[1])
        for row in (await db.execute(
            select(ModuloTransacao.id_modulo, ModuloTransacao.id_transacao)
        )).all()
    }

    criados = 0
    for slug, codigos in MODULO_TRANSACOES.items():
        modulo = modulos.get(slug)
        if modulo is None:
            continue
        for codigo in codigos:
            id_transacao = transacoes.get(codigo)
            if id_transacao is None:
                continue
            if (modulo.id, id_transacao) in existentes:
                continue
            db.add(ModuloTransacao(id_modulo=modulo.id, id_transacao=id_transacao))
            existentes.add((modulo.id, id_transacao))
            criados += 1

    return {"modulos": len(modulos), "vinculos": criados}


async def garantir_contratacao_inicial(db: AsyncSession, tenant_id: int) -> list[str]:
    """Contrata para o tenant todos os módulos contratáveis e ativos — mas
    SÓ quando ele ainda não tiver NENHUMA linha em `aprimora_py.tenant_modulo`.

    "Nenhuma linha" e não "nenhuma linha viva": esta função roda a cada
    deploy (o seed inteiro é idempotente por design). Se contratasse sempre
    que a lista de disponíveis estivesse vazia, ressuscitaria uma
    descontratação DELIBERADA feita pelo platform admin — que fica
    registrada como linha `excluido=true`/`ativo=false`, não como ausência
    de linha. Checar "nenhuma linha viva" apagaria essa distinção e violaria
    a garantia de `contratar()` (services/modulos.py) de que descontratar
    suspende, não é revertido por trás.

    Fechamento do Critical do review de branch: o backfill da migration
    0073 é um `CROSS JOIN` sobre os tenants que já existem NO MOMENTO em
    que ela roda. Em banco limpo — CI (`alembic upgrade head` antes de
    qualquer tenant existir) e `scripts/bootstrap-db.sh` (mesma ordem) — o
    backfill roda contra zero tenants, e nada depois contratava: tenant
    novo nascia com `disponiveis = {'comum'}` e todo o resto bloqueado por
    403, inclusive para o super-usuário (o gate de módulos roda antes do
    bypass de SU). É este `seed_bootstrap` quem fecha a lacuna.
    """
    tem_alguma_linha = (
        await db.execute(
            select(TenantModulo.id).where(TenantModulo.tenant_id == tenant_id).limit(1)
        )
    ).first()
    if tem_alguma_linha is not None:
        return []
    return await contratar_modulos_iniciais(db, tenant_id, None)


async def garantir_workflows_transporte(db: AsyncSession) -> list[str]:
    """Cria, para cada tenant com o módulo `transporte` contratado (ativo,
    não excluído), as `WorkflowDefinition` de `SEMENTES`
    (`services/transporte_workflow.py`) — SÓ o slug que ainda não existe
    para aquele tenant. Idempotente por design (roda a cada deploy) e nunca
    sobrescreve edição do tenant: a checagem é "existe alguma linha desse
    slug", não "está na versão da semente".

    P8 D1 (Task 3) só declara `transporte-ocorrencia` em `SEMENTES`; as
    Tasks 4/5 acrescentam `alvara`/`convocacao` só mexendo em `SEMENTES` —
    este laço já cobre qualquer slug novo sem precisar de outra mudança
    aqui.
    """
    # Import local: `transporte_workflow` importa de `transporte_regulado`
    # no nível de módulo, então importar no topo deste arquivo criaria um
    # ciclo se `transporte_regulado` algum dia importasse `seed_bootstrap`
    # — hoje não importa, mas o padrão do resto do módulo é `from . import
    # transporte_workflow as _wf` dentro da função, e seguir aqui evita
    # surpresa se isso mudar.
    from ..services.transporte_workflow import SEMENTES

    tenant_ids = (
        await db.execute(
            select(TenantModulo.tenant_id)
            .join(Modulo, Modulo.id == TenantModulo.id_modulo)
            .where(
                Modulo.slug == "transporte",
                TenantModulo.ativo.is_(True),
                TenantModulo.excluido.is_(False),
            )
        )
    ).scalars().all()

    criadas: list[str] = []
    for tenant_id in tenant_ids:
        # `workflow_definition` tem RLS FORCE: sob papel sem BYPASSRLS, tanto
        # o SELECT de existência quanto o INSERT precisam da GUC do tenant —
        # e o flush tem de acontecer AINDA sob essa GUC (linha pendente de um
        # tenant flushada sob a GUC do próximo viola a policy; foi assim que
        # test_seed_bootstrap pegou esta função na suíte completa).
        await _set_local_tenant(db, tenant_id)
        for slug, dsl in SEMENTES.items():
            existe = (
                await db.execute(
                    select(WorkflowDefinition.id)
                    .where(
                        WorkflowDefinition.tenant_id == tenant_id,
                        WorkflowDefinition.slug == slug,
                    )
                    .limit(1)
                )
            ).first()
            if existe is not None:
                continue
            db.add(
                WorkflowDefinition(
                    tenant_id=tenant_id,
                    slug=slug,
                    nome=slug.replace("-", " ").title(),
                    versao=1,
                    ativo=True,
                    dsl=dsl,
                    criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            criadas.append(f"{tenant_id}:{slug}")
        # Flush por tenant, ainda sob a GUC dele (ver comentário acima).
        await db.flush()
    return criadas


async def seed(db: AsyncSession) -> dict:
    # 1. Catálogo global (sistema app=aprimora + nível 0). O stub
    # sistema_chamados.tipo_chamado (Task 1) deixa o trigger legado passar.
    sistema = (
        await db.execute(select(Sistema).where(Sistema.app == APP))
    ).scalars().first()
    if sistema is None:
        sistema = Sistema(sistema="Aprimora", app=APP, url="/", excluido=False)
        db.add(sistema)
        await db.flush()

    nivel = (
        await db.execute(select(Nivel).where(Nivel.valor == 0))
    ).scalars().first()
    if nivel is None:
        nivel = Nivel(nivel="Super Usuario", valor=0, excluido=False)
        db.add(nivel)
        await db.flush()

    # 2. Tenant piloto (slug fixo "sobral" — só o nome de exibição mudou)
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    ).scalars().first()
    if tenant is None:
        tenant = Tenant(
            slug=TENANT_SLUG,
            nome="Minha Prefeitura",
            plano="basico",
            ativo=True,
            # Tenant.criado_em é TIMESTAMP WITHOUT TIME ZONE — usar UTC naive
            # (aware quebra o insert asyncpg num DB fresco: "offset-naive and
            # offset-aware datetimes").
            criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(tenant)
        await db.flush()
    tenant_id = tenant.id

    await _set_local_tenant(db, tenant_id)

    # 3. Admin super-usuário
    usuario = (
        await db.execute(
            select(Usuario).where(
                Usuario.email == ADMIN_EMAIL, Usuario.tenant_id == tenant_id
            )
        )
    ).scalars().first()
    if usuario is None:
        usuario = Usuario(
            tenant_id=tenant_id,
            nome="Admin Sobral",
            email=ADMIN_EMAIL,
            senha="",
            senha_bcrypt=hash_password(ADMIN_SENHA),
            cpf="00000000000",
            ativo=True,
            excluido=False,
            app=APP,
            nivel_acesso_sigilo="interno",
            must_change_password=False,
        )
        db.add(usuario)
        await db.flush()

    # 4. Grupo SU + vínculo
    grupo = (
        await db.execute(
            select(Grupo).where(
                Grupo.tenant_id == tenant_id,
                Grupo.id_nivel == nivel.id,
                Grupo.id_sistema == sistema.id,
            )
        )
    ).scalars().first()
    if grupo is None:
        grupo = Grupo(
            id_nivel=nivel.id,
            id_sistema=sistema.id,
            grupo="Administradores",
            tenant_id=tenant_id,
            excluido=False,
        )
        db.add(grupo)
        await db.flush()

    vinculo = (
        await db.execute(
            select(UsuarioGrupo).where(
                UsuarioGrupo.id_usuario == usuario.id,
                UsuarioGrupo.id_grupo == grupo.id,
            )
        )
    ).scalars().first()
    if vinculo is None:
        db.add(
            UsuarioGrupo(
                id_usuario=usuario.id,
                id_grupo=grupo.id,
                tenant_id=tenant_id,
                ativo=True,
                excluido=False,
            )
        )

    # 5. Segredo JWT
    jwt_exists = (
        await db.execute(
            text(
                "SELECT 1 FROM utils.sistema_constante "
                "WHERE constante='KEY_LOGIN_GLOBAL_JWT' LIMIT 1"
            )
        )
    ).first()
    if jwt_exists is None:
        await db.execute(
            text(
                "INSERT INTO utils.sistema_constante (constante, valor_padrao, excluido) "
                "VALUES ('KEY_LOGIN_GLOBAL_JWT', :v, false)"
            ),
            {"v": secrets.token_urlsafe(48)},
        )

    # 6. Catálogo global protocolos.acao.
    #
    # Sem estas linhas o módulo de protocolo fica INUTILIZÁVEL: abrir processo
    # falha com "Ação 'ABERTURA' não cadastrada em protocolos.acao — execute o
    # seed", e encaminhar/receber falham igual. Era o caso da VPS até
    # 2026-07-27 — quem semeava era `ci/seed-e2e.sql`, que só roda no CI, e o
    # deploy não tinha equivalente.
    #
    # A tabela é catálogo GLOBAL (não tem tenant_id), então o escopo é este
    # seed e não o provisionamento de tenant. `status_acao`/`status_movimentacao`
    # são descritivos — só aparecem na listagem de movimentações; o código usa
    # apenas `acao.id`.
    for flag, nome, status_acao, status_mov, texto in [
        ("ABERTURA", "Abertura", "aberto", "inicial", "Processo aberto"),
        ("ENCAMINHAMENTO", "Encaminhamento", "aberto", "encaminhado",
         "Processo encaminhado"),
        ("RECEBIMENTO", "Recebimento", "aberto", "recebido",
         "Processo recebido"),
    ]:
        existe = (
            await db.execute(
                text(
                    "SELECT 1 FROM protocolos.acao "
                    "WHERE flag = :f AND excluido = false LIMIT 1"
                ),
                {"f": flag},
            )
        ).first()
        if existe is None:
            await db.execute(
                text(
                    "INSERT INTO protocolos.acao "
                    "(flag, acao, status_acao, status_movimentacao, texto_acao, "
                    " ativo, excluido) "
                    "VALUES (:f, :n, :sa, :sm, :t, true, false)"
                ),
                {"f": flag, "n": nome, "sa": status_acao, "sm": status_mov,
                 "t": texto},
            )

    vinculos_sistema = await garantir_sistema_transacao(db)
    resultado_modulos = await semear_modulos(db)
    contratados = await garantir_contratacao_inicial(db, tenant_id)
    workflows_transporte = await garantir_workflows_transporte(db)

    return {
        "tenant_id": tenant_id,
        "usuario_id": usuario.id,
        "is_super": True,
        "vinculos_sistema": vinculos_sistema,
        "modulos": resultado_modulos,
        "modulos_contratados": contratados,
        "workflows_transporte_criados": workflows_transporte,
    }


async def _main() -> int:
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    print(f"[seed_bootstrap] OK: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
