"""Versão nova de documento (SI-72, RF-04 V1): corrigir sem apagar o anterior.

Tudo pela API, com usuário COMUM (o super-usuário passaria por cima do sigilo
— ver CLAUDE.md §Testes). Cobre o "pronto quando" do card e as regras
combinadas:

- a versão nova entra no fim do processo; a anterior continua na lista com o
  MESMO número (folha não se renumera), marcada como substituída;
- a nova herda tipo, publicidade e documento exigido;
- só a vigente recebe correção (409 ao ramificar); arquivado não recebe;
- nenhuma das duas versões pode ser excluída;
- sigilo: upload, versão nova e exclusão em processo acima da credencial dão
  404 (antes, o upload e a exclusão nem olhavam o sigilo);
- documento de outro processo ou de outra prefeitura: 404;
- o portal do cidadão mostra só a vigente.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Acao,
    Anexo,
    Assunto,
    Manifestante,
    Movimentacao,
    Processo,
    TipoProcesso,
    Usuario,
)
from app.schemas.processo import ArquivarRequest
from app.services.acoes_processo import arquivar
from app.services.cidadao_processos import get_meu_detail
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name
CPF_CIDADAO = "52998224725"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _usuario_comum(s, tenant_id: int, unidade_id: int) -> int:
    """Usuário não-SU, credencial `interno`, com a transação `processo`."""
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
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo, id_unidade_trabalho)
        VALUES (:t, 'Servidor', :e, '', :c, true, false, :app, 'interno', :u) RETURNING id
    """), {"t": tenant_id, "e": f"serv-{uuid.uuid4().hex[:8]}@versao.test",
           "c": uuid.uuid4().hex[:11], "app": APP, "u": unidade_id})).scalar_one()
    gid = (await s.execute(text(
        "INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido) "
        "VALUES (:t, :n, :s, 'Grupo Versao', false) RETURNING id"
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
        tipo_manif = (await s.execute(text(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"
        ), {"t": tenant.id})).scalar_one()
        abertura = (await s.execute(select(Acao.id).where(Acao.flag == "ABERTURA"))).scalar_one()
        tp = TipoProcesso(tenant_id=tenant.id, tipo_processo="Geral",
                          exige_processo_pai=False, ativo=True, excluido=False)
        manif = Manifestante(tenant_id=tenant.id, id_tipo_manifestante=tipo_manif,
                             nome="Maria", cpf_cnpj=CPF_CIDADAO, ativo=True, excluido=False)
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
                          exige_processo_pai=False, ativo=True, excluido=False)
        s.add(assunto)
        await s.flush()
        servidor = await _usuario_comum(s, tenant.id, unidade)

        async def processo(nivel: str = "ostensivo") -> int:
            p = Processo(
                tenant_id=tenant.id, id_assunto=assunto.id, virtual=True,
                data_hora_abertura=datetime.now(),
                numero_processo=f"{slug}-{uuid.uuid4().hex[:6]}", situacao="protocolado",
                id_unidade_proprietaria=unidade, id_manifestante=manif.id,
                id_local_atual=unidade, nivel_sigilo=nivel, ativo=True, excluido=False,
            )
            s.add(p)
            await s.flush()
            mov = Movimentacao(
                tenant_id=tenant.id, id_processo=p.id, id_unidade_responsavel=unidade,
                id_acao=abertura, id_usuario=servidor, data_hora_movimentacao=datetime.now(),
                ativo=True, excluido=False,
            )
            s.add(mov)
            await s.flush()
            p.id_ultima_movimentacao = mov.id
            return p.id

        principal, outro, arquivado = await processo(), await processo(), await processo()
        reservado = await processo("reservado")
        await s.commit()
    return {
        "tenant": tenant, "unidade": unidade, "servidor": servidor,
        "principal": principal, "outro": outro, "arquivado": arquivado,
        "reservado": reservado,
    }


async def _limpar(admin_engine, tenant_id: int) -> None:
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.minuta_historico WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta WHERE tenant_id=:t",
            "UPDATE protocolos.anexo SET id_anexo_anterior=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
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
    a = await _prefeitura(admin_engine, "versao-a-")
    b = await _prefeitura(admin_engine, "versao-b-")
    yield {"a": a, "b": b}
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    await _limpar(admin_engine, a["tenant"].id)
    await _limpar(admin_engine, b["tenant"].id)


def _como(admin_engine, pref: dict) -> AsyncClient:
    async def _usuario():
        async with _sm(admin_engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == pref["servidor"])
            )).scalar_one()

    app.dependency_overrides[get_current_user] = _usuario
    arreio_tenant_http(pref["tenant"].id, pref["tenant"].slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _anexar(cli, processo_id: int, nome: str, publico: bool = True):
    return await cli.post(
        f"/api/v2/processos/{processo_id}/anexos",
        data={"descricao": nome, "publico": str(publico).lower()},
        files={"file": (f"{nome}.txt", nome.encode(), "text/plain")},
    )


async def _nova_versao(cli, processo_id: int, anexo_id: int, conteudo: bytes = b"corrigido",
                       motivo: str | None = "Faltava a assinatura do requerente"):
    data = {"motivo": motivo} if motivo else {}
    return await cli.post(
        f"/api/v2/processos/{processo_id}/anexos/{anexo_id}/versoes",
        data=data,
        files={"file": ("corrigido.txt", conteudo, "text/plain")},
    )


def _por_id(det: dict) -> dict[int, dict]:
    return {an["id"]: an for an in det["anexos"]}


@pytest.mark.asyncio
async def test_versao_nova_entra_no_fim_e_anterior_fica_no_historico(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        r = await _anexar(cli, a["principal"], "Requerimento")
        assert r.status_code == 201, r.text
        v1 = r.json()["id"]
        r = await _anexar(cli, a["principal"], "Comprovante")
        assert r.status_code == 201, r.text
        comprovante = r.json()["id"]
        antes = _por_id((await cli.get(f"/api/v2/processos/{a['principal']}")).json())
        assert antes[v1]["aceita_nova_versao"] is True

        r = await _nova_versao(cli, a["principal"], v1)
        assert r.status_code == 201, r.text
        v2 = r.json()
        assert v2["versao"] == 2 and v2["id_anexo_anterior"] == v1
        assert v2["motivo_versao"] == "Faltava a assinatura do requerente"

        det = (await cli.get(f"/api/v2/processos/{a['principal']}")).json()
    lista = _por_id(det)
    # A anterior continua no processo, com o MESMO número: folha não se renumera.
    assert lista[v1]["documento_numero"] == antes[v1]["documento_numero"]
    assert lista[comprovante]["documento_numero"] == antes[comprovante]["documento_numero"]
    assert lista[v1]["id_anexo_substituto"] == v2["id"]
    assert lista[v1]["aceita_nova_versao"] is False
    # A nova entra no fim, como qualquer juntada, e herda o que identifica o documento.
    nova = lista[v2["id"]]
    assert nova["documento_numero"] == len(det["anexos"])
    assert nova["id_anexo_substituto"] is None and nova["aceita_nova_versao"] is True
    assert nova["descricao"] == "Requerimento"
    assert nova["publico"] is True

    # Ficou rastro de quem corrigiu.
    async with _sm(admin_engine)() as s:
        acao = (await s.execute(text(
            "SELECT payload->>'id_anexo_anterior' FROM aprimora_py.audit_log "
            "WHERE tenant_id=:t AND acao='processo.anexo_nova_versao'"
        ), {"t": a["tenant"].id})).scalar_one()
        assert int(acao) == v1


@pytest.mark.asyncio
async def test_herda_tipo_e_publicidade(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Laudo", publico=False)).json()["id"]
        r = await _nova_versao(cli, a["principal"], v1, motivo=None)
        assert r.status_code == 201, r.text
        assert r.json()["publico"] is False
        assert r.json()["motivo_versao"] is None
    async with _sm(admin_engine)() as s:
        antigo = (await s.execute(select(Anexo).where(Anexo.id == v1))).scalar_one()
        novo = (await s.execute(select(Anexo).where(Anexo.id == r.json()["id"]))).scalar_one()
        assert novo.id_tipo_anexo == antigo.id_tipo_anexo
        assert novo.documento_exigido_key == antigo.documento_exigido_key


@pytest.mark.asyncio
async def test_so_a_vigente_recebe_correcao(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Planta")).json()["id"]
        v2 = (await _nova_versao(cli, a["principal"], v1)).json()["id"]
        r = await _nova_versao(cli, a["principal"], v1)
        assert r.status_code == 409, r.text
        assert "substituído" in r.json()["detail"]
        # Sobre a vigente, a cadeia continua.
        r = await _nova_versao(cli, a["principal"], v2)
        assert r.status_code == 201 and r.json()["versao"] == 3


@pytest.mark.asyncio
async def test_substituida_nao_sai_e_vigente_enviada_por_engano_sai(admin_engine, cen):
    """A substituída é histórico. A vigente pode ser excluída (arquivo errado)
    e a anterior volta a valer, aceitando de novo uma versão nova."""
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Ofício")).json()["id"]
        v2 = (await _nova_versao(cli, a["principal"], v1)).json()["id"]
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{v1}")
        assert r.status_code == 400 and "histórico" in r.json()["detail"]

        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{v2}")
        assert r.status_code == 204, r.text
        lista = _por_id((await cli.get(f"/api/v2/processos/{a['principal']}")).json())
        assert v2 not in lista
        assert lista[v1]["id_anexo_substituto"] is None
        assert lista[v1]["aceita_nova_versao"] is True

        # E a versão certa entra em seguida, de novo como versão 2.
        r = await _nova_versao(cli, a["principal"], v1)
        assert r.status_code == 201, r.text
        assert r.json()["versao"] == 2


@pytest.mark.asyncio
async def test_vigente_assinada_nao_sai(admin_engine, cen, monkeypatch):
    """A trava de assinatura (Assinatura v2, testada em test_assinatura_v2)
    continua valendo para a versão vigente; aqui ela é simulada."""
    from app.services import anexos as anexos_svc

    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Termo")).json()["id"]
        v2 = (await _nova_versao(cli, a["principal"], v1)).json()["id"]

    async def _assinado(_db, anexo_id, *, tenant_id):
        return anexo_id == v2

    monkeypatch.setattr(anexos_svc, "anexo_esta_assinado", _assinado)
    async with _como(admin_engine, a) as cli:
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{v2}")
        assert r.status_code == 400 and "assinatura" in r.json()["detail"]


@pytest.mark.asyncio
async def test_processo_arquivado_nao_recebe_versao(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["arquivado"], "Termo")).json()["id"]
    async with _sm(admin_engine)() as s:
        await arquivar(s, a["arquivado"], ArquivarRequest(motivo="Demanda atendida"),
                       tenant_id=a["tenant"].id, usuario_id=a["servidor"],
                       is_super_usuario=True)
        await s.commit()
    async with _como(admin_engine, a) as cli:
        r = await _nova_versao(cli, a["arquivado"], v1)
        assert r.status_code == 409 and "arquivado" in r.json()["detail"]


@pytest.mark.asyncio
async def test_sigilo_barra_upload_versao_e_exclusao(admin_engine, cen):
    """Processo `reservado`, usuário com credencial `interno`: 404 nas três
    rotas, sem gravar nada. Antes do SI-72 o upload e a exclusão passavam."""
    a = cen["a"]
    # Documento posto no processo sigiloso por fora da API (quem tem credencial).
    async with _sm(admin_engine)() as s:
        mov = (await s.execute(select(Processo.id_ultima_movimentacao).where(
            Processo.id == a["reservado"]))).scalar_one()
        anexo = Anexo(tenant_id=a["tenant"].id, publico=False, ativo=True, excluido=False,
                      descricao="Parecer sigiloso", e_doc=f"sig-{uuid.uuid4().hex[:12]}.txt")
        s.add(anexo)
        await s.flush()
        await s.execute(text(
            "INSERT INTO protocolos.anexo_processo (tenant_id, id_processo, id_anexo, "
            "id_movimentacao, ativo, excluido, ordem, anexo_herdado) "
            "VALUES (:t, :p, :a, :m, true, false, 1, false)"
        ), {"t": a["tenant"].id, "p": a["reservado"], "a": anexo.id, "m": mov})
        await s.commit()
        sigiloso = anexo.id

    async with _como(admin_engine, a) as cli:
        r = await _anexar(cli, a["reservado"], "Intruso")
        assert r.status_code == 404, r.text
        r = await _nova_versao(cli, a["reservado"], sigiloso)
        assert r.status_code == 404, r.text
        r = await cli.delete(f"/api/v2/processos/{a['reservado']}/anexos/{sigiloso}")
        assert r.status_code == 404, r.text

    async with _sm(admin_engine)() as s:
        n = (await s.execute(text(
            "SELECT count(*) FROM protocolos.anexo_processo WHERE id_processo=:p"
        ), {"p": a["reservado"]})).scalar_one()
        assert n == 1
        ainda = (await s.execute(select(Anexo).where(Anexo.id == sigiloso))).scalar_one()
        assert ainda.excluido is False


@pytest.mark.asyncio
async def test_documento_de_outro_processo_ou_prefeitura_da_404(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Contrato")).json()["id"]
        # Mesmo documento, processo errado.
        r = await _nova_versao(cli, a["outro"], v1)
        assert r.status_code == 404, r.text
    # Servidor de outra prefeitura, com os ids de A.
    async with _como(admin_engine, b) as cli:
        r = await _nova_versao(cli, a["principal"], v1)
        assert r.status_code == 404, r.text
        r = await _nova_versao(cli, b["principal"], v1)
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_portal_do_cidadao_mostra_so_a_vigente(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Alvará")).json()["id"]
        v2 = (await _nova_versao(cli, a["principal"], v1)).json()["id"]
    async with _sm(admin_engine)() as s:
        det = await get_meu_detail(
            s, SimpleNamespace(cpf_cnpj=CPF_CIDADAO), a["principal"],
            tenant_id=a["tenant"].id,
        )
    assert det is not None
    assert [an.id for an in det.anexos] == [v2]


def _pdf(paginas: int) -> bytes:
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    for i in range(paginas):
        c.drawString(72, 720, f"pagina {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.parametrize("paginas", [1, 17, 120])
def test_contagem_de_paginas_nao_soma_o_no_da_arvore(paginas):
    """Até o SI-72 a conta somava o nó `/Type /Pages`: 17 páginas viravam 18,
    e o erro passava para as "fls." de todo documento seguinte."""
    from app.services.anexos import contar_paginas_pdf

    conteudo = _pdf(paginas)
    assert conteudo.count(b"/Type /Page") > paginas  # a conta antiga erraria
    assert contar_paginas_pdf(conteudo) == paginas


def test_contagem_de_paginas_de_pdf_ilegivel_usa_a_estimativa():
    from app.services.anexos import contar_paginas_pdf

    quebrado = b"%PDF-1.4 lixo /Type /Pages /Type /Page /Type /Page sem xref"
    assert contar_paginas_pdf(quebrado) == 2
    assert contar_paginas_pdf(b"nada") is None


@pytest.mark.asyncio
async def test_upload_grava_paginas_reais(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos",
            data={"descricao": "Laudo", "publico": "true"},
            files={"file": ("laudo.pdf", _pdf(17), "application/pdf")},
        )
        assert r.status_code == 201, r.text
        assert r.json()["qtd_paginas"] == 17


def _texto(pdf: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf)).pages)


def test_carimbo_marca_substituido_e_versao():
    from app.services.pdf_carimbo import carimbar_pdf_bytes, nome_cache

    original = _pdf(3)
    comum = _texto(carimbar_pdf_bytes(original, numero_processo="P1", e_doc="1.pdf"))
    assert "SUBSTITU" not in comum and "versão" not in comum

    vigente = _texto(carimbar_pdf_bytes(original, numero_processo="P1", e_doc="9.pdf", versao=2))
    assert "versão 2" in vigente and "SUBSTITU" not in vigente

    antigo = carimbar_pdf_bytes(
        original, numero_processo="P1", e_doc="1.pdf", substituido_pela_versao=2
    )
    # A faixa sai em TODAS as páginas: quem imprime uma folha solta também vê.
    from io import BytesIO

    from pypdf import PdfReader

    for pagina in PdfReader(BytesIO(antigo)).pages:
        assert "SUBSTITUÍDO PELA VERSÃO 2" in (pagina.extract_text() or "")

    # Cada estado tem o seu cache: voltar a ser vigente reaproveita o comum.
    assert nome_cache(7) == "7.pdf"
    assert nome_cache(7, 2) == "7-subst-v2.pdf"


@pytest.mark.asyncio
async def test_carimbo_pela_rota_acompanha_o_estado_da_versao(admin_engine, cen):
    a = cen["a"]

    async def carimbado(cli, anexo_id) -> str:
        r = await cli.get(f"/api/v2/anexos/{anexo_id}/carimbado.pdf")
        assert r.status_code == 200, r.text
        return _texto(r.content)

    async with _como(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos",
            data={"descricao": "Projeto", "publico": "true"},
            files={"file": ("projeto.pdf", _pdf(2), "application/pdf")},
        )
        v1 = r.json()["id"]
        assert "SUBSTITU" not in await carimbado(cli, v1)  # já fica no cache

        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos/{v1}/versoes",
            files={"file": ("projeto-v2.pdf", _pdf(2), "application/pdf")},
        )
        v2 = r.json()["id"]
        # O cache antigo não esconde a mudança de estado.
        assert "SUBSTITUÍDO PELA VERSÃO 2" in await carimbado(cli, v1)
        assert "versão 2" in await carimbado(cli, v2)

        # Versão nova excluída: a anterior volta a sair sem a faixa.
        r = await cli.delete(f"/api/v2/processos/{a['principal']}/anexos/{v2}")
        assert r.status_code == 204, r.text
        assert "SUBSTITU" not in await carimbado(cli, v1)


@pytest.mark.asyncio
async def test_pdf_completo_mantem_a_substituida_com_a_faixa(admin_engine, cen):
    """A substituída continua no PDF do processo (folha não se renumera), com a
    faixa em cada página dela; a vigente entra depois, sem faixa."""
    from io import BytesIO

    from pypdf import PdfReader

    from app.services.pdf_montagem import gerar_processo_completo_pdf
    from app.services.processos import get_processo_detail

    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos",
            data={"descricao": "Memorial", "publico": "true"},
            files={"file": ("memorial.pdf", _pdf(2), "application/pdf")},
        )).json()["id"]
        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos/{v1}/versoes",
            files={"file": ("memorial-v2.pdf", _pdf(3), "application/pdf")},
        )
        assert r.status_code == 201, r.text

    async with _sm(admin_engine)() as s:
        s.info["tenant_id"] = a["tenant"].id
        detail = await get_processo_detail(s, a["principal"], tenant_id=a["tenant"].id)
        pdf = await gerar_processo_completo_pdf(detail, tenant_slug=a["tenant"].slug)
    paginas = [p.extract_text() or "" for p in PdfReader(BytesIO(pdf)).pages]
    # capa (1) + v1 (2) + v2 (3)
    assert len(paginas) == 6
    assert all("SUBSTITUÍDO PELA VERSÃO 2" in t for t in paginas[1:3])
    assert not any("SUBSTITU" in t for t in paginas[3:])
    assert all("versão 2" in t for t in paginas[3:])


# ---------------------------------------------------------------------------
# Versão REDIGIDA no sistema (minuta que, finalizada, vira a versão nova)
# ---------------------------------------------------------------------------


async def _rascunho_versao(cli, processo_id: int, anexo_id: int, **extra):
    corpo = {"titulo": "Requerimento corrigido", "id_anexo_substitui": anexo_id, **extra}
    return await cli.post(f"/api/v2/processos/{processo_id}/minutas", json=corpo)


@pytest.mark.asyncio
async def test_versao_redigida_vira_versao_ao_finalizar(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Requerimento")).json()["id"]
        r = await _rascunho_versao(
            cli, a["principal"], v1,
            corpo_html="<p>Texto corrigido</p>", motivo_versao="Assinatura incluída",
        )
        assert r.status_code == 201, r.text
        mid = r.json()["id"]
        assert r.json()["id_anexo_substitui"] == v1

        # Enquanto é rascunho, nada muda no processo.
        lista = _por_id((await cli.get(f"/api/v2/processos/{a['principal']}")).json())
        assert lista[v1]["id_anexo_substituto"] is None

        r = await cli.post(f"/api/v2/minutas/{mid}/finalizar")
        assert r.status_code == 200, r.text
        v2 = r.json()["id_anexo_final"]
        lista = _por_id((await cli.get(f"/api/v2/processos/{a['principal']}")).json())
    assert lista[v1]["id_anexo_substituto"] == v2
    nova = lista[v2]
    assert nova["versao"] == 2 and nova["id_anexo_anterior"] == v1
    assert nova["motivo_versao"] == "Assinatura incluída"
    assert nova["publico"] is True  # herdou do anterior
    assert nova["redigido"] is True and nova["aceita_nova_versao"] is True


@pytest.mark.asyncio
async def test_versao_de_documento_redigido_comeca_do_texto_anterior(admin_engine, cen):
    """Antes o documento redigido não aceitava versão ("reabra a minuta")."""
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        r = await cli.post(f"/api/v2/processos/{a['principal']}/minutas", json={
            "titulo": "Parecer", "corpo_html": "<p>Parecer original com erro</p>",
        })
        mid = r.json()["id"]
        v1 = (await cli.post(f"/api/v2/minutas/{mid}/finalizar")).json()["id_anexo_final"]
        lista = _por_id((await cli.get(f"/api/v2/processos/{a['principal']}")).json())
        assert lista[v1]["redigido"] is True and lista[v1]["aceita_nova_versao"] is True

        r = await _rascunho_versao(cli, a["principal"], v1)
        assert r.status_code == 201, r.text
        assert "Parecer original com erro" in r.json()["corpo_html"]


@pytest.mark.asyncio
async def test_dois_rascunhos_sobre_a_mesma_versao_so_um_vira_versao(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Ofício")).json()["id"]
        m1 = (await _rascunho_versao(cli, a["principal"], v1, corpo_html="<p>A</p>")).json()["id"]
        m2 = (await _rascunho_versao(cli, a["principal"], v1, corpo_html="<p>B</p>")).json()["id"]
        assert (await cli.post(f"/api/v2/minutas/{m1}/finalizar")).status_code == 200
        r = await cli.post(f"/api/v2/minutas/{m2}/finalizar")
        assert r.status_code == 409 and "substituído" in r.json()["detail"]
        # O segundo continua rascunho, sem anexo criado.
        assert (await cli.get(f"/api/v2/minutas/{m2}")).json()["status"] == "rascunho"


@pytest.mark.asyncio
async def test_versao_redigida_recusa_despacho_e_alvo_invalido(admin_engine, cen):
    a = cen["a"]
    async with _como(admin_engine, a) as cli:
        v1 = (await _anexar(cli, a["principal"], "Termo")).json()["id"]
        r = await _rascunho_versao(cli, a["principal"], v1, finalidade="despacho")
        assert r.status_code == 400, r.text
        # Documento de outro processo.
        r = await _rascunho_versao(cli, a["outro"], v1, corpo_html="<p>x</p>")
        assert r.status_code == 404, r.text
        # Processo sigiloso acima da credencial: o guard da minuta barra antes.
        r = await _rascunho_versao(cli, a["reservado"], v1, corpo_html="<p>x</p>")
        assert r.status_code == 404, r.text
