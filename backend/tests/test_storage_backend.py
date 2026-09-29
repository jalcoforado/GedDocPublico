"""Abstração de storage de anexos (`services/storage.py`, backlog §3.1).

Três coisas que este arquivo trava:

1. **O padrão continua sendo o filesystem local, com o mesmo comportamento de
   antes** — inclusive o fallback de leitura para o path legado — e ligar esse
   padrão não exige `aioboto3` (dependência opcional, fora da imagem).
2. **O round-trip do `LocalFSStorage` é isolado por tenant**: o que um grava,
   o outro não enxerga.
3. **O storage não abre atalho em volta do sigilo.** O download ganhou um ramo
   `StreamingResponse` para storage não-local; os testes HTTP exercitam os dois
   ramos com usuário COMUM (não super-usuário, que passaria por cima de tudo) e
   provam que, sem credencial, a resposta é a mesma 404 de um anexo inexistente
   e o storage nem chega a ser consultado.
"""
from __future__ import annotations

import io
import subprocess
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings, tenant_anexos_dir
from app.services import storage as storage_mod
from app.services.storage import LocalFSStorage, S3Storage, obter_storage
from tests.conftest import as_user_dependency, provisionar_tenant_de_teste
from tests.test_guarda_anexo_sigiloso import _catalogos, _processo

APP = get_settings().app_name


@pytest.fixture
def storage_temporario(monkeypatch, tmp_path):
    """Raiz de storage (por tenant e legada) num diretório descartável."""
    s = get_settings()
    monkeypatch.setattr(s, "tenants_storage_root", str(tmp_path / "tenants"))
    monkeypatch.setattr(s, "uploads_dir", str(tmp_path / "legado"))
    (tmp_path / "legado").mkdir()
    return tmp_path


# ------------------------------------------------------------------ unidade


def test_padrao_e_filesystem_local():
    assert Settings.model_fields["storage_backend"].default == "local"
    assert get_settings().storage_backend == "local"
    assert isinstance(obter_storage(), LocalFSStorage)


def test_s3_so_quando_configurado(monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_backend", "s3")
    # Construir não importa aioboto3 nem abre conexão.
    assert isinstance(obter_storage(), S3Storage)


def test_valor_invalido_derruba_em_vez_de_cair_no_local():
    with pytest.raises(ValidationError):
        Settings(storage_backend="S3 ")


def test_importar_anexos_nao_exige_aioboto3():
    """`aioboto3` é extra opcional (`.[s3]`) e não está na imagem. Subprocesso
    para não depender do que outros testes já importaram."""
    codigo = (
        "import sys\n"
        "import app.services.storage, app.services.anexos, app.routers.anexos\n"
        "import app.services.pdf_carimbo, app.services.pdf_montagem\n"
        "assert 'aioboto3' not in sys.modules, 'aioboto3 importado sem S3'\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


async def test_localfs_round_trip_isolado_por_tenant(storage_temporario):
    st = LocalFSStorage()
    conteudo = b"x" * 200_000  # > 1 chunk de 64 KiB

    assert not await st.exists("tenant-a", "1.pdf")
    await st.put("tenant-a", "1.pdf", conteudo)

    assert await st.exists("tenant-a", "1.pdf")
    assert await st.get_bytes("tenant-a", "1.pdf") == conteudo
    pedacos = [c async for c in st.get_stream("tenant-a", "1.pdf")]
    assert len(pedacos) > 1
    assert b"".join(pedacos) == conteudo
    caminho = await st.get_local_path_if_possible("tenant-a", "1.pdf")
    assert caminho == tenant_anexos_dir("tenant-a") / "1.pdf"

    # Outro tenant não enxerga o arquivo — nem por exists, nem por leitura.
    assert not await st.exists("tenant-b", "1.pdf")
    assert await st.get_local_path_if_possible("tenant-b", "1.pdf") is None
    with pytest.raises(FileNotFoundError):
        await st.get_bytes("tenant-b", "1.pdf")
    with pytest.raises(FileNotFoundError):
        [c async for c in st.get_stream("tenant-b", "1.pdf")]

    await st.delete("tenant-b", "1.pdf")  # no-op, não apaga o do tenant-a
    assert await st.exists("tenant-a", "1.pdf")
    await st.delete("tenant-a", "1.pdf")
    assert not await st.exists("tenant-a", "1.pdf")
    with pytest.raises(FileNotFoundError):
        await st.get_bytes("tenant-a", "1.pdf")


async def test_localfs_mantem_fallback_legado(storage_temporario):
    """Anexo pré-Fase 14 mora em `uploads_dir`; a leitura continua achando."""
    (storage_temporario / "legado" / "7.txt").write_bytes(b"legado")
    st = LocalFSStorage()
    assert await st.exists("qualquer", "7.txt")
    assert await st.get_bytes("qualquer", "7.txt") == b"legado"
    # delete não mexe no diretório legado, que é compartilhado.
    await st.delete("qualquer", "7.txt")
    assert (storage_temporario / "legado" / "7.txt").exists()


# ------------------------------------------------------------------ HTTP


def _pdf_valido() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _anexo(s, tenant_id: int, slug: str, processo_id: int, unidade_id: int,
                 ext: str, conteudo: bytes) -> int:
    movimentacao = int((await s.execute(text(
        "INSERT INTO protocolos.movimentacao "
        "(tenant_id, id_processo, id_unidade_responsavel, id_acao, "
        " data_hora_movimentacao, ativo, excluido) "
        "SELECT :t, :p, :u, id, NOW(), true, false "
        "FROM protocolos.acao WHERE flag = 'ABERTURA' LIMIT 1 RETURNING id"
    ), {"t": tenant_id, "p": processo_id, "u": unidade_id})).scalar_one())
    anexo_id = int((await s.execute(text(
        "INSERT INTO protocolos.anexo (tenant_id, publico, ativo, excluido, descricao) "
        "VALUES (:t, false, true, false, 'doc storage') RETURNING id"
    ), {"t": tenant_id})).scalar_one())
    e_doc = f"{anexo_id}.{ext}"
    await s.execute(text("UPDATE protocolos.anexo SET e_doc = :e WHERE id = :i"),
                    {"e": e_doc, "i": anexo_id})
    await s.execute(text(
        "INSERT INTO protocolos.anexo_processo "
        "(tenant_id, id_processo, id_anexo, id_movimentacao, ordem, ativo, "
        " excluido, anexo_herdado) VALUES (:t, :p, :a, :m, 1, true, false, false)"
    ), {"t": tenant_id, "p": processo_id, "a": anexo_id, "m": movimentacao})
    await LocalFSStorage().put(slug, e_doc, conteudo)
    return anexo_id


async def _usuario_comum(s, tenant_id: int, credencial: str) -> int:
    """Não super-usuário, com leitura de `processo` e a credencial pedida."""
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
        VALUES (:t, 'Usuario Storage', :e, '', :cpf, true, false, :a, :cred)
        RETURNING id"""), {"t": tenant_id, "e": f"stor-{uuid.uuid4().hex[:8]}@storage.test",
                           "cpf": f"{uuid.uuid4().int % 10**11:011d}", "a": APP,
                           "cred": credencial})).scalar_one())
    gid = int((await s.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, :g, false) RETURNING id"""),
        {"t": tenant_id, "n": nivel_id, "s": sistema_id,
         "g": f"Grupo Storage {uuid.uuid4().hex[:6]}"})).scalar_one())
    await s.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :a)"""), {"t": tenant_id, "u": uid, "g": gid, "a": APP})
    tr = int((await s.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo='processo' AND excluido=false LIMIT 1"
    ))).scalar_one())
    await s.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, false, false, false, false)"""),
        {"t": tenant_id, "g": gid, "tr": tr})
    return uid


@pytest_asyncio.fixture
async def ambiente(admin_engine, storage_temporario):
    tenant = await provisionar_tenant_de_teste(admin_engine, "stor-")
    async with _sm(admin_engine)() as s:
        cat = await _catalogos(s, tenant.id)
        pid = await _processo(s, tenant.id, cat, "reservado")
        anexo_txt = await _anexo(s, tenant.id, tenant.slug, pid, cat["unidade"],
                                 "txt", b"conteudo reservado")
        anexo_pdf = await _anexo(s, tenant.id, tenant.slug, pid, cat["unidade"],
                                 "pdf", _pdf_valido())
        com_credencial = await _usuario_comum(s, tenant.id, "reservado")
        sem_credencial = await _usuario_comum(s, tenant.id, "interno")
        await s.commit()
    yield {
        "tenant": tenant, "anexo_txt": anexo_txt, "anexo_pdf": anexo_pdf,
        "com_credencial": com_credencial, "sem_credencial": sem_credencial,
    }
    # Tenant e linhas dele saem pelo `_limpa_tenants_do_modulo`; a categoria é
    # catálogo global e não.
    async with _sm(admin_engine)() as s:
        await s.execute(text("DELETE FROM protocolos.categoria WHERE id = :i"),
                        {"i": cat["categoria"]})
        await s.commit()


async def _get(admin_engine, amb, usuario_id: int, caminho: str):
    tenant = amb["tenant"]
    as_user_dependency(admin_engine, usuario_id, tenant.id, tenant.slug)()
    from app.main import app
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


class _StorageRemotoFake(LocalFSStorage):
    """Simula storage não-local: sem path, só streaming. Registra as chamadas
    para provar que, sem autorização, o storage nem é consultado."""

    def __init__(self):
        self.chamadas: list[str] = []

    async def exists(self, tenant_slug, e_doc):
        self.chamadas.append(f"exists:{e_doc}")
        return await super().exists(tenant_slug, e_doc)

    def get_stream(self, tenant_slug, e_doc):
        self.chamadas.append(f"get_stream:{e_doc}")
        return super().get_stream(tenant_slug, e_doc)

    async def get_local_path_if_possible(self, tenant_slug, e_doc):
        return None


@pytest.fixture
def storage_remoto(monkeypatch):
    fake = _StorageRemotoFake()
    import app.routers.anexos as r_anexos
    import app.services.anexos as s_anexos
    monkeypatch.setattr(s_anexos, "obter_storage", lambda: fake)
    monkeypatch.setattr(r_anexos, "obter_storage", lambda: fake)
    monkeypatch.setattr(storage_mod, "obter_storage", lambda: fake)
    return fake


async def test_http_download_local_continua_funcionando(admin_engine, ambiente):
    r = await _get(admin_engine, ambiente, ambiente["com_credencial"],
                   f"/api/v2/anexos/{ambiente['anexo_txt']}/download")
    assert r.status_code == 200, r.text
    assert r.content == b"conteudo reservado"
    assert "attachment" in r.headers["content-disposition"]


async def test_http_sigilo_nega_igual_a_inexistente(admin_engine, ambiente):
    """Sem credencial: 404 com a MESMA resposta de um id que não existe."""
    negado = await _get(admin_engine, ambiente, ambiente["sem_credencial"],
                        f"/api/v2/anexos/{ambiente['anexo_txt']}/download")
    inexistente = await _get(admin_engine, ambiente, ambiente["sem_credencial"],
                             "/api/v2/anexos/999999999/download")
    assert negado.status_code == 404
    assert (negado.status_code, negado.json()) == (inexistente.status_code, inexistente.json())


async def test_http_download_por_streaming_quando_storage_nao_e_local(
    admin_engine, ambiente, storage_remoto
):
    r = await _get(admin_engine, ambiente, ambiente["com_credencial"],
                   f"/api/v2/anexos/{ambiente['anexo_txt']}/download")
    assert r.status_code == 200, r.text
    assert r.content == b"conteudo reservado"
    assert f"get_stream:{ambiente['anexo_txt']}.txt" in storage_remoto.chamadas


async def test_http_streaming_nao_pula_o_guard_de_sigilo(
    admin_engine, ambiente, storage_remoto
):
    """O ramo novo não abre atalho: sem credencial é 404, e o storage não é
    sequer consultado — a autorização vem antes de resolver o arquivo."""
    r = await _get(admin_engine, ambiente, ambiente["sem_credencial"],
                   f"/api/v2/anexos/{ambiente['anexo_txt']}/download")
    assert r.status_code == 404
    assert r.json()["detail"] == "Anexo não encontrado"
    assert storage_remoto.chamadas == []


async def test_http_carimbado_le_pelo_storage(admin_engine, ambiente, storage_remoto):
    """`carimbar_anexo_com_cache` virou async e lê o original pela abstração —
    funciona mesmo sem path local."""
    r = await _get(admin_engine, ambiente, ambiente["com_credencial"],
                   f"/api/v2/anexos/{ambiente['anexo_pdf']}/carimbado.pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert len(PdfReader(io.BytesIO(r.content)).pages) == 1

    negado = await _get(admin_engine, ambiente, ambiente["sem_credencial"],
                        f"/api/v2/anexos/{ambiente['anexo_pdf']}/carimbado.pdf")
    assert negado.status_code == 404
