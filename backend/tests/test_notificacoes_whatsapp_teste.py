"""`POST /api/v2/notificacoes/whatsapp-test` — backlog 1.0.6.

O endpoint mandava mensagem paga do tenant para **telefone arbitrário do
payload**, exigindo apenas estar autenticado: vetor de custo e de assédio, não
de vazamento. O conserto NÃO foi gatear quem chama — o único chamador é
`/perfil/notificacoes`, a página do próprio usuário, e exigir transação ali
tiraria de todo usuário comum a capacidade de conferir o próprio telefone. O
conserto foi tirar o **destino** das mãos do chamador e limitar a taxa.

As duas propriedades que estes testes travam:

1. **O destino não vem do request.** Mandar `telefone` de terceiro no corpo não
   muda para onde vai — a mensagem sai para o telefone do perfil de quem chama.
   O teste manda um número de terceiro DIFERENTE do perfil e confere na linha
   gravada; sem esse número diferente, o teste passaria mesmo se o payload
   voltasse a mandar.
2. **O limite conta por usuário, não por telefone.** Contar por telefone seria
   contornável com `PUT /notificacoes/telefone`, que é livre — que é justamente
   o caminho que sobra depois da propriedade 1.

Controle positivo em toda negativa: antes de cada 400/429 o teste prova que a
chamada legítima passa. Sem isso, "levantou exceção" não distingue o conserto
de um endpoint quebrado.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Notificacao, Usuario
from app.routers.notificacoes import WHATSAPP_TESTE_LIMITE
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

# Número de terceiro. Existe para ser DIFERENTE do telefone do perfil: é a
# comparação entre os dois que prova que o destino não veio do corpo.
TELEFONE_DE_TERCEIRO = "+5511900000000"
TELEFONE_DO_PERFIL = "+5588988887777"

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar(engine):
    slug = f"wa-{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Teste WhatsApp",
            admin_email=f"{slug}@e2e.test",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _admin_do_tenant(engine, tenant_id: int) -> Usuario:
    async with _sm(engine)() as s:
        return (
            await s.execute(select(Usuario).where(Usuario.tenant_id == tenant_id))
        ).scalars().first()


async def _set_telefone(engine, usuario_id: int, telefone: str | None) -> None:
    async with _sm(engine)() as s:
        await s.execute(
            text("UPDATE utils.usuario SET telefone = :t WHERE id = :i"),
            {"t": telefone, "i": usuario_id},
        )
        await s.commit()


async def _testes_gravados(engine, tenant_id: int) -> list[Notificacao]:
    async with _sm(engine)() as s:
        return list(
            (
                await s.execute(
                    select(Notificacao)
                    .where(
                        Notificacao.tenant_id == tenant_id,
                        Notificacao.tipo == "teste_whatsapp",
                    )
                    .order_by(Notificacao.id)
                )
            ).scalars()
        )


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.notificacao_preferencia WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
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


async def _post(corpo: dict):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/api/v2/notificacoes/whatsapp-test", json=corpo)


@pytest.mark.asyncio
async def test_telefone_no_corpo_nao_muda_o_destino(admin_engine):
    """A propriedade central. Manda telefone de terceiro; sai para o do perfil."""
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        await _set_telefone(admin_engine, admin.id, TELEFONE_DO_PERFIL)
        _as_user(admin_engine, admin.id, tenant.id, tenant.slug)

        r = await _post(
            {"telefone": TELEFONE_DE_TERCEIRO, "mensagem": "oi"}
        )
        assert r.status_code == 200, r.text

        gravadas = await _testes_gravados(admin_engine, tenant.id)
        assert len(gravadas) == 1, "esperava exatamente uma notificação de teste"
        n = gravadas[0]

        # O vínculo com o usuário é o que prova a origem do destino: o motor só
        # resolve telefone a partir de `id_usuario`, e é esse campo que o
        # limite de taxa conta depois.
        assert n.id_usuario == admin.id, (
            "a notificação nasceu sem vínculo com quem chamou — o endpoint "
            "voltou a passar `Destinatario(telefone=...)` em vez de "
            "`Destinatario(id_usuario=...)`, e com isso tanto o destino quanto "
            "o limite de taxa deixam de valer."
        )
        assert TELEFONE_DE_TERCEIRO not in (n.payload or {}).get("telefone", ""), (
            "o número de terceiro do corpo chegou na notificação"
        )
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine

        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_schema_nao_aceita_mais_destino(admin_engine):
    """Guarda de contrato: reintroduzir `telefone` no schema reprova aqui.

    Separado do teste acima de propósito. Aquele mede o comportamento; este
    mede a superfície. Alguém pode reintroduzir o campo no schema sem usá-lo
    no router — e nesse dia o teste de comportamento continua verde enquanto o
    contrato público volta a prometer um destino que não existe.
    """
    from app.schemas.notificacao import WhatsAppTestRequest

    assert "telefone" not in WhatsAppTestRequest.model_fields, (
        "`WhatsAppTestRequest.telefone` voltou. Ele era destino livre: "
        "qualquer autenticado do tenant mandava mensagem paga para número "
        "arbitrário (backlog 1.0.6). Se o produto precisa mesmo mandar para "
        "terceiro, isso exige decidir ANTES quem tem autorização — hoje "
        "ninguém tem."
    )


@pytest.mark.asyncio
async def test_sem_telefone_no_perfil_da_400_e_nao_grava(admin_engine):
    """Negativa com controle positivo na mesma sessão e no mesmo usuário."""
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        await _set_telefone(admin_engine, admin.id, None)
        _as_user(admin_engine, admin.id, tenant.id, tenant.slug)

        r = await _post({"mensagem": "sem telefone"})
        assert r.status_code == 400, r.text
        assert not await _testes_gravados(admin_engine, tenant.id), (
            "recusou com 400 MAS gravou notificação"
        )

        # Controle positivo: o MESMO usuário, salvando o telefone, consegue.
        # Sem isto o 400 acima não distingue "faltava telefone" de "o endpoint
        # está quebrado para todo mundo".
        await _set_telefone(admin_engine, admin.id, TELEFONE_DO_PERFIL)
        r2 = await _post({"mensagem": "com telefone"})
        assert r2.status_code == 200, r2.text
        assert len(await _testes_gravados(admin_engine, tenant.id)) == 1
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine

        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_limite_conta_por_usuario_e_nao_por_telefone(admin_engine):
    """Trocar o telefone do perfil NÃO devolve cota.

    É o caminho que sobra depois de o destino sair do payload: `PUT
    /notificacoes/telefone` é livre, então "troco meu número e testo de novo"
    seria um jeito barato de queimar a credencial do tenant se o limite fosse
    por telefone.
    """
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        await _set_telefone(admin_engine, admin.id, TELEFONE_DO_PERFIL)
        _as_user(admin_engine, admin.id, tenant.id, tenant.slug)

        for i in range(WHATSAPP_TESTE_LIMITE):
            r = await _post({"mensagem": f"teste {i}"})
            assert r.status_code == 200, f"envio {i} dentro da cota falhou: {r.text}"

        r = await _post({"mensagem": "estourando"})
        assert r.status_code == 429, r.text

        # Troca o telefone e tenta de novo: continua 429.
        await _set_telefone(admin_engine, admin.id, "+5511911112222")
        r = await _post({"mensagem": "outro numero"})
        assert r.status_code == 429, (
            "trocar o telefone do perfil devolveu cota — o limite está contando "
            "por telefone, não por usuário, e o contorno continua aberto."
        )

        assert len(await _testes_gravados(admin_engine, tenant.id)) == (
            WHATSAPP_TESTE_LIMITE
        ), "as chamadas recusadas com 429 gravaram notificação"
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine

        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_limite_e_por_usuario_nao_por_tenant(admin_engine):
    """Um usuário no limite não bloqueia o outro do mesmo tenant.

    Contar por tenant transformaria o limite de proteção contra abuso em
    negação de serviço entre colegas: quem chegasse primeiro travaria os
    demais.
    """
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        await _set_telefone(admin_engine, admin.id, TELEFONE_DO_PERFIL)

        async with _sm(admin_engine)() as s:
            outro_id = (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario (tenant_id, nome, email, senha, "
                        "cpf, ativo, excluido, app, nivel_acesso_sigilo, telefone) "
                        "VALUES (:t, 'Colega', :e, 'x', :c, true, false, :app, "
                        "'ostensivo', :tel) RETURNING id"
                    ),
                    {
                        "t": tenant.id,
                        "e": f"colega-{uuid.uuid4().hex[:8]}@e2e.test",
                        "c": uuid.uuid4().hex[:11],
                        # Da configuração, não literal: o container de dev roda
                        # `APP_NAME=aprimora` e o CI roda `sistemas` (deriva do
                        # item 1.0 do backlog). Literal aqui passa numa das duas
                        # e falha na outra.
                        "app": APP,
                        "tel": "+5588977776666",
                    },
                )
            ).scalar_one()
            await s.commit()

        _as_user(admin_engine, admin.id, tenant.id, tenant.slug)
        for i in range(WHATSAPP_TESTE_LIMITE):
            assert (await _post({"mensagem": f"a{i}"})).status_code == 200
        assert (await _post({"mensagem": "a-estoura"})).status_code == 429

        _as_user(admin_engine, outro_id, tenant.id, tenant.slug)
        r = await _post({"mensagem": "b0"})
        assert r.status_code == 200, (
            "o segundo usuário do tenant foi barrado pela cota do primeiro — "
            f"o limite está por tenant, não por usuário: {r.text}"
        )
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine

        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)
