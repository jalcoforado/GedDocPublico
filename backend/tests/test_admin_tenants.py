"""Admin SaaS / Gestão de Tenants (PR3a, revisado em SEC-01A e SEC-RLS-00C).

Cobre o serviço único de provisionamento (incl. **sob os papéis RLS de
produção**: ato de plataforma em `aprimora_platform`, ato municipal em
`aprimora_app`), o modo de falha do provisionamento partido, slug
imutável/validação, limites/plano armazenados, módulos derivados do plano e
bloqueio por desativação.

`provisionar_tenant` deixou de ser atômico em `SEC-RLS-00C` — são duas conexões
e dois papéis, e nenhuma transação abarca as duas. A propriedade que substituiu
a atomicidade ("ou completo e ativo, ou inerte e retomável") está em
`test_falha_no_ato_municipal_deixa_tenant_inerte_e_retomavel`.

A allowlist de e-mail que antes era testada aqui foi removida em SEC-01A — ver
`test_gate_de_plataforma_nao_aceita_identidade_municipal`, mais abaixo, e a
matriz completa em `test_platform_token_validator.py`.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import modulos_do_plano
from app.schemas.admin_tenant import AdminTenantOut, AdminTenantUpdate
from app.services.provisioning_tenant import (
    ProvisioningError,
    SlugIndisponivelError,
    provisionar_tenant,
    validar_slug,
)


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cleanup(admin_engine, tenant_id: int) -> None:
    """Remove tudo que o provisionamento cria, em ordem FK-safe (via ged_user)."""
    Session = _sessionmaker(admin_engine)
    async with Session() as s:
        for stmt in (
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


def _novo_slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(session_factory, slug, **kw):
    async with session_factory() as s:
        return await provisionar_tenant(
            s,
            slug=slug,
            nome=kw.get("nome", "Prefeitura Teste"),
            admin_email=kw.get("admin_email", f"{slug}@teste.local"),
            admin_nome=kw.get("admin_nome", "Administrador"),
            admin_cpf=kw.get("admin_cpf", uuid.uuid4().hex[:11]),
            plano=kw.get("plano", "basico"),
            limite_usuarios=kw.get("limite_usuarios"),
            limite_armazenamento_mb=kw.get("limite_armazenamento_mb"),
            ator_usuario_id=kw.get("ator_usuario_id"),
        )


# ---- serviço: provisionamento completo (admin_engine / ged_user) ----
async def test_provisiona_tenant_completo(admin_engine):
    slug = _novo_slug("prov")
    Session = _sessionmaker(admin_engine)
    tenant, senha = await _provisionar(
        Session, slug, plano="profissional", limite_usuarios=10, limite_armazenamento_mb=2048
    )
    try:
        assert senha and len(senha) >= 8
        async with Session() as s:
            t = (await s.execute(text("SELECT plano, limite_usuarios, limite_armazenamento_mb, ativo FROM aprimora_py.tenant WHERE id=:t"), {"t": tenant.id})).first()
            assert t.plano == "profissional" and t.limite_usuarios == 10 and t.limite_armazenamento_mb == 2048 and t.ativo is True
            # admin bcrypt-only (sem MD5)
            u = (await s.execute(text("SELECT senha, senha_bcrypt FROM utils.usuario WHERE tenant_id=:t"), {"t": tenant.id})).first()
            assert u.senha == "" and u.senha_bcrypt and u.senha_bcrypt.startswith("$2")
            for tbl in ("utils.grupo", "utils.usuario_grupo", "utils.unidade_trabalho", "protocolos.tipo_manifestante"):
                n = (await s.execute(text(f"SELECT count(*) FROM {tbl} WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one()
                assert n == 1, f"{tbl} deveria ter 1 linha"
            audit = (await s.execute(text("SELECT count(*) FROM aprimora_py.audit_log WHERE tenant_id=:t AND acao='tenant.provisionado'"), {"t": tenant.id})).scalar_one()
            assert audit == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- CRÍTICO: provisionamento sob a role RLS de produção (aprimora_app) ----
async def test_provisiona_sob_rls_producao(admin_engine, app_session, platform_session):
    """Cada ato no seu papel, os dois NOBYPASSRLS (SEC-RLS-00C).

    **O que mudou, e por que a versão nova prova mais.** A versão anterior
    rodava o provisionamento INTEIRO em `aprimora_app` e concluía "o contexto de
    tenant está certo". Só que ela também dependia — sem dizer — de o papel
    municipal poder inserir em `aprimora_py.tenant` e `tenant_modulo`, que é
    exatamente o buraco de entitlement que este PR fecha. Verde ali significava
    as duas coisas ao mesmo tempo, e a segunda era um defeito.

    Agora são dois papéis, e as duas propriedades ficam separadas e afirmadas:

    - o **ato de plataforma** roda em `aprimora_platform`, que tem os grants
      cross-tenant enumerados da 0076;
    - o **ato municipal** roda em `aprimora_app`, NOBYPASSRLS: sem o
      `SET LOCAL app.tenant_id` do serviço, todo insert tenant-scoped morreria
      na policy `WITH CHECK`. É a mesma coisa que a versão antiga media.

    A metade que sumiu daqui — "o papel municipal NÃO cria tenant" — não se
    perdeu: virou teste próprio, com controle positivo, em
    `test_entitlement_fronteira_sql.py`.
    """
    slug = _novo_slug("rls")
    tenant, senha = await provisionar_tenant(
        app_session, db_plataforma=platform_session,
        slug=slug, nome="RLS Prod", admin_email=f"{slug}@t.local",
        admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
    )
    try:
        assert tenant.id and senha
        # confirma via ged_user (bypass) que o bootstrap tenant-scoped foi gravado
        async with _sessionmaker(admin_engine)() as s:
            n = (await s.execute(text("SELECT count(*) FROM utils.usuario WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one()
            assert n == 1
            # O ato 3 rodou: tenant completo é tenant ATIVO. Sem esta asserção o
            # teste passaria com o tenant inerte, que é o estado de falha.
            ativo = (await s.execute(text("SELECT ativo FROM aprimora_py.tenant WHERE id=:t"), {"t": tenant.id})).scalar_one()
            assert ativo is True, (
                "o tenant ficou inativo: o ato de ativação (3) não rodou, e o "
                "município não resolveria por subdomínio."
            )
            # O ato 1 rodou pelo papel de plataforma: a contratação existe.
            mods = (await s.execute(text("SELECT count(*) FROM aprimora_py.tenant_modulo WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one()
            assert mods > 0, "nenhum módulo contratado — o ato de plataforma não gravou"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- slug duplicado / inválido / reservado ----
async def test_slug_duplicado_409(admin_engine):
    slug = _novo_slug("dup")
    Session = _sessionmaker(admin_engine)
    tenant, _ = await _provisionar(Session, slug)
    try:
        with pytest.raises(SlugIndisponivelError):
            await _provisionar(Session, slug, admin_cpf=uuid.uuid4().hex[:11])
    finally:
        await _cleanup(admin_engine, tenant.id)


def test_slug_validacao():
    assert validar_slug("Sobral-2") == "sobral-2"
    for ruim in ("ab", "-bad", "bad-", "admin", "www", "com espaco", "a"):
        with pytest.raises(ProvisioningError):
            validar_slug(ruim)


# ---- o modo de falha do provisionamento partido (SEC-RLS-00C) ----
async def test_falha_no_ato_municipal_deixa_tenant_inerte_e_retomavel(
    admin_engine, monkeypatch
):
    """O teste que substitui `test_bootstrap_transacional_rollback`.

    **O que o teste antigo afirmava e deixou de ser verdade.** Ele afirmava
    "rollback total — sem tenant órfão": uma transação só, falha no meio, nada
    fica. Depois de `SEC-RLS-00C` isso é impossível *por construção* — são duas
    conexões e dois papéis de banco, e nenhuma transação abarca as duas. Manter
    a asserção antiga exigiria desfazer a partição, ou compensar com um `DELETE`
    em `aprimora_py.tenant` que nenhum papel tem nem deve ter.

    **O que passa a valer, e é o que este teste trava:** ou o tenant está
    completo e ativo, ou está **inerte e retomável**. As duas metades:

    1. o tenant existe, mas com `ativo = false` — e a consulta do
       `TenantMiddleware` (`slug = :s AND ativo = true`) NÃO o encontra, então
       ninguém entra nele e nada vaza;
    2. a retomada conclui o provisionamento, e o tenant fica utilizável.

    A simulação é a mesma de antes (`hash_password` explode no meio do ato
    municipal), o que mantém o teste ancorado num ponto real do caminho: depois
    do commit do ato de plataforma, antes do commit do ato municipal.
    """
    slug = _novo_slug("inerte")
    import app.services.provisioning_tenant as ps

    def _boom(_):
        raise RuntimeError("falha simulada no meio do ato municipal")

    monkeypatch.setattr(ps, "hash_password", _boom)
    Session = _sessionmaker(admin_engine)
    tenant_id = None
    try:
        async with Session() as s:
            with pytest.raises(ps.ProvisionamentoIncompletoError) as exc:
                await provisionar_tenant(
                    s, slug=slug, nome="X", admin_email="x@x.local",
                    admin_nome="X", admin_cpf=uuid.uuid4().hex[:11],
                )
        tenant_id = exc.value.tenant_id
        assert exc.value.slug == slug
        assert "retomar" in str(exc.value), (
            "a exceção do provisionamento parcial precisa dizer COMO concluir; "
            "sem isso o operador fica com um tenant inerte e nenhuma instrução."
        )

        async with Session() as s:
            # 1a. o tenant existe — não houve compensação por DELETE
            linha = (
                await s.execute(
                    text("SELECT id, ativo FROM aprimora_py.tenant WHERE slug=:s"),
                    {"s": slug},
                )
            ).first()
            assert linha is not None, (
                "o tenant sumiu: alguém acrescentou compensação por DELETE. "
                "Apagar tenant não é operação de runtime nenhum (0076)."
            )
            assert linha.ativo is False, "o tenant incompleto ficou ATIVO"

            # 1b. e é INERTE: a query do TenantMiddleware não o resolve
            resolvido = (
                await s.execute(
                    text(
                        "SELECT id FROM aprimora_py.tenant "
                        " WHERE slug=:s AND ativo=true"
                    ),
                    {"s": slug},
                )
            ).scalar_one_or_none()
            assert resolvido is None, (
                "o tenant incompleto resolve por subdomínio — é a diferença "
                "entre 'inerte' e 'meio aberto'."
            )

            # 1c. sem admin: o ato municipal não deixou usuário para trás
            usuarios = (
                await s.execute(
                    text("SELECT count(*) FROM utils.usuario WHERE tenant_id=:t"),
                    {"t": linha.id},
                )
            ).scalar_one()
            assert usuarios == 0

        # 2. a retomada conclui — com o defeito corrigido, como na vida real
        monkeypatch.undo()
        async with Session() as s:
            tenant, senha = await ps.retomar_provisionamento(
                s, slug=slug, admin_email="x@x.local", admin_nome="X",
                admin_cpf=uuid.uuid4().hex[:11],
            )
        assert senha, "a retomada tinha de gerar a senha do admin que faltava"
        assert tenant.ativo is True

        async with Session() as s:
            usuarios = (
                await s.execute(
                    text("SELECT count(*) FROM utils.usuario WHERE tenant_id=:t"),
                    {"t": tenant.id},
                )
            ).scalar_one()
            assert usuarios == 1
            acoes = [
                a
                for (a,) in (
                    await s.execute(
                        text(
                            "SELECT acao FROM aprimora_py.audit_log "
                            " WHERE tenant_id=:t ORDER BY id"
                        ),
                        {"t": tenant.id},
                    )
                ).all()
            ]
            assert acoes == ["tenant.provisionamento_retomado"], (
                f"trilha inesperada: {acoes}. A retomada tem de aparecer como "
                "evento próprio — quem audita precisa saber que este tenant "
                "não nasceu num ato só."
            )
    finally:
        if tenant_id is not None:
            await _cleanup(admin_engine, tenant_id)


async def test_retomar_recusa_tenant_ativo(admin_engine):
    """Retomar um tenant ATIVO é escalada de privilégio, não recuperação.

    Sem esta recusa, `app.cli.tenant retomar` seria um caminho de uma linha para
    criar um super-usuário dentro de um município em produção — o ato municipal
    cria justamente admin + grupo "Super Usuário" + vínculo.

    Provado com um tenant de verdade, completo e ativo (não com um mock): o que
    se quer travar é a condição `tenant.ativo`, e ela só existe depois que o
    provisionamento inteiro deu certo.
    """
    import app.services.provisioning_tenant as ps

    slug = _novo_slug("ativo")
    Session = _sessionmaker(admin_engine)
    tenant, _ = await _provisionar(Session, slug)
    try:
        async with Session() as s:
            with pytest.raises(ProvisioningError) as exc:
                await ps.retomar_provisionamento(
                    s, slug=slug, admin_email="invasor@x.local",
                    admin_nome="Invasor", admin_cpf=uuid.uuid4().hex[:11],
                )
        assert "já está ativo" in str(exc.value).lower()

        async with Session() as s:
            n = (
                await s.execute(
                    text("SELECT count(*) FROM utils.usuario WHERE tenant_id=:t"),
                    {"t": tenant.id},
                )
            ).scalar_one()
        assert n == 1, (
            "a recusa não impediu a criação do usuário — o teste passaria pela "
            "exceção certa com o efeito colateral errado."
        )
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- gate de plataforma: o e-mail saiu do caminho de decisão (SEC-01A) ----
async def test_assinatura_do_gate_de_plataforma_nao_recebe_identidade_municipal():
    """Substitui `test_require_platform_admin_allowlist`, removido em SEC-01A.

    O teste antigo montava um `SimpleNamespace(email=...)` e afirmava que o
    e-mail certo passava — ou seja, **testava a vulnerabilidade F-01 como se
    fosse contrato**. Não dá para adaptá-lo: o comportamento que ele travava é
    exatamente o que este PR remove.

    O que sobra de afirmável aqui é **só a forma** da dependência nova: ela não
    recebe `Usuario` nenhum, então não há por onde uma credencial municipal
    entrar — nem por engano, nem por `dependency_overrides`. O nome do teste diz
    exatamente isso, e nada além.

    Uma versão anterior deste teste também fazia `inspect.getsource(...)` e
    exigia que a palavra "email" não aparecesse no corpo do gate. Foi removido
    por ser frágil nos dois sentidos: um comentário contendo "e-mail" o
    quebraria, e uma decisão baseada em `claims["email"]` tomada em **outra**
    função passaria batido. Quem trava o comportamento é
    `test_platform_admin_identity.py::
    test_email_de_operador_em_token_de_plataforma_valido_nao_autoriza`, provado
    por inversão. O resto dos 24 cenários está em
    `test_platform_token_validator.py`.
    """
    import inspect

    from app.auth.plataforma import require_platform_admin

    parametros = inspect.signature(require_platform_admin).parameters
    assert set(parametros) == {"request", "db"}, (
        f"assinatura inesperada do gate de plataforma: {list(parametros)}. "
        "Qualquer parâmetro que traga identidade municipal (`Usuario`, e-mail, "
        "`get_current_user`) recria o achado F-01."
    )


# ---- desativação bloqueia resolução por subdomínio ----
async def test_desativado_bloqueia_resolucao(admin_engine):
    slug = _novo_slug("deact")
    Session = _sessionmaker(admin_engine)
    tenant, _ = await _provisionar(Session, slug)
    try:
        async with Session() as s:
            await s.execute(text("UPDATE aprimora_py.tenant SET ativo=false WHERE id=:t"), {"t": tenant.id})
            await s.commit()
        # mesma query do TenantMiddleware: slug + ativo=true → não resolve
        async with Session() as s:
            achado = (await s.execute(text("SELECT id FROM aprimora_py.tenant WHERE slug=:s AND ativo=true"), {"s": slug})).scalar_one_or_none()
        assert achado is None
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- contratos: slug imutável, módulos por plano, listagem sem dados internos ----
def test_update_schema_nao_tem_slug():
    assert "slug" not in AdminTenantUpdate.model_fields


def test_modulos_derivam_do_plano():
    assert "protocolo" in modulos_do_plano("basico")
    assert len(modulos_do_plano("enterprise")) > len(modulos_do_plano("basico"))
    assert modulos_do_plano("inexistente") == modulos_do_plano("basico")


def test_admin_out_so_registro_de_tenant():
    campos = set(AdminTenantOut.model_fields)
    # nunca expõe dados tenant-scoped (conteúdo interno do tenant)
    assert {"usuarios", "processos", "anexos", "manifestantes"}.isdisjoint(campos)


def test_cli_usa_mesmo_servico():
    from app.cli import tenant as cli
    assert cli.provisionar_tenant is provisionar_tenant
