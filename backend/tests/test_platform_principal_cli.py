"""SEC-01A — a CLI `app.cli.platform_principal` cumpre o runbook.

A CLI é **contrato operacional**, não conveniência: é o único caminho para
cadastrar o primeiro operador (runbook §2), para cortar acesso (§4) e para o
break-glass (§5). Ela é usada em incidente, por duas pessoas, sob pressão, a
partir de um comando copiado do runbook. Um flag renomeado quebra o
copiar-e-colar exatamente na hora em que ninguém vai improvisar.

Daí a divisão dos testes:

- os de **parser** conferem, literalmente, as linhas de comando que o runbook
  documenta. Falham se alguém "traduzir" um flag;
- os de **comportamento** exercitam `criar`/`revogar`/`break-glass` contra o
  banco, pelo papel `aprimora_platform` — que é o papel que o runbook exige e
  cuja ausência a CLI tem de denunciar em vez de contornar com `ged_user`.

Os corpos assíncronos (`_criar`, `_revogar`, `_break_glass`) são chamados
diretamente: `main()` faz `asyncio.run`, que estoura dentro do loop do pytest.
O que `main()` acrescenta — a montagem do parser — está coberto pelos testes de
parser, então nada fica sem prova.
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fixtures.platform_operator_tokens import TEST_ISSUER

from app.cli import platform_principal as cli


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Parser — as linhas de comando do runbook, literais
# ---------------------------------------------------------------------------


def test_parser_aceita_o_comando_de_bootstrap_do_runbook():
    """Runbook §2, passo 3."""
    args = cli.construir_parser().parse_args(
        [
            "criar",
            "--issuer", "https://accounts.google.com",
            "--subject", "1234567890",
            "--display-label", "operador@exemplo.test",
            "--reason", "bootstrap inicial — TICKET-1",
            "--approved-by", "Fulana",
        ]
    )
    assert args.fn is cli._criar
    assert args.issuer == "https://accounts.google.com"
    assert args.subject == "1234567890"
    assert args.display_label == "operador@exemplo.test"
    assert args.reason.startswith("bootstrap inicial")
    assert args.approved_by == "Fulana"
    assert args.break_glass is False


def test_parser_aceita_o_comando_de_revogacao_do_runbook():
    """Runbook §4."""
    args = cli.construir_parser().parse_args(
        [
            "revogar",
            "--issuer", "https://accounts.google.com",
            "--subject", "1234567890",
            "--reason", "desligamento",
            "--revoked-by", "Beltrano",
        ]
    )
    assert args.fn is cli._revogar
    assert args.revoked_by == "Beltrano"


def test_parser_aceita_os_dois_comandos_de_break_glass_do_runbook():
    """Runbook §5: ativação com `--minutes`/dupla `--approved-by`, e
    `break-glass encerrar` para fechar antes do prazo."""
    parser = cli.construir_parser()
    ativar = parser.parse_args(
        [
            "break-glass",
            "--principal", "7",
            "--minutes", "60",
            "--reason", "incidente X",
            "--approved-by", "Pessoa 1",
            "--approved-by", "Pessoa 2",
        ]
    )
    assert ativar.acao == "ativar"
    assert ativar.principal == 7
    assert ativar.minutes == 60
    assert ativar.approved_by == ["Pessoa 1", "Pessoa 2"]

    encerrar = parser.parse_args(["break-glass", "encerrar", "--principal", "7"])
    assert encerrar.acao == "encerrar"


def test_cli_nao_usa_a_sessao_municipal():
    """Runbook §2, passo 5: "não contornar com `ged_user`".

    `database.SessionLocal` é o pool municipal (`DATABASE_URL`, hoje SUPERUSER).
    Se a CLI o importasse, o procedimento documentado — parar e aplicar a
    migration quando o papel não existe — deixaria de acontecer, porque tudo
    funcionaria em `ged_user` e ninguém notaria.
    """
    assert not hasattr(cli, "SessionLocal"), (
        "a CLI importou `SessionLocal` — é o pool municipal, e usá-lo faria o "
        "cadastro de operador funcionar mesmo sem a migration aplicada"
    )
    assert cli.sessao_plataforma.__module__ == "app.database_plataforma"


# ---------------------------------------------------------------------------
# Comportamento
# ---------------------------------------------------------------------------


@pytest.fixture
def limpeza():
    """Coleta ids criados no teste para remover no fim."""
    return []


@pytest.fixture(autouse=True)
async def _remove_o_que_o_teste_criou(admin_engine, limpeza):
    yield
    if not limpeza:
        return
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "DELETE FROM aprimora_py.platform_audit_log "
                " WHERE platform_principal_id = ANY(:ids)"
            ),
            {"ids": limpeza},
        )
        await s.execute(
            text("DELETE FROM aprimora_py.platform_principal WHERE id = ANY(:ids)"),
            {"ids": limpeza},
        )
        await s.commit()


async def _ler(admin_engine, principal_id: int):
    async with _sm(admin_engine)() as s:
        return (
            await s.execute(
                text(
                    "SELECT ativo, break_glass, valid_until, revogado_em, "
                    "       revogado_por, motivo_revogacao "
                    "  FROM aprimora_py.platform_principal WHERE id = :p"
                ),
                {"p": principal_id},
            )
        ).one()


async def _id_por_subject(admin_engine, subject: str) -> int:
    async with _sm(admin_engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM aprimora_py.platform_principal WHERE subject = :s"),
                    {"s": subject},
                )
            ).scalar_one()
        )


async def test_criar_cadastra_operador_ativo_e_deixa_trilha(
    admin_engine, plataforma_configurada, limpeza
):
    subject = f"cli-{uuid.uuid4().hex[:8]}"
    codigo = await cli._criar(
        argparse.Namespace(
            issuer=TEST_ISSUER,
            subject=subject,
            display_label="operador@test.local",
            reason="teste de CLI",
            approved_by="Testemunha",
            break_glass=False,
        )
    )
    assert codigo == 0
    principal_id = await _id_por_subject(admin_engine, subject)
    limpeza.append(principal_id)

    linha = await _ler(admin_engine, principal_id)
    assert linha.ativo is True, "operador cadastrado tem de já poder entrar (runbook §2.4)"
    assert linha.break_glass is False

    async with _sm(admin_engine)() as s:
        acoes = (
            await s.execute(
                text(
                    "SELECT acao FROM aprimora_py.platform_audit_log "
                    " WHERE platform_principal_id = :p"
                ),
                {"p": principal_id},
            )
        ).scalars().all()
    assert acoes == ["principal.criado"]


async def test_criar_com_break_glass_nasce_inativo(admin_engine, plataforma_configurada, limpeza):
    """ADR §2.8: o principal de emergência é **pré-cadastrado e inativo**.

    Se nascesse ativo, o break-glass deixaria de ser um procedimento com dupla
    aprovação e viraria uma conta permanente esperando ser usada.
    """
    subject = f"cli-bg-{uuid.uuid4().hex[:8]}"
    assert (
        await cli._criar(
            argparse.Namespace(
                issuer=TEST_ISSUER,
                subject=subject,
                display_label="emergencia@test.local",
                reason="pré-cadastro de emergência",
                approved_by="Testemunha",
                break_glass=True,
            )
        )
        == 0
    )
    principal_id = await _id_por_subject(admin_engine, subject)
    limpeza.append(principal_id)
    linha = await _ler(admin_engine, principal_id)
    assert linha.ativo is False
    assert linha.break_glass is True


async def test_criar_duplicado_falha_em_vez_de_reativar(
    admin_engine, plataforma_configurada, limpeza
):
    subject = f"cli-dup-{uuid.uuid4().hex[:8]}"
    ns = argparse.Namespace(
        issuer=TEST_ISSUER,
        subject=subject,
        display_label="x@test.local",
        reason="primeiro",
        approved_by="A",
        break_glass=False,
    )
    assert await cli._criar(ns) == 0
    limpeza.append(await _id_por_subject(admin_engine, subject))
    assert await cli._criar(ns) == 1, (
        "criar duas vezes o mesmo par (iss, sub) não pode passar em silêncio: "
        "reativação silenciosa apagaria o motivo de uma revogação anterior"
    )


async def test_revogar_desativa_e_registra_quem_e_por_que(
    admin_engine, principal_ativo, plataforma_configurada
):
    subject, principal_id = principal_ativo
    codigo = await cli._revogar(
        argparse.Namespace(
            issuer=TEST_ISSUER,
            subject=subject,
            reason="desligamento",
            revoked_by="Gestora",
        )
    )
    assert codigo == 0
    linha = await _ler(admin_engine, principal_id)
    assert linha.ativo is False
    assert linha.revogado_por == "Gestora"
    assert linha.motivo_revogacao == "desligamento"
    # O CHECK `ck_platform_principal_revogacao` exige revogação tudo-ou-nada com
    # `ativo = false`; ter chegado aqui prova que a CLI não deixa estado meio
    # revogado — o que produziria um "revogado" que ainda opera.
    assert linha.revogado_em is not None


async def test_revogar_duas_vezes_falha(admin_engine, principal_ativo, plataforma_configurada):
    subject, _ = principal_ativo
    ns = argparse.Namespace(
        issuer=TEST_ISSUER, subject=subject, reason="m", revoked_by="G"
    )
    assert await cli._revogar(ns) == 0
    assert await cli._revogar(ns) == 1, (
        "a segunda revogação sobrescreveria motivo e autor da primeira"
    )


async def test_break_glass_exige_dupla_aprovacao(
    admin_engine, principal_ativo, plataforma_configurada
):
    """ADR §2.8 / runbook §5.1. Uma aprovação só — inclusive a mesma pessoa
    repetida — não abre a janela."""
    _subject, principal_id = principal_ativo
    for aprovadores in (None, [], ["Só eu"], ["Mesma", "Mesma"]):
        codigo = await cli._break_glass(
            argparse.Namespace(
                acao="ativar",
                principal=principal_id,
                minutes=60,
                reason="incidente",
                approved_by=aprovadores,
            )
        )
        assert codigo == 1, f"aprovadores={aprovadores} abriu break-glass indevidamente"


async def test_break_glass_ativa_com_prazo_e_encerra(
    admin_engine, principal_ativo, plataforma_configurada
):
    _subject, principal_id = principal_ativo
    antes = datetime.utcnow()
    assert (
        await cli._break_glass(
            argparse.Namespace(
                acao="ativar",
                principal=principal_id,
                minutes=60,
                reason="IdP fora do ar + incidente",
                approved_by=["Pessoa 1", "Pessoa 2"],
            )
        )
        == 0
    )
    linha = await _ler(admin_engine, principal_id)
    assert linha.ativo is True and linha.break_glass is True
    assert linha.valid_until is not None
    assert linha.valid_until <= antes + timedelta(minutes=61), (
        "a janela passou de 60 min — o prazo é o que impede o break-glass de "
        "virar acesso permanente"
    )

    assert (
        await cli._break_glass(
            argparse.Namespace(
                acao="encerrar", principal=principal_id, minutes=60, reason="", approved_by=None
            )
        )
        == 0
    )
    linha = await _ler(admin_engine, principal_id)
    assert linha.ativo is False


async def test_break_glass_nao_e_renovavel(admin_engine, principal_ativo, plataforma_configurada):
    """Runbook §5.3: "não renovável — um segundo período exige nova dupla
    aprovação e novo registro". Renovar em cima da janela aberta apagaria o
    prazo original e o registro de que ela existiu."""
    _subject, principal_id = principal_ativo
    ns = argparse.Namespace(
        acao="ativar",
        principal=principal_id,
        minutes=60,
        reason="incidente",
        approved_by=["Pessoa 1", "Pessoa 2"],
    )
    assert await cli._break_glass(ns) == 0
    assert await cli._break_glass(ns) == 1


async def test_break_glass_recusa_prazo_maior_que_60_min(
    admin_engine, principal_ativo, plataforma_configurada
):
    _subject, principal_id = principal_ativo
    codigo = await cli._break_glass(
        argparse.Namespace(
            acao="ativar",
            principal=principal_id,
            minutes=1440,
            reason="incidente",
            approved_by=["Pessoa 1", "Pessoa 2"],
        )
    )
    assert codigo == 1


async def test_sem_platform_db_url_a_cli_para_em_vez_de_contornar(monkeypatch):
    """Runbook §2, passo 5. A CLI **para** e manda aplicar a migration."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_DB_URL", "")
    get_settings.cache_clear()
    try:
        codigo = await cli._executar(argparse.Namespace(fn=cli._listar))
    finally:
        get_settings.cache_clear()
    assert codigo == 1
