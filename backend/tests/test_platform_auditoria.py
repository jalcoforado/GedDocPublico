"""SEC-01A — decisão **D-a**: as duas trilhas, e a que o município enxerga.

Por que um arquivo só para isto. A auditoria é o tipo de coisa que "passa" sem
existir: `services/audit.py` engole a exceção do flush (linhas ~68-70), de modo
que uma rota pode responder 200, parecer auditada e não ter gravado nada. Esse
silêncio é dívida conhecida e sai em `SEC-RLS-00B`; o caminho de plataforma,
porém, **não pode depender dele** — e "não depende" só é afirmável lendo a linha
gravada. Todos os testes aqui vão ao banco conferir a linha.

A trilha do município é a parte que mais tenta sumir numa refatoração: ela é
"redundante" à primeira vista, e não é. Sem ela a prefeitura perde o registro de
que seu cadastro foi alterado ou seu módulo contratado — por alguém de fora
dela. Um PR de segurança que apaga o rastro do titular do dado piorou a
segurança.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def cliente_operador(principal_ativo, plataforma_configurada):
    subject, principal_id = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c, principal_id
    from app.database import engine as app_engine

    await app_engine.dispose()


@pytest_asyncio.fixture
async def tenants_limpos(admin_engine, two_tenants):
    """`two_tenants` + limpeza das tabelas que a operação de plataforma toca.

    O teardown de `two_tenants` não conhece `audit_log`, `tenant_modulo` nem
    `platform_audit_log`; sem esta limpeza o `DELETE FROM aprimora_py.tenant`
    bate nas FKs e o teste termina em erro mesmo passando.
    """
    yield two_tenants
    tid_a, tid_b = two_tenants
    async with _sm(admin_engine)() as s:
        for tabela in (
            "aprimora_py.platform_audit_log",
            "aprimora_py.audit_log",
            "aprimora_py.tenant_modulo",
        ):
            coluna = "tenant_alvo_id" if "platform" in tabela else "tenant_id"
            await s.execute(
                text(f"DELETE FROM {tabela} WHERE {coluna} IN (:a, :b)"),
                {"a": tid_a, "b": tid_b},
            )
        await s.commit()


@pytest.mark.asyncio
async def test_contratacao_grava_as_duas_trilhas(admin_engine, cliente_operador, tenants_limpos):
    """A trilha autoritativa **e** a do município, com o mesmo `correlation_id`.

    O `correlation_id` compartilhado não é enfeite: é o que permite, num
    incidente, casar "o que o operador fez" com "o que a prefeitura viu".
    """
    cliente, principal_id = cliente_operador
    tenant_id, _outro = tenants_limpos

    r = await cliente.put(
        f"/api/v2/admin/tenants/{tenant_id}/modulos",
        json={"slugs": ["protocolo", "frota"]},
    )
    assert r.status_code == 200, r.text

    async with _sm(admin_engine)() as s:
        plataforma = (
            await s.execute(
                text(
                    "SELECT platform_principal_id, issuer, subject, acao, "
                    "       tenant_alvo_id, detalhe, correlation_id "
                    "  FROM aprimora_py.platform_audit_log "
                    " WHERE tenant_alvo_id = :t AND acao = 'tenant.modulos_definidos'"
                ),
                {"t": tenant_id},
            )
        ).one_or_none()
        assert plataforma is not None, (
            "a trilha AUTORITATIVA não foi gravada. Uma operação cross-tenant sem "
            "registro de quem a fez é pior do que uma operação recusada."
        )
        assert plataforma.platform_principal_id == principal_id
        assert plataforma.detalhe == {"slugs": ["frota", "protocolo"]}

        municipal = (
            await s.execute(
                text(
                    "SELECT tenant_id, id_usuario, acao, entidade, payload, request_id "
                    "  FROM aprimora_py.audit_log "
                    " WHERE tenant_id = :t AND acao = 'tenant.modulos_definidos'"
                ),
                {"t": tenant_id},
            )
        ).one_or_none()
        assert municipal is not None, (
            "a entrada VISÍVEL AO MUNICÍPIO sumiu. Ela existia antes de SEC-01A e "
            "a decisão D-a manda preservá-la: sem ela a prefeitura não fica "
            "sabendo que seu módulo foi contratado."
        )
        assert municipal.tenant_id == tenant_id
        assert municipal.id_usuario is None, (
            "`id_usuario` tem de ser nulo: o operador de plataforma não é um "
            "`utils.usuario`, e forçá-lo na coluna violaria a FK"
        )
        assert municipal.request_id == plataforma.correlation_id


@pytest.mark.asyncio
async def test_trilha_do_municipio_vai_para_o_tenant_ALVO_e_nao_para_o_do_host(
    admin_engine, cliente_operador, tenants_limpos
):
    """A propriedade cross-tenant, provada por inversão.

    A requisição chega com o `Host` do tenant A — que é o que o
    `TenantMiddleware` resolve e o que a sessão municipal instalaria em
    `app.tenant_id`. A operação, porém, é sobre o tenant **B**. Se a auditoria
    herdasse o tenant do middleware, a linha cairia em A: a prefeitura errada
    veria um registro que não é dela, e a certa não veria nada.

    Hoje isso passaria mesmo errado, porque o runtime ainda tem `BYPASSRLS`
    (F-12) e a linha entraria em qualquer lugar. Por isso o teste confere o
    `tenant_id` da linha, e não apenas que ela existe.
    """
    cliente, _ = cliente_operador
    tenant_a, tenant_b = tenants_limpos

    async with _sm(admin_engine)() as s:
        slug_a = (
            await s.execute(
                text("SELECT slug FROM aprimora_py.tenant WHERE id = :t"), {"t": tenant_a}
            )
        ).scalar_one()

    from app.config import get_settings

    r = await cliente.put(
        f"/api/v2/admin/tenants/{tenant_b}",
        json={"nome": "Prefeitura Renomeada"},
        headers={"Host": f"{slug_a}.{get_settings().base_domain}"},
    )
    assert r.status_code == 200, r.text

    async with _sm(admin_engine)() as s:
        linhas = (
            await s.execute(
                text(
                    "SELECT tenant_id FROM aprimora_py.audit_log "
                    " WHERE acao = 'tenant.editado' AND tenant_id IN (:a, :b)"
                ),
                {"a": tenant_a, "b": tenant_b},
            )
        ).scalars().all()
    assert linhas == [tenant_b], (
        f"a trilha do município caiu em {linhas}, esperado apenas [{tenant_b}]. "
        "Auditoria de operação de plataforma pertence ao tenant ALVO, nunca ao "
        "tenant do `Host` de quem chamou."
    )


@pytest.mark.asyncio
async def test_provisionar_tenant_pela_borda_http_com_token_administrativo(
    admin_engine, cliente_operador
):
    """`POST /admin/tenants` é a única rota de plataforma com **duas** sessões:
    a municipal, porque `provisionar_tenant` semeia `utils.*` (e o papel de
    plataforma não tem — nem deve ter — DML ali), e a de plataforma, para a
    trilha. Partir o provisionamento é item de `SEC-RLS-00B`.

    A combinação não tinha teste HTTP nenhum antes deste PR: os testes de
    provisionamento chamavam o serviço direto. Sem este, a rota poderia estar
    quebrada — por sessão trocada, por `ator_usuario_id` inválido, por qualquer
    coisa — e a suíte inteira continuaria verde.
    """
    import uuid

    cliente, principal_id = cliente_operador
    slug = f"sec01a-http-{uuid.uuid4().hex[:6]}"
    tenant_id = None
    try:
        r = await cliente.post(
            "/api/v2/admin/tenants",
            json={
                "slug": slug,
                "nome": "Prefeitura Provisionada por Operador",
                "admin_email": f"{slug}@teste.test",
                "admin_nome": "Administrador",
                "admin_cpf": uuid.uuid4().hex[:11],
            },
        )
        assert r.status_code == 201, r.text
        corpo = r.json()
        tenant_id = corpo["tenant"]["id"]
        assert corpo["senha_temporaria"]

        async with _sm(admin_engine)() as s:
            trilha = (
                await s.execute(
                    text(
                        "SELECT platform_principal_id, acao FROM aprimora_py.platform_audit_log "
                        " WHERE tenant_alvo_id = :t"
                    ),
                    {"t": tenant_id},
                )
            ).one_or_none()
            assert trilha is not None, "provisionamento por operador sem trilha de plataforma"
            assert trilha.platform_principal_id == principal_id
            assert trilha.acao == "tenant.provisionado"
    finally:
        if tenant_id is not None:
            async with _sm(admin_engine)() as s:
                for stmt in (
                    "DELETE FROM aprimora_py.platform_audit_log WHERE tenant_alvo_id=:t",
                    "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
                    "DELETE FROM utils.grupo WHERE tenant_id=:t",
                    "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
                    "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
                    "DELETE FROM utils.usuario WHERE tenant_id=:t",
                    "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
                    "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
                    "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
                    "DELETE FROM aprimora_py.tenant WHERE id=:t",
                ):
                    await s.execute(text(stmt), {"t": tenant_id})
                await s.commit()


@pytest.mark.asyncio
async def test_provisionamento_que_para_no_ato_municipal_devolve_500_e_deixa_tenant_inerte(
    monkeypatch, admin_engine, cliente_operador
):
    """O modo de falha da partição, pela borda HTTP (SEC-RLS-00C).

    Os dois atos são transações separadas — o de plataforma comita antes de o
    municipal começar —, então esta é a única rota do sistema que pode terminar
    com "meio feito". O contrato, verificado aqui inteiro:

    1. a resposta é **500**, não 201 e não 400. `ProvisionamentoIncompletoError`
       herda de `ProvisioningError`, cujo `except` mapeia para 400; se alguém
       trocar a ordem das cláusulas, o operador recebe "payload inválido" para
       um pedido que estava correto e cujo tenant já existe no banco;
    2. o tenant existe e está **inativo** — nada foi apagado por compensação, e
       o município não resolve por subdomínio;
    3. a trilha AUTORITATIVA registra `tenant.provisionamento_incompleto`. Sem
       isso, o único registro do incidente seria uma linha de log.

    A falha é injetada em `hash_password`, que roda no meio do ato municipal —
    depois do commit do ato de plataforma, antes do commit do municipal. É o
    ponto exato onde a partição dói.
    """
    import uuid

    import app.services.provisioning_tenant as ps

    def _boom(_):
        raise RuntimeError("falha simulada no ato municipal")

    monkeypatch.setattr(ps, "hash_password", _boom)

    cliente, principal_id = cliente_operador
    slug = f"sec00c-parcial-{uuid.uuid4().hex[:6]}"
    tenant_id = None
    try:
        r = await cliente.post(
            "/api/v2/admin/tenants",
            json={
                "slug": slug,
                "nome": "Provisionamento que para no meio",
                "admin_email": f"{slug}@teste.test",
                "admin_nome": "Administrador",
                "admin_cpf": uuid.uuid4().hex[:11],
            },
        )
        assert r.status_code == 500, (
            f"esperava 500; recebi {r.status_code}: {r.text}. 400 aqui significa "
            "que o `except ProvisioningError` capturou antes do específico."
        )
        assert "retomar" in r.text, (
            "a resposta precisa dizer COMO concluir — o tenant já existe e o "
            "operador fica sem instrução."
        )

        async with _sm(admin_engine)() as s:
            linha = (
                await s.execute(
                    text("SELECT id, ativo FROM aprimora_py.tenant WHERE slug = :s"),
                    {"s": slug},
                )
            ).first()
            assert linha is not None, (
                "o tenant sumiu: alguém acrescentou compensação por DELETE."
            )
            tenant_id = linha.id
            assert linha.ativo is False, "o tenant incompleto ficou ATIVO"

            acoes = [
                a
                for (a,) in (
                    await s.execute(
                        text(
                            "SELECT acao FROM aprimora_py.platform_audit_log "
                            " WHERE tenant_alvo_id = :t ORDER BY id"
                        ),
                        {"t": tenant_id},
                    )
                ).all()
            ]
            assert acoes == ["tenant.provisionamento_incompleto"], (
                f"trilha de plataforma inesperada: {acoes}"
            )
    finally:
        if tenant_id is not None:
            async with _sm(admin_engine)() as s:
                for stmt in (
                    "DELETE FROM aprimora_py.platform_audit_log WHERE tenant_alvo_id=:t",
                    "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
                    "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
                    "DELETE FROM aprimora_py.tenant WHERE id=:t",
                ):
                    await s.execute(text(stmt), {"t": tenant_id})
                await s.commit()


@pytest.mark.asyncio
async def test_falha_da_projecao_municipal_nao_vira_500_e_fica_auditada(
    monkeypatch, admin_engine, cliente_operador, tenants_limpos
):
    """A projeção municipal falha **depois** do commit. A resposta é sucesso.

    Nesse ponto a alteração já está aplicada: propagar a exceção devolveria 500
    sobre uma operação bem-sucedida, o que mente sobre o resultado e convida o
    operador a repetir — em `definir_modulos`, repetir é reescrever a
    contratação.

    Mas "não virar 500" não pode significar "sumir". As duas metades são
    verificadas: a operação **de fato aconteceu** (a contratação está no banco)
    e a falha **de fato foi registrada** na trilha autoritativa, com o mesmo
    `correlation_id`. É essa segunda metade que separa isto do `except
    Exception` de `services/audit.py`, que o próprio PR critica: lá a trilha
    engolida é a única e não sobra rastro; aqui a autoritativa está íntegra e a
    perda da projeção é ela mesma um evento auditável.
    """
    import app.routers.admin_tenants as router

    cliente, principal_id = cliente_operador
    tenant_id, _ = tenants_limpos

    async def _projecao_quebrada(**kwargs):
        raise RuntimeError("policy de RLS negou o INSERT na trilha do tenant")

    monkeypatch.setattr(router, "registrar_no_tenant", _projecao_quebrada)

    r = await cliente.put(
        f"/api/v2/admin/tenants/{tenant_id}/modulos",
        json={"slugs": ["protocolo"]},
    )
    assert r.status_code == 200, (
        f"HTTP {r.status_code}: a falha da projeção municipal virou erro para o "
        "cliente, sobre uma operação que JÁ foi comitada."
    )

    async with _sm(admin_engine)() as s:
        contratado = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.tenant_modulo "
                    " WHERE tenant_id = :t AND excluido = false"
                ),
                {"t": tenant_id},
            )
        ).scalar_one()
        assert contratado >= 1, "a operação não foi aplicada — o 200 seria mentira"

        falha = (
            await s.execute(
                text(
                    "SELECT platform_principal_id, detalhe, correlation_id "
                    "  FROM aprimora_py.platform_audit_log "
                    " WHERE tenant_alvo_id = :t "
                    "   AND acao = 'plataforma.projecao_municipal_falhou'"
                ),
                {"t": tenant_id},
            )
        ).one_or_none()
        assert falha is not None, (
            "a projeção municipal falhou em SILÊNCIO. Sem esta linha, a perda da "
            "trilha do município é indetectável — que é exatamente o defeito de "
            "`services/audit.py` que este PR se recusa a repetir."
        )
        assert falha.platform_principal_id == principal_id
        assert falha.detalhe["acao_original"] == "tenant.modulos_definidos"

        sucesso = (
            await s.execute(
                text(
                    "SELECT correlation_id FROM aprimora_py.platform_audit_log "
                    " WHERE tenant_alvo_id = :t AND acao = 'tenant.modulos_definidos'"
                ),
                {"t": tenant_id},
            )
        ).scalar_one()
        assert falha.correlation_id == sucesso, (
            "sem o mesmo correlation_id não dá para casar a falha com a operação "
            "que a causou"
        )


@pytest.mark.asyncio
async def test_falha_da_trilha_autoritativa_nao_e_engolida(admin_engine, principal_ativo):
    """O contraponto explícito a `services/audit.py`.

    Lá, um flush que falha vira log e a operação segue como se nada fosse. Aqui
    não: `registrar_operacao` propaga. Provado forçando um alvo inexistente, que
    viola a FK `tenant_alvo_id → aprimora_py.tenant.id`.
    """
    from sqlalchemy.exc import IntegrityError

    from app.database_plataforma import sessao_plataforma
    from app.models import PlatformPrincipal
    from app.services.plataforma_auditoria import registrar_operacao

    _subject, principal_id = principal_ativo
    async with sessao_plataforma() as db:
        principal = await db.get(PlatformPrincipal, principal_id)
        with pytest.raises(IntegrityError):
            await registrar_operacao(
                db,
                principal=principal,
                acao="teste.alvo_inexistente",
                tenant_alvo_id=999_999_999,
            )
        await db.rollback()
