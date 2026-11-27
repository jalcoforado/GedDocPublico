"""SI-68 — assinatura com senha posicionada na página do documento.

Pronto quando: o usuário assina escolhendo o lugar; o PDF baixado mostra o selo
naquele ponto, sem página extra; o `/validar` continua funcionando.

Três blocos:
1. Desenho (sem banco): o selo cai onde a tela disse, inclusive em página com
   origem deslocada e girada; nunca sai da página; nunca cria página.
2. Serviço (`assinar`): a posição é validada antes da senha, gravada nas
   colunas e nas evidências, e o hash continua sendo o do ORIGINAL — o
   `/validar` dá íntegro depois do selo e depois do segundo signatário.
3. HTTP: `/anexos/{id}/carimbado.pdf` serve o carimbo com o selo por cima.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, RectangleObject
from sqlalchemy import select, text

from app.config import tenant_anexos_dir
from app.models import AssinaturaAnexo
from app.schemas.assinatura import AssinarRequest, PosicaoSelo, SolicitarAssinaturaRequest
from app.services.assinaturas import (
    AssinaturaError,
    assinar,
    listar_minhas_pendentes,
    solicitar_assinatura,
    validar_assinatura,
)
from app.services.pdf_carimbo import carimbar_pdf_bytes
from app.services.pdf_selo_assinatura import (
    SELO_ALTURA_PT,
    SELO_LARGURA_PT,
    SeloAssinatura,
    aplicar_selos_pdf_bytes,
    canto_do_selo_em_pontos,
    selos_dos_anexos,
    transformacao_vista_para_pdf,
)
from tests.test_assinatura_v2 import SENHA, _session, _uobj, v2_env  # noqa: F401 — fixture
from tests.test_storage_backend import _get, _sm, ambiente, storage_temporario  # noqa: F401

A4 = (595.0, 842.0)
RAIZ = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- utilidades


def _pdf(paginas: int = 2, *, tamanho=A4, rotacao: int = 0, origem=(0.0, 0.0)) -> bytes:
    w = PdfWriter()
    for _ in range(paginas):
        p = w.add_blank_page(width=tamanho[0], height=tamanho[1])
        if origem != (0.0, 0.0):
            ox, oy = origem
            caixa = RectangleObject([ox, oy, ox + tamanho[0], oy + tamanho[1]])
            p[NameObject("/MediaBox")] = caixa
        if rotacao:
            p[NameObject("/Rotate")] = NumberObject(rotacao)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _selo(pagina=1, x=0.5, y=0.25, nome="Maria Assinante", url="https://x.test/validar/abc"):
    return SeloAssinatura(
        pagina=pagina, x=x, y=y, nome=nome, cargo="Secretária de Administração",
        dt_assinatura=datetime(2026, 11, 27, 14, 32), codigo_validacao="codigo-teste-123",
        url_validacao=url,
    )


def _posicoes_do_texto(page, trecho: str) -> list[tuple[float, float]]:
    """Onde (espaço do usuário do PDF) o pypdf vê começar o texto que contém
    `trecho`."""
    achados: list[tuple[float, float]] = []

    def visitor(texto, cm, tm, _font, _size):
        if trecho in texto:
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            achados.append((x, y))

    page.extract_text(visitor_text=visitor)
    return achados


# Onde o rótulo "ASSINADO…" começa, relativo ao canto inferior esquerdo do selo
# (com QR): padding + QR + padding à direita; topo − padding − 6 para cima.
_ROTULO_DX = 6 + (SELO_ALTURA_PT - 12) + 6
_ROTULO_DY = SELO_ALTURA_PT - 6 - 6


# --------------------------------------------------------- 1. desenho puro


def test_selo_na_pagina_escolhida_sem_pagina_extra():
    saida = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(_pdf(3), [_selo(pagina=2)])))
    assert len(saida.pages) == 3
    assert "Maria Assinante" in saida.pages[1].extract_text()
    assert "Maria Assinante" not in saida.pages[0].extract_text()
    assert "Maria Assinante" not in saida.pages[2].extract_text()
    texto = saida.pages[1].extract_text()
    assert "Secretária de Administração" in texto
    assert "27/11/2026" in texto and "14:32" in texto
    assert "codigo-teste-123" in texto


def test_selo_cai_no_ponto_da_tela_pagina_retrato():
    saida = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(_pdf(1), [_selo(x=0.5, y=0.25)])))
    (x, y), = _posicoes_do_texto(saida.pages[0], "ASSINADO")
    # Canto sup. esq. do selo em (297.5, 210.5) medido do topo → inferior em
    # y = 842 − 210.5 − 62 = 569.5.
    assert x == pytest.approx(297.5 + _ROTULO_DX, abs=0.5)
    assert y == pytest.approx(569.5 + _ROTULO_DY, abs=0.5)


def test_selo_respeita_origem_deslocada_da_caixa():
    saida = PdfReader(io.BytesIO(
        aplicar_selos_pdf_bytes(_pdf(1, origem=(100.0, 50.0)), [_selo(x=0.0, y=0.0)])
    ))
    (x, y), = _posicoes_do_texto(saida.pages[0], "ASSINADO")
    assert x == pytest.approx(100 + _ROTULO_DX, abs=0.5)
    assert y == pytest.approx(50 + 842 - SELO_ALTURA_PT + _ROTULO_DY, abs=0.5)


@pytest.mark.parametrize("rot", [90, 180, 270])
def test_selo_em_pagina_girada_cai_onde_a_tela_mostrou(rot):
    """Na tela a página aparece girada (842 × 595 em 90°/270°). O ponto que a
    pessoa escolheu ali tem de corresponder ao ponto certo do espaço do PDF."""
    w, h = A4
    vw, vh = (h, w) if rot in (90, 270) else (w, h)
    selo = _selo(x=0.1, y=0.1)
    saida = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(_pdf(1, rotacao=rot), [selo])))
    (x, y), = _posicoes_do_texto(saida.pages[0], "ASSINADO")

    u0, v0 = canto_do_selo_em_pontos(selo.x, selo.y, vw, vh)
    a, b, c, d, e, f = transformacao_vista_para_pdf(0, 0, w, h, rot)
    u, v = u0 + _ROTULO_DX, v0 + _ROTULO_DY
    assert (x, y) == (pytest.approx(a * u + c * v + e, abs=0.5),
                      pytest.approx(b * u + d * v + f, abs=0.5))
    assert 0 <= x <= w and 0 <= y <= h


@pytest.mark.parametrize(
    "rot, canto_visto_sup_esq, canto_pdf",
    [
        # Canto superior esquerdo da página VISTA ↔ canto do espaço do PDF.
        (0, (0, 842), (0, 842)),
        (90, (0, 595), (0, 0)),      # girar 90° horário leva o inf. esq. ao topo esq.
        (180, (0, 842), (595, 0)),
        (270, (0, 595), (595, 842)),
    ],
)
def test_transformacao_dos_cantos(rot, canto_visto_sup_esq, canto_pdf):
    a, b, c, d, e, f = transformacao_vista_para_pdf(0, 0, *A4, rot)
    u, v = canto_visto_sup_esq
    assert (a * u + c * v + e, b * u + d * v + f) == pytest.approx(canto_pdf)


def test_selo_nunca_sai_da_pagina():
    # x = y = 1 (canto inferior direito na tela) → o quadrado encosta na borda.
    assert canto_do_selo_em_pontos(1.0, 1.0, *A4) == (A4[0] - SELO_LARGURA_PT, 0.0)
    assert canto_do_selo_em_pontos(0.0, 0.0, *A4) == (0.0, A4[1] - SELO_ALTURA_PT)


def test_varios_selos_e_nome_longo_cabe_no_quadrado():
    longo = "Fulano de Tal " * 10
    saida = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(
        _pdf(1), [_selo(x=0.0, y=0.0, nome="Primeira Pessoa"), _selo(x=0.6, y=0.8, nome=longo)]
    )))
    texto = saida.pages[0].extract_text()
    assert "Primeira Pessoa" in texto
    assert "…" in texto and longo.strip() not in texto


def test_selo_sem_url_nao_quebra():
    saida = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(_pdf(1), [_selo(url=None)])))
    assert "Maria Assinante" in saida.pages[0].extract_text()


def test_carimbo_primeiro_selo_por_cima_mesmas_paginas():
    original = _pdf(2)
    carimbado = carimbar_pdf_bytes(original, numero_processo="P1/2026", e_doc="x.pdf")
    final = PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(carimbado, [_selo(pagina=1)])))
    assert len(final.pages) == 2
    texto = final.pages[0].extract_text()
    assert "Processo P1/2026" in texto and "Maria Assinante" in texto
    # O selo vem DEPOIS do carimbo no content stream (= desenhado por cima).
    assert texto.index("Processo P1/2026") < texto.index("ASSINADO")


def test_posicao_fora_da_faixa_e_recusada_pelo_schema():
    for ruim in ({"pagina": 0, "x": 0.1, "y": 0.1}, {"pagina": 1, "x": 1.5, "y": 0.1},
                 {"pagina": 1, "x": 0.1, "y": -0.01}):
        with pytest.raises(ValidationError):
            AssinarRequest(senha="x", posicao=ruim)
    assert AssinarRequest(senha="x").posicao is None


def test_tamanho_do_selo_igual_na_tela_e_no_pdf():
    """A tela desenha o quadrado com o mesmo tamanho em pontos; se um mudar
    sozinho, a pessoa posiciona um quadrado e o PDF desenha outro.

    Mesma assimetria de `test_guarda_contrato_paginado.py`: o container local
    monta só `./backend`, então aqui pula; no CI (repositório inteiro) falha."""
    arquivo = RAIZ / "frontend" / "lib" / "selo-assinatura.ts"
    if not arquivo.exists():
        if os.getenv("CI"):
            pytest.fail(f"`{arquivo}` não encontrado com CI=1 — conserte o caminho.")
        pytest.skip("frontend/ fora do alcance (container monta só ./backend); roda no CI.")
    ts = arquivo.read_text(encoding="utf-8")
    largura = re.search(r"SELO_LARGURA_PT\s*=\s*([\d.]+)", ts)
    altura = re.search(r"SELO_ALTURA_PT\s*=\s*([\d.]+)", ts)
    assert largura and altura, "constantes não encontradas em frontend/lib/selo-assinatura.ts"
    assert float(largura.group(1)) == SELO_LARGURA_PT
    assert float(altura.group(1)) == SELO_ALTURA_PT


# ------------------------------------------------------------- 2. serviço


@pytest_asyncio.fixture
async def env_pdf(v2_env):  # noqa: F811
    """O anexo do v2_env vira um PDF de 2 páginas."""
    e_doc = f"si68-{uuid.uuid4().hex[:8]}.pdf"
    conteudo = _pdf(2)
    caminho = tenant_anexos_dir(v2_env["slug"]) / e_doc
    caminho.write_bytes(conteudo)
    yield {**v2_env, "e_doc_pdf": e_doc, "pdf": conteudo, "pdf_path": caminho}
    caminho.unlink(missing_ok=True)


async def _anexo_vira_pdf(admin_engine, env):
    async with _session(admin_engine) as s:
        await s.execute(
            text("UPDATE protocolos.anexo SET e_doc = :e WHERE id = :i"),
            {"e": env["e_doc_pdf"], "i": env["anexo"]},
        )
        await s.commit()


async def _pedir(admin_engine, env, *assinantes) -> list[int]:
    async with _session(admin_engine) as s:
        await solicitar_assinatura(
            s, env["processo"],
            SolicitarAssinaturaRequest(id_assinantes=list(assinantes), id_anexos=[env["anexo"]]),
            tenant_id=env["tenant_id"], usuario_id=env["usuario_moderno"],
            unidade_solicitante_id=env["unidade"],
        )
    async with _session(admin_engine) as s:
        rows = (await s.execute(text(
            "SELECT aa.id FROM protocolos.assinatura_anexo aa "
            "JOIN protocolos.usuario_assinatura ua ON ua.id = aa.id_usuario_assinatura "
            "WHERE aa.tenant_id = :t AND aa.id_anexo = :a AND aa.status = 'pendente' "
            "ORDER BY ua.ordem"
        ), {"t": env["tenant_id"], "a": env["anexo"]})).scalars().all()
    return list(rows)


async def _assinar(admin_engine, env, aa_id, usuario, posicao=None):
    async with _session(admin_engine) as s:
        return await assinar(
            s, aa_id, tenant_id=env["tenant_id"], usuario_id=usuario, senha=SENHA,
            tenant_slug=env["slug"], posicao=posicao,
        )


async def _servido(admin_engine, env) -> PdfReader:
    """O que o `carimbado.pdf` serve: carimbo do original + selos."""
    async with _session(admin_engine) as s:
        selos = (await selos_dos_anexos(
            s, [env["anexo"]], tenant_id=env["tenant_id"], tenant_slug=env["slug"]
        )).get(env["anexo"], [])
    carimbado = carimbar_pdf_bytes(env["pdf"], numero_processo="P", e_doc=env["e_doc_pdf"])
    return PdfReader(io.BytesIO(aplicar_selos_pdf_bytes(carimbado, selos)))


async def _validar(admin_engine, env, aa_id):
    async with _session(admin_engine) as s:
        return await validar_assinatura(
            s, aa_id, tenant_id=env["tenant_id"], tenant_slug=env["slug"],
            usuario=_uobj(env["usuario_moderno"]),
        )


async def test_assinar_com_posicao_grava_e_desenha_e_validar_continua_integro(admin_engine, env_pdf):
    await _anexo_vira_pdf(admin_engine, env_pdf)
    aa_id, = await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    pos = PosicaoSelo(pagina=2, x=0.55, y=0.8)
    aa = await _assinar(admin_engine, env_pdf, aa_id, env_pdf["usuario_moderno"], pos)

    assert (aa.selo_pagina, aa.selo_x, aa.selo_y) == (2, 0.55, 0.8)
    assert aa.evidencias["posicao_selo"] == {"pagina": 2, "x": 0.55, "y": 0.8}
    # O hash é do ORIGINAL — o selo não mexe no arquivo.
    assert aa.documento_hash == hashlib.sha256(env_pdf["pdf"]).hexdigest()
    assert env_pdf["pdf_path"].read_bytes() == env_pdf["pdf"]

    servido = await _servido(admin_engine, env_pdf)
    assert len(servido.pages) == 2
    assert "ASSINADO ELETRONICAMENTE" in servido.pages[1].extract_text()
    assert "ASSINADO ELETRONICAMENTE" not in servido.pages[0].extract_text()
    assert aa.codigo_validacao in servido.pages[1].extract_text()

    v = await _validar(admin_engine, env_pdf, aa_id)
    assert v.integro is True and v.legado is False


async def test_segundo_signatario_soma_selo_e_nao_invalida_o_primeiro(admin_engine, env_pdf):
    await _anexo_vira_pdf(admin_engine, env_pdf)
    primeiro, segundo = await _pedir(
        admin_engine, env_pdf, env_pdf["usuario_moderno"], env_pdf["usuario_outro"]
    )
    await _assinar(admin_engine, env_pdf, primeiro, env_pdf["usuario_moderno"],
                   PosicaoSelo(pagina=1, x=0.05, y=0.85))
    await _assinar(admin_engine, env_pdf, segundo, env_pdf["usuario_outro"],
                   PosicaoSelo(pagina=1, x=0.6, y=0.85))

    texto = (await _servido(admin_engine, env_pdf)).pages[0].extract_text()
    assert texto.count("ASSINADO ELETRONICAMENTE") == 2
    assert "V2 moderno" in texto and "V2 outro" in texto
    assert (await _validar(admin_engine, env_pdf, primeiro)).integro is True
    assert (await _validar(admin_engine, env_pdf, segundo)).integro is True


async def test_pagina_inexistente_recusa_antes_da_senha(admin_engine, env_pdf):
    await _anexo_vira_pdf(admin_engine, env_pdf)
    aa_id, = await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    async with _session(admin_engine) as s:
        with pytest.raises(AssinaturaError, match="2 página"):
            # Senha errada de propósito: se a posição não fosse checada antes,
            # o erro seria "Senha incorreta" e gastaria uma tentativa.
            await assinar(
                s, aa_id, tenant_id=env_pdf["tenant_id"], usuario_id=env_pdf["usuario_moderno"],
                senha="errada", tenant_slug=env_pdf["slug"],
                posicao=PosicaoSelo(pagina=3, x=0.1, y=0.1),
            )
    async with _session(admin_engine) as s:
        aa = (await s.execute(select(AssinaturaAnexo).where(AssinaturaAnexo.id == aa_id))).scalar_one()
        falhas = (await s.execute(text(
            "SELECT count(*) FROM aprimora_py.audit_log WHERE tenant_id = :t "
            "AND acao = 'assinatura.tentativa_falha'"
        ), {"t": env_pdf["tenant_id"]})).scalar_one()
    assert aa.status == "pendente" and aa.selo_pagina is None
    assert falhas == 0


async def test_posicao_em_anexo_que_nao_e_pdf_e_recusada(admin_engine, env_pdf):
    # Sem `_anexo_vira_pdf`: o anexo segue .txt.
    aa_id, = await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    with pytest.raises(AssinaturaError, match="PDF"):
        await _assinar(admin_engine, env_pdf, aa_id, env_pdf["usuario_moderno"],
                       PosicaoSelo(pagina=1, x=0.1, y=0.1))


async def test_sem_posicao_continua_como_antes_e_sem_selo(admin_engine, env_pdf):
    await _anexo_vira_pdf(admin_engine, env_pdf)
    aa_id, = await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    aa = await _assinar(admin_engine, env_pdf, aa_id, env_pdf["usuario_moderno"])
    assert aa.status == "assinada" and aa.selo_pagina is None
    assert "posicao_selo" not in aa.evidencias
    async with _session(admin_engine) as s:
        assert await selos_dos_anexos(
            s, [env_pdf["anexo"]], tenant_id=env_pdf["tenant_id"], tenant_slug=env_pdf["slug"]
        ) == {}
    assert (await _validar(admin_engine, env_pdf, aa_id)).integro is True


async def test_pendencia_diz_se_o_anexo_e_pdf(admin_engine, env_pdf):
    await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    async with _session(admin_engine) as s:
        txt, = await listar_minhas_pendentes(s, env_pdf["usuario_moderno"], tenant_id=env_pdf["tenant_id"])
    assert txt.anexo_pdf is False
    await _anexo_vira_pdf(admin_engine, env_pdf)
    async with _session(admin_engine) as s:
        pdf, = await listar_minhas_pendentes(s, env_pdf["usuario_moderno"], tenant_id=env_pdf["tenant_id"])
    assert pdf.anexo_pdf is True


async def test_selos_nao_cruzam_tenant(admin_engine, env_pdf, two_tenants):
    await _anexo_vira_pdf(admin_engine, env_pdf)
    aa_id, = await _pedir(admin_engine, env_pdf, env_pdf["usuario_moderno"])
    await _assinar(admin_engine, env_pdf, aa_id, env_pdf["usuario_moderno"],
                   PosicaoSelo(pagina=1, x=0.1, y=0.1))
    _, outro_tenant = two_tenants
    async with _session(admin_engine) as s:
        assert await selos_dos_anexos(
            s, [env_pdf["anexo"]], tenant_id=outro_tenant, tenant_slug="outro"
        ) == {}


# ---------------------------------------------------------------- 3. HTTP


async def test_http_carimbado_serve_o_selo_por_cima(admin_engine, ambiente):  # noqa: F811
    tenant = ambiente["tenant"]
    anexo = ambiente["anexo_pdf"]
    usuario = ambiente["com_credencial"]
    async with _sm(admin_engine)() as s:
        processo, unidade = (await s.execute(text(
            "SELECT p.id, p.id_unidade_proprietaria FROM protocolos.anexo_processo ap "
            "JOIN protocolos.processo p ON p.id = ap.id_processo "
            "WHERE ap.id_anexo = :a AND ap.tenant_id = :t"
        ), {"a": anexo, "t": tenant.id})).one()
        solic = (await s.execute(text(
            "INSERT INTO protocolos.solicitacao_assinatura (tenant_id, id_processo, id_solicitante, "
            "id_usuario, realizada, ativo, excluido, dt_inicio, dt_fim, cancelada) "
            "VALUES (:t,:p,:u,:u,true,true,false,NOW(),NOW(),false) RETURNING id"
        ), {"t": tenant.id, "p": processo, "u": usuario})).scalar_one()
        ua = (await s.execute(text(
            "INSERT INTO protocolos.usuario_assinatura (tenant_id, id_solicitacao_assinatura, "
            "id_assinante, id_unidade_trabalho, realizada, ordem, id_usuario, ativo, excluido, status) "
            "VALUES (:t,:s,:u,:un,true,1,:u,true,false,'realizada') RETURNING id"
        ), {"t": tenant.id, "s": solic, "u": usuario, "un": unidade})).scalar_one()
        await s.execute(text(
            "INSERT INTO protocolos.assinatura_anexo (tenant_id, id_usuario_assinatura, id_anexo, "
            "assinado, dt_assinatura, id_usuario, ativo, excluido, id_processo, status, "
            "nivel_assinatura, codigo_validacao, validacao_publica_revogada, "
            "selo_pagina, selo_x, selo_y) "
            "VALUES (:t,:ua,:a,true,NOW(),:u,true,false,:p,'assinada','simples',:c,false,1,0,0)"
        ), {"t": tenant.id, "ua": ua, "a": anexo, "u": usuario, "p": processo,
            "c": f"si68-{uuid.uuid4().hex}"})
        await s.commit()
    try:
        r = await _get(admin_engine, ambiente, usuario, f"/api/v2/anexos/{anexo}/carimbado.pdf")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        pdf = PdfReader(io.BytesIO(r.content))
        assert len(pdf.pages) == 1
        texto = pdf.pages[0].extract_text()
        assert "Usuario Storage" in texto and "ASSINADO ELETRONICAMENTE" in texto

        negado = await _get(admin_engine, ambiente, ambiente["sem_credencial"],
                            f"/api/v2/anexos/{anexo}/carimbado.pdf")
        assert negado.status_code == 404
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(text("DELETE FROM protocolos.assinatura_anexo WHERE id_usuario_assinatura = :u"), {"u": ua})
            await s.execute(text("DELETE FROM protocolos.usuario_assinatura WHERE id = :u"), {"u": ua})
            await s.execute(text("DELETE FROM protocolos.solicitacao_assinatura WHERE id = :s"), {"s": solic})
            await s.commit()
