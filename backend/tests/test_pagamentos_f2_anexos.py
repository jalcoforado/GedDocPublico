"""Testes de anexos de débito (F2, Task 5).

Reaproveita o storage de anexos de protocolo através do vínculo próprio
`pagamentos.anexo_debito` — soft-delete, versionado por `versao_debito` e,
opcionalmente, amarrado a um `PedidoAjuste`.

Padrão de dados e HTTP: copiados de `test_pagamentos_f2_ajustes.py`
(`_provisionar`/`_criar_usuario`/`_setup_debito`/`_usuario_com`/`_post`/`_get`,
`arreio_tenant_http`).
"""
from __future__ import annotations

import io
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_ajustes as ajustes
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar_usuario(engine, tenant_id: int, nome: str) -> int:
    async with _sm(engine)() as s:
        uid = (await s.execute(text(
            "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, "
            "cpf, ativo, excluido, app, nivel_acesso_sigilo, must_change_password) "
            "VALUES (:t, :n, :e, '', '', :c, true, false, 'sistemas', 'interno', false) "
            "RETURNING id"
        ), {"t": tenant_id, "n": nome, "e": f"{uuid.uuid4().hex[:10]}@t.local",
            "c": str(uuid.uuid4().int)[:11]})).scalar_one()
        await s.commit()
    return uid


async def _provisionar(engine):
    slug = _slug("pagf2ax")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F2 Anexos", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    solicitante_id = await _criar_usuario(engine, tenant.id, "Solicitante")
    gestor_id = await _criar_usuario(engine, tenant.id, "Gestor")
    validador_id = await _criar_usuario(engine, tenant.id, "Validador")
    return tenant, solicitante_id, gestor_id, validador_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.anexo_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_versao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.pedido_ajuste WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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


async def _setup_debito(engine, tenant_id: int, usuario_id: int):
    """Cria um débito completo em rascunho — cópia do helper homônimo de
    `test_pagamentos_f2_ajustes.py`."""
    async with _sm(engine)() as s:
        fornecedor = await cad.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Empresa LTDA"),
        )
        fonte = await cad.criar_fonte(
            s, tenant_id=tenant_id,
            payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria",
                grupos_despesa_permitidos=[],
            ),
        )
        await cad.criar_conta(
            s, tenant_id=tenant_id,
            payload=ContaCreate(
                nome="Conta Teste", banco="001", agencia="1",
                conta=uuid.uuid4().hex[:8], id_fonte_recursos=fonte.id,
                grupo_despesa="CUSTEIO", saldo_inicial="10000.00", ativa=True,
            ),
        )

        from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
        stmt = select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        unidade = (await s.execute(stmt)).scalar()
        if not unidade:
            tipo = (await s.execute(select(TipoUnidadeTrabalho).limit(1))).scalar()
            if not tipo:
                tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
                s.add(tipo)
                await s.flush()
            unidade = UnidadeTrabalho(
                tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
                unidade_trabalho="Unidade Teste",
            )
            s.add(unidade)
            await s.flush()

        natureza = await cad.criar_natureza(
            s, tenant_id=tenant_id,
            payload=NaturezaCreate(codigo=f"N{uuid.uuid4().hex[:5]}", descricao="Teste"),
        )
        contrato = await cad.criar_contrato(
            s, tenant_id=tenant_id,
            payload=ContratoCreate(
                numero=f"CT-{uuid.uuid4().hex[:8]}", id_fornecedor=fornecedor.id,
                id_unidade=unidade.id, objeto="Serviços de Teste",
                vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                valor_total=Decimal("5000.00"), categoria="SERVICOS",
            ),
        )

        debito = await svc.criar_debito(
            s, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=DebitoCreate(
                numero_nf="NF123456", id_fornecedor=fornecedor.id,
                id_natureza=natureza.id, id_contrato=contrato.id,
                id_fonte_recursos=fonte.id, id_unidade=unidade.id,
                valor_total=Decimal("1000.00"), descricao="Débito de Teste",
                competencia="2026-01",
                parcelas=[ParcelaCreate(numero=1, valor=Decimal("1000.00"), vencimento="2026-02-01")],
            ),
        )
    return debito


async def _usuario_com(engine, tenant_id: int, codigos: list[str]) -> int:
    """Usuário NÃO super-usuário, com exatamente as transações pedidas."""
    async with _sm(engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one())
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Usuario Comum Anexo', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"anexo-{uuid.uuid4().hex[:8]}@f2.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Grupo Anexo {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        for codigo in codigos:
            tr = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo=:c AND excluido=false LIMIT 1"
            ), {"c": codigo})).scalar_one()
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                VALUES (:t, :g, :tr, false, false, false, false)"""),
                {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


def _fake_file(name="doc.pdf", content=b"%PDF-1.4 conteudo de teste"):
    return {"file": (name, io.BytesIO(content), "application/pdf")}


async def _upload(engine, tenant_id, slug, usuario_id, caminho, *, data=None, files=None):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(caminho, data=data or {}, files=files or _fake_file())
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _get(engine, tenant_id, slug, usuario_id, caminho):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _delete(engine, tenant_id, slug, usuario_id, caminho):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.delete(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_upload_e_download_de_anexo_de_debito(admin_engine):
    tenant, solicitante_id, _gestor_id, _validador_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar", "pagamento_gerir",
                                                       "pagamento_validar", "pagamento_autorizar"])

    r = await _upload(admin_engine, tenant.id, tenant.slug, uid,
                      f"/api/v2/pagamentos/debitos/{debito.id}/anexos",
                      data={"descricao": "Comprovante"})
    assert r.status_code == 201, (r.status_code, r.text)
    body = r.json()
    assert body["versao_debito"] == debito.versao
    assert body["id_pedido_ajuste"] is None
    assert body["nome"] == "Comprovante"
    assert body["tamanho"] and body["tamanho"] > 0
    assert body["tipo"] == "pdf"
    anexo_debito_id = body["id"]

    # Listagem enxerga o vínculo.
    r2 = await _get(admin_engine, tenant.id, tenant.slug, uid,
                    f"/api/v2/pagamentos/debitos/{debito.id}/anexos")
    assert r2.status_code == 200, r2.text
    assert [item["id"] for item in r2.json()] == [anexo_debito_id]

    # Download entrega o conteúdo gravado.
    r3 = await _get(admin_engine, tenant.id, tenant.slug, uid,
                    f"/api/v2/pagamentos/anexos-debito/{anexo_debito_id}/download")
    assert r3.status_code == 200, r3.text
    assert r3.content == b"%PDF-1.4 conteudo de teste"

    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_download_cross_tenant_e_404(admin_engine):
    tenant_a, solicitante_a, _, _ = await _provisionar(admin_engine)
    tenant_b, _, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant_a.id, solicitante_a)
    uid_a = await _usuario_com(admin_engine, tenant_a.id, ["pagamento_solicitar"])
    uid_b = await _usuario_com(admin_engine, tenant_b.id, ["pagamento_solicitar"])

    r = await _upload(admin_engine, tenant_a.id, tenant_a.slug, uid_a,
                      f"/api/v2/pagamentos/debitos/{debito.id}/anexos")
    assert r.status_code == 201, r.text
    anexo_debito_id = r.json()["id"]

    r2 = await _get(admin_engine, tenant_b.id, tenant_b.slug, uid_b,
                    f"/api/v2/pagamentos/anexos-debito/{anexo_debito_id}/download")
    assert r2.status_code == 404, (r2.status_code, r2.text)

    await _cleanup(admin_engine, tenant_a.id)
    await _cleanup(admin_engine, tenant_b.id)


@pytest.mark.asyncio
async def test_download_de_vinculo_excluido_e_404(admin_engine):
    tenant, solicitante_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])

    r = await _upload(admin_engine, tenant.id, tenant.slug, uid,
                      f"/api/v2/pagamentos/debitos/{debito.id}/anexos")
    assert r.status_code == 201, r.text
    anexo_debito_id = r.json()["id"]

    r_del = await _delete(admin_engine, tenant.id, tenant.slug, uid,
                          f"/api/v2/pagamentos/debitos/{debito.id}/anexos/{anexo_debito_id}")
    assert r_del.status_code == 204, (r_del.status_code, r_del.text)

    r2 = await _get(admin_engine, tenant.id, tenant.slug, uid,
                    f"/api/v2/pagamentos/anexos-debito/{anexo_debito_id}/download")
    assert r2.status_code == 404, (r2.status_code, r2.text)

    async with _sm(admin_engine)() as s:
        row = (await s.execute(text(
            "SELECT acao FROM aprimora_py.audit_log WHERE tenant_id=:t "
            "AND acao='anexo_debito.removido'"
        ), {"t": tenant.id})).fetchall()
        assert len(row) == 1

    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_upload_em_debito_terminal_e_409(admin_engine):
    tenant, solicitante_id, _, _ = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])

    async with _sm(admin_engine)() as s:
        await svc.cancelar(
            s, tenant_id=tenant.id, debito_id=debito.id, usuario_id=solicitante_id,
            lock_version=debito.lock_version, justificativa="Não é mais necessário.")

    r = await _upload(admin_engine, tenant.id, tenant.slug, uid,
                      f"/api/v2/pagamentos/debitos/{debito.id}/anexos")
    assert r.status_code == 409, (r.status_code, r.text)

    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_anexo_em_resposta_a_pedido_referencia_o_pedido(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id = await _provisionar(admin_engine)
    debito = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=solicitante_id, lock_version=debito.lock_version)
        debito = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=gestor_id, lock_version=debito.lock_version)
        debito = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito.id,
            usuario_id=validador_id, lock_version=debito.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante",
            descricao="Falta o comprovante de liquidação anexado ao processo.",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )

    async with _sm(admin_engine)() as s:
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito.id)
    pedido_id = pedidos[0].id

    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
    r = await _upload(admin_engine, tenant.id, tenant.slug, uid,
                      f"/api/v2/pagamentos/debitos/{debito.id}/anexos",
                      data={"descricao": "Comprovante", "id_pedido_ajuste": str(pedido_id)})
    assert r.status_code == 201, (r.status_code, r.text)
    assert r.json()["id_pedido_ajuste"] == pedido_id
    assert r.json()["versao_debito"] == debito.versao

    async with _sm(admin_engine)() as s:
        row = (await s.execute(text(
            "SELECT id_pedido_ajuste FROM pagamentos.anexo_debito WHERE id=:i"
        ), {"i": r.json()["id"]})).scalar_one()
        assert row == pedido_id

    await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_pedido_de_outro_debito_e_422(admin_engine):
    tenant, solicitante_id, gestor_id, validador_id = await _provisionar(admin_engine)
    debito1 = await _setup_debito(admin_engine, tenant.id, solicitante_id)
    debito2 = await _setup_debito(admin_engine, tenant.id, solicitante_id)

    async with _sm(admin_engine)() as s:
        debito1 = await svc.enviar_para_gestor(
            s, tenant_id=tenant.id, debito_id=debito1.id,
            usuario_id=solicitante_id, lock_version=debito1.lock_version)
        debito1 = await svc.gestor_autorizar(
            s, tenant_id=tenant.id, debito_id=debito1.id,
            usuario_id=gestor_id, lock_version=debito1.lock_version)
        debito1 = await svc.solicitar_ajuste(
            s, tenant_id=tenant.id, debito_id=debito1.id,
            usuario_id=validador_id, lock_version=debito1.lock_version,
            etapa="VALIDACAO", motivo="Falta comprovante", descricao="Falta comprovante",
            transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL",
        )
        pedidos = await ajustes.listar_pedidos(s, tenant_id=tenant.id, debito_id=debito1.id)
    pedido_id = pedidos[0].id

    uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_solicitar"])
    r = await _upload(admin_engine, tenant.id, tenant.slug, uid,
                      f"/api/v2/pagamentos/debitos/{debito2.id}/anexos",
                      data={"id_pedido_ajuste": str(pedido_id)})
    assert r.status_code == 422, (r.status_code, r.text)

    await _cleanup(admin_engine, tenant.id)
