"""Listagem de débitos paginada no servidor.

A tela de Solicitações baixava TODOS os débitos do tenant e paginava, buscava e
contava por etapa no navegador; as quatro filas por etapa faziam o mesmo para
mostrar uma fração. O que se trava aqui:

- `/pagina` devolve só a página pedida e o total REAL do recorte;
- a busca por texto acha por descrição, fornecedor, NF e NE, e `%` digitado
  pelo usuário é texto, não curinga;
- `/contagem-por-situacao` bate com o que a página lista;
- `GET /debitos` aceita várias situações de uma vez, que é o que as filas usam;
- "pagina" e "contagem-por-situacao" não são engolidas por `/{debito_id}`.

Pela porta HTTP, com usuário comum (auditor: só lê).
"""
from __future__ import annotations

import uuid

import pytest

from app.services import pagamentos_debitos as svc
from tests.test_pagamentos_f3_elegibilidade import (
    _base, _novo_usuario, _payload_debito, _provisionar, _sm,
)
from tests.test_pagamentos_f4_retencao import _cleanup, _get, _usuario_com

BASE = "/api/v2/pagamentos/debitos"


async def _cenario(engine):
    """5 débitos: 3 em rascunho, 2 aguardando o gestor. Um rascunho tem
    descrição e NF próprias, para a busca."""
    t = await _provisionar(engine)
    forn, nat, fonte, conta, unidade = await _base(engine, t.id)
    autor = await _novo_usuario(engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
    ids: list[int] = []
    for i in range(5):
        payload = _payload_debito(forn, nat, fonte, conta, unidade)
        if i == 0:
            payload = payload.model_copy(update={
                "descricao": "Reforma do telhado 100% concluída", "numero_nf": "NF-ZETA-9"})
        async with _sm(engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=autor, payload=payload)
        ids.append(d.id)
    for debito_id in ids[3:]:
        async with _sm(engine)() as s:
            d = await svc.obter_debito(s, tenant_id=t.id, debito_id=debito_id)
            await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=debito_id,
                                         usuario_id=autor, lock_version=d.lock_version)
    leitor = await _usuario_com(engine, t.id, ["pagamento_auditar"])
    return t, ids, leitor, forn


@pytest.mark.asyncio
async def test_http_pagina_corta_no_servidor_e_informa_o_total_real(admin_engine):
    t, ids, leitor, _forn = await _cenario(admin_engine)
    try:
        resp = await _get(admin_engine, t.id, t.slug, leitor, f"{BASE}/pagina?page_size=2")
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert (corpo["total"], corpo["page"], corpo["page_size"]) == (5, 1, 2)
        # Mais novos primeiro.
        assert [d["id"] for d in corpo["items"]] == sorted(ids, reverse=True)[:2]

        resp = await _get(admin_engine, t.id, t.slug, leitor, f"{BASE}/pagina?page_size=2&page=3")
        assert [d["id"] for d in resp.json()["items"]] == sorted(ids, reverse=True)[4:]

        # Página além do fim: lista vazia, total intacto — não é erro.
        resp = await _get(admin_engine, t.id, t.slug, leitor, f"{BASE}/pagina?page_size=2&page=9")
        assert resp.status_code == 200 and resp.json()["items"] == []
        assert resp.json()["total"] == 5
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_pagina_filtra_por_varias_situacoes_e_a_contagem_bate(admin_engine):
    t, ids, leitor, _forn = await _cenario(admin_engine)
    try:
        resp = await _get(admin_engine, t.id, t.slug, leitor,
                          f"{BASE}/pagina?situacao_tramitacao=AGUARDANDO_GESTOR")
        assert sorted(d["id"] for d in resp.json()["items"]) == sorted(ids[3:])

        resp = await _get(
            admin_engine, t.id, t.slug, leitor,
            f"{BASE}/pagina?situacao_tramitacao=RASCUNHO&situacao_tramitacao=AGUARDANDO_GESTOR")
        assert resp.json()["total"] == 5

        resp = await _get(admin_engine, t.id, t.slug, leitor, f"{BASE}/contagem-por-situacao")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"RASCUNHO": 3, "AGUARDANDO_GESTOR": 2}

        # A listagem inteira (a das filas por etapa) aceita o mesmo filtro múltiplo.
        resp = await _get(admin_engine, t.id, t.slug, leitor,
                          f"{BASE}?situacao_tramitacao=AGUARDANDO_GESTOR")
        assert resp.status_code == 200, resp.text
        assert sorted(d["id"] for d in resp.json()) == sorted(ids[3:])
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_busca_por_texto_acha_por_descricao_nf_e_fornecedor(admin_engine):
    t, ids, leitor, forn = await _cenario(admin_engine)
    try:
        async def achados(q: str) -> list[int]:
            resp = await _get(admin_engine, t.id, t.slug, leitor, f"{BASE}/pagina?q={q}")
            assert resp.status_code == 200, resp.text
            return sorted(d["id"] for d in resp.json()["items"])

        assert await achados("telhado") == [ids[0]]
        assert await achados("nf-zeta") == [ids[0]]           # sem diferenciar maiúsculas
        assert await achados(forn.nome.split()[0]) == sorted(ids)  # pelo nome do fornecedor
        assert await achados("inexistente-xyz") == []
        # `%` digitado é texto: só acha quem tem "100%" de verdade.
        assert await achados("100%25") == [ids[0]]
        assert await achados("%25") == [ids[0]]

        # A contagem acompanha a busca.
        resp = await _get(admin_engine, t.id, t.slug, leitor,
                          f"{BASE}/contagem-por-situacao?q=telhado")
        assert resp.json() == {"RASCUNHO": 1}
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_sem_permissao_de_leitura_nao_pagina(admin_engine):
    t, _ids, _leitor, _forn = await _cenario(admin_engine)
    try:
        # Tem uma transação, mas de outro módulo.
        estranho = await _usuario_com(admin_engine, t.id, ["usuario"])
        for caminho in (f"{BASE}/pagina", f"{BASE}/contagem-por-situacao"):
            resp = await _get(admin_engine, t.id, t.slug, estranho, caminho)
            assert resp.status_code == 403, f"{caminho}: {resp.text}"
    finally:
        await _cleanup(admin_engine, t.id)
