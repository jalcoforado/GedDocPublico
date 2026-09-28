"""Testes para o IA Assistente Global (Chatbot de busca)."""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.services.ia.assistente import AssistenteError
from app.services.ia.assistente_global import responder_global, _extrair_parametros
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class LLMFalsoGlobal:
    """Mock do LLM que responde diferentemente na extração de intenção e na resposta final."""

    def __init__(self, json_extracao: dict, texto_final: str = "Resposta final") -> None:
        self.json_extracao = json_extracao
        self.texto_final = texto_final
        self.chamadas = 0
        self.system_recebido = None
        self.messages_recebidas = None

    async def stream(self, *, system: str, pergunta: str | None = None, messages: list[dict] | None = None):
        self.chamadas += 1
        self.system_recebido = system
        self.messages_recebidas = messages
        
        if self.chamadas == 1:
            # Primeira chamada: extrair parâmetros
            yield json.dumps(self.json_extracao)
        else:
            # Segunda chamada: resposta final
            yield self.texto_final


@pytest_asyncio.fixture
async def cenario(admin_engine):
    """Fixture básica de tenant e processo para testes de busca."""
    slug = f"ia2-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref IA2", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )

    async with _sm(admin_engine)() as s:
        from app.models import Assunto, Manifestante, TipoProcesso

        unidade_id = int((await s.execute(
            text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant.id},
        )).scalar_one())
        tipo_manif_id = int((await s.execute(
            text("SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant.id},
        )).scalar_one())

        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral",
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(tp)
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant.id, assunto="Poda de arvore",
            id_tipo_processo=tp.id, exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        manifestante = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=tipo_manif_id,
            nome="Jose Solicitante", cpf_cnpj=uuid.uuid4().hex[:11],
            ativo=True, excluido=False,
        )
        s.add_all([assunto, manifestante])
        await s.flush()

        processo_id = int((await s.execute(text("""
            INSERT INTO protocolos.processo
                (tenant_id, numero_processo, data_hora_abertura, ativo,
                 excluido, corpo, nivel_sigilo, id_unidade_proprietaria,
                 id_assunto, id_manifestante, virtual, migrado, externo)
            VALUES (:t, :num, NOW(), true, false, 'Corpo teste', 'ostensivo', :u,
                    :a, :m, false, false, false)
            RETURNING id
        """), {
            "t": tenant.id, "num": f"POD-{uuid.uuid4().hex[:6]}",
            "u": unidade_id, "a": assunto.id, "m": manifestante.id,
        })).scalar_one())

        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app = :a AND excluido = false LIMIT 1"
        ), {"a": APP})).scalar_one())
        
        nivel_id = int((await s.execute(text(
            "INSERT INTO utils.nivel (nivel, valor, excluido) "
            "VALUES ('Operacional Busca', 1, false) RETURNING id"
        ))).scalar_one())
        
        transacao_id = (await s.execute(text(
            "SELECT id FROM utils.transacao WHERE codigo = 'processo' "
            "AND excluido = false LIMIT 1"
        ))).scalar_one()
        
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Servidor Busca', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id
        """), {"t": tenant.id, "e": f"busca-{slug}@t.local",
               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
               
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, 'Grupo Busca IA', false) RETURNING id
        """), {"t": tenant.id, "n": nivel_id, "s": sistema_id})).scalar_one())
        
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo
                (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)
        """), {"t": tenant.id, "u": uid, "g": gid, "a": APP})
        
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            VALUES (:t, :g, :tr, true, true, true, false)
        """), {"t": tenant.id, "g": gid, "tr": transacao_id})
        
        await s.commit()

    yield {
        "tenant": tenant,
        "slug": slug,
        "processo_id": processo_id,
        "usuario_id": uid,
    }

    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant.id})
        await s.commit()


async def _usuario(engine, uid: int):
    from app.models import Usuario
    async with _sm(engine)() as s:
        return (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()


@pytest.mark.asyncio
async def test_extrair_parametros_valido():
    """Testa se a extração de JSON da intenção da IA funciona."""
    llm = LLMFalsoGlobal(json_extracao={"busca": "Jose", "status": "Aberto"})
    params = await _extrair_parametros("Buscar processos do Jose abertos", llm)
    assert params.get("busca") == "Jose"
    assert params.get("status") == "Aberto"


@pytest.mark.asyncio
async def test_extrair_parametros_invalido():
    """Testa se a extração resiste a falha de JSON devolvendo dicionário vazio."""
    class LLMBad:
        async def stream(self, **kwargs):
            yield "Eu nao sei o que fazer, desculpe."
            
    params = await _extrair_parametros("texto solto", LLMBad())
    assert params == {}


@pytest.mark.asyncio
async def test_responder_global_busca_com_sucesso(admin_engine, cenario):
    """Testa o loop completo de extrair -> buscar -> gerar resposta final."""
    usuario = await _usuario(admin_engine, cenario["usuario_id"])
    llm = LLMFalsoGlobal(
        json_extracao={"busca": "Poda"}, 
        texto_final="Encontrei 1 processo sobre poda."
    )
    
    async with _sm(admin_engine)() as s:
        pedacos = [
            p async for p in responder_global(
                s,
                pergunta="Busque os processos de poda",
                tenant_id=cenario["tenant"].id,
                usuario=usuario,
                cliente=llm,
            )
        ]
        
    resposta_completa = "".join(pedacos)
    assert resposta_completa == "Encontrei 1 processo sobre poda."
    # Verifica se os resultados do processo criado no cenario foram injetados nas messages
    assert llm.messages_recebidas is not None
    assert "Poda de arvore" in str(llm.messages_recebidas)


@pytest.mark.asyncio
async def test_responder_global_nenhum_resultado(admin_engine, cenario):
    usuario = await _usuario(admin_engine, cenario["usuario_id"])
    # "LixoInexistente" não deve retornar nada
    llm = LLMFalsoGlobal(
        json_extracao={"busca": "LixoInexistente"},
        texto_final="Nenhum resultado."
    )
    
    async with _sm(admin_engine)() as s:
        pedacos = [
            p async for p in responder_global(
                s,
                pergunta="Buscar lixo inexistente",
                tenant_id=cenario["tenant"].id,
                usuario=usuario,
                cliente=llm,
            )
        ]
        
    assert "".join(pedacos) == "Nenhum resultado."
    assert "Nenhum processo encontrado na base de dados para estes crit" in str(llm.messages_recebidas)


@pytest.mark.asyncio
async def test_pergunta_invalida_barrada(admin_engine, cenario):
    usuario = await _usuario(admin_engine, cenario["usuario_id"])
    async with _sm(admin_engine)() as s:
        with pytest.raises(AssistenteError):
            await anext(responder_global(
                s,
                pergunta="",
                tenant_id=cenario["tenant"].id,
                usuario=usuario,
                cliente=LLMFalsoGlobal({}),
            ))


# ============================================================
# HTTP Tests
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


def _arreio(cenario, uid: int, llm):
    from app.auth.deps import _resolve_current_user, get_db
    from app.main import app
    from app.models import Usuario
    from app.routers.ia import get_llm_client

    arreio_tenant_http(cenario["tenant"].id, cenario["slug"])

    async def _resolver(db: AsyncSession = Depends(get_db)):
        return (await db.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()

    app.dependency_overrides[_resolve_current_user] = _resolver
    app.dependency_overrides[get_llm_client] = lambda: llm


@pytest.mark.asyncio
async def test_http_perguntar_global(admin_engine, cenario, cliente_http):
    _arreio(cenario, cenario["usuario_id"], LLMFalsoGlobal({"busca": "Poda"}, "Tudo certo!"))
    r = await cliente_http.post(
        "/api/v2/ia/perguntar-global",
        json={"pergunta": "Oi, busque poda"}
    )
    assert r.status_code == 200
    assert "Tudo certo!" in r.text
