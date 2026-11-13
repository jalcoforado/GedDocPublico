"""Sigilo nos relatórios (Processos, Tramitação, Assinaturas).

Os três relatórios não aplicavam o recorte de sigilo que a listagem (Caixas)
aplica: quem tinha a permissão `processo` via processo reservado/secreto — com
o nome do manifestante — no JSON, no CSV e no PDF. Aqui se trava:

- os três serviços filtram pelos níveis da credencial (e super-usuário vê tudo);
- `niveis_permitidos` é OBRIGATÓRIO nos três — esquecer de passar não pode
  virar "vê tudo" (é erro de chamada, não default aberto);
- toda rota `/relatorios/*` resolve o nível pela mesma dependência da listagem.

Integração (Postgres), reaproveitando o ambiente de `test_sigilo_enforcement`.
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import text

from app.schemas.relatorio import RelatorioFiltro
from app.schemas.relatorio_assinaturas import AssinaturasFiltro
from app.services.relatorios import gerar_relatorio
from app.services.relatorios_assinaturas import gerar_assinaturas
from app.services.relatorios_tramitacao import gerar_tramitacao
from app.services.sigilo import niveis_permitidos

from .test_sigilo_enforcement import _insert_processo, _session, sigilo_env  # noqa: F401

INTERNO = niveis_permitidos("interno")


async def _dois_processos(admin_engine, env) -> tuple[int, int]:
    tid = env["tenant_id"]
    async with _session(admin_engine) as s:
        aberto = await _insert_processo(s, tid, env, "ostensivo")
        reservado = await _insert_processo(s, tid, env, "reservado")
        await s.commit()
    return aberto, reservado


async def test_relatorio_processos_respeita_sigilo(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    aberto, reservado = await _dois_processos(admin_engine, sigilo_env)

    async with _session(admin_engine) as s:
        r = await gerar_relatorio(
            s, RelatorioFiltro(), tenant_id=tid, niveis_permitidos=INTERNO
        )
        ids = {p.id for p in r.processos}
        assert ids == {aberto}
        assert reservado not in ids
        # Os totais e as quebras também não podem contar o que a lista esconde.
        assert r.totais.total == 1
        assert sum(i.count for i in r.por_tipo_processo) == 1
        assert sum(i.count for i in r.por_unidade_proprietaria) == 1

        tudo = await gerar_relatorio(
            s, RelatorioFiltro(), tenant_id=tid, niveis_permitidos=None
        )
        assert {p.id for p in tudo.processos} == {aberto, reservado}


async def test_relatorio_tramitacao_respeita_sigilo(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    aberto, reservado = await _dois_processos(admin_engine, sigilo_env)

    async with _session(admin_engine) as s:
        r = await gerar_tramitacao(
            s, RelatorioFiltro(), tenant_id=tid, niveis_permitidos=INTERNO
        )
        assert {p.id for p in r.processos} == {aberto}
        assert r.qtd_processos == 1

        tudo = await gerar_tramitacao(
            s, RelatorioFiltro(), tenant_id=tid, niveis_permitidos=None
        )
        assert {p.id for p in tudo.processos} == {aberto, reservado}


async def test_relatorio_assinaturas_respeita_sigilo(admin_engine, sigilo_env):
    tid = sigilo_env["tenant_id"]
    usuario = sigilo_env["usuario"]
    aberto, reservado = await _dois_processos(admin_engine, sigilo_env)

    async with _session(admin_engine) as s:
        for pid in (aberto, reservado):
            await s.execute(
                text(
                    """
                    INSERT INTO protocolos.solicitacao_assinatura
                        (tenant_id, id_processo, id_solicitante, id_usuario,
                         realizada, ativo, excluido, cancelada, dt_inicio)
                    VALUES (:tid, :pid, :u, :u, false, true, false, false, NOW())
                    """
                ),
                {"tid": tid, "pid": pid, "u": usuario},
            )
        await s.commit()

    try:
        async with _session(admin_engine) as s:
            r = await gerar_assinaturas(
                s, AssinaturasFiltro(), tenant_id=tid, niveis_permitidos=INTERNO
            )
            assert {x.id_processo for x in r.solicitacoes} == {aberto}
            assert r.totais.total == 1

            tudo = await gerar_assinaturas(
                s, AssinaturasFiltro(), tenant_id=tid, niveis_permitidos=None
            )
            assert {x.id_processo for x in tudo.solicitacoes} == {aberto, reservado}
    finally:
        # O fixture apaga os processos; a solicitação aponta para eles.
        async with _session(admin_engine) as s:
            await s.execute(
                text("DELETE FROM protocolos.solicitacao_assinatura WHERE tenant_id = :t"),
                {"t": tid},
            )
            await s.commit()


@pytest.mark.parametrize("fn", [gerar_relatorio, gerar_tramitacao, gerar_assinaturas])
def test_niveis_permitidos_e_obrigatorio(fn):
    """Sem default: um chamador novo que esquecer o sigilo quebra na hora,
    em vez de entregar o relatório inteiro."""
    param = inspect.signature(fn).parameters["niveis_permitidos"]
    assert param.default is inspect.Parameter.empty
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_toda_rota_de_relatorio_resolve_o_sigilo():
    """Toda rota de `/relatorios` que devolve dado de processo decide o sigilo
    de quem consulta (`niveis_acesso_usuario`, o mesmo recorte da listagem),
    direto ou por um dos ajudantes do router. Rota nova tem de entrar numa das
    duas listas, senão este teste quebra.

    Desde o SI-34 as rotas chamam `niveis_acesso_usuario` no corpo (antes era a
    dependência `acesso_niveis_dep`); a garantia é a mesma.
    """
    import inspect

    from app.routers import relatorios as mod

    # Não devolvem processo: opções do filtro, catálogo de colunas e as
    # definições salvas (só a definição; os dados rodam com o sigilo de quem abre).
    SEM_DADO_DE_PROCESSO = {
        "servicos_do_filtro",
        "montado_catalogo",
        "salvos_listar",
        "salvos_criar",
        "salvos_obter",
        "salvos_atualizar",
        "salvos_excluir",
    }
    AJUDANTES = ("_gerencial", "_tramitacao", "_montado")
    for nome in AJUDANTES:
        assert "niveis_acesso_usuario" in inspect.getsource(getattr(mod, nome)), nome

    def resolve_sigilo(fn) -> bool:
        src = inspect.getsource(fn)
        return "niveis_acesso_usuario" in src or any(
            f"await {h}(" in src for h in AJUDANTES
        )

    rotas = [r for r in mod.router.routes if getattr(r, "endpoint", None)]
    assert len(rotas) >= 9
    nomes = {r.endpoint.__name__ for r in rotas}
    assert SEM_DADO_DE_PROCESSO <= nomes, "lista desatualizada: " + str(SEM_DADO_DE_PROCESSO - nomes)
    sem_sigilo = [
        r.path
        for r in rotas
        if r.endpoint.__name__ not in SEM_DADO_DE_PROCESSO and not resolve_sigilo(r.endpoint)
    ]
    assert sem_sigilo == []


async def test_busca_global_nao_lista_processo_sigiloso(admin_engine, sigilo_env):
    """A busca (Ctrl+K) não pode revelar o número de processo que o detalhe
    esconde com 404."""
    from app.routers.busca import busca_global

    tid = sigilo_env["tenant_id"]
    aberto, reservado = await _dois_processos(admin_engine, sigilo_env)

    async with _session(admin_engine) as s:
        num = {
            r.id: r.numero_processo
            for r in (
                await s.execute(
                    text("SELECT id, numero_processo FROM protocolos.processo WHERE id = ANY(:ids)"),
                    {"ids": [aberto, reservado]},
                )
            ).all()
        }
        # Os dois números terminam em "/2026"; "/2026" acha os dois.
        r = await busca_global(q="/2026", _=None, tenant_id=tid, db=s, niveis=INTERNO)
        achados = {p["id"] for p in r["processos"]}
        assert aberto in achados
        assert reservado not in achados

        r = await busca_global(q=num[reservado], _=None, tenant_id=tid, db=s, niveis=INTERNO)
        assert r["processos"] == []

        tudo = await busca_global(q=num[reservado], _=None, tenant_id=tid, db=s, niveis=None)
        assert [p["id"] for p in tudo["processos"]] == [reservado]
