"""SI-67 — trocar o modelo de um rascunho já aberto no editor.

`POST /minutas/{id}/aplicar-modelo` refaz o corpo a partir do modelo, com os
campos automáticos do processo (`services/placeholders.py`), e SUBSTITUI o
texto atual. Garantias testadas com o operador COMUM (não super-usuário, que
passa por cima de sigilo e permissão):

- o corpo vira o modelo resolvido, a versão sobe e o texto anterior continua
  no histórico — trocar de modelo não apaga trabalho;
- "documento em branco" (`id_template` nulo) limpa o corpo;
- o destinatário digitado na tela alimenta `{{destinatario.nome}}`;
- versão desatualizada, minuta finalizada e modelo de outra prefeitura são
  recusados sem mexer na minuta.

O 404 para minuta de processo sigiloso, de outra prefeitura e de rascunho
alheio está em `test_guarda_minuta_sigilosa.py` (ROTAS_DA_MINUTA).
"""
from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.main import app
from app.models import Minuta, MinutaHistorico, TemplateDocumento
from tests.test_guarda_minuta_sigilosa import SEGREDO, _cliente, _limpar, _prefeitura, _sm

MODELO = (
    "<p>Processo {{processo.numero}}</p>"
    "<p>Ao(À) {{destinatario.nome}}</p>"
    "<p>Prezado(a), segue para análise.</p>"
)


async def _modelo(admin_engine, tenant_id: int, nome: str, corpo: str = MODELO) -> int:
    async with _sm(admin_engine)() as s:
        t = TemplateDocumento(
            tenant_id=tenant_id, nome=nome, corpo_html=corpo, ativo=True, padrao=False,
            excluido=False, criado_em=datetime.now(),
        )
        s.add(t)
        await s.commit()
        return t.id


@pytest_asyncio.fixture
async def cen(admin_engine):
    a = await _prefeitura(admin_engine, "minmod-a-")
    b = await _prefeitura(admin_engine, "minmod-b-")
    a["modelo"] = await _modelo(admin_engine, a["tenant"].id, "Ofício")
    b["modelo"] = await _modelo(admin_engine, b["tenant"].id, "Ofício de outra prefeitura")
    async with _sm(admin_engine)() as s:
        a["numero"] = (await s.execute(text(
            "SELECT numero_processo FROM protocolos.processo WHERE id = :p"
        ), {"p": a["p_ostensivo"]})).scalar_one()
    yield {"a": a, "b": b}
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    for pref in (a, b):
        async with _sm(admin_engine)() as s:
            await s.execute(text("DELETE FROM protocolos.template_documento WHERE tenant_id=:t"),
                            {"t": pref["tenant"].id})
            await s.commit()
        await _limpar(admin_engine, pref["tenant"].id)


async def _minuta(admin_engine, minuta_id: int) -> Minuta:
    async with _sm(admin_engine)() as s:
        return (await s.execute(select(Minuta).where(Minuta.id == minuta_id))).scalar_one()


@pytest.mark.asyncio
async def test_trocar_modelo_substitui_o_texto_e_guarda_o_anterior(admin_engine, cen):
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/minutas/{a['m_ostensivo']}/aplicar-modelo",
            json={"id_template": a["modelo"], "destinatario": "Secretaria de Obras", "versao": 1},
        )
    assert r.status_code == 200, r.text
    corpo = r.json()["corpo_html"]
    assert a["numero"] in corpo
    assert "Secretaria de Obras" in corpo
    assert "{{" not in corpo
    assert SEGREDO not in corpo  # o texto anterior foi substituído
    assert r.json()["versao"] == 2
    assert r.json()["id_template_origem"] == a["modelo"]
    assert r.json()["destinatario"] == "Secretaria de Obras"

    async with _sm(admin_engine)() as s:
        versoes = (await s.execute(
            select(MinutaHistorico.versao).where(MinutaHistorico.id_minuta == a["m_ostensivo"])
        )).scalars().all()
    assert 2 in versoes


@pytest.mark.asyncio
async def test_documento_em_branco_limpa_o_texto(admin_engine, cen):
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/minutas/{a['m_ostensivo']}/aplicar-modelo",
            json={"id_template": None, "versao": 1},
        )
    assert r.status_code == 200, r.text
    assert r.json()["corpo_html"] == ""
    assert r.json()["id_template_origem"] is None


@pytest.mark.asyncio
async def test_versao_desatualizada_nao_troca(admin_engine, cen):
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/minutas/{a['m_ostensivo']}/aplicar-modelo",
            json={"id_template": a["modelo"], "versao": 7},
        )
    assert r.status_code == 409, r.text
    m = await _minuta(admin_engine, a["m_ostensivo"])
    assert (m.versao, m.corpo_html) == (1, f"<p>{SEGREDO}</p>")


@pytest.mark.asyncio
async def test_modelo_de_outra_prefeitura_da_404(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    async with _cliente(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/minutas/{a['m_ostensivo']}/aplicar-modelo",
            json={"id_template": b["modelo"], "versao": 1},
        )
    assert r.status_code == 404, r.text
    m = await _minuta(admin_engine, a["m_ostensivo"])
    assert (m.versao, m.corpo_html) == (1, f"<p>{SEGREDO}</p>")


@pytest.mark.asyncio
async def test_minuta_finalizada_nao_troca_de_modelo(admin_engine, cen):
    a = cen["a"]
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.minuta SET status='cancelada' WHERE id=:m"),
                        {"m": a["m_ostensivo"]})
        await s.commit()
    async with _cliente(admin_engine, a) as cli:
        r = await cli.post(
            f"/api/v2/minutas/{a['m_ostensivo']}/aplicar-modelo",
            json={"id_template": a["modelo"]},
        )
    assert r.status_code == 409, r.text
    m = await _minuta(admin_engine, a["m_ostensivo"])
    assert m.corpo_html == f"<p>{SEGREDO}</p>"
