"""Senha sem MD5: cadastro em bcrypt e conversão da credencial legada.

Cobre os DOIS realms — cidadão (`utils.usuario_externo`) e servidor
municipal (`utils.usuario`) — porque a rampa de saída é a mesma nos dois e
separá-los faria uma metade envelhecer sem a outra.

Estes testes cobrem o COMPORTAMENTO; `test_guarda_md5.py` cobre a regra estática
que impede a volta. Os dois são necessários e nenhum substitui o outro: a guarda
não sabe se o login funciona, e o comportamento não sabe se algum caminho novo
voltou a gravar MD5 amanhã.

O defeito que originou o arquivo: até 2026-08-06 `cadastrar()` gravava
`senha=hash_md5(payload.senha)` — hash sem sal, reversível por rainbow table, de
senha escolhida por pessoa, na porta mais exposta do sistema (cadastro público,
sem convite e sem servidor no meio). Todo o resto do sistema já gravava
`senha=""`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import SENHA_MINIMA, hash_md5, verify_md5
from app.models import Usuario, UsuarioExterno
from app.schemas.cidadao import CadastroCidadaoRequest
from app.services import cidadao_auth
from app.services.provisioning_tenant import provisionar_tenant

# Sem `pytestmark` de módulo: o último teste é síncrono, e a marca global faria
# o pytest avisar em cada rodada. Cada async carrega a sua.
SENHA = "senha-forte-1"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _cpf() -> str:
    return uuid.uuid4().hex[:11].translate(str.maketrans("abcdef", "012345"))


@pytest_asyncio.fixture
async def tenant(admin_engine):
    slug = f"md5-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        t, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref MD5", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    yield t
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("DELETE FROM utils.usuario_externo WHERE tenant_id = :t"),
            {"t": t.id},
        )
        await s.commit()


async def _le(engine, cid: int) -> UsuarioExterno:
    async with _sm(engine)() as s:
        return (
            await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))
        ).scalar_one()


@pytest.mark.asyncio
async def test_cadastro_nao_grava_md5(admin_engine, tenant) -> None:
    """O defeito original, cravado: a coluna legada nasce vazia."""
    async with _sm(admin_engine)() as s:
        c = await cidadao_auth.cadastrar(
            s,
            CadastroCidadaoRequest(
                cpf_cnpj=_cpf(), nome="Maria Cidadã",
                email=f"{uuid.uuid4().hex[:8]}@e2e.test", senha=SENHA,
            ),
            tenant_id=tenant.id,
            app="portal",
        )

    linha = await _le(admin_engine, c.id)
    assert not linha.senha, (
        f"cadastro gravou MD5 legado ({linha.senha!r}). Hash sem sal de senha "
        "escolhida por pessoa é reversível — a coluna `senha` tem de nascer vazia."
    )
    # Controle: não basta estar vazia por acidente de a senha não ter sido salva.
    assert linha.senha_bcrypt and linha.senha_bcrypt.startswith("$2"), (
        "sem bcrypt a assertiva acima passaria com o cadastro simplesmente "
        "quebrado, sem senha nenhuma"
    )
    assert not verify_md5(SENHA, linha.senha or ""), "a senha ainda casa por MD5"


@pytest.mark.asyncio
async def test_cadastrado_hoje_faz_login(admin_engine, tenant) -> None:
    """Sem o MD5, o login continua funcionando — só por bcrypt."""
    cpf = _cpf()
    async with _sm(admin_engine)() as s:
        await cidadao_auth.cadastrar(
            s,
            CadastroCidadaoRequest(
                cpf_cnpj=cpf, nome="João", email=f"{uuid.uuid4().hex[:8]}@e2e.test",
                senha=SENHA,
            ),
            tenant_id=tenant.id,
            app="portal",
        )

    async with _sm(admin_engine)() as s:
        logado = await cidadao_auth.login(
            s, tenant_id=tenant.id, cpf_cnpj=cpf, senha=SENHA
        )
    assert logado.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(cidadao_auth.CidadaoAuthError):
            await cidadao_auth.login(
                s, tenant_id=tenant.id, cpf_cnpj=cpf, senha="outra-coisa-9"
            )


@pytest.mark.asyncio
async def test_login_converte_credencial_legada_e_apaga_o_md5(
    admin_engine, tenant
) -> None:
    """A rampa de saída do MD5, que é o que permite `verify_md5` seguir vivo.

    Fabrica o estado do banco de produção — cidadão criado pelo PHP, só com MD5
    — e prova que o primeiro login converte para bcrypt E remove o hash legado.
    Sem o segundo efeito o rehash apenas ACRESCENTA, e a linha ficaria para
    sempre com um hash reversível ao lado do bcrypt.
    """
    cpf = _cpf()
    async with _sm(admin_engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant.id, nome="Legado", cpf_cnpj=cpf,
            email=f"{uuid.uuid4().hex[:8]}@e2e.test",
            senha=hash_md5(SENHA),  # credencial só-MD5, como o PHP deixava
            senha_bcrypt=None,
            ativo=True, excluido=False, uid=uuid.uuid4(),
            data_criacao=datetime.now(), login_govbr=False, telefone_whatsapp=False,
        )
        s.add(c)
        await s.commit()
        cid = c.id

    antes = await _le(admin_engine, cid)
    assert antes.senha and not antes.senha_bcrypt, "o arreio não montou o estado legado"

    async with _sm(admin_engine)() as s:
        await cidadao_auth.login(s, tenant_id=tenant.id, cpf_cnpj=cpf, senha=SENHA)

    depois = await _le(admin_engine, cid)
    assert depois.senha_bcrypt and depois.senha_bcrypt.startswith("$2"), (
        "o login autenticou por MD5 e não gravou bcrypt — a conversão não aconteceu"
    )
    assert not depois.senha, (
        f"o MD5 sobreviveu à conversão ({depois.senha!r}). O rehash só acrescenta; "
        "quem apaga o hash reversível é o `senha = \"\"` no mesmo ato."
    )

    # E o cidadão continua entrando com a MESMA senha, agora por bcrypt.
    async with _sm(admin_engine)() as s:
        assert await cidadao_auth.login(
            s, tenant_id=tenant.id, cpf_cnpj=cpf, senha=SENHA
        )


def test_o_piso_de_senha_vale_no_cadastro() -> None:
    """Era 4. Quatro caracteres são ~1,7 milhão de combinações minúsculas."""
    base = dict(cpf_cnpj="12345678901", nome="Maria", email="m@e2e.test")

    with pytest.raises(ValidationError):
        CadastroCidadaoRequest(**base, senha="a" * (SENHA_MINIMA - 1))

    aceita = CadastroCidadaoRequest(**base, senha="a" * SENHA_MINIMA)
    assert aceita.senha

    assert SENHA_MINIMA >= 8, (
        "SENHA_MINIMA caiu abaixo de 8 (NIST SP 800-63B §5.1.1.2 para segredo "
        "escolhido pelo usuário). Se a redução é deliberada, mude aqui também — "
        "com o motivo no diff."
    )


# ============================================================
# Servidor municipal (`utils.usuario`) — mesma rampa, por HTTP
# ============================================================


@pytest_asyncio.fixture
async def cliente_http():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()


@pytest.mark.asyncio
async def test_login_do_admin_converte_e_apaga_o_md5(
    admin_engine, tenant, cliente_http
) -> None:
    """O mesmo de cima, no realm municipal e passando pelo router de verdade.

    Vai por HTTP e não pelo service porque a conversão mora no
    `routers/auth.py` — teste de service não passaria por ela. O `Host` resolve
    o tenant pelo middleware: `/login` lê `request.state.tenant_id` antes de
    qualquer `Depends`, então override de dependência não alcança.

    Efeito colateral que este teste também protege: enquanto a credencial for
    só-MD5, a assinatura eletrônica recusa (`AssinaturaCredencialLegadaError`,
    HTTP 409) e manda o usuário relogar. Se o login parar de converter, aquela
    mensagem vira um beco sem saída.
    """
    email = f"legado-{uuid.uuid4().hex[:8]}@t.local"
    async with _sm(admin_engine)() as s:
        uid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "(tenant_id, nome, email, senha, senha_bcrypt, cpf, ativo, "
                        " excluido, must_change_password) "
                        "VALUES (:t, 'Servidor Legado', :e, :md5, NULL, :cpf, true, "
                        " false, false) RETURNING id"
                    ),
                    {
                        "t": tenant.id,
                        "e": email,
                        "md5": hash_md5(SENHA),
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()

    r = await cliente_http.post(
        "/api/v2/auth/login",
        json={"email": email, "senha": SENHA},
        headers={"Host": f"{tenant.slug}.aprimora.local"},
    )
    assert r.status_code == 200, r.text

    async with _sm(admin_engine)() as s:
        linha = (
            await s.execute(select(Usuario).where(Usuario.id == uid))
        ).scalar_one()

    assert linha.senha_bcrypt and linha.senha_bcrypt.startswith("$2"), (
        "o login autenticou por MD5 e não gravou bcrypt"
    )
    assert not linha.senha, (
        f"o MD5 sobreviveu ao login ({linha.senha!r}). O rehash só ACRESCENTA "
        'bcrypt; quem remove o hash reversível é o `user.senha = ""`.'
    )
