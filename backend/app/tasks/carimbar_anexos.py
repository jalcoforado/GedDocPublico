"""Task: carimba os PDFs de um processo e entrega um .zip com eles.

Fase 14: cache de carimbados e arquivos lidos vão por tenant
(tenant_carimbados_dir + resolve_anexo_path).

SI-72: o resultado era só um relatório .txt (a pessoa clicava e recebia um
texto técnico). Agora é um .zip com um PDF carimbado por documento, na ordem
do processo, e o relatório dentro. O download passa por `routers/jobs.py::
_job_autorizado` (só quem disparou, com sigilo reconferido).
"""
from __future__ import annotations

import asyncio
import re
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from ..config import (
    get_settings,
    resolve_anexo_path,
    tenant_carimbados_dir,
    tenant_jobs_dir,
)
from ..models import Job, Processo
from ..schemas.processo import AnexoNoProcesso
from ..services.pdf_carimbo import carimbar_pdf_bytes, nome_cache
from ..services.processos import _load_anexos
from ._task_db import task_session_scope
from .celery_app import celery_app

settings = get_settings()


@celery_app.task(name="app.tasks.carimbar_anexos.run", bind=True)
def run(
    self, job_id: int, processo_id: int, tenant_id: int, tenant_slug: str
) -> str | None:
    return asyncio.run(
        _run_async(self, job_id, processo_id, tenant_id, tenant_slug)
    )


async def _run_async(
    task, job_id: int, processo_id: int, tenant_id: int, tenant_slug: str
) -> str | None:
    async with task_session_scope(tenant_id=tenant_id) as (_engine, Session):
        async with Session() as db:
            job = await db.get(Job, job_id)
            if job is None:
                return None
            job.status = "em_andamento"
            job.iniciado_em = datetime.utcnow()
            job.celery_task_id = task.request.id
            await db.commit()

        try:
            async with Session() as db:
                proc = (
                    await db.execute(
                        select(Processo).where(
                            Processo.id == processo_id,
                            Processo.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()
                if proc is None:
                    raise RuntimeError(f"Processo {processo_id} não encontrado")
                numero = proc.numero_processo

                # SI-72 — mesma lista do processo e do PDF completo: número do
                # documento, versões, e sem os desentranhados (a consulta
                # antiga os incluía).
                anexos = await _load_anexos(db, processo_id, tenant_id)

            out_dir = tenant_jobs_dir(tenant_slug) / str(job_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / nome_do_zip(numero)
            r = gerar_zip_carimbados(
                anexos, numero_processo=numero, tenant_slug=tenant_slug, destino=out_path,
                processo_id=processo_id,
            )
            rel = str(out_path.relative_to(settings.tenants_storage_root))

            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "concluido"
                    job.resultado_path = rel
                    job.descricao = (
                        f"PDFs carimbados #{processo_id}: {r['no_zip']} no .zip, "
                        f"{len(r['falhas'])} falha(s)"
                    )
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            return rel
        except Exception as e:
            async with Session() as db:
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = "falhou"
                    job.erro = f"{e}\n\n{traceback.format_exc()}"
                    job.concluido_em = datetime.utcnow()
                    await db.commit()
            raise


_PROIBIDOS_EM_NOME = re.compile(r'[\/:*?"<>|\r\n\t]+')


def nome_do_zip(numero_processo: str | None) -> str:
    base = _PROIBIDOS_EM_NOME.sub("-", numero_processo or "processo").strip("- ")
    return f"pdfs-carimbados-{base}.zip"


def _nome_no_zip(a: AnexoNoProcesso) -> str:
    """'Doc 04 - CNPJ (versão 2).pdf' — o número do documento na frente deixa
    a pasta na ordem do processo e o nome único."""
    descricao = _PROIBIDOS_EM_NOME.sub(" ", a.descricao or f"Anexo {a.id}").strip()[:80]
    if descricao.lower().endswith(".pdf"):
        descricao = descricao[:-4]
    versao = f" (versão {a.versao})" if (a.versao or 1) > 1 else ""
    substituida = " - substituída" if a.id_anexo_substituto else ""
    return f"Doc {a.documento_numero or 0:02d} - {descricao}{versao}{substituida}.pdf"


def gerar_zip_carimbados(
    anexos: list[AnexoNoProcesso],
    *,
    numero_processo: str,
    tenant_slug: str,
    destino: Path,
    processo_id: int,
) -> dict:
    """Carimba (ou reaproveita do cache) cada PDF do processo e grava um .zip
    com eles e um `relatorio.txt`. Antes do SI-72 o resultado era só o
    relatório: a pessoa clicava e recebia um .txt técnico.

    A versão substituída entra, com a faixa "substituído pela versão N" — é
    o mesmo conjunto do PDF completo, só que um arquivo por documento.
    """
    por_id = {a.id: a for a in anexos}
    carimbados_dir = tenant_carimbados_dir(tenant_slug)
    carimbados = cacheados = sem_arquivo = nao_pdf = 0
    falhas: list[str] = []
    no_zip = 0

    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for a in anexos:
            if not a.e_doc or not a.e_doc.lower().endswith(".pdf"):
                nao_pdf += 1
                continue
            substituta = None
            if a.id_anexo_substituto is not None:
                sucessora = por_id.get(a.id_anexo_substituto)
                substituta = sucessora.versao if sucessora else (a.versao or 1) + 1
            cache = carimbados_dir / nome_cache(a.id, substituta)
            if cache.exists():
                cacheados += 1
            else:
                src = resolve_anexo_path(tenant_slug, a.e_doc)
                if src is None:
                    sem_arquivo += 1
                    continue
                try:
                    cache.write_bytes(
                        carimbar_pdf_bytes(
                            src.read_bytes(),
                            numero_processo=numero_processo,
                            e_doc=a.e_doc,
                            versao=a.versao or 1,
                            substituido_pela_versao=substituta,
                        )
                    )
                    carimbados += 1
                except Exception as e:  # noqa: BLE001 — um PDF ruim não derruba o lote
                    falhas.append(f"Doc {a.documento_numero} (#{a.id}): {type(e).__name__}: {e}")
                    continue
            zf.write(cache, arcname=_nome_no_zip(a))
            no_zip += 1

        relatorio = (
            f"Processo: {numero_processo} (#{processo_id})\n"
            f"PDFs no arquivo: {no_zip}\n"
            f"Carimbados agora: {carimbados}\n"
            f"Já estavam prontos: {cacheados}\n"
            f"Documentos que não são PDF (fora do .zip): {nao_pdf}\n"
            f"Sem arquivo no armazenamento: {sem_arquivo}\n"
            f"Falhas: {len(falhas)}\n"
        )
        if falhas:
            relatorio += "\nDetalhes das falhas:\n" + "\n".join(f"  - {f}" for f in falhas)
        zf.writestr("relatorio.txt", relatorio)

    return {"no_zip": no_zip, "falhas": falhas, "relatorio": relatorio}
