"""Tarefas em segundo plano: quem dispara e quem baixa (SI-72).

Até o SI-72, `GET /jobs/{id}` e `GET /jobs/{id}/resultado` só conferiam a
prefeitura, o módulo e a permissão `processo`: qualquer servidor baixava o
resultado de tarefa alheia trocando o id — inclusive o PDF completo de processo
sigiloso. E disparar o PDF completo ou o carimbo de um processo sigiloso não
olhava sigilo nenhum. Também cobre o .zip de PDFs carimbados, que substituiu o
relatório .txt do pré-carimbo.

Usuário COMUM (o super-usuário passaria por cima — CLAUDE.md §Testes).
"""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.config import get_settings, tenant_jobs_dir
from app.main import app
from app.models import Job
from app.services.processos import _load_anexos
from app.tasks.carimbar_anexos import gerar_zip_carimbados
from tests.test_anexo_versao import (
    _como,
    _limpar,
    _pdf,
    _prefeitura,
    _sm,
    _usuario_comum,
)


@pytest_asyncio.fixture
async def cen(admin_engine):
    a = await _prefeitura(admin_engine, "jobs-a-")
    async with _sm(admin_engine)() as s:
        a["colega"] = await _usuario_comum(s, a["tenant"].id, a["unidade"])
        await s.commit()
    yield a
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        await s.execute(text("DELETE FROM aprimora_py.job WHERE tenant_id=:t"),
                        {"t": a["tenant"].id})
        await s.commit()
    await _limpar(admin_engine, a["tenant"].id)


def _como_usuario(admin_engine, a: dict, uid: int):
    return _como(admin_engine, {**a, "servidor": uid})


async def _job_concluido(admin_engine, a: dict, dono: int, processo_id: int) -> int:
    """Job de PDF completo já concluído, com arquivo de resultado no disco."""
    async with _sm(admin_engine)() as s:
        job = Job(
            tenant_id=a["tenant"].id, tipo="processo_completo", status="concluido",
            parametros={"id_processo": processo_id}, id_usuario=dono,
            criado_em=datetime.utcnow(), concluido_em=datetime.utcnow(),
        )
        s.add(job)
        await s.flush()
        pasta = tenant_jobs_dir(a["tenant"].slug) / str(job.id)
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"processo-{processo_id}.pdf"
        arquivo.write_bytes(_pdf(1))
        job.resultado_path = str(arquivo.relative_to(get_settings().tenants_storage_root))
        await s.commit()
        return job.id


@pytest.mark.asyncio
async def test_so_quem_disparou_ve_e_baixa_o_resultado(admin_engine, cen):
    a = cen
    jid = await _job_concluido(admin_engine, a, a["servidor"], a["principal"])
    async with _como_usuario(admin_engine, a, a["servidor"]) as cli:
        assert (await cli.get(f"/api/v2/jobs/{jid}")).status_code == 200
        r = await cli.get(f"/api/v2/jobs/{jid}/resultado")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
    # Colega da mesma prefeitura, com a mesma permissão: não vê nem baixa.
    async with _como_usuario(admin_engine, a, a["colega"]) as cli:
        assert (await cli.get(f"/api/v2/jobs/{jid}")).status_code == 404
        assert (await cli.get(f"/api/v2/jobs/{jid}/resultado")).status_code == 404


@pytest.mark.asyncio
async def test_resultado_de_processo_sigiloso_reconfere_a_credencial(admin_engine, cen):
    """O dono da tarefa perdeu acesso (aqui: o job aponta processo reservado e a
    credencial é `interno`) — o download reconfere e dá 404."""
    a = cen
    jid = await _job_concluido(admin_engine, a, a["servidor"], a["reservado"])
    async with _como_usuario(admin_engine, a, a["servidor"]) as cli:
        assert (await cli.get(f"/api/v2/jobs/{jid}/resultado")).status_code == 404


@pytest.mark.asyncio
async def test_disparar_tarefa_de_processo_sigiloso_da_404(admin_engine, cen, monkeypatch):
    import app.tasks.carimbar_anexos as t_carimbo
    import app.tasks.processo_completo as t_completo

    enfileiradas: list = []

    class _Fila:
        @staticmethod
        def delay(*args):
            enfileiradas.append(args)

    monkeypatch.setattr(t_completo, "run", _Fila)
    monkeypatch.setattr(t_carimbo, "run", _Fila)
    a = cen
    async with _como_usuario(admin_engine, a, a["servidor"]) as cli:
        for rota in ("processo-completo", "carimbar-anexos"):
            r = await cli.post(f"/api/v2/jobs/{rota}", json={"id_processo": a["reservado"]})
            assert r.status_code == 404, (rota, r.text)
            r = await cli.post(f"/api/v2/jobs/{rota}", json={"id_processo": 999999999})
            assert r.status_code == 404, (rota, r.text)
        # No processo que ele alcança, dispara normalmente.
        r = await cli.post("/api/v2/jobs/carimbar-anexos", json={"id_processo": a["principal"]})
        assert r.status_code == 202, r.text
    assert len(enfileiradas) == 1
    async with _sm(admin_engine)() as s:
        n = (await s.execute(text(
            "SELECT count(*) FROM aprimora_py.job WHERE tenant_id=:t"
        ), {"t": a["tenant"].id})).scalar_one()
        assert n == 1


@pytest.mark.asyncio
async def test_zip_tem_um_pdf_carimbado_por_documento_na_ordem_do_processo(
    admin_engine, cen, tmp_path
):
    a = cen
    async with _como_usuario(admin_engine, a, a["servidor"]) as cli:
        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos",
            data={"descricao": "Requerimento", "publico": "true"},
            files={"file": ("req.pdf", _pdf(2), "application/pdf")},
        )
        v1 = r.json()["id"]
        await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos",
            data={"descricao": "Planilha", "publico": "true"},
            files={"file": ("p.txt", b"nao e pdf", "text/plain")},
        )
        r = await cli.post(
            f"/api/v2/processos/{a['principal']}/anexos/{v1}/versoes",
            files={"file": ("req2.pdf", _pdf(3), "application/pdf")},
        )
        assert r.status_code == 201, r.text

    async with _sm(admin_engine)() as s:
        anexos = await _load_anexos(s, a["principal"], a["tenant"].id)
    destino = Path(tmp_path) / "saida.zip"
    res = gerar_zip_carimbados(
        anexos, numero_processo="P-1/2026", tenant_slug=a["tenant"].slug,
        destino=destino, processo_id=a["principal"],
    )
    assert res["no_zip"] == 2 and not res["falhas"]

    from pypdf import PdfReader

    with zipfile.ZipFile(destino) as zf:
        nomes = zf.namelist()
        assert nomes == [
            "Doc 01 - Requerimento - substituída.pdf",
            "Doc 03 - Requerimento (versão 2).pdf",
            "relatorio.txt",
        ]
        antigo = PdfReader(io.BytesIO(zf.read(nomes[0])))
        assert len(antigo.pages) == 2
        assert "SUBSTITUÍDO PELA VERSÃO 2" in (antigo.pages[0].extract_text() or "")
        novo = PdfReader(io.BytesIO(zf.read(nomes[1])))
        assert len(novo.pages) == 3
        assert "P-1/2026" in (novo.pages[0].extract_text() or "")
        relatorio = zf.read("relatorio.txt").decode()
        assert "PDFs no arquivo: 2" in relatorio
        assert "não são PDF (fora do .zip): 1" in relatorio
