"""SEC-01A — a matriz de claims, cenário a cenário.

Contrato: `docs/architecture/security/platform-operator-claims-matrix.md`.
Cada teste nomeia o número do cenário que trava. Os que não estão aqui estão
declarados no fim do arquivo, com o motivo — uma matriz normativa com cobertura
parcial e silenciosa é pior do que uma sem cobertura, porque parece completa.

Todos os testes sobem pela **borda HTTP real** (`ASGITransport` sobre o app),
com token emitido pelos fixtures de SEC-00 e o JWKS servido em memória. Nenhum
`dependency_overrides` no gate: sobrescrever a dependência sob teste faria o
teste concordar consigo mesmo em vez de exercitar a validação.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fixtures.platform_operator_tokens import (
    MUNICIPAL_AUDIENCE,
    MUNICIPAL_ISSUER,
    TEST_ISSUER,
)

from app.main import app

ROTA = "/api/v2/admin/tenants"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _get(token: str | None = None, rota: str = ROTA, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(rota, headers=headers, **kwargs)


@pytest.fixture(autouse=True)
async def _descarta_engine_municipal():
    """O `TenantMiddleware` e `/admin/me` usam o engine municipal global; sem
    descartá-lo, o pool sobrevive ao event loop do teste e o seguinte quebra
    com `Event loop is closed`."""
    yield
    from app.database import engine as app_engine

    await app_engine.dispose()


# ---------------------------------------------------------------------------
# Cenário 1 — o caso feliz. Sem ele, todo "deny" abaixo poderia estar provando
# apenas que a fronteira nega tudo.
# ---------------------------------------------------------------------------


async def test_cenario_1_token_valido_e_principal_ativo_passa(principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    r = await _get(plataforma_configurada.token(subject=subject))
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


async def test_gate_nao_olha_e_mail_nenhum(principal_ativo, plataforma_configurada):
    """O contraponto direto de F-01: o mesmo principal passa com QUALQUER
    rótulo de e-mail no token, inclusive nenhum. Se algum dia alguém
    reintroduzir uma comparação de e-mail no caminho de decisão, este teste é o
    que quebra primeiro."""
    subject, _ = principal_ativo
    r = await _get(
        plataforma_configurada.token(subject=subject, email="qualquer-outro@test.local")
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Cenários 2, 3, 15 e 20 — autorização: o principal
# ---------------------------------------------------------------------------


async def test_cenario_3_principal_inexistente_e_403(plataforma_configurada):
    """Autenticado no IdP não é autorizado. É exatamente o 403 que o runbook §2
    manda provocar no bootstrap, para então colher `(iss, sub)` do registro."""
    r = await _get(plataforma_configurada.token(subject=f"sem-principal-{uuid.uuid4().hex[:8]}"))
    assert r.status_code == 403, r.text


async def test_cenario_3_tentativa_negada_deixa_trilha_com_iss_e_sub(
    admin_engine, plataforma_configurada
):
    """A trilha da tentativa negada NÃO é decoração: é a única fonte de
    `(iss, sub)` para o bootstrap do primeiro operador (runbook §2, passo 2).

    Prova por leitura da linha, não por "não estourou": o caminho de auditoria
    de plataforma não pode depender do silêncio de `services/audit.py`, que
    engole a exceção do flush.
    """
    subject = f"negado-{uuid.uuid4().hex[:8]}"
    r = await _get(plataforma_configurada.token(subject=subject))
    assert r.status_code == 403

    async with _sm(admin_engine)() as s:
        linha = (
            await s.execute(
                text(
                    "SELECT issuer, acao, platform_principal_id, detalhe "
                    "FROM aprimora_py.platform_audit_log WHERE subject = :s"
                ),
                {"s": subject},
            )
        ).one_or_none()
        assert linha is not None, (
            "tentativa negada não deixou linha em platform_audit_log — sem ela o "
            "runbook §2 não tem de onde tirar o par (iss, sub) do operador novo"
        )
        assert linha.issuer == TEST_ISSUER
        assert linha.acao == "plataforma.acesso_negado"
        assert linha.platform_principal_id is None
        await s.execute(
            text("DELETE FROM aprimora_py.platform_audit_log WHERE subject = :s"),
            {"s": subject},
        )
        await s.commit()


async def test_cenario_2_principal_inativo_e_403(admin_engine, principal_ativo, plataforma_configurada):
    subject, principal_id = principal_ativo
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE aprimora_py.platform_principal SET ativo = false WHERE id = :p"),
            {"p": principal_id},
        )
        await s.commit()
    r = await _get(plataforma_configurada.token(subject=subject))
    assert r.status_code == 403, r.text


async def test_cenario_15_mesmo_subject_outro_issuer_e_403(principal_ativo, plataforma_configurada):
    """Proibição 7 do ADR: o mesmo `sub` vindo de outro issuer **não** é a mesma
    identidade. O token é assinado pela mesma chave, então o que nega é o par,
    não a criptografia."""
    subject, _ = principal_ativo
    r = await _get(plataforma_configurada.token_de_outro_issuer(subject=subject))
    # Recusado já na validação do token (`iss` diferente do configurado) — mais
    # cedo do que o 403 que a matriz admite, e por motivo mais forte.
    assert r.status_code == 401, r.text


async def test_cenario_20_break_glass_expirado_e_403(
    admin_engine, principal_ativo, plataforma_configurada
):
    """Janela de emergência vencida nega mesmo com `ativo = true` gravado.

    Sem esta verificação, o break-glass de 60 minutos (ADR §2.8) viraria acesso
    permanente concedido durante um incidente — que é o modo clássico de o
    procedimento de emergência virar a porta dos fundos.
    """
    subject, principal_id = principal_ativo
    agora = datetime.utcnow()
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE aprimora_py.platform_principal "
                "SET break_glass = true, valid_from = :de, valid_until = :ate "
                "WHERE id = :p"
            ),
            {"de": agora - timedelta(hours=2), "ate": agora - timedelta(hours=1), "p": principal_id},
        )
        await s.commit()
    r = await _get(plataforma_configurada.token(subject=subject))
    assert r.status_code == 403, r.text


async def test_revogacao_tem_efeito_imediato(admin_engine, principal_ativo, plataforma_configurada):
    """ADR §2.4: o principal é consultado a CADA requisição, sem cache de
    sessão. Provado por inversão: o mesmo token passa, é revogado, e o mesmo
    token para de passar — sem esperar o `exp`."""
    subject, principal_id = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    assert (await _get(token)).status_code == 200

    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE aprimora_py.platform_principal SET ativo = false, "
                "revogado_em = NOW(), revogado_por = 'teste', "
                "motivo_revogacao = 'revogação imediata' WHERE id = :p"
            ),
            {"p": principal_id},
        )
        await s.commit()

    assert (await _get(token)).status_code == 403, (
        "o MESMO token continuou valendo depois da revogação — sinal de cache de "
        "sessão, que é justamente o que faria a revogação levar 8 h em vez de minutos"
    )


# ---------------------------------------------------------------------------
# Cenários 4, 5 e §2 — confusão de token
# ---------------------------------------------------------------------------


async def test_cenario_4_token_municipal_hs256_e_401(plataforma_configurada):
    """Token no formato municipal real — `build_payload` é a função que a
    aplicação usa para emitir a sessão de qualquer servidor de prefeitura."""
    from jose import jwt as jose_jwt

    from app.auth.jwt import build_payload

    token = jose_jwt.encode(build_payload(1, "x@y.test", 1), "segredo-municipal", algorithm="HS256")
    assert (await _get(token)).status_code == 401


async def test_cenario_4_realm_municipal_com_assinatura_valida_e_401(plataforma_configurada):
    """A variante que importa: token assinado pela chave **certa** do IdP de
    plataforma, mas com `iss`/`aud` municipais. O que nega é o realm, não a
    assinatura — que é a propriedade que o ADR §2.2 pede."""
    token = plataforma_configurada.token(issuer=MUNICIPAL_ISSUER, audience=MUNICIPAL_AUDIENCE)
    assert (await _get(token)).status_code == 401


async def test_claims_municipais_em_token_de_plataforma_sao_recusados(
    principal_ativo, plataforma_configurada
):
    """Matriz §2: `usuario_id`, `tenant_id`, `conexao`, `app` num token de
    plataforma são **rejeição**, não "ignorar o campo".

    Aqui o token é impecável em tudo o mais — issuer certo, audience certa,
    assinatura válida, principal ativo. Ignorar os claims municipais o aceitaria,
    e é exatamente o cenário de um realm fundido por engano de configuração.
    """
    subject, _ = principal_ativo
    token = plataforma_configurada.token(
        subject=subject,
        claims_extras={"usuario_id": 1, "tenant_id": 1, "conexao": "ged_saas_db", "app": "sistemas"},
    )
    assert (await _get(token)).status_code == 401


async def test_cenario_5_token_de_cidadao_e_401(plataforma_configurada):
    from app.auth.jwt import build_cidadao_payload

    from jose import jwt as jose_jwt

    token = jose_jwt.encode(
        build_cidadao_payload(1, "00000000000", 1), "segredo-municipal", algorithm="HS256"
    )
    assert (await _get(token)).status_code == 401


async def test_cookie_municipal_nao_autentica_a_fronteira(principal_ativo, plataforma_configurada):
    """O gate lê **só** o header `Authorization`. Aceitar o cookie
    `aprimora_token` recriaria o compartilhamento de sessão que o ADR §1.5
    aponta como defeito — e é o embrião dos cenários 17/18, de SEC-01B."""
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(ROTA, cookies={"aprimora_token": token})
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Cenários 6 a 11 — o token em si
# ---------------------------------------------------------------------------


async def test_cenario_6_audience_de_outro_ambiente_e_401(plataforma_configurada):
    """Um token de homologação apresentado em produção. É o que a audience por
    ambiente existe para pegar."""
    assert (await _get(plataforma_configurada.token_de_outro_ambiente())).status_code == 401


async def test_cenario_7_hs256_com_segredo_municipal_e_401(principal_ativo, plataforma_configurada):
    """Recusado **pelo algoritmo**, não pela assinatura.

    A diferença é a razão de o cenário existir: o segredo HS256 municipal é o
    mesmo do PHP legado (ADR §1.4). Uma fronteira que recusa "porque a
    assinatura não bateu" passa a depender de um segredo que já circula fora
    daqui; recusando pelo header, o segredo poderia ser público que não muda
    nada. O teste prova a propriedade forte: mesmo assinado com o segredo certo
    do realm municipal, o token não entra.
    """
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, segredo_hs256="segredo-municipal")
    r = await _get(token)
    assert r.status_code == 401
    assert "algoritmo" in r.json()["detail"].lower(), (
        f"esperava recusa pelo ALGORITMO; recebi: {r.json()['detail']}"
    )


async def test_cenario_8_alg_none_e_401(principal_ativo, plataforma_configurada):
    """`alg: none` não sai do `OperatorTokenFactory` (o python-jose se recusa a
    emitir), então é montado à mão aqui — é o único jeito de exercitar o
    cenário sem um emissor que produza tokens inseguros."""
    subject, _ = principal_ativo
    agora = int(time.time())
    payload = {
        "iss": TEST_ISSUER,
        "aud": "aprimora-operator-test",
        "sub": subject,
        "iat": agora,
        "exp": agora + 900,
        "hd": "test.local",
        "email_verified": True,
    }

    def _b64(dados: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()

    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}."
    assert (await _get(token)).status_code == 401


async def test_cenario_9_token_expirado_e_401(plataforma_configurada):
    assert (await _get(plataforma_configurada.token_expirado())).status_code == 401


async def test_cenario_10_iat_no_futuro_e_401(principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, emitido_ha=-300)
    r = await _get(token)
    assert r.status_code == 401, r.text


async def test_tolerancia_de_relogio_de_60s_e_aceita(principal_ativo, plataforma_configurada):
    """A matriz permite **até** 60 s de tolerância. Sem este controle, o teste
    anterior passaria com uma implementação que rejeitasse qualquer desvio —
    inclusive o relógio do container adiantado por meio segundo."""
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, emitido_ha=-30)
    assert (await _get(token)).status_code == 200


async def test_token_sem_exp_e_401(principal_ativo, plataforma_configurada):
    """`exp` é obrigatório (matriz §1) — e não era exigido.

    A python-jose 3.3.0 tem `require_exp` com default `False`, e
    `_validate_exp` começa com `if "exp" not in claims: return`. O token sem
    `exp` passava por toda a cadeia. O dano não é teórico: um token que **nunca
    expira** rebaixa a revogação do principal de defesa em profundidade a defesa
    única — some a camada que faz o acesso morrer sozinho em 15 minutos.

    O Google sempre emite `exp`, então isto não era explorável contra ele. Mas
    `PLATFORM_OIDC_ISSUER` é configurável para qualquer IdP, e o módulo afirma
    fail-closed em tudo.
    """
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, omitir=("exp",))
    assert (await _get(token)).status_code == 401


async def test_token_sem_aud_e_401(principal_ativo, plataforma_configurada):
    """`aud` é obrigatório (matriz §1) — mesma armadilha do `require_exp`.

    É o outro lado do cenário 24: lá se prova que **sem audience configurada**
    a fronteira nega; aqui, que um token **sem o claim** também nega. Faltando
    este, a audience deixa de discriminar ambiente — um token de homologação
    sem `aud` seria aceito em produção, que é exatamente o que o cenário 6
    existe para impedir.
    """
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, omitir=("aud",))
    assert (await _get(token)).status_code == 401


async def test_cenario_11_kid_desconhecido_e_401(principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, kid="kid-que-nao-esta-no-jwks")
    r = await _get(token)
    assert r.status_code == 401, r.text
    assert "kid" in r.json()["detail"].lower()


async def test_cenario_12_jwks_indisponivel_com_cache_expirado_e_503(
    monkeypatch, principal_ativo, plataforma_configurada
):
    """`503`, **nunca** allow (ADR §2.6, proibição 8).

    O 503 é a metade que se costuma esquecer: um `401` aqui mentiria sobre a
    causa e mandaria o operador procurar defeito na credencial dele enquanto o
    problema é nosso.
    """
    from app.auth import plataforma as validador

    subject, _ = principal_ativo

    async def _jwks_fora_do_ar(url: str):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(validador, "_buscar_jwks", _jwks_fora_do_ar)
    validador.limpar_cache_jwks()  # cache vazio == cache expirado

    r = await _get(plataforma_configurada.token(subject=subject))
    assert r.status_code == 503, r.text


async def test_jwks_em_cache_sobrevive_a_queda_do_idp(
    monkeypatch, principal_ativo, plataforma_configurada
):
    """Contrapeso do cenário 12: com cache **válido**, a queda do IdP não
    derruba a fronteira. Sem este teste, a implementação mais simples que
    satisfaz o 503 seria "nunca cachear", e aí toda requisição bateria no
    Google."""
    from app.auth import plataforma as validador

    subject, _ = principal_ativo
    assert (await _get(plataforma_configurada.token(subject=subject))).status_code == 200

    async def _jwks_fora_do_ar(url: str):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(validador, "_buscar_jwks", _jwks_fora_do_ar)
    assert (await _get(plataforma_configurada.token(subject=subject))).status_code == 200


def test_teto_de_cache_do_jwks_e_24h():
    """Runbook §6: respeitar o `Cache-Control` do IdP, com teto de 24 h."""
    from app.auth.plataforma import TETO_CACHE_JWKS_S, _max_age

    assert _max_age("public, max-age=3600") == 3600
    assert _max_age("public, max-age=999999") == TETO_CACHE_JWKS_S
    assert _max_age("") > 0  # sem cabeçalho, cacheia por um piso, não para sempre


# ---------------------------------------------------------------------------
# Cenários 13 e 14 — política de domínio e de conta
# ---------------------------------------------------------------------------


async def test_cenario_13_hd_de_outro_dominio_e_403(principal_ativo, plataforma_configurada):
    """Com principal EXISTENTE, como a matriz especifica: o que nega é o
    domínio, não a ausência de cadastro."""
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, hosted_domain="dominio-alheio.test")
    assert (await _get(token)).status_code == 403


async def test_hd_ausente_e_403(principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, hosted_domain=None)
    assert (await _get(token)).status_code == 403


async def test_cenario_14_email_nao_verificado_e_403(principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject, email_verified=False)
    assert (await _get(token)).status_code == 403


# ---------------------------------------------------------------------------
# Cenário 16 — a recíproca: o realm municipal recusa o token de plataforma
# ---------------------------------------------------------------------------


async def test_cenario_16_token_de_plataforma_em_rota_municipal_e_401(
    principal_ativo, plataforma_configurada
):
    """Já valia antes deste PR (o `decode_token` municipal casa `iss`/`aud`
    próprios), e é justamente por isso que precisa de teste: a propriedade é
    frágil a alguém apontar `JWT_ISS`/`JWT_AUD` para os valores de plataforma,
    e nada avisaria."""
    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    r = await _get(token, rota="/api/v2/permissoes/me")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Cenários 19 e "papel de banco" — a sessão dedicada
# ---------------------------------------------------------------------------


def test_cenario_19_operacao_sem_tenant_alvo_explicito_e_400():
    from fastapi import HTTPException

    from app.auth.plataforma import exigir_tenant_alvo

    assert exigir_tenant_alvo(7) == 7
    with pytest.raises(HTTPException) as ei:
        exigir_tenant_alvo(None)
    assert ei.value.status_code == 400


async def test_sessao_de_plataforma_nao_herda_app_tenant_id(plataforma_configurada):
    """A propriedade estrutural do item 5 do ADR §2.2, provada onde importa.

    A sessão municipal recebe `SET LOCAL app.tenant_id` a cada BEGIN, a partir
    do `Host`. Se a de plataforma herdasse isso, uma operação cross-tenant
    ficaria em cima do tenant de quem chamou — e a auditoria do alvo iria parar
    no tenant errado.
    """
    from app.database_plataforma import sessao_plataforma

    async with sessao_plataforma() as s:
        atual = (
            await s.execute(text("SELECT current_setting('app.tenant_id', true)"))
        ).scalar_one()
    assert not atual, f"a sessão de plataforma nasceu com app.tenant_id = {atual!r}"


async def test_sessao_de_plataforma_usa_o_papel_aprimora_platform(plataforma_configurada):
    """Matriz §3, "Papel de banco". Sem isto, `PLATFORM_DB_URL` poderia apontar
    para `ged_user` e tudo continuaria verde — com a fronteira inteira rodando
    em SUPERUSER/BYPASSRLS, que é o achado F-12."""
    from app.database_plataforma import sessao_plataforma

    async with sessao_plataforma() as s:
        papel, super_usuario, bypass = (
            await s.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()
    assert papel == "aprimora_platform"
    assert super_usuario is False
    assert bypass is False


async def test_sem_platform_db_url_a_fronteira_devolve_500_e_nao_cai_no_pool_municipal(
    monkeypatch, plataforma_configurada, principal_ativo
):
    """Erro de CONFIGURAÇÃO (500), nunca fallback silencioso para `get_db`.

    Cair no pool municipal seria trocar uma indisponibilidade por um contorno da
    fronteira inteira — e ninguém perceberia, porque tudo continuaria
    funcionando.
    """
    from app.config import get_settings

    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_DB_URL", "")
    get_settings.cache_clear()
    r = await _get(token)
    assert r.status_code == 500, r.text


# ---------------------------------------------------------------------------
# Cenários 23 e 24 — configuração ausente nega
# ---------------------------------------------------------------------------


async def test_cenario_23_hosted_domain_ausente_nega_tudo(
    monkeypatch, principal_ativo, plataforma_configurada
):
    """`PLATFORM_OIDC_HOSTED_DOMAIN` sem default (D-2). Ausente ⇒ nega, e nunca
    "aceita qualquer `hd`" — que é o que um default embutido produziria."""
    from app.config import get_settings

    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_OIDC_HOSTED_DOMAIN", "")
    get_settings.cache_clear()
    assert (await _get(token)).status_code == 403


async def test_cenario_24_audience_ausente_nega_tudo(
    monkeypatch, principal_ativo, plataforma_configurada
):
    from app.config import get_settings

    subject, _ = principal_ativo
    token = plataforma_configurada.token(subject=subject)
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_OIDC_AUDIENCE", "")
    get_settings.cache_clear()
    assert (await _get(token)).status_code == 401


def test_configuracao_de_plataforma_nao_tem_default(monkeypatch):
    """A garantia por trás dos cenários 23 e 24, no nível da configuração.

    Um `Settings` com `extra="ignore"` engole variável digitada errada; o
    fail-closed, portanto, não pode depender do Pydantic reclamar. Aqui se
    afirma que o valor de fábrica é vazio — se alguém puser um default
    "conveniente" no futuro, quebra aqui e não em produção.
    """
    from app.config import Settings

    for campo in (
        "platform_oidc_issuer",
        "platform_oidc_audience",
        "platform_oidc_jwks_url",
        "platform_oidc_hosted_domain",
        "platform_db_url",
    ):
        assert Settings.model_fields[campo].default == "", (
            f"`{campo}` ganhou default. Configuração faltante tem de NEGAR "
            "(ADR-016 §2.6); um default embutido converte esquecimento em porta aberta."
        )


def test_allowlist_de_email_saiu_do_caminho_de_decisao():
    """O critério de aceite de SEC-01A, verificado no código e não na prosa."""
    from app import config as cfg
    from app.auth import deps

    assert not hasattr(cfg, "is_platform_admin"), (
        "`is_platform_admin` voltou ao `config.py` — é o caminho de decisão do "
        "achado F-01 (autorização por string de e-mail)."
    )
    assert "platform_admin_emails" not in cfg.Settings.model_fields
    assert not hasattr(deps, "require_platform_admin"), (
        "o gate de plataforma voltou para `auth/deps.py`, que é a cadeia de "
        "identidade MUNICIPAL. Ele vive em `auth/plataforma.py`."
    )


# ---------------------------------------------------------------------------
# Cenário 22 — teste arquitetural
# ---------------------------------------------------------------------------


def test_cenario_22_nenhum_endpoint_cria_principal_de_plataforma():
    """ADR §2.2, item 3: nenhum caminho municipal cria, altera, ativa ou concede
    `platform_principal`. "Impossível por construção" tem de ser verificável, e
    revisão de código não é verificação.

    Duas afirmações independentes:
      1. o app **não expõe rota alguma** que fale de principal;
      2. nenhum módulo de `app/routers/` constrói ou insere um principal — usar
         o tipo como anotação é permitido, escrever não é.
    """
    from pathlib import Path

    from app.main import app as fastapi_app

    rotas = [getattr(r, "path", "") for r in fastapi_app.routes]
    assert not [p for p in rotas if "principal" in p.lower()], (
        f"apareceu rota HTTP falando de principal: {[p for p in rotas if 'principal' in p.lower()]}. "
        "A concessão é por CLI no host, com dupla presença — um endpoint que cria "
        "o primeiro operador é um endpoint que cria o segundo (runbook §2)."
    )

    routers = Path(__file__).resolve().parent.parent / "app" / "routers"
    ofensores = []
    for arquivo in sorted(routers.glob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if "PlatformPrincipal(" in texto or "INSERT INTO aprimora_py.platform_principal" in texto:
            ofensores.append(arquivo.name)
    assert ofensores == [], (
        f"módulos de router escrevendo em platform_principal: {ofensores}. "
        "A escrita mora em `app/cli/platform_principal.py`, executada no host."
    )


# ---------------------------------------------------------------------------
# O que este arquivo NÃO cobre, e por quê
#
#   21  — mora em `test_platform_admin_identity.py`, junto do resto do
#         esquema; é o teste vermelho que abriu o PR e o marcador `xfail`
#         removido é a prova de que ele virou verde por trabalho, não por
#         asserção afrouxada.
#   17  — cookie de operador enviado a API municipal.
#   18  — cookie municipal enviado ao console de operador.
#         Ambos pressupõem o cookie e a árvore React do console, que nascem em
#         `SEC-01B`. O que dá para travar hoje está em
#         `test_cookie_municipal_nao_autentica_a_fronteira`.
# ---------------------------------------------------------------------------
