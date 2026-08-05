"""Guarda dos scripts de backup da VPS.

Até 2026-08-05 a VPS de homologação tinha exatamente UM backup: um dump manual
de 24 de julho, 43 KB, gravado em `/root/backups` — a mesma máquina do banco.
Sem cron, sem timer, sem cópia externa. Doze dias de dado operacional a um
`DROP` de distância.

Havia um `backup_database` em `scripts/deploy.sh`, desligado por padrão, e
escrito assim:

    docker compose exec -T db pg_dump ... > "$ARQUIVO" || log "Backup skipped"
    log "✓ Backup saved to $ARQUIVO"

O redirecionamento do shell cria o arquivo **antes** de o `pg_dump` rodar. Dump
que falha deixa no disco um arquivo de zero byte com nome de backup, o `||`
engole o erro, o deploy segue para a migration e o log afirma `✓ Backup saved`.
Três mentiras encadeadas, todas com exit code 0.

É a mesma família do export vazio que `app/cli/backup.py` já barra e do backup
sem contexto de tenant descrito lá: **artefato sintaticamente plausível e
inútil, cujo defeito só se manifesta no dia do restore** — meses depois e longe
da causa.

Esta guarda trava as propriedades que impedem a recaída. Ela NÃO prova que o
backup funciona: isso é trabalho do `scripts/backup-verificar.sh`, que restaura
de verdade num banco descartável. Guarda estática não substitui restore.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BACKUP_SH = RAIZ / "scripts" / "backup-aprimora.sh"
VERIFICAR_SH = RAIZ / "scripts" / "backup-verificar.sh"
DEPLOY_SH = RAIZ / "scripts" / "deploy.sh"
UNIDADES = RAIZ / "deploy" / "systemd"


def _exige_raiz() -> None:
    """Pula fora do CI; **falha** dentro dele.

    Mesma assimetria de `test_guarda_portas_publicadas.py` e pelo mesmo motivo:
    o container local monta só `./backend:/app`, então `scripts/` não existe
    ali. O CI roda pytest no runner com o repositório inteiro.
    """
    if BACKUP_SH.exists():
        return
    if os.getenv("CI"):
        pytest.fail(
            f"`{BACKUP_SH}` não encontrado COM CI=1. A guarda de backup não "
            "pode ser pulada no CI. Se o script foi movido ou removido, "
            "conserte o caminho — ou explique a remoção no diff."
        )
    pytest.skip(
        "scripts/ fora do alcance (container monta só ./backend). Esta guarda "
        "roda no CI; para exercitá-la aqui: docker cp scripts aprimora-py-backend:/"
    )


def test_o_deploy_nao_redireciona_pg_dump_para_arquivo() -> None:
    """O padrão exato que produziu o arquivo de zero byte.

    Qualquer linha que redirecione a saída de um `pg_dump` para arquivo está
    fabricando o artefato antes de saber se o comando funcionou. O jeito certo
    é `pg_dump --file=`, que só cria o arquivo quando o dump acontece.
    """
    _exige_raiz()
    # Comentário não executa — e o `backup_database` de hoje cita o padrão
    # antigo justamente para explicar por que ele saiu.
    infratores = [
        f"{DEPLOY_SH.name}:{n}: {linha.strip()}"
        for n, linha in enumerate(DEPLOY_SH.read_text(encoding="utf-8").splitlines(), 1)
        if not linha.strip().startswith("#")
        and "pg_dump" in linha
        and ">" in linha.split("pg_dump", 1)[1]
    ]
    assert not infratores, (
        "Saída de `pg_dump` redirecionada para arquivo: "
        + "; ".join(infratores)
        + ". O shell cria o arquivo antes de o comando rodar, então dump que "
        "falha deixa um backup de zero byte. Use `pg_dump --file=`."
    )


def test_o_backup_pre_deploy_nao_engole_falha() -> None:
    """Falha de backup pré-deploy tem de abortar o deploy, não virar log.

    Um `|| log "Backup skipped"` transforma a ausência de backup em linha de
    log — e a linha seguinte ainda anunciava sucesso. O deploy que vem logo
    depois roda migration.
    """
    _exige_raiz()
    texto = DEPLOY_SH.read_text(encoding="utf-8")
    corpo = texto.split("backup_database()", 1)
    assert len(corpo) == 2, "função `backup_database` sumiu do deploy.sh."
    # Da abertura da função até a próxima função de topo.
    trecho = corpo[1].split("\n}\n", 1)[0]
    assert "Backup skipped" not in trecho, (
        "`backup_database` voltou a engolir a falha com 'Backup skipped'. "
        "Backup que falha em silêncio é pior que backup nenhum: cria a crença "
        "de que existe um."
    )
    assert "error " in trecho or "error(" in trecho, (
        "`backup_database` não chama `error` em nenhum caminho. Se o backup "
        "pré-deploy pode falhar sem abortar o deploy, ele não protege a "
        "migration que vem a seguir — que é a única razão de existir."
    )


def test_o_script_de_backup_para_no_primeiro_erro() -> None:
    """`set -euo pipefail`, sem o qual todo o resto é decorativo."""
    _exige_raiz()
    for script in (BACKUP_SH, VERIFICAR_SH):
        cabecalho = "\n".join(script.read_text(encoding="utf-8").splitlines()[:60])
        assert "set -euo pipefail" in cabecalho, (
            f"`{script.name}` não tem `set -euo pipefail` nas primeiras 60 "
            "linhas. Sem `-e` o script segue depois do erro; sem `-o pipefail` "
            "um `pg_dump | algo` esconde a falha do `pg_dump`."
        )


def test_o_backup_verifica_antes_de_publicar() -> None:
    """A propriedade central: nada aparece no destino sem ter passado no teste.

    Não dá para provar a ordem por leitura estática, mas dá para provar que os
    três controles existem — e o diff de quem remover um deles fica visível.
    """
    _exige_raiz()
    texto = BACKUP_SH.read_text(encoding="utf-8")
    for marca, porque in [
        ("pg_restore -l", "sem ler o índice do dump, arquivo corrompido passa"),
        ("MIN_BYTES_DUMP", "sem piso de tamanho, dump truncado passa"),
        ("sha256sum", "sem checksum, corrupção posterior à gravação passa"),
        (".parcial", "sem publicação atômica, backup pela metade fica com nome de pronto"),
    ]:
        assert marca in texto, (
            f"`{BACKUP_SH.name}` perdeu o controle `{marca}` — {porque}."
        )


def test_o_backup_inclui_papeis_e_uploads() -> None:
    """Dump só do banco restaura processos apontando para arquivos que sumiram.

    E dump sem `--globals-only` restaura num cluster novo até bater no primeiro
    `GRANT ... TO aprimora_app`, com o papel inexistente.
    """
    _exige_raiz()
    texto = BACKUP_SH.read_text(encoding="utf-8")
    assert "--globals-only" in texto, (
        "o backup não salva os papéis globais. Restore em cluster novo morre "
        "nos GRANTs da família SEC (aprimora_app, _worker, _migrator, _platform)."
    )
    assert "uploads" in texto, (
        "o backup não salva os uploads. Anexo não vive no banco: o caminho é "
        "registro, o arquivo é disco."
    )


def test_a_unidade_systemd_nao_ignora_falha() -> None:
    """`ExecStart=-` faz o systemd tratar saída não-zero como sucesso.

    É um caractere. A unidade fica verde para sempre e `systemctl --failed`
    nunca acusa nada — o backup some sem ninguém perceber.
    """
    _exige_raiz()
    for unidade in sorted(UNIDADES.glob("aprimora-backup*.service")):
        for linha in unidade.read_text(encoding="utf-8").splitlines():
            if linha.startswith("ExecStart="):
                assert not linha.startswith("ExecStart=-"), (
                    f"`{unidade.name}` usa `ExecStart=-`, que faz o systemd "
                    "ignorar a falha. A unidade ficaria verde com o backup "
                    "quebrado."
                )


def test_existe_agendamento_habilitavel() -> None:
    """Controle contra verde por vacuidade.

    Sem isto, apagar `deploy/systemd/` inteiro deixaria os testes acima verdes:
    nenhum arquivo, nenhum infrator. E o estado 'sem agendamento' é exatamente
    o que esta guarda foi escrita para não deixar voltar.
    """
    _exige_raiz()
    timers = sorted(UNIDADES.glob("aprimora-backup*.timer"))
    assert timers, (
        "não há nenhum timer de backup em deploy/systemd/. A VPS passou de "
        "24/jul a 05/ago sem backup nenhum exatamente por não haver "
        "agendamento — ver o docstring do módulo."
    )
    for timer in timers:
        texto = timer.read_text(encoding="utf-8")
        assert "[Install]" in texto, (
            f"`{timer.name}` não tem seção [Install]; `systemctl enable` "
            "recusa a unidade e o agendamento nunca passa a valer."
        )
        assert "OnCalendar=" in texto, f"`{timer.name}` não agenda nada."
    diario = [t for t in timers if "verificar" not in t.name]
    assert diario, "não há timer do backup em si, só da verificação."
