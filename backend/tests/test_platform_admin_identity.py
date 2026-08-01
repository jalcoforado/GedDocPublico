"""SEC-01A — identidade do operador de plataforma: esquema, grants e F-01.

Este arquivo cobre três coisas, nesta ordem de importância:

1. **Cenário 21 da matriz de claims** — a regressão do achado **F-01**: um
   usuário *municipal* criado em outro tenant, com e-mail idêntico ao de um
   operador de plataforma, alcançava operação cross-tenant. Foi o teste vermelho
   que abriu o PR, marcado `xfail(strict=True)` enquanto a parte 1 entregava só
   esquema e grants; o marcador saiu com o validador de token da parte 2 (ver
   `docs/architecture/security/platform-operator-claims-matrix.md`).
   Os demais 23 cenários da matriz estão em `test_platform_token_validator.py`.
2. **Higiene de grants** — `aprimora_app` (o papel do runtime municipal) não
   escreve nas tabelas de plataforma. Sem este teste, a garantia é revogada em
   silêncio na próxima vez que alguém mexer no bootstrap do CI (foi exatamente o
   que o `GRANT ... ON ALL TABLES` pós-migration fazia).
3. **Estrutura de `platform_principal`** — sem `tenant_id`, sem FK para
   `utils.usuario`, chave natural `(issuer, subject)`. ADR-016 §2.2 proíbe o
   vínculo "por constraint e por revisão"; aqui ele é proibido por teste.

Autoridade: `docs/architecture/adr/ADR-016-platform-operator-identity.md`.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.jwt import build_payload, encode_token, get_jwt_secret
from app.config import get_settings
from app.main import app

# E-mail do "operador" — domínio reservado `.test`, nunca um operador real
# (ADR-016 §10, Q-2: nenhum operador real vai para código ou seed).
EMAIL_OPERADOR = "operador-plataforma@sec01a.test"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# 1. Cenário 21 — a colisão de e-mail (F-01)
# ---------------------------------------------------------------------------


async def test_cenario_21_usuario_municipal_com_email_de_operador_e_negado(
    admin_engine, plataforma_configurada
) -> None:
    """Matriz de claims, cenário 21 — regressão de **F-01**.

    O índice de unicidade de e-mail é `UNIQUE (tenant_id, email) WHERE excluido
    IS FALSE`: o mesmo e-mail existe em quantos tenants quiser. Enquanto a
    autorização de plataforma comparava **a string do e-mail**, qualquer tenant
    capaz de criar um usuário com o e-mail certo produzia um administrador de
    plataforma.

    Este teste nasceu **vermelho** na parte 1 do PR, marcado `xfail(strict=True)`.
    O marcador saiu na parte 2, junto com a allowlist — e é essa remoção que
    prova que a entrega aconteceu, porque com `strict=True` o teste reprovaria
    caso passasse com o marcador ainda no lugar.

    O arranjo é o pior caso possível, de propósito:

    - a fronteira de plataforma está **inteiramente configurada e viva**
      (`plataforma_configurada`) — se o 401 viesse de configuração ausente, o
      teste não provaria nada, e foi essa a armadilha da versão anterior, que
      precisava LIGAR a allowlist para não passar por acidente;
    - existe um operador de plataforma **de verdade**, ativo, cujo
      `display_label` é exatamente este e-mail;
    - o invasor apresenta um token municipal **válido**, do seu próprio tenant,
      com o `Host` do seu próprio tenant.

    A única coisa que ele não tem é um principal em `platform_principal` — e é
    só isso que decide. O e-mail deixou de participar.

    Sobe pela borda HTTP real: o defeito vivia na cadeia de dependências
    (`require_platform_admin` → `get_current_user` → `Usuario.email`), e um
    teste de unidade sobre a dependência não a exercita.
    """
    suffix = uuid.uuid4().hex[:8]
    slug = f"sec01a-{suffix}"
    tenant_id: int | None = None
    principal_id: int | None = None

    Session = _sm(admin_engine)
    async with Session() as s:
        tenant_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
                        "VALUES (:slug, :nome, true, 'basico', NOW()) RETURNING id"
                    ),
                    {"slug": slug, "nome": f"Prefeitura Invasora {suffix}"},
                )
            ).scalar_one()
        )
        usuario_id = int(
            (
                await s.execute(
                    text(
                        """
                        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf,
                                                   ativo, excluido, app, nivel_acesso_sigilo)
                        VALUES (:t, 'Usuario Colidente', :email, '', :cpf,
                                true, false, :app, 'interno')
                        RETURNING id
                        """
                    ),
                    {
                        "t": tenant_id,
                        "email": EMAIL_OPERADOR,
                        "cpf": uuid.uuid4().hex[:11],
                        "app": get_settings().app_name,
                    },
                )
            ).scalar_one()
        )
        # O operador de plataforma REAL, com este mesmo e-mail como rótulo. É o
        # que torna a colisão concreta: não é "ninguém tem esse e-mail", é "o
        # e-mail é de um operador ativo e ainda assim não vale nada aqui".
        principal_id = int(
            (
                await s.execute(
                    _SQL_INSERE_PRINCIPAL,
                    dict(
                        _PRINCIPAL_TESTE,
                        subject=f"sec01a-colisao-{suffix}",
                        display_label=EMAIL_OPERADOR,
                    ),
                )
            ).scalar_one()
        )
        await s.execute(
            text("UPDATE aprimora_py.platform_principal SET ativo = true WHERE id = :p"),
            {"p": principal_id},
        )
        segredo = await get_jwt_secret(s)
        await s.commit()

    token = encode_token(
        build_payload(usuario_id, EMAIL_OPERADOR, tenant_id), segredo
    )

    try:
        host = f"{slug}.{get_settings().base_domain}"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v2/admin/tenants",
                headers={"Host": host, "Authorization": f"Bearer {token}"},
            )
        assert r.status_code in (401, 403), (
            f"HTTP {r.status_code}: um usuário municipal do tenant `{slug}`, cuja "
            f"única credencial é ter o e-mail `{EMAIL_OPERADOR}`, listou os "
            "tenants da plataforma. É o achado F-01: a autorização cross-tenant "
            "é uma comparação de string sobre um dado que não é único "
            "globalmente. O e-mail não pode participar da decisão."
        )
    finally:
        from app.database import engine as app_engine

        await app_engine.dispose()
        async with Session() as s:
            await s.execute(
                text("DELETE FROM utils.usuario WHERE tenant_id = :t"), {"t": tenant_id}
            )
            await s.execute(
                text("DELETE FROM aprimora_py.tenant WHERE id = :t"), {"t": tenant_id}
            )
            await s.execute(
                text("DELETE FROM aprimora_py.platform_principal WHERE id = :p"),
                {"p": principal_id},
            )
            await s.commit()


# ---------------------------------------------------------------------------
# 2. Higiene de grants — o runtime municipal não escreve na plataforma
# ---------------------------------------------------------------------------

_PRINCIPAL_TESTE = {
    "issuer": "https://operator.test.local",
    "display_label": EMAIL_OPERADOR,
    "concedido_por": "teste automatizado",
    "motivo_concessao": "controle do teste de grants",
}

_SQL_INSERE_PRINCIPAL = text(
    """
    INSERT INTO aprimora_py.platform_principal
        (issuer, subject, display_label, concedido_por, motivo_concessao)
    VALUES (:issuer, :subject, :display_label, :concedido_por, :motivo_concessao)
    RETURNING id
    """
)


async def test_papel_de_plataforma_escreve_no_principal_controle_positivo(
    platform_session: AsyncSession,
) -> None:
    """CONTROLE POSITIVO dos dois testes seguintes.

    Sem ele, "permission denied" para `aprimora_app` provaria apenas que a
    tabela está quebrada, ausente ou sem sequence — e o teste de negativa
    ficaria verde num mundo em que a plataforma inteira não funciona.
    """
    params = dict(_PRINCIPAL_TESTE, subject=f"sec01a-controle-{uuid.uuid4().hex[:8]}")
    principal_id = int(
        (await platform_session.execute(_SQL_INSERE_PRINCIPAL, params)).scalar_one()
    )
    assert principal_id > 0

    await platform_session.execute(
        text(
            "INSERT INTO aprimora_py.platform_audit_log "
            "(platform_principal_id, issuer, subject, acao) "
            "VALUES (:p, :issuer, :subject, 'teste.controle_positivo')"
        ),
        {"p": principal_id, "issuer": params["issuer"], "subject": params["subject"]},
    )
    # Rollback: o controle positivo não deixa lixo. Se a transação tivesse de
    # ser comitada para provar algo, o teste teria de limpar por conta própria.
    await platform_session.rollback()


async def test_aprimora_app_nao_escreve_em_platform_principal(
    app_session: AsyncSession,
) -> None:
    """A garantia central da higiene de grants (ADR §2.3).

    O bootstrap do CI rodava `GRANT ... ON ALL TABLES IN SCHEMA aprimora_py TO
    aprimora_app` **depois** das migrations — o que dava DML na tabela recém
    criada e desfazia qualquer REVOKE. A ordem foi corrigida em
    `.github/workflows/backend-tests.yml`; este teste é o que impede a
    regressão de voltar em silêncio.
    """
    params = dict(_PRINCIPAL_TESTE, subject=f"sec01a-negado-{uuid.uuid4().hex[:8]}")
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(_SQL_INSERE_PRINCIPAL, params)
    await app_session.rollback()
    msg = str(exc.value).lower()
    assert "permission denied" in msg or "permissão negada" in msg, (
        "esperava negativa de PRIVILÉGIO ao inserir em platform_principal como "
        f"`aprimora_app`; recebi: {msg}"
    )


async def test_aprimora_app_nao_escreve_em_platform_audit_log(
    app_session: AsyncSession,
) -> None:
    """Mesma garantia para a trilha de plataforma (decisão D-a).

    Uma trilha que o papel municipal pode escrever é uma trilha que ele pode
    forjar.
    """
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(
            text(
                "INSERT INTO aprimora_py.platform_audit_log (issuer, subject, acao) "
                "VALUES ('https://operator.test.local', 'x', 'teste.forjado')"
            )
        )
    await app_session.rollback()
    msg = str(exc.value).lower()
    assert "permission denied" in msg or "permissão negada" in msg, (
        "esperava negativa de PRIVILÉGIO ao inserir em platform_audit_log como "
        f"`aprimora_app`; recebi: {msg}"
    )


async def test_papel_de_plataforma_nao_e_superuser_nem_bypassrls(
    admin_session: AsyncSession,
) -> None:
    """ADR §2.3/D-5: nenhum papel de runtime pode ser `SUPERUSER`, e
    `BYPASSRLS` não é solução genérica. O papel existe para ter grants
    cross-tenant **declarados**, não para contornar policy."""
    linha = (
        await admin_session.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcanlogin FROM pg_roles "
                "WHERE rolname = 'aprimora_platform'"
            )
        )
    ).one_or_none()
    assert linha is not None, (
        "papel `aprimora_platform` não existe — a migration 0076 não foi "
        "aplicada neste banco. No CI isso significa que o `GRANT ... TO "
        "aprimora_platform` de qualquer migration futura vai falhar."
    )
    rolsuper, rolbypassrls, rolcanlogin = linha
    assert rolsuper is False, "`aprimora_platform` não pode ser SUPERUSER"
    assert rolbypassrls is False, "`aprimora_platform` não pode ter BYPASSRLS"
    assert rolcanlogin is True, "o papel precisa de LOGIN — é usado por PLATFORM_DB_URL"


# ---------------------------------------------------------------------------
# 3. Estrutura — o vínculo proibido pelo ADR §2.2
# ---------------------------------------------------------------------------


async def test_platform_principal_nao_tem_tenant_id_nem_fk_para_usuario(
    admin_session: AsyncSession,
) -> None:
    """ADR §2.2: é **proibido** vincular o principal a `utils.usuario.id`, a
    e-mail municipal ou a qualquer cadastro de tenant.

    Duas afirmações, uma consulta cada:

    - nenhuma coluna `tenant_id` (que, além do vínculo proibido, faria a
      tabela cair na guarda de RLS de `test_rls_bypass_caracterizacao.py`);
    - nenhuma FK saindo da tabela para `utils.*` ou `protocolos.*`.
    """
    colunas = {
        c
        for (c,) in (
            await admin_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'aprimora_py' "
                    "  AND table_name = 'platform_principal'"
                )
            )
        ).all()
    }
    assert colunas, "tabela `aprimora_py.platform_principal` não existe"
    assert "tenant_id" not in colunas, (
        "`platform_principal` ganhou coluna `tenant_id`. O principal de "
        "plataforma não pertence a tenant nenhum (ADR-016 §2.2) — e com a "
        "coluna a tabela ainda passaria a reprovar a guarda de RLS."
    )
    assert not (colunas & {"id_usuario", "usuario_id", "email"}), (
        "`platform_principal` ganhou coluna de identidade municipal: "
        f"{sorted(colunas & {'id_usuario', 'usuario_id', 'email'})}. O e-mail "
        "entra apenas como `display_label`, e não decide nada."
    )

    fks = (
        await admin_session.execute(
            text(
                """
                SELECT con.conname,
                       nf.nspname || '.' || cf.relname AS referenciada
                  FROM pg_constraint con
                  JOIN pg_class c    ON c.oid  = con.conrelid
                  JOIN pg_namespace n  ON n.oid  = c.relnamespace
                  JOIN pg_class cf   ON cf.oid = con.confrelid
                  JOIN pg_namespace nf ON nf.oid = cf.relnamespace
                 WHERE con.contype = 'f'
                   AND n.nspname = 'aprimora_py'
                   AND c.relname = 'platform_principal'
                """
            )
        )
    ).all()
    assert fks == [], (
        f"`platform_principal` tem FK para {[r.referenciada for r in fks]}. "
        "Qualquer vínculo com cadastro de tenant é proibido pelo ADR-016 §2.2 "
        "— é exatamente o acoplamento que produziu o achado F-01."
    )


async def test_platform_principal_tem_chave_natural_issuer_subject(
    platform_session: AsyncSession,
) -> None:
    """Q-5: `id` é a PK interna; `(issuer, subject)` é a chave natural única.

    Provado por inversão — o segundo INSERT do mesmo par tem de estourar. Ler o
    catálogo provaria a existência da constraint, não o seu efeito.

    E o mesmo `subject` em **issuer diferente** é outra identidade (cenário 15
    da matriz, proibição 7 do ADR): tem de ser aceito.
    """
    subject = f"sec01a-chave-{uuid.uuid4().hex[:8]}"
    params = dict(_PRINCIPAL_TESTE, subject=subject)
    await platform_session.execute(_SQL_INSERE_PRINCIPAL, params)

    with pytest.raises(DBAPIError) as exc:
        await platform_session.execute(_SQL_INSERE_PRINCIPAL, params)
    await platform_session.rollback()
    assert "uq_platform_principal_iss_sub" in str(exc.value), (
        f"esperava violação da chave natural (issuer, subject); recebi: {exc.value}"
    )

    # Mesmo subject, outro issuer: identidades distintas, INSERT aceito.
    await platform_session.execute(_SQL_INSERE_PRINCIPAL, params)
    await platform_session.execute(
        _SQL_INSERE_PRINCIPAL,
        dict(params, issuer="https://outro-idp.test.local"),
    )
    await platform_session.rollback()


async def test_platform_principal_recusa_issuer_que_nao_e_url(
    platform_session: AsyncSession,
) -> None:
    """O `CHECK` de `issuer` é a parte "proibido por constraint" do ADR §2.2:
    a coluna não aceita um id de usuário municipal nem um e-mail no lugar do
    issuer OIDC."""
    for issuer_invalido in ("42", EMAIL_OPERADOR, ""):
        with pytest.raises(DBAPIError) as exc:
            await platform_session.execute(
                _SQL_INSERE_PRINCIPAL,
                dict(
                    _PRINCIPAL_TESTE,
                    issuer=issuer_invalido,
                    subject=f"sec01a-issuer-{uuid.uuid4().hex[:8]}",
                ),
            )
        await platform_session.rollback()
        assert "ck_platform_principal_issuer_url" in str(exc.value), (
            f"issuer `{issuer_invalido}` foi aceito ou falhou por outro motivo: "
            f"{exc.value}"
        )
