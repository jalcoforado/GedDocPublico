"""Guarda do prefixo de `notificacao.link_url`.

Desde a F3 (2026-08-03) as telas de módulo moram em `/m/<slug>/…`, e as URLs
antigas continuam vivas por **308 permanentes**. O redirect existe para o que
**já foi gravado** — não para o que ainda vai ser.

A distinção importa porque `notificacao.link_url` é **registro histórico
permanente**: cada linha nasce e fica. Notificação gravada com `/processos/{id}`
funciona, mas custa um salto extra e deixa a URL velha na barra do usuário, para
sempre. E `permanent: true` é cache de navegador: destino errado que chegue a
produção não se conserta com redeploy.

Até a F4 havia exatamente **um** escritor — `tasks/verificar_sla_workflows.py` —
e ele gravava o prefixo legado. Um só é fácil de consertar à mão; o problema é o
segundo. A P5.3 deixou explicitamente em aberto a "notificação automática por
job" do transporte, e esse job vai gravar `link_url`. Sem esta guarda ele nasce
legado, ninguém percebe, e a dívida volta multiplicada.

**O que esta guarda NÃO faz:** conferir se a rota existe. Ela olha o prefixo, não
o destino. `/m/protocolo/processos/{id}` com id errado passa aqui — quem cobre
destino é `frontend/__tests__/rotas-modulo.test.ts`.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Os cinco módulos contratáveis mais `comum`. Mesma lista de
# `app/cli/seed_bootstrap.py::MODULO_TRANSACOES` e de `frontend/lib/menus/`.
SLUGS = ("protocolo", "pagamentos", "frota", "transporte", "administracao", "comum")

# As transversais da D5, que moram na raiz de `app/(app)/` de propósito: elas
# agregam ATRAVÉS dos módulos, e prefixá-las com um slug seria mentira.
TRANSVERSAIS = ("/home", "/dashboard", "/perfil", "/para-assinar")

# `link_url="..."` ou `link_url=f"..."`, só a forma literal. Valor vindo de
# variável escapa desta guarda — e é por isso que o docstring pede que se
# escreva o literal na chamada.
PADRAO = re.compile(r"""link_url\s*=\s*f?["']([^"']+)["']""")


def _aceitavel(url: str) -> bool:
    if url.startswith(tuple(f"/m/{s}/" for s in SLUGS)):
        return True
    return url in TRANSVERSAIS or url.startswith(tuple(t + "/" for t in TRANSVERSAIS))


def test_todo_link_url_nasce_com_prefixo_de_modulo() -> None:
    infratores: list[str] = []
    for arquivo in sorted(APP.rglob("*.py")):
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            for url in PADRAO.findall(linha):
                if not _aceitavel(url):
                    rel = arquivo.relative_to(APP.parent)
                    infratores.append(f"{rel}:{n}: {url!r}")

    assert not infratores, (
        "`link_url` gravado sem prefixo de módulo: "
        + "; ".join(infratores)
        + ". A URL antiga funciona pelo 308, mas `notificacao.link_url` é "
        "registro PERMANENTE — cada linha assim é um salto extra e uma URL "
        f"velha na barra, para sempre. Use `/m/<slug>/…` (slugs: "
        f"{', '.join(SLUGS)}) ou uma transversal ({', '.join(TRANSVERSAIS)})."
    )


def test_a_guarda_enxerga_algum_link_url() -> None:
    """Controle contra verde por vacuidade.

    Se alguém renomear o campo, mover a escrita para um helper que monte a
    string em variável, ou simplesmente apagar o único escritor, o teste acima
    fica verde por não achar nada — e passaria a afirmar sobre um conjunto
    vazio. Este teste transforma isso em vermelho, que é onde a decisão fica
    visível na revisão.
    """
    achados = [
        url
        for arquivo in APP.rglob("*.py")
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
        for url in PADRAO.findall(linha)
    ]
    assert achados, (
        "nenhuma escrita literal de `link_url` encontrada em app/. Ou o campo "
        "mudou de nome, ou a escrita passou a montar a URL numa variável — e "
        "nos dois casos a guarda acima virou decorativa. Ajuste o PADRAO ou "
        "remova as duas, com o motivo no diff."
    )
