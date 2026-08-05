"""Guarda das portas publicadas pelo `docker-compose.yml`.

Em 2026-08-05, ao conferir um relatório externo, verifiquei que a VPS de
homologação respondia da internet nas portas **5432 (Postgres), 8000 (backend)
e 3100 (frontend)**, além da 8090 do nginx. A senha do banco está literal no
próprio `docker-compose.yml`, num repositório **público**, e `ged_user` é
`SUPERUSER` com `BYPASSRLS` — ou seja, quem lesse o repositório tinha, em tese,
o banco inteiro de todos os tenants. O servidor nem TLS oferecia (sonda de
`SSLRequest` respondeu `N`).

O conserto é prefixar `127.0.0.1:` em toda porta que não seja a entrada
pública. Esta guarda existe porque a regressão é **silenciosa nos dois
sentidos**: publicar em `0.0.0.0` não quebra nada — ao contrário, é mais
conveniente para depurar — e o sintoma só aparece como incidente.

Duas coisas que esta guarda NÃO cobre, e por isso ficam registradas aqui:

- **`ufw` não alcança porta publicada por container.** O Docker insere DNAT em
  `PREROUTING`, que desvia do `INPUT`. Bloqueio a quente tem de ir na chain
  `DOCKER-USER`. Na VPS há uma unidade systemd (`aprimora-fecha-portas`) que
  faz isso depois do `docker.service`, como defesa em profundidade.
- **O DNAT reescreve a porta antes da `DOCKER-USER`**, então regra de firewall
  tem de casar a porta de DENTRO do container (3000), não a publicada (3100).
  Descobri isso porque a 3100 continuou aberta depois da primeira regra.

`docker-compose.override.yml` é gitignored e usa `!override`, então pode
republicar em `0.0.0.0` na máquina de quem desenvolve. Isso é aceitável e está
fora do alcance desta guarda, que governa o arquivo versionado — o que vai para
a VPS.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "docker-compose.yml"

# A única porta que deve responder da internet: o nginx, que é a entrada
# oficial e o único ponto onde a resolução de tenant por `Host` funciona.
# Acrescentar aqui é decisão de exposição — não faça sem motivo escrito.
PUBLICAS_PERMITIDAS = {"8090"}


def _exige_compose() -> None:
    """Pula fora do CI; **falha** dentro dele.

    Mesma assimetria de `test_guarda_portao_de_deploy.py` e pelo mesmo motivo:
    o container local monta só `./backend:/app`, então o `docker-compose.yml`
    da raiz não existe ali. O CI roda pytest no runner com o repositório
    inteiro. Sem a assimetria explícita a guarda sumiria em silêncio no único
    lugar onde é obrigatória.

    Para exercitá-la localmente:

        docker cp docker-compose.yml aprimora-py-backend:/
    """
    if COMPOSE.exists():
        return
    if os.getenv("CI"):
        pytest.fail(
            f"`{COMPOSE}` não encontrado COM CI=1. A guarda de portas "
            "publicadas não pode ser pulada no CI. Se a estrutura do "
            "repositório mudou, conserte o caminho."
        )
    pytest.skip(
        "docker-compose.yml fora do alcance (container monta só ./backend). "
        "Esta guarda roda no CI; veja o docstring para exercitá-la aqui."
    )


def _portas_publicadas() -> list[tuple[str, str]]:
    """Devolve (serviço, entrada de `ports`) para cada porta publicada.

    Só a forma curta em string é aceita; a forma longa (mapa com `published`/
    `host_ip`) faria esta análise mentir por omissão, então é rejeitada
    explicitamente em vez de ignorada.
    """
    dados = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    saida: list[tuple[str, str]] = []
    for servico, conf in (dados.get("services") or {}).items():
        for entrada in (conf or {}).get("ports") or []:
            if not isinstance(entrada, str):
                pytest.fail(
                    f"Serviço `{servico}` publica porta na forma longa "
                    f"({entrada!r}). Esta guarda só analisa a forma curta; "
                    "use `\"127.0.0.1:HOST:CONTAINER\"` ou estenda a guarda."
                )
            saida.append((servico, entrada))
    return saida


def test_nenhuma_porta_publicada_em_todas_as_interfaces() -> None:
    """Toda porta publicada tem de ser `127.0.0.1:` ou estar na allowlist."""
    _exige_compose()
    infratores = []
    for servico, entrada in _portas_publicadas():
        if entrada.startswith("127.0.0.1:"):
            continue
        porta_host = entrada.split(":")[0]
        if porta_host in PUBLICAS_PERMITIDAS:
            continue
        infratores.append(f"{servico}: {entrada!r}")
    assert not infratores, (
        "Porta publicada em todas as interfaces (0.0.0.0), acessível da "
        "internet na VPS: " + "; ".join(infratores) + ". Prefixe com "
        "`127.0.0.1:`, ou — se a exposição for deliberada — acrescente a porta "
        "a PUBLICAS_PERMITIDAS com o motivo por escrito."
    )


def test_o_banco_nao_e_publicado_na_internet() -> None:
    """Caso específico do `db`, cravado à parte.

    O teste acima já cobriria, mas uma allowlist é editável e o banco é o
    ativo cujo vazamento não tem conserto. Aqui não há allowlist: se alguém
    publicar o Postgres em `0.0.0.0`, reprova, e o diff do teste torna a
    decisão visível na revisão.
    """
    _exige_compose()
    for servico, entrada in _portas_publicadas():
        if servico != "db":
            continue
        assert entrada.startswith("127.0.0.1:"), (
            f"O serviço `db` publica {entrada!r}. O Postgres não pode "
            "responder fora de localhost: a senha está literal neste mesmo "
            "arquivo, o repositório é público e `ged_user` é SUPERUSER com "
            "BYPASSRLS. Aconteceu de verdade — ver o docstring do módulo."
        )


def test_a_entrada_publica_continua_publicada() -> None:
    """Controle: prova que a guarda não passaria por 'não há porta nenhuma'.

    Sem isto, apagar todas as linhas de `ports` deixaria os dois testes acima
    verdes — verdes por vacuidade, que é o modo de falha que esta suíte mais
    persegue.
    """
    _exige_compose()
    nginx = [e for s, e in _portas_publicadas() if s == "nginx"]
    assert nginx, "O nginx não publica porta nenhuma — a aplicação está inacessível."
    assert any(re.match(r"^8090:", e) for e in nginx), (
        f"O nginx deveria publicar 8090 em todas as interfaces; achei {nginx}. "
        "É a entrada pública — restringi-la a localhost derruba o acesso."
    )
