"""Conta por e-mail DESLIGADA (`CONTA_POR_EMAIL=false`, o padrão desde
2026-11-09): o sistema age como se o e-mail não existisse. Ninguém pode ficar
preso esperando um link ou um código que não vai chegar — nem com SMTP
configurado, porque a chave manda.

A conta por e-mail LIGADA está em `test_conta_email_2fa.py`.
"""
from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.main import app
from tests.conftest import as_user_dependency

# Só fixtures e ajudantes. NÃO importar `conta_por_email_ligada` (autouse):
# importada aqui, ela ligaria a chave neste arquivo também.
from tests.test_conta_email_2fa import (  # noqa: F401
    SENHA,
    _host,
    _login,
    caixa,
    cenario,
    client,
)


@pytest.fixture(autouse=True)
def conta_por_email_desligada(monkeypatch):
    """Chave desligada, mas com SMTP e 2FA configurados: prova que é a chave
    que manda, e não a falta de servidor de e-mail."""
    s = get_settings()
    monkeypatch.setattr(s, "conta_por_email", False)
    monkeypatch.setattr(s, "smtp_host", "smtp.teste.invalid")
    monkeypatch.setattr(s, "dois_fatores_email", True)


async def test_login_sem_codigo(cenario, client, caixa):
    r = await _login(client, cenario)
    assert r.status_code == 200, r.text
    assert r.json()["requer_2fa"] is False and r.json()["access_token"]
    assert caixa == [], "nenhum e-mail sai com a chave desligada"


async def test_tela_de_login_sabe_que_esta_desligada(cenario, client):
    r = await client.get("/api/v2/branding/me", headers=_host(cenario))
    assert r.status_code == 200 and r.json()["conta_por_email"] is False


async def test_servidor_novo_exige_senha_do_admin(admin_engine, cenario, client, caixa):
    """Sem convite possível, vale o rito de antes: o admin define a senha
    temporária, e a pessoa troca no primeiro acesso."""
    as_user_dependency(admin_engine, cenario["admin_id"], cenario["tid"], cenario["slug"])()
    base = {"nome": "Novo", "cpf": uuid.uuid4().hex[:11]}
    r = await client.post(
        "/api/v2/usuarios", json={**base, "email": f"a-{uuid.uuid4().hex[:8]}@t.local"}, headers=_host(cenario)
    )
    assert r.status_code == 422 and "senha" in r.json()["detail"]

    novo = f"b-{uuid.uuid4().hex[:8]}@t.local"
    r = await client.post(
        "/api/v2/usuarios", json={**base, "email": novo, "senha": "temporaria-1"}, headers=_host(cenario)
    )
    assert r.status_code == 201, r.text
    assert caixa == []
    app.dependency_overrides.clear()

    r = await _login(client, cenario, email=novo, senha="temporaria-1")
    assert r.status_code == 200 and r.json()["must_change_password"] is True


async def test_resetar_senha_ativa_convite_pendente(admin_engine, cenario, client):
    """Quem ficou com convite pendente (criado com a chave ligada) tem saída
    pela tela: o "Resetar senha" do admin ativa a conta."""
    as_user_dependency(admin_engine, cenario["admin_id"], cenario["tid"], cenario["slug"])()
    r = await client.get(f"/api/v2/usuarios?q={cenario['convidado']}", headers=_host(cenario))
    uid = r.json()["items"][0]["id"]
    r = await client.post(f"/api/v2/usuarios/{uid}/resetar-senha", headers=_host(cenario))
    assert r.status_code == 200, r.text
    temporaria = r.json()["senha_temporaria"]
    app.dependency_overrides.clear()

    r = await _login(client, cenario, email=cenario["convidado"], senha=temporaria)
    assert r.status_code == 200 and r.json()["must_change_password"] is True


async def test_cidadao_entra_sem_confirmar_email(cenario, client, caixa, monkeypatch):
    cpf = "".join(str(int(ch, 16) % 10) for ch in uuid.uuid4().hex[:11])
    r = await client.post(
        "/api/v2/cidadao/cadastrar",
        json={"cpf_cnpj": cpf, "nome": "Cidadão", "email": "cid@t.local", "senha": "senha-cidadao-1"},
        headers=_host(cenario),
    )
    assert r.status_code == 201 and r.json()["email_verificado_em"] is not None
    assert caixa == []
    login = {"cpf_cnpj": cpf, "senha": "senha-cidadao-1"}
    assert (await client.post("/api/v2/cidadao/login", json=login, headers=_host(cenario))).status_code == 200


async def test_cidadao_cadastrado_com_a_chave_ligada_nao_fica_preso(cenario, client, caixa, monkeypatch):
    """Cadastro feito enquanto a chave estava ligada nasce sem confirmação.
    Desligada a chave, ele entra assim mesmo."""
    cpf = "".join(str(int(ch, 16) % 10) for ch in uuid.uuid4().hex[:11])
    monkeypatch.setattr(get_settings(), "conta_por_email", True)
    r = await client.post(
        "/api/v2/cidadao/cadastrar",
        json={"cpf_cnpj": cpf, "nome": "Cidadã", "email": "cida@t.local", "senha": "senha-cidada-1"},
        headers=_host(cenario),
    )
    assert r.status_code == 201 and r.json()["email_verificado_em"] is None

    monkeypatch.setattr(get_settings(), "conta_por_email", False)
    login = {"cpf_cnpj": cpf, "senha": "senha-cidada-1"}
    assert (await client.post("/api/v2/cidadao/login", json=login, headers=_host(cenario))).status_code == 200
