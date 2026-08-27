"""Guarda do portão de deploy — `.github/workflows/deploy-vps.yml`.

Até 2026-08-04 os quatro workflows disparavam juntos no `push` para `main`, e a
VPS recebia código **mesmo com a suíte vermelha**. Aconteceu no push `a1a0c8e`:
`Backend tests` reprovou e o `Deploy to VPS` subiu assim mesmo.

O conserto foi trocar o gatilho por `workflow_run` mais um job `gate` que
confere os outros dois workflows por API. Esta guarda existe porque **os dois
modos de falha do portão são silenciosos**:

- se o gatilho ou o `needs`/`if` sumir, volta a deployar em cima de vermelho —
  e nada avisa, porque o deploy continua "verde";
- se alguém **renomear** um workflow de teste, o `gate` procura um nome que não
  existe mais. A busca devolve `ausente`, o portão barra tudo, e o sintoma é
  "os deploys pararam" sem nenhum erro apontando para a causa.

O segundo é o que motiva a parte mais importante deste arquivo: cruzar os nomes
que o portão procura com o `name:` real de cada workflow.

A lógica de decisão do script (oito ramos: tudo verde, cada workflow vermelho,
workflow ausente, origem que não é push, gatilho cancelado, disparo manual) foi
exercitada à mão com um `gh` de mentira, e não é reexecutada aqui — isto é uma
guarda estrutural, não um teste de shell.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
DEPLOY = WORKFLOWS / "deploy-vps.yml"
# Os três que o portão exige verdes. Mudou aqui? Tem de mudar no `gate` também
# — é exatamente o que `test_nomes_procurados_pelo_portao_existem` confere.
TESTES_EXIGIDOS = ("Backend tests", "Frontend tests", "E2E assinatura")


def _exige_workflows() -> None:
    """Pula fora do CI; **falha** dentro dele.

    Mesma assimetria de `test_guarda_contrato_paginado.py`, pelo mesmo motivo: o
    container local monta só `./backend:/app`, então `.github/` não existe ali.
    O CI roda pytest no runner com o repositório inteiro. Sem a assimetria
    explícita, a guarda sumiria em silêncio no único lugar onde é obrigatória.

    Para exercitá-la localmente:

        docker exec aprimora-py-backend mkdir -p /.github/workflows
        docker cp .github/workflows/. aprimora-py-backend:/.github/workflows/
    """
    if DEPLOY.exists():
        return
    if os.getenv("CI"):
        pytest.fail(
            f"`{DEPLOY}` não encontrado COM CI=1. A guarda do portão de deploy "
            "não pode ser pulada no CI. Se a estrutura do repositório mudou, "
            "conserte o caminho."
        )
    pytest.skip(
        ".github/workflows fora do alcance (container monta só ./backend). "
        "Esta guarda roda no CI; veja o docstring para exercitá-la aqui."
    )


def _carrega(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _gatilhos(doc: dict) -> dict:
    """`on:` vira booleano `True` no YAML 1.1 do PyYAML.

    Ler `doc["on"]` devolve `None` e a guarda passaria sem conferir nada — é o
    tipo de teste que fica verde por não testar. Daí a checagem das duas formas.
    """
    if "on" in doc:
        return doc["on"]
    return doc[True]


def test_deploy_nao_dispara_direto_no_push():
    """O gatilho de `push` é justamente o que fazia a VPS receber vermelho."""
    _exige_workflows()
    gatilhos = _gatilhos(_carrega(DEPLOY))

    assert "push" not in gatilhos, (
        "`deploy-vps.yml` voltou a disparar em `push`. Isso desfaz o conserto de "
        "2026-08-04: o deploy correria em paralelo com os testes e a VPS "
        "receberia código reprovado. O gatilho tem de ser `workflow_run`."
    )
    assert "workflow_run" in gatilhos
    assert "Backend tests" in gatilhos["workflow_run"]["workflows"]
    # Um workflow só no gatilho, de propósito: `workflow_run` com vários dispara
    # uma vez POR workflow que termina, e dois deploys simultâneos são piores
    # que um deploy tardio.
    assert len(gatilhos["workflow_run"]["workflows"]) == 1, (
        "Mais de um workflow no gatilho dispara o deploy uma vez por workflow "
        "que termina, não uma vez quando todos terminam."
    )


def test_deploy_depende_do_portao():
    """Sem `needs` + `if`, o job `gate` vira enfeite: roda e não decide nada."""
    _exige_workflows()
    jobs = _carrega(DEPLOY)["jobs"]

    assert "gate" in jobs, "o job `gate` sumiu do `deploy-vps.yml`"
    deploy = jobs["deploy"]
    assert "gate" in (deploy.get("needs") or []), "`deploy` não depende de `gate`"
    condicao = (deploy.get("if") or "").replace('"', "'")
    assert "needs.gate.outputs.liberado == 'true'" in condicao, (
        "`deploy` não está condicionado à saída do portão. Com `needs` e sem "
        "`if`, ele roda mesmo com o portão barrando."
    )


def test_nomes_procurados_pelo_portao_existem():
    """O modo de falha mais traiçoeiro: workflow renomeado.

    O portão procura os outros dois **por nome**. Renomear um deles faz a busca
    devolver `ausente`, o portão barra, e o sintoma é "pararam os deploys" — sem
    erro que aponte a causa. Aqui os nomes procurados são cruzados com o `name:`
    real de cada arquivo.
    """
    _exige_workflows()
    doc = _carrega(DEPLOY)
    script = doc["jobs"]["gate"]["steps"][0]["run"]
    gatilho = _gatilhos(doc)["workflow_run"]["workflows"]

    nomes_reais = {
        _carrega(f)["name"]
        for f in WORKFLOWS.glob("*.yml")
        if f.name != DEPLOY.name
    }
    # Controle: sem isto, um diretório vazio faria o teste passar por vacuidade.
    assert len(nomes_reais) >= 3, f"só {len(nomes_reais)} workflows lidos: {nomes_reais}"

    for exigido in TESTES_EXIGIDOS:
        assert exigido in nomes_reais, (
            f"o portão exige o workflow {exigido!r}, que não existe mais em "
            f".github/workflows. Nomes reais: {sorted(nomes_reais)}. "
            "Renomear um workflow de teste faz o portão barrar TODO deploy, em "
            "silêncio."
        )
        # Cada exigido tem de ser citado: ou no gatilho, ou dentro do script.
        citado = exigido in gatilho or exigido in script
        assert citado, (
            f"{exigido!r} existe, mas o portão não o consulta em lugar nenhum — "
            "ele poderia reprovar e o deploy sairia assim mesmo."
        )


def test_workflows_de_teste_rodam_em_push_para_main():
    """O portão só funciona se os três realmente rodarem no push.

    Um `paths:` acrescentado a qualquer um deles faria o workflow ser pulado em
    parte dos pushes; o portão então veria `ausente` e barraria o deploy — de
    novo, silêncio. E se o pulado fosse o `Backend tests`, que é o GATILHO, não
    haveria deploy nenhum.
    """
    _exige_workflows()
    por_nome = {
        _carrega(f)["name"]: _carrega(f)
        for f in WORKFLOWS.glob("*.yml")
        if f.name != DEPLOY.name
    }

    for exigido in TESTES_EXIGIDOS:
        push = _gatilhos(por_nome[exigido]).get("push") or {}
        assert "main" in (push.get("branches") or []), (
            f"{exigido!r} não roda em push para `main`; o portão nunca o verá."
        )
        assert "paths" not in push, (
            f"{exigido!r} ganhou filtro `paths:`. Em push que não case o filtro "
            "ele não roda, o portão o vê como `ausente` e barra o deploy — ou, "
            "se for o `Backend tests`, nem chega a existir deploy."
        )


# ---------------------------------------------------------------------------
# O SHA aprovado tem de ser o SHA que sobe (2026-08-16)
#
# O portão confere que os três workflows fecharam verdes **naquele SHA**, e o
# `deploy.sh` jogava isso fora com `git reset --hard origin/main`: subia o
# `main` do momento do deploy. Commit que entrasse em `main` entre o fim da
# suíte e o deploy ia junto, sem nunca ter passado pelo portão — o portão
# aprovava um SHA e a VPS recebia outro.
#
# É defeito SILENCIOSO nas duas direções: o deploy fica verde, e o commit não
# testado roda em homologação sem nada apontar para isso. Por isso a guarda
# cobre as duas pontas — quem passa (`deploy-vps.yml`) e quem consome
# (`deploy.sh`) —, já que remover qualquer uma reabre o buraco.
# ---------------------------------------------------------------------------
DEPLOY_SH = Path(__file__).resolve().parents[2] / "scripts" / "deploy.sh"


def test_workflow_passa_o_sha_aprovado_para_o_script():
    _exige_workflows()
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "export DEPLOY_SHA=" in texto, (
        "O `deploy-vps.yml` parou de exportar DEPLOY_SHA. Sem ele o `deploy.sh` "
        "cai em origin/main e a VPS volta a receber um SHA que o portão não "
        "aprovou."
    )
    assert "workflow_run.head_sha" in texto, (
        "DEPLOY_SHA precisa vir do `head_sha` do run que abriu o portão — é ele "
        "que os três workflows aprovaram. Qualquer outra origem (github.ref, "
        "topo do branch) reabre a janela."
    )


def test_script_de_deploy_usa_o_sha_recebido():
    if not DEPLOY_SH.exists():
        if os.getenv("CI"):
            pytest.fail(f"`{DEPLOY_SH}` não encontrado COM CI=1.")
        pytest.skip("scripts/ fora do alcance (container monta só ./backend).")
    texto = DEPLOY_SH.read_text(encoding="utf-8")
    assert "DEPLOY_SHA" in texto, (
        "`pull_code` voltou a ignorar DEPLOY_SHA. O workflow passa a variável e "
        "o script a descarta: o portão aprova um SHA e a VPS recebe outro."
    )
    # `origin/main` CONTINUA no arquivo, e é correto — é o fallback da invocação
    # manual no servidor. O que não pode voltar é ele ser o único caminho.
    assert 'git reset --hard "$alvo"' in texto, (
        "O `reset` no SHA alvo sumiu de `pull_code`. Só sobrou o fallback, que "
        "é o comportamento antigo."
    )


# ---------------------------------------------------------------------------
# Autenticação do deploy (2026-08-27)
#
# O login root por senha na porta 22 é o vetor provável do minerador instalado
# em 25/08. O workflow passou a preferir CHAVE, com senha só enquanto o secret
# `VPS_SSH_KEY` não existir — shim transitório, para que fechar a senha no
# servidor e trocar o workflow não precisem acontecer no mesmo minuto.
#
# As duas propriedades abaixo somem sem sintoma: o deploy continua verde nos
# dois casos, e o que se perde é invisível de fora.
# ---------------------------------------------------------------------------
def test_a_senha_do_vps_nao_e_interpolada_no_script():
    """`$VPS_PASSWORD` vem do ambiente, nunca de `${{ env.VPS_PASSWORD }}`.

    A diferença não é estilo. `${{ }}` é substituído pelo Actions ANTES de o
    shell existir, então a senha passa a fazer parte do texto do script — ela
    aparece em `set -x`, em mensagem de erro do bash e em qualquer eco acidental
    do comando. Lida do ambiente, o mascaramento de segredo do runner continua
    valendo.
    """
    _exige_workflows()
    doc = _carrega(DEPLOY)
    # SÓ o corpo dos `run:`. A ligação `VPS_PASSWORD: ${{ secrets.VPS_PASSWORD }}`
    # no bloco `env:` é a forma CERTA de trazer o segredo e não pode ser
    # confundida com o defeito — a primeira versão deste teste varria o arquivo
    # inteiro e reprovava exatamente a linha correta.
    scripts = [
        passo["run"]
        for job in doc["jobs"].values()
        for passo in job.get("steps", [])
        if isinstance(passo, dict) and "run" in passo
    ]
    assert scripts, "nenhum `run:` encontrado — a varredura ficaria vácua"
    for script in scripts:
        for forma in ("${{ env.VPS_PASSWORD }}", "${{ secrets.VPS_PASSWORD }}"):
            assert forma not in script, (
                f"A senha do VPS é interpolada no corpo de um `run:` via {forma}. "
                "Use `$VPS_PASSWORD` (variável de ambiente), que o runner mascara."
            )


def test_deploy_prefere_chave_e_avisa_quando_cai_na_senha():
    """O caminho de chave existe E a queda para senha é BARULHENTA.

    Sem o aviso, o shim vira permanente por inércia: o deploy funciona, ninguém
    olha, e a porta 22 segue aberta a senha por meses. O `::warning::` põe isso
    no resumo de cada execução.
    """
    _exige_workflows()
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "secrets.VPS_SSH_KEY" in texto, (
        "o caminho de autenticação por chave sumiu do deploy"
    )
    assert "::warning::VPS_SSH_KEY ausente" in texto, (
        "a queda para senha ficou silenciosa — é assim que um shim transitório "
        "vira permanente"
    )
