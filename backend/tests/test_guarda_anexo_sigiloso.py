"""Download de anexo tem de respeitar o sigilo do processo dono.

O defeito, encontrado em 2026-08-05: `GET /anexos/{id}/download` e
`GET /anexos/{id}/carimbado.pdf` exigiam só `get_current_user` e chamavam o
carregador cru `get_anexo_path`, que filtra tenant/`excluido`/`ativo` e mais
nada. Qualquer autenticado do tenant baixava o anexo de um processo
**ultrassecreto** iterando `anexo_id`. A listagem já filtrava por
`nivel_sigilo`, então o processo não aparecia para esse usuário — o documento
vinha assim mesmo.

O guard `assert_acesso_processo` já existia e já era usado em quatro lugares,
inclusive no download **pela via de assinatura**. Só a via direta ficou de
fora — e nenhum teste cruzava anexo com sigilo.

Por que este arquivo existe, e não mais um caso em `test_sigilo_enforcement.py`:
aquele arquivo testa serviço, e o defeito morava na costura router↔service.
Teste de serviço não teria pego, como não pegou por todo esse tempo.

O caso que sustenta os outros é `test_o_carregador_cru_continua_devolvendo`:
ele prova que a diferença está na checagem nova e não em qualquer outro
filtro. Sem ele, um erro no setup (anexo do tenant errado, vínculo
inexistente) deixaria o teste de negação verde sem provar nada.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import tenant_anexos_dir
from app.services.anexos import (
    AnexoError,
    get_anexo_path,
    get_anexo_path_autorizado,
)
from app.services.sigilo import SigiloAcessoError

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


def _sessao(admin_engine):
    return async_sessionmaker(
        admin_engine, expire_on_commit=False, class_=AsyncSession
    )()


async def _catalogos(s: AsyncSession, tenant_id: int) -> dict[str, int]:
    sfx = uuid.uuid4().hex[:8]
    categoria = int((await s.execute(text(
        "INSERT INTO protocolos.categoria (categoria, tipo, ativo, excluido) "
        "VALUES (:n, 'PF', true, false) RETURNING id"
    ), {"n": f"AnxSig {sfx}"})).scalar_one())
    tipo_manif = int((await s.execute(text(
        "INSERT INTO protocolos.tipo_manifestante "
        "(tenant_id, tipo_manifestante, id_categoria, ativo, excluido) "
        "VALUES (:t, :n, :c, true, false) RETURNING id"
    ), {"t": tenant_id, "n": f"AnxSig {sfx}", "c": categoria})).scalar_one())
    manifestante = int((await s.execute(text(
        "INSERT INTO protocolos.manifestante "
        "(tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
        "VALUES (:t, :tm, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "tm": tipo_manif, "n": f"AnxSig {sfx}"})).scalar_one())
    unidade = int((await s.execute(text(
        "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) "
        "VALUES (:t, :n, false) RETURNING id"
    ), {"t": tenant_id, "n": f"AnxSig {sfx}"})).scalar_one())
    tipo_proc = int((await s.execute(text(
        "INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) "
        "VALUES (:t, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "n": f"AnxSig {sfx}"})).scalar_one())
    assunto = int((await s.execute(text(
        "INSERT INTO protocolos.assunto "
        "(tenant_id, id_tipo_processo, assunto, ativo, excluido) "
        "VALUES (:t, :tp, :n, true, false) RETURNING id"
    ), {"t": tenant_id, "tp": tipo_proc, "n": f"AnxSig {sfx}"})).scalar_one())
    return {
        "categoria": categoria,
        "tipo_manifestante": tipo_manif,
        "manifestante": manifestante,
        "unidade": unidade,
        "tipo_processo": tipo_proc,
        "assunto": assunto,
    }


async def _processo(s: AsyncSession, tenant_id: int, cat: dict, nivel: str) -> int:
    return int((await s.execute(text(
        """
        INSERT INTO protocolos.processo
            (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
             numero_processo, nivel_sigilo, virtual, externo, ativo, excluido,
             migrado, data_hora_abertura)
        VALUES (:t, :a, :m, :u, :n, :niv, true, false, true, false, false, NOW())
        RETURNING id
        """
    ), {
        "t": tenant_id, "a": cat["assunto"], "m": cat["manifestante"],
        "u": cat["unidade"], "n": f"AS{uuid.uuid4().hex[:6]}/2026", "niv": nivel,
    })).scalar_one())


async def _anexo_com_arquivo(
    s: AsyncSession, tenant_id: int, tenant_slug: str, processo_id: int, unidade_id: int
) -> int:
    """Anexo + vínculo + arquivo físico. O arquivo importa: sem ele o
    carregador cru levanta AnexoError e o caso positivo não provaria nada."""
    # `anexo_processo.id_movimentacao` é NOT NULL — no fluxo real vem de
    # `processo.id_ultima_movimentacao`, que um processo inserido direto não
    # tem. Por isso a movimentação de abertura nasce aqui.
    movimentacao = int((await s.execute(text(
        "INSERT INTO protocolos.movimentacao "
        "(tenant_id, id_processo, id_unidade_responsavel, id_acao, "
        " data_hora_movimentacao, ativo, excluido) "
        "SELECT :t, :p, :u, id, NOW(), true, false "
        "FROM protocolos.acao WHERE flag = 'ABERTURA' LIMIT 1 RETURNING id"
    ), {"t": tenant_id, "p": processo_id, "u": unidade_id})).scalar_one())
    anexo_id = int((await s.execute(text(
        "INSERT INTO protocolos.anexo "
        "(tenant_id, publico, ativo, excluido, descricao) "
        "VALUES (:t, false, true, false, 'documento de teste') RETURNING id"
    ), {"t": tenant_id})).scalar_one())
    e_doc = f"{anexo_id}.txt"
    await s.execute(text(
        "UPDATE protocolos.anexo SET e_doc = :e WHERE id = :i"
    ), {"e": e_doc, "i": anexo_id})
    await s.execute(text(
        "INSERT INTO protocolos.anexo_processo "
        "(tenant_id, id_processo, id_anexo, id_movimentacao, ordem, ativo, "
        " excluido, anexo_herdado) "
        "VALUES (:t, :p, :a, :m, 1, true, false, false)"
    ), {"t": tenant_id, "p": processo_id, "a": anexo_id, "m": movimentacao})
    destino = tenant_anexos_dir(tenant_slug) / e_doc
    destino.write_bytes(b"conteudo sigiloso de teste")
    return anexo_id


@pytest_asyncio.fixture
async def ambiente(admin_engine, two_tenants):
    tid, _outro = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        slug = (await s.execute(text(
            "SELECT slug FROM aprimora_py.tenant WHERE id = :t"
        ), {"t": tid})).scalar_one()
        cat = await _catalogos(s, tid)
        pid_reservado = await _processo(s, tid, cat, "reservado")
        pid_ostensivo = await _processo(s, tid, cat, "ostensivo")
        anexo_reservado = await _anexo_com_arquivo(
            s, tid, slug, pid_reservado, cat["unidade"]
        )
        anexo_ostensivo = await _anexo_com_arquivo(
            s, tid, slug, pid_ostensivo, cat["unidade"]
        )
        await s.commit()

    yield {
        "tenant_id": tid,
        "tenant_slug": slug,
        "anexo_reservado": anexo_reservado,
        "anexo_ostensivo": anexo_ostensivo,
        "processo_reservado": pid_reservado,
        **cat,
    }

    async with Session() as s:
        await s.execute(text(
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id = :t"
        ), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.anexo WHERE tenant_id = :t"), {"t": tid})
        # Movimentação e usuários seguram o tenant por FK — sem apagá-los aqui,
        # o teardown do `two_tenants` estoura com ForeignKeyViolationError e o
        # erro aparece longe da causa.
        await s.execute(text("DELETE FROM protocolos.movimentacao WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.processo WHERE tenant_id = :t"), {"t": tid})
        await s.execute(text(
            "DELETE FROM utils.usuario WHERE tenant_id = :t AND email LIKE 'anxsig-%@anexo.test'"
        ), {"t": tid})
        await s.execute(text("DELETE FROM protocolos.assunto WHERE id = :i"), {"i": cat["assunto"]})
        await s.execute(text("DELETE FROM protocolos.tipo_processo WHERE id = :i"), {"i": cat["tipo_processo"]})
        await s.execute(text("DELETE FROM utils.unidade_trabalho WHERE id = :i"), {"i": cat["unidade"]})
        await s.execute(text("DELETE FROM protocolos.manifestante WHERE id = :i"), {"i": cat["manifestante"]})
        await s.execute(text("DELETE FROM protocolos.tipo_manifestante WHERE id = :i"), {"i": cat["tipo_manifestante"]})
        await s.execute(text("DELETE FROM protocolos.categoria WHERE id = :i"), {"i": cat["categoria"]})
        await s.commit()


async def _usuario(s: AsyncSession, tenant_id: int, credencial: str) -> SimpleNamespace:
    """Usuário comum (não super) com a credencial de sigilo pedida.

    `assert_acesso_processo` chama `load_permissions`, que lê o banco — então
    o usuário precisa existir de verdade, não ser um SimpleNamespace solto.
    Sem grupo nenhum: o ponto é justamente que hoje qualquer autenticado do
    tenant chega ao download.
    """
    uid = int((await s.execute(text(
        """
        INSERT INTO utils.usuario
            (tenant_id, nome, email, senha, cpf, ativo, excluido, nivel_acesso_sigilo)
        VALUES (:t, 'Anx Sigilo', :e, '', :cpf, true, false, :cred)
        RETURNING id
        """
    ), {
        "t": tenant_id,
        "e": f"anxsig-{uuid.uuid4().hex[:8]}@anexo.test",
        "cpf": f"{uuid.uuid4().int % 10**11:011d}",
        "cred": credencial,
    })).scalar_one())
    return SimpleNamespace(id=uid, nivel_acesso_sigilo=credencial)


# ---------------------------------------------------------------- comportamento


async def test_credencial_insuficiente_nao_baixa_anexo_sigiloso(admin_engine, ambiente):
    """O defeito em uma linha: credencial `interno`, processo `reservado`."""
    async with _sessao(admin_engine) as s:
        usuario = await _usuario(s, ambiente["tenant_id"], "interno")
        await s.commit()

    async with _sessao(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await get_anexo_path_autorizado(
                s,
                ambiente["anexo_reservado"],
                tenant_id=ambiente["tenant_id"],
                tenant_slug=ambiente["tenant_slug"],
                usuario=usuario,
            )


async def test_o_carregador_cru_continua_devolvendo(admin_engine, ambiente):
    """Prova que a negação acima vem da checagem nova, e não do setup.

    Este é o caso que dá sentido ao anterior. Se o anexo estivesse no tenant
    errado, sem vínculo ou sem arquivo, `get_anexo_path_autorizado` levantaria
    de qualquer jeito e o teste de negação passaria sem testar sigilo nenhum.
    Aqui o carregador cru entrega o mesmo anexo sem reclamar — logo a única
    diferença entre os dois caminhos é a autorização.

    É também o registro executável da vulnerabilidade: era exatamente isto que
    os dois endpoints chamavam até 2026-08-05.
    """
    async with _sessao(admin_engine) as s:
        anexo, path = await get_anexo_path(
            s,
            ambiente["anexo_reservado"],
            tenant_id=ambiente["tenant_id"],
            tenant_slug=ambiente["tenant_slug"],
        )
        assert anexo.id == ambiente["anexo_reservado"]
        assert path.exists()


async def test_credencial_suficiente_baixa(admin_engine, ambiente):
    async with _sessao(admin_engine) as s:
        usuario = await _usuario(s, ambiente["tenant_id"], "reservado")
        await s.commit()

    async with _sessao(admin_engine) as s:
        anexo, path = await get_anexo_path_autorizado(
            s,
            ambiente["anexo_reservado"],
            tenant_id=ambiente["tenant_id"],
            tenant_slug=ambiente["tenant_slug"],
            usuario=usuario,
        )
        assert anexo.id == ambiente["anexo_reservado"]
        assert path.exists()


async def test_processo_ostensivo_segue_acessivel(admin_engine, ambiente):
    """A correção não pode fechar o caso comum — é a maioria dos anexos."""
    async with _sessao(admin_engine) as s:
        usuario = await _usuario(s, ambiente["tenant_id"], "interno")
        await s.commit()

    async with _sessao(admin_engine) as s:
        anexo, _path = await get_anexo_path_autorizado(
            s,
            ambiente["anexo_ostensivo"],
            tenant_id=ambiente["tenant_id"],
            tenant_slug=ambiente["tenant_slug"],
            usuario=usuario,
        )
        assert anexo.id == ambiente["anexo_ostensivo"]


async def test_anexo_sem_vinculo_ativo_e_negado(admin_engine, ambiente):
    """Sem vínculo não há processo cujo sigilo consultar → nega.

    Decisão deliberada de fail-closed, ao contrário do fail-open intencional
    da modularização: ali o esquecimento vira teste vermelho; aqui viraria
    documento sigiloso servido.
    """
    async with _sessao(admin_engine) as s:
        usuario = await _usuario(s, ambiente["tenant_id"], "ultrassecreto")
        await s.execute(text(
            "UPDATE protocolos.anexo_processo SET excluido = true "
            "WHERE id_anexo = :a AND tenant_id = :t"
        ), {"a": ambiente["anexo_reservado"], "t": ambiente["tenant_id"]})
        await s.commit()

    async with _sessao(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await get_anexo_path_autorizado(
                s,
                ambiente["anexo_reservado"],
                tenant_id=ambiente["tenant_id"],
                tenant_slug=ambiente["tenant_slug"],
                usuario=usuario,
            )


async def test_autorizacao_precede_a_resolucao_do_arquivo(admin_engine, ambiente):
    """Arquivo ausente não pode virar canal de confirmação de existência.

    Se a ordem se invertesse, quem não tem credencial receberia `AnexoError`
    ("Arquivo X não está no storage") para anexo existente e `SigiloAcessoError`
    para inexistente — distinguindo os dois casos justamente para quem não
    deveria distinguir.
    """
    async with _sessao(admin_engine) as s:
        usuario = await _usuario(s, ambiente["tenant_id"], "interno")
        await s.commit()

    destino = tenant_anexos_dir(ambiente["tenant_slug"]) / f"{ambiente['anexo_reservado']}.txt"
    destino.unlink(missing_ok=True)

    async with _sessao(admin_engine) as s:
        with pytest.raises(SigiloAcessoError):
            await get_anexo_path_autorizado(
                s,
                ambiente["anexo_reservado"],
                tenant_id=ambiente["tenant_id"],
                tenant_slug=ambiente["tenant_slug"],
                usuario=usuario,
            )
        # E o motivo é mesmo a ordem: sem a credencial resolvida, o carregador
        # cru falharia por arquivo ausente.
        with pytest.raises(AnexoError):
            await get_anexo_path(
                s,
                ambiente["anexo_reservado"],
                tenant_id=ambiente["tenant_id"],
                tenant_slug=ambiente["tenant_slug"],
            )


# ---------------------------------------------------------------- estrutural


def test_nenhum_router_chama_o_carregador_cru() -> None:
    """Router só pode usar `get_anexo_path_autorizado`.

    A guarda comportamental acima protege os dois endpoints que existem hoje.
    Esta protege o terceiro, que ainda não foi escrito: chamar `get_anexo_path`
    de um router é sempre um download sem checagem de sigilo, e foi exatamente
    assim que o defeito nasceu.
    """
    infratores = []
    for arquivo in sorted(ROUTERS.glob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if "get_anexo_path" not in linha:
                continue
            if "get_anexo_path_autorizado" in linha:
                continue
            infratores.append(f"{arquivo.name}:{numero}: {linha.strip()}")
    assert not infratores, (
        "Router chamando o carregador cru `get_anexo_path`, que NÃO checa o "
        "sigilo do processo: " + "; ".join(infratores) + ". Use "
        "`get_anexo_path_autorizado`, que recebe o usuário."
    )


def test_a_guarda_estrutural_esta_olhando_o_lugar_certo() -> None:
    """Controle: se o diretório mudar de lugar, o teste acima passa vazio."""
    assert ROUTERS.is_dir(), f"{ROUTERS} não existe — conserte o caminho."
    assert (ROUTERS / "anexos.py").exists(), "anexos.py não está onde a guarda procura."
    assert any(
        "get_anexo_path_autorizado" in a.read_text(encoding="utf-8")
        for a in ROUTERS.glob("*.py")
    ), "Nenhum router usa `get_anexo_path_autorizado` — a guarda ficaria vácua."
