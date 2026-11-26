"""Despacho sem encaminhar (SI-62, RF-03).

Tudo pela API, com usuário COMUM (não super-usuário, que passaria por cima de
lotação e sigilo — ver CLAUDE.md §Testes). Cobre o "pronto quando" do card:

- registrar despacho sem escolher unidade de destino, e o processo FICA na
  unidade;
- o despacho concluído vira movimentação na linha do tempo, com o PDF
  assinado (e, por ser anexo, entra no PDF do processo);
- o rascunho não aparece como ato e só o autor o vê;
- senha errada não grava nada; dois cliques não duplicam;
- bloqueios: arquivado, em trânsito, quem não é lotado, outra prefeitura;
- o rascunho de despacho não se finaliza nem vai ao Google pelo caminho comum.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.auth.password import hash_password
from app.config import get_settings
from app.main import app
from app.models import (
    Acao,
    Anexo,
    AssinaturaAnexo,
    Assunto,
    Despacho,
    Encaminhamento,
    Manifestante,
    Minuta,
    Movimentacao,
    Processo,
    TipoProcesso,
    Usuario,
)
from app.schemas.processo import ArquivarRequest
from app.services.acoes_processo import arquivar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name
SENHA = "Senha-Despacho-123"
TEXTO = "Analisei a documentação. Aguardando parecer jurídico."


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _usuario_comum(s, tenant_id: int, unidade_id: int | None) -> int:
    sistema_id = (await s.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await s.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
    ))).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (await s.execute(text(
            "INSERT INTO utils.nivel (nivel, valor, excluido) "
            "VALUES ('Operacional', 1, false) RETURNING id"
        ))).scalar_one()
    transacao_id = (await s.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = 'processo' AND excluido = false LIMIT 1"
    ))).scalar_one()
    uid = (await s.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo, id_unidade_trabalho)
        VALUES (:t, 'Chefe', :e, '', :h, :c, true, false, :app, 'interno', :u) RETURNING id
    """), {"t": tenant_id, "e": f"chefe-{uuid.uuid4().hex[:8]}@despacho.test",
           "h": hash_password(SENHA), "c": uuid.uuid4().hex[:11], "app": APP,
           "u": unidade_id})).scalar_one()
    gid = (await s.execute(text(
        "INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido) "
        "VALUES (:t, :n, :s, 'Grupo Despacho', false) RETURNING id"
    ), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await s.execute(text(
        "INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app) "
        "VALUES (:t, :u, :g, true, false, :app)"
    ), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await s.execute(text(
        "INSERT INTO utils.grupo_transacao "
        "(tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido) "
        "VALUES (:t, :g, :tr, true, true, true, false)"
    ), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return uid


async def _prefeitura(admin_engine, prefixo: str) -> dict:
    slug = f"{prefixo}{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome=f"Pref {slug}", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(admin_engine)() as s:
        unidade = (await s.execute(text(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t ORDER BY id LIMIT 1"
        ), {"t": tenant.id})).scalar_one()
        outra_unidade = (await s.execute(text(
            "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) "
            "VALUES (:t, 'Procuradoria', false) RETURNING id"
        ), {"t": tenant.id})).scalar_one()
        tipo_manif = (await s.execute(text(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"
        ), {"t": tenant.id})).scalar_one()
        abertura = (await s.execute(select(Acao.id).where(Acao.flag == "ABERTURA"))).scalar_one()
        prioridade = (await s.execute(text(
            "SELECT id FROM protocolos.prioridade WHERE excluido = false ORDER BY id LIMIT 1"
        ))).scalar_one()
        tp = TipoProcesso(tenant_id=tenant.id, tipo_processo="Geral",
                          exige_processo_pai=False, ativo=True, excluido=False)
        manif = Manifestante(tenant_id=tenant.id, id_tipo_manifestante=tipo_manif,
                             nome="Maria", ativo=True, excluido=False)
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
                          exige_processo_pai=False, ativo=True, excluido=False)
        s.add(assunto)
        await s.flush()
        chefe = await _usuario_comum(s, tenant.id, unidade)
        colega = await _usuario_comum(s, tenant.id, unidade)
        de_fora = await _usuario_comum(s, tenant.id, outra_unidade)

        async def processo() -> int:
            p = Processo(
                tenant_id=tenant.id, id_assunto=assunto.id, virtual=True,
                data_hora_abertura=datetime.now(),
                numero_processo=f"{slug}-{uuid.uuid4().hex[:6]}", situacao="protocolado",
                id_unidade_proprietaria=unidade, id_manifestante=manif.id,
                id_local_atual=unidade, nivel_sigilo="ostensivo", ativo=True, excluido=False,
            )
            s.add(p)
            await s.flush()
            mov = Movimentacao(
                tenant_id=tenant.id, id_processo=p.id, id_unidade_responsavel=unidade,
                id_acao=abertura, id_usuario=chefe, data_hora_movimentacao=datetime.now(),
                ativo=True, excluido=False,
            )
            s.add(mov)
            await s.flush()
            p.id_ultima_movimentacao = mov.id
            return p.id

        na_mesa, arquivado, em_transito = await processo(), await processo(), await processo()
        await s.flush()
        # Arquivado pelo serviço de verdade (a movimentação exige o registro
        # em `protocolos.arquivamento`).
        await arquivar(s, arquivado, ArquivarRequest(motivo="Demanda atendida"),
                       tenant_id=tenant.id, usuario_id=chefe, is_super_usuario=True)
        s.add(Encaminhamento(
            tenant_id=tenant.id, id_processo=em_transito, id_unidade_origem=unidade,
            id_unidade_destino=outra_unidade, id_prioridade=prioridade, id_usuario=chefe,
        ))
        await s.commit()
        return {
            "tenant": tenant, "unidade": unidade, "chefe": chefe, "colega": colega,
            "de_fora": de_fora, "na_mesa": na_mesa, "arquivado": arquivado,
            "em_transito": em_transito,
        }


async def _limpar(admin_engine, tenant_id: int) -> None:
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.assinatura_anexo WHERE tenant_id=:t",
            "DELETE FROM protocolos.usuario_assinatura WHERE tenant_id=:t",
            "DELETE FROM protocolos.solicitacao_assinatura WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta_historico WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
            "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
            "DELETE FROM protocolos.encaminhamento WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.arquivamento WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest_asyncio.fixture
async def cen(admin_engine):
    a = await _prefeitura(admin_engine, "desp-a-")
    b = await _prefeitura(admin_engine, "desp-b-")
    yield {"a": a, "b": b}
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    await _limpar(admin_engine, a["tenant"].id)
    await _limpar(admin_engine, b["tenant"].id)


def _como(admin_engine, pref: dict, quem: str) -> AsyncClient:
    async def _usuario():
        async with _sm(admin_engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == pref[quem]))).scalar_one()

    app.dependency_overrides[get_current_user] = _usuario
    arreio_tenant_http(pref["tenant"].id, pref["tenant"].slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _rascunho(cli: AsyncClient, processo_id: int, texto: str = TEXTO) -> int:
    r = await cli.post(f"/api/v2/processos/{processo_id}/minutas", json={
        "titulo": "Despacho", "finalidade": "despacho", "corpo_html": f"<p>{texto}</p>",
    })
    assert r.status_code == 201, r.text
    assert r.json()["finalidade"] == "despacho"
    return r.json()["id"]


async def _concluir(cli: AsyncClient, minuta_id: int, senha: str = SENHA, arquivos=None):
    return await cli.post(
        f"/api/v2/minutas/{minuta_id}/concluir-despacho",
        data={"senha": senha},
        files=arquivos or [],
    )


async def _contar(admin_engine, modelo, *cond) -> int:
    async with _sm(admin_engine)() as s:
        return (await s.execute(select(func.count()).select_from(modelo).where(*cond))).scalar_one()


@pytest.mark.asyncio
async def test_concluir_despacho_fica_na_unidade_e_entra_na_linha_do_tempo(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        r = await _concluir(cli, mid, arquivos=[("arquivos", ("parecer.txt", b"anexo", "text/plain"))])
        assert r.status_code == 201, r.text
        resp = r.json()

        det = (await cli.get(f"/api/v2/processos/{a['na_mesa']}")).json()
    despachos = [m for m in det["movimentacoes"] if m["acao_flag"] == "DESPACHO"]
    assert len(despachos) == 1
    m = despachos[0]
    assert m["despacho"]["despacho"] == TEXTO
    assert m["despacho"]["id_anexo"] == resp["id_anexo"]
    # O arquivo enviado junto acompanha o despacho (filho do PDF).
    assert [x["descricao"] for x in m["despacho"]["anexos"]] == ["parecer.txt"]
    filho = next(an for an in det["anexos"] if an["descricao"] == "parecer.txt")
    assert filho["id_anexo_principal"] == resp["id_anexo"]
    assert m["unidade_responsavel"] is not None
    # Entra no detalhe do processo, que é de onde sai o PDF do processo.
    assert resp["id_anexo"] in {an["id"] for an in det["anexos"]}

    async with _sm(admin_engine)() as s:
        p = (await s.execute(select(Processo).where(Processo.id == a["na_mesa"]))).scalar_one()
        assert p.id_local_atual == a["unidade"]          # ficou na unidade
        assert p.id_ultima_movimentacao == resp["id_movimentacao"]
        anexo = (await s.execute(select(Anexo).where(Anexo.id == resp["id_anexo"]))).scalar_one()
        assert anexo.publico is False                    # cidadão não vê
        aa = (await s.execute(select(AssinaturaAnexo).where(
            AssinaturaAnexo.id_anexo == resp["id_anexo"]))).scalar_one()
        assert aa.assinado and aa.status == "assinada"
        assert aa.id_usuario == a["chefe"] and aa.documento_hash and aa.codigo_validacao
        minuta = (await s.execute(select(Minuta).where(Minuta.id == mid))).scalar_one()
        assert minuta.status == "finalizada" and minuta.id_anexo_final == resp["id_anexo"]
    # Nenhum encaminhamento novo: o despacho não manda o processo a lugar nenhum.
    assert await _contar(admin_engine, Encaminhamento,
                         Encaminhamento.id_processo == a["na_mesa"]) == 0
    # O anexo enviado junto entrou ligado ao processo.
    assert await _contar(admin_engine, Anexo, Anexo.tenant_id == a["tenant"].id,
                         Anexo.descricao == "parecer.txt") == 1


@pytest.mark.asyncio
async def test_rascunho_so_o_autor_ve_e_nao_e_ato(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        det = (await cli.get(f"/api/v2/processos/{a['na_mesa']}")).json()
        assert not [m for m in det["movimentacoes"] if m["acao_flag"] == "DESPACHO"]
        assert mid in {x["id"] for x in (await cli.get(
            f"/api/v2/processos/{a['na_mesa']}/minutas")).json()}
    async with _como(admin_engine, a, "colega") as cli:
        lista = (await cli.get(f"/api/v2/processos/{a['na_mesa']}/minutas")).json()
        assert mid not in {x["id"] for x in lista}
        assert (await cli.get(f"/api/v2/minutas/{mid}")).status_code == 404
        assert (await _concluir(cli, mid)).status_code == 404


@pytest.mark.asyncio
async def test_senha_errada_nao_grava_nada(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        r = await _concluir(cli, mid, senha="errada")
        assert r.status_code == 400, r.text
    assert await _contar(admin_engine, Despacho, Despacho.id_processo == a["na_mesa"]) == 0
    assert await _contar(admin_engine, Anexo, Anexo.tenant_id == a["tenant"].id) == 0
    async with _sm(admin_engine)() as s:
        assert (await s.execute(select(Minuta.status).where(Minuta.id == mid))).scalar_one() == "rascunho"


@pytest.mark.asyncio
async def test_concluir_duas_vezes_nao_duplica(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        assert (await _concluir(cli, mid)).status_code == 201
        assert (await _concluir(cli, mid)).status_code == 409
    assert await _contar(admin_engine, Despacho, Despacho.id_processo == a["na_mesa"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("onde", ["arquivado", "em_transito"])
async def test_nao_despacha_arquivado_nem_em_transito(admin_engine, cen, onde):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a[onde])
        r = await _concluir(cli, mid)
        assert r.status_code == 409, r.text
    assert await _contar(admin_engine, Despacho, Despacho.id_processo == a[onde]) == 0


@pytest.mark.asyncio
async def test_so_quem_e_lotado_na_unidade_despacha(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "de_fora") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        r = await _concluir(cli, mid)
        assert r.status_code == 403, r.text
    assert await _contar(admin_engine, Despacho, Despacho.id_processo == a["na_mesa"]) == 0


@pytest.mark.asyncio
async def test_outra_prefeitura_nao_alcanca(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
    async with _como(admin_engine, b, "chefe") as cli:
        assert (await _concluir(cli, mid)).status_code == 404
        r = await cli.post(f"/api/v2/processos/{a['na_mesa']}/minutas", json={
            "titulo": "Despacho", "finalidade": "despacho", "corpo_html": "<p>x</p>"})
        assert r.status_code in (404, 400), r.text
    assert await _contar(admin_engine, Despacho, Despacho.id_processo == a["na_mesa"]) == 0


@pytest.mark.asyncio
async def test_rascunho_de_despacho_nao_finaliza_nem_vai_ao_google(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        assert (await cli.post(f"/api/v2/minutas/{mid}/finalizar")).status_code == 409
        assert (await cli.post(f"/api/v2/minutas/{mid}/criar-em-google")).status_code == 409
        r = await cli.post(f"/api/v2/processos/{a['na_mesa']}/minutas", json={
            "titulo": "Despacho", "finalidade": "despacho", "origem": "google"})
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_anexo_enviado_depois_nao_vira_anexo_do_despacho(admin_engine, cen):
    """Todo anexo se liga à ÚLTIMA movimentação; depois do despacho, sem o
    processo andar, um upload cai na movimentação dele. O vínculo com o
    despacho é o documento principal, e é isso que a linha do tempo mostra."""
    a = cen["a"]
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        r = await _concluir(cli, mid, arquivos=[("arquivos", ("parecer.txt", b"x", "text/plain"))])
        assert r.status_code == 201, r.text
        r = await cli.post(f"/api/v2/processos/{a['na_mesa']}/anexos",
                           data={"descricao": "depois.txt"},
                           files={"file": ("depois.txt", b"y", "text/plain")})
        assert r.status_code in (200, 201), r.text
        det = (await cli.get(f"/api/v2/processos/{a['na_mesa']}")).json()
    despacho = next(m for m in det["movimentacoes"] if m["acao_flag"] == "DESPACHO")
    assert [x["descricao"] for x in despacho["despacho"]["anexos"]] == ["parecer.txt"]
    depois = next(an for an in det["anexos"] if an["descricao"] == "depois.txt")
    assert depois["id_anexo_principal"] is None


@pytest.mark.asyncio
async def test_desarquivado_volta_a_receber_despacho(admin_engine, cen):
    """SI-60: desarquivar desativa o arquivamento sem apagá-lo. Arquivado é ter
    arquivamento EM VIGOR; contar "existe arquivamento" deixaria o processo
    desarquivado proibido de receber despacho para sempre."""
    from app.schemas.processo import DesarquivarRequest
    from app.services.acoes_processo import desarquivar

    a = cen["a"]
    async with _sm(admin_engine)() as s:
        await desarquivar(s, a["arquivado"], DesarquivarRequest(justificativa="Reaberto para análise"),
                          tenant_id=a["tenant"].id, usuario_id=a["chefe"])
        await s.commit()
    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["arquivado"])
        r = await _concluir(cli, mid)
        assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_despacho_depois_do_recebimento_impede_cancelar_o_recebimento(admin_engine, cen):
    """RF-02 (SI-61): o recebimento só se cancela se nada aconteceu depois. O
    despacho avulso é um ato — e, como movimentação, ele aparece para a regra."""
    from app.services.acoes_processo import motivo_bloqueio_cancelar_recebimento

    a = cen["a"]
    async with _sm(admin_engine)() as s:
        recebimento = (await s.execute(select(Acao.id).where(Acao.flag == "RECEBIMENTO"))).scalar_one()
        prioridade = (await s.execute(text(
            "SELECT id FROM protocolos.prioridade WHERE excluido = false ORDER BY id LIMIT 1"
        ))).scalar_one()
        enc = Encaminhamento(
            tenant_id=a["tenant"].id, id_processo=a["na_mesa"], id_unidade_origem=a["unidade"],
            id_unidade_destino=a["unidade"], id_prioridade=prioridade, id_usuario=a["chefe"],
            recebido=True, data_hora_recebimento=datetime.now(),
        )
        s.add(enc)
        await s.flush()
        receb = Movimentacao(
            tenant_id=a["tenant"].id, id_processo=a["na_mesa"], id_unidade_responsavel=a["unidade"],
            id_acao=recebimento, id_encaminhamento=enc.id, id_usuario=a["chefe"],
            data_hora_movimentacao=datetime.now(), ativo=True, excluido=False,
        )
        s.add(receb)
        await s.flush()
        await s.execute(text("UPDATE protocolos.processo SET id_ultima_movimentacao=:m WHERE id=:p"),
                        {"m": receb.id, "p": a["na_mesa"]})
        await s.commit()
        assert await motivo_bloqueio_cancelar_recebimento(
            s, a["na_mesa"], a["tenant"].id, receb, enc) is None  # antes: cancelável

    async with _como(admin_engine, a, "chefe") as cli:
        mid = await _rascunho(cli, a["na_mesa"])
        assert (await _concluir(cli, mid)).status_code == 201

    async with _sm(admin_engine)() as s:
        receb = (await s.execute(select(Movimentacao).where(Movimentacao.id == receb.id))).scalar_one()
        enc = (await s.execute(select(Encaminhamento).where(Encaminhamento.id == enc.id))).scalar_one()
        motivo = await motivo_bloqueio_cancelar_recebimento(s, a["na_mesa"], a["tenant"].id, receb, enc)
    assert motivo is not None and "despacho" in motivo.lower()
