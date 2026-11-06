"""Conta por e-mail (0136): 2FA no login do servidor, "esqueci a senha",
convite do servidor e confirmação de e-mail do cidadão.

Os e-mails são capturados trocando `conta_email.enviar_email` — o que os
testes conferem é o que sairia para a caixa da pessoa (código, link) e o que
NÃO pode acontecer: sessão emitida antes do código, link reaproveitado, o
desafio do 2FA servindo de sessão, conta de convite entrando sem aceitar.

O tenant vem pelo `Host` (`TenantMiddleware`), como em
`test_sec1_login_me_flag.py`: as rotas públicas leem `request.state`.
"""
from __future__ import annotations

import re
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import hash_password
from app.config import get_settings
from app.main import app
from app.services import conta_email, conta_tokens
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import as_user_dependency

SENHA = "senha-conta-teste"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
def caixa(monkeypatch):
    """Caixa de saída: cada e-mail que o sistema mandaria."""
    enviados: list[dict] = []

    async def _capturar(*, para, assunto, texto, tenant_id=None):
        enviados.append({"para": para, "assunto": assunto, "texto": texto})

    monkeypatch.setattr(conta_email, "enviar_email", _capturar)
    return enviados


@pytest.fixture
def com_2fa(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "dois_fatores_email", True)
    # 2FA só liga com SMTP configurado (sem ele o código não chegaria). Os
    # e-mails são capturados por `caixa`; o host aqui nunca é contatado.
    monkeypatch.setattr(s, "smtp_host", "smtp.teste.invalid")


@pytest_asyncio.fixture
async def cenario(admin_engine):
    slug = f"conta{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Conta", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    email = f"serv-{uuid.uuid4().hex[:8]}@t.local"
    convidado = f"conv-{uuid.uuid4().hex[:8]}@t.local"
    async with _sm(admin_engine)() as s:
        uid = (
            await s.execute(
                text(
                    "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                    "ativo, excluido) VALUES (:t, 'Servidora', :e, '', :bc, :c, true, false) RETURNING id"
                ),
                {"t": tenant.id, "e": email, "bc": hash_password(SENHA), "c": uuid.uuid4().hex[:11]},
            )
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, cpf, "
                "ativo, excluido, email_verificado_em) "
                "VALUES (:t, 'Convidado', :e, '', :bc, :c, true, false, NULL)"
            ),
            {"t": tenant.id, "e": convidado, "bc": hash_password(uuid.uuid4().hex), "c": uuid.uuid4().hex[:11]},
        )
        await s.commit()
        admin_id = (
            await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id = :t AND email = :e"),
                {"t": tenant.id, "e": f"{slug}@t.local"},
            )
        ).scalar_one()
    yield {
        "slug": tenant.slug, "tid": tenant.id, "email": email, "uid": uid,
        "convidado": convidado, "admin_id": admin_id,
    }


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()


def _host(c) -> dict[str, str]:
    return {"Host": f"{c['slug']}.aprimora.local"}


def _codigo(email: dict) -> str:
    return re.search(r"\b(\d{6})\b", email["assunto"]).group(1)


def _token(email: dict) -> str:
    return re.search(r"token=([A-Za-z0-9_\-]+)", email["texto"]).group(1)


async def _login(client, c, email=None, senha=SENHA):
    return await client.post(
        "/api/v2/auth/login", json={"email": email or c["email"], "senha": senha}, headers=_host(c)
    )


# ------------------------------------------------------------------ 2FA


async def test_login_pede_codigo_e_nao_emite_sessao(cenario, client, caixa, com_2fa):
    r = await _login(client, cenario)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["requer_2fa"] is True and corpo["desafio"]
    assert corpo["access_token"] is None
    assert "aprimora_token" not in r.cookies
    assert len(caixa) == 1 and caixa[0]["para"] == cenario["email"]
    assert corpo["email_mascarado"].endswith("@t.local") and cenario["email"] not in corpo["email_mascarado"]


async def test_codigo_certo_entra_uma_vez_so(cenario, client, caixa, com_2fa):
    desafio = (await _login(client, cenario)).json()["desafio"]
    codigo = _codigo(caixa[-1])
    errado = "000000" if codigo != "000000" else "111111"

    r = await client.post("/api/v2/auth/login/2fa", json={"desafio": desafio, "codigo": errado}, headers=_host(cenario))
    assert r.status_code == 401
    r = await client.post("/api/v2/auth/login/2fa", json={"desafio": desafio, "codigo": codigo}, headers=_host(cenario))
    assert r.status_code == 200, r.text
    assert r.json()["access_token"] and r.json()["usuario_id"] == cenario["uid"]
    r = await client.post("/api/v2/auth/login/2fa", json={"desafio": desafio, "codigo": codigo}, headers=_host(cenario))
    assert r.status_code == 401, "o mesmo código não pode entrar duas vezes"


async def test_cinco_erros_matam_o_codigo(cenario, client, caixa, com_2fa):
    desafio = (await _login(client, cenario)).json()["desafio"]
    codigo = _codigo(caixa[-1])
    errado = "000000" if codigo != "000000" else "111111"
    for _ in range(conta_tokens.MAX_TENTATIVAS_CODIGO):
        await client.post("/api/v2/auth/login/2fa", json={"desafio": desafio, "codigo": errado}, headers=_host(cenario))
    r = await client.post("/api/v2/auth/login/2fa", json={"desafio": desafio, "codigo": codigo}, headers=_host(cenario))
    assert r.status_code == 401, "depois do limite de erros nem o código certo vale"


async def test_desafio_nao_serve_de_sessao(cenario, client, caixa, com_2fa):
    desafio = (await _login(client, cenario)).json()["desafio"]
    r = await client.get(
        "/api/v2/auth/me", headers={**_host(cenario), "Authorization": f"Bearer {desafio}"}
    )
    assert r.status_code == 401


async def test_computador_lembrado_pula_o_codigo_ate_a_senha_mudar(admin_engine, cenario, client, caixa, com_2fa):
    desafio = (await _login(client, cenario)).json()["desafio"]
    r = await client.post(
        "/api/v2/auth/login/2fa",
        json={"desafio": desafio, "codigo": _codigo(caixa[-1]), "lembrar": True},
        headers=_host(cenario),
    )
    lembrar = r.cookies.get("aprimora_2fa_lembrar")
    assert lembrar

    client.cookies.set("aprimora_2fa_lembrar", lembrar)
    r = await _login(client, cenario)
    assert r.json()["requer_2fa"] is False and r.json()["access_token"]

    async with _sm(admin_engine)() as s:
        await s.execute(
            text("UPDATE utils.usuario SET senha_bcrypt = :bc WHERE id = :id"),
            {"bc": hash_password(SENHA), "id": cenario["uid"]},
        )
        await s.commit()
    r = await _login(client, cenario)
    assert r.json()["requer_2fa"] is True, "trocar a senha derruba os computadores lembrados"


# ------------------------------------------------------- esqueci a senha


async def test_esqueci_senha_responde_igual_e_redefine_uma_vez(cenario, client, caixa):
    r = await client.post("/api/v2/auth/esqueci-senha", json={"email": "ninguem@t.local"}, headers=_host(cenario))
    aviso = r.json()["detail"]
    assert r.status_code == 202 and caixa == []

    r = await client.post("/api/v2/auth/esqueci-senha", json={"email": cenario["email"]}, headers=_host(cenario))
    assert r.status_code == 202 and r.json()["detail"] == aviso, "não pode revelar se a conta existe"
    assert "/login/redefinir-senha?token=" in caixa[-1]["texto"]
    token = _token(caixa[-1])

    nova = "outra-senha-forte"
    r = await client.post("/api/v2/auth/redefinir-senha", json={"token": token, "nova_senha": nova}, headers=_host(cenario))
    assert r.status_code == 200 and r.json()["tipo"] == "servidor"
    assert (await _login(client, cenario, senha=nova)).status_code == 200
    assert (await _login(client, cenario)).status_code == 401
    r = await client.post("/api/v2/auth/redefinir-senha", json={"token": token, "nova_senha": "mais-uma-senha"}, headers=_host(cenario))
    assert r.status_code == 400, "o link vale uma vez"


# --------------------------------------------------------------- convite


async def test_convidado_so_entra_depois_de_aceitar(cenario, client, caixa):
    assert (await _login(client, cenario, email=cenario["convidado"])).status_code == 401

    # "Esqueci a senha" de quem não aceitou o convite reenvia o CONVITE.
    await client.post("/api/v2/auth/esqueci-senha", json={"email": cenario["convidado"]}, headers=_host(cenario))
    assert "/login/convite?token=" in caixa[-1]["texto"]
    token = _token(caixa[-1])

    r = await client.post("/api/v2/auth/convite/info", json={"token": token}, headers=_host(cenario))
    assert r.json() == {"nome": "Convidado", "email": cenario["convidado"]}
    r = await client.post("/api/v2/auth/convite/aceitar", json={"token": token, "nova_senha": "minha-senha-1"}, headers=_host(cenario))
    assert r.status_code == 200
    r = await _login(client, cenario, email=cenario["convidado"], senha="minha-senha-1")
    assert r.status_code == 200 and r.json()["must_change_password"] is False


# ---------------------------------------------------------------- cidadão


async def test_cidadao_confirma_email_antes_de_entrar(cenario, client, caixa):
    cpf = "".join(str(int(ch, 16) % 10) for ch in uuid.uuid4().hex[:11])
    r = await client.post(
        "/api/v2/cidadao/cadastrar",
        json={"cpf_cnpj": cpf, "nome": "Cidadã", "email": "cida@t.local", "senha": "senha-cidada-1"},
        headers=_host(cenario),
    )
    assert r.status_code == 201, r.text
    assert "/login/verificar-email?token=" in caixa[-1]["texto"]

    login = {"cpf_cnpj": cpf, "senha": "senha-cidada-1"}
    r = await client.post("/api/v2/cidadao/login", json=login, headers=_host(cenario))
    assert r.status_code == 403 and r.headers.get("x-motivo") == "email-nao-confirmado"
    r = await client.post("/api/v2/cidadao/login", json={**login, "senha": "errada-errada"}, headers=_host(cenario))
    assert r.status_code == 401, "senha errada não revela que o cadastro existe"

    r = await client.post("/api/v2/auth/verificar-email", json={"token": _token(caixa[-1])}, headers=_host(cenario))
    assert r.status_code == 200 and r.json()["tipo"] == "cidadao"
    r = await client.post("/api/v2/cidadao/login", json=login, headers=_host(cenario))
    assert r.status_code == 200, r.text


async def test_admin_cria_servidor_por_convite(admin_engine, cenario, client, caixa):
    """A tela não manda mais senha: a conta nasce por convite, sem e-mail
    verificado (o `None` explícito tem de virar NULL, não o default NOW())."""
    as_user_dependency(admin_engine, cenario["admin_id"], cenario["tid"], cenario["slug"])()
    novo = f"novo-{uuid.uuid4().hex[:8]}@t.local"
    r = await client.post(
        "/api/v2/usuarios",
        json={"nome": "Novo Servidor", "email": novo, "cpf": uuid.uuid4().hex[:11]},
        headers=_host(cenario),
    )
    assert r.status_code == 201, r.text
    assert r.json()["email_verificado_em"] is None
    assert caixa[-1]["para"] == novo and "/login/convite?token=" in caixa[-1]["texto"]
    app.dependency_overrides.clear()

    assert (await _login(client, cenario, email=novo, senha="qualquer-coisa")).status_code == 401
    r = await client.post(
        "/api/v2/auth/convite/aceitar",
        json={"token": _token(caixa[-1]), "nova_senha": "senha-do-novo-1"},
        headers=_host(cenario),
    )
    assert r.status_code == 200
    assert (await _login(client, cenario, email=novo, senha="senha-do-novo-1")).status_code == 200


async def test_sem_smtp_o_2fa_nao_tranca_ninguem(cenario, client, caixa, monkeypatch):
    """2FA ligado mas sem servidor de e-mail: o código nunca chegaria. O login
    segue só com a senha (e registra o erro) em vez de trancar a prefeitura."""
    monkeypatch.setattr(get_settings(), "dois_fatores_email", True)
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    r = await _login(client, cenario)
    assert r.status_code == 200 and r.json()["requer_2fa"] is False and r.json()["access_token"]
    assert caixa == []
