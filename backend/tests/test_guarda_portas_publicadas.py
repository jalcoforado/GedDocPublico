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
FECHA_PORTAS = RAIZ / "deploy" / "vps" / "aprimora-fecha-portas.sh"
UNIDADE_FECHA_PORTAS = RAIZ / "deploy" / "systemd" / "aprimora-fecha-portas.service"

# A única porta que deve responder da internet: o nginx, que é a entrada
# oficial e o único ponto onde a resolução de tenant por `Host` funciona.
# Acrescentar aqui é decisão de exposição — não faça sem motivo escrito.
PUBLICAS_PERMITIDAS = {"8090"}


def _exige(*caminhos: Path) -> None:
    """Pula fora do CI; **falha** dentro dele.

    Mesma assimetria de `test_guarda_portao_de_deploy.py` e pelo mesmo motivo:
    o container local monta só `./backend:/app`, então nem `docker-compose.yml`
    nem `deploy/` existem ali. O CI roda pytest no runner com o repositório
    inteiro. Sem a assimetria explícita a guarda sumiria em silêncio no único
    lugar onde é obrigatória.

    **Recebe TODOS os arquivos de que o teste depende, e não só o compose.**
    A primeira versão checava apenas o `docker-compose.yml`: numa máquina onde
    ele tivesse sido copiado e `deploy/` não, os testes de firewall estouravam
    com falha dura — um deles com `FileNotFoundError` cru — parecendo defeito
    de código quando era só arquivo fora de alcance. Aconteceu ao rodar a suíte
    completa em 2026-08-06.

    Para exercitá-la localmente:

        docker cp docker-compose.yml aprimora-py-backend:/
        docker cp deploy aprimora-py-backend:/
    """
    faltando = [c for c in caminhos if not c.exists()]
    if not faltando:
        return
    nomes = ", ".join(f"`{c}`" for c in faltando)
    if os.getenv("CI"):
        pytest.fail(
            f"{nomes} não encontrado(s) COM CI=1. Esta guarda não pode ser "
            "pulada no CI. Se a estrutura do repositório mudou, conserte o "
            "caminho — ou explique a remoção no diff."
        )
    pytest.skip(
        f"{nomes} fora do alcance (container monta só ./backend). Esta guarda "
        "roda no CI; veja o docstring para exercitá-la aqui."
    )


def _exige_compose() -> None:
    _exige(COMPOSE)


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


def _portas_bloqueadas_pelo_firewall() -> set[str]:
    """Lê a lista `PORTAS=` do script de firewall versionado."""
    for linha in FECHA_PORTAS.read_text(encoding="utf-8").splitlines():
        if linha.startswith("PORTAS="):
            # PORTAS="${PORTAS:-5432 8000 ...}"
            miolo = linha.split(":-", 1)[-1].rstrip('}"')
            return set(miolo.split())
    pytest.fail(f"não achei a linha `PORTAS=` em {FECHA_PORTAS.name}.")


def test_o_firewall_cobre_todo_servico_nao_publico() -> None:
    """Cruza o compose com a segunda camada de defesa.

    A camada 1 é o bind em `127.0.0.1` deste compose. A camada 2 são as regras
    de `DOCKER-USER` aplicadas por `deploy/vps/aprimora-fecha-portas.sh` na VPS.
    Elas existem porque a camada 1 é um arquivo editável — e porque
    `docker-compose.override.yml`, gitignored, pode republicar em `0.0.0.0` sem
    passar por guarda nenhuma.

    O que se confere aqui é a porta do **lado de dentro** do container. O DNAT
    do Docker reescreve a porta antes da chain `DOCKER-USER`, então bloquear a
    porta publicada não adianta quando o mapeamento é `3100:3000`. Foi
    exatamente esse detalhe que deixou a 3100 aberta depois da primeira
    tentativa de bloqueio, em 2026-08-05.
    """
    _exige(COMPOSE, FECHA_PORTAS)
    bloqueadas = _portas_bloqueadas_pelo_firewall()
    faltando = []
    for servico, entrada in _portas_publicadas():
        partes = entrada.split(":")
        porta_container = partes[-1]
        porta_host = partes[-2]
        if porta_host in PUBLICAS_PERMITIDAS:
            continue
        if porta_container not in bloqueadas:
            faltando.append(f"{servico}: {entrada!r} (dentro: {porta_container})")
    assert not faltando, (
        "Serviço publicado que o firewall da VPS não bloqueia: "
        + "; ".join(faltando)
        + f". Acrescente a porta de DENTRO do container a `PORTAS=` em "
        f"{FECHA_PORTAS.name}."
    )


def test_a_unidade_de_firewall_roda_depois_do_docker() -> None:
    """`After=docker.service`, sem o qual a unidade fica verde e inútil.

    O daemon recria a chain `DOCKER-USER` ao subir. Regra inserida antes disso
    é levada junto — e o sintoma é `systemctl status` ativo com as portas
    abertas.
    """
    _exige(UNIDADE_FECHA_PORTAS)
    texto = UNIDADE_FECHA_PORTAS.read_text(encoding="utf-8")
    assert "After=docker.service" in texto, (
        f"`{UNIDADE_FECHA_PORTAS.name}` sem `After=docker.service`: o daemon "
        "recria a chain DOCKER-USER ao subir e apaga as regras."
    )
    assert "ExecStart=-" not in texto, (
        f"`{UNIDADE_FECHA_PORTAS.name}` usa `ExecStart=-`, que faz o systemd "
        "ignorar a falha."
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
