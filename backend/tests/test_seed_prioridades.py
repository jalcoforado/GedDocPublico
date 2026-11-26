"""O catálogo de prioridades de encaminhamento vem do `seed_bootstrap`.

`protocolos.encaminhamento.id_prioridade` é NOT NULL com FK, e a tela de
encaminhar lista as prioridades ATIVAS num seletor obrigatório. O catálogo vem
vazio do schema e nenhum seed o preenchia: em banco limpo ninguém tramitava
processo. Nenhum teste via, porque todo teste de tramitação cria a própria
`Prioridade` na fixture — o defeito só existia fora da suíte.

`Prioridade` é catálogo GLOBAL (sem `tenant_id`), compartilhado com os testes
que rodam ao lado. Por isso nada aqui apaga linha que não criou.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_bootstrap import PRIORIDADES_PADRAO, garantir_prioridades


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _ativas(s: AsyncSession) -> int:
    return (
        await s.execute(
            text(
                "SELECT count(*) FROM protocolos.prioridade "
                "WHERE ativo = true AND excluido = false"
            )
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_banco_bootstrapado_tem_prioridade_para_encaminhar(admin_engine):
    """O CI roda o `seed_bootstrap` antes da suíte; se o catálogo estiver vazio
    aqui, está vazio em toda instalação nova."""
    async with _sm(admin_engine)() as s:
        assert await _ativas(s) >= 1, (
            "protocolos.prioridade sem linha ativa — a tela de encaminhar fica "
            "com o seletor vazio e ninguém tramita. Rode o seed_bootstrap."
        )


@pytest.mark.asyncio
async def test_com_catalogo_vazio_o_seed_cria_as_padrao_em_ordem_de_fator(admin_engine):
    """Catálogo vazio de verdade, dentro de uma transação que é desfeita no
    fim: as prioridades existentes são desativadas só para este teste, e o
    `ROLLBACK` devolve tudo como estava."""
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.prioridade SET ativo = false"))
        assert await _ativas(s) == 0

        assert await garantir_prioridades(s) == len(PRIORIDADES_PADRAO)

        # É a consulta da tela (`/catalogo/prioridades`): ativas, por fator.
        nomes = (
            await s.execute(
                text(
                    "SELECT prioridade FROM protocolos.prioridade "
                    "WHERE ativo = true AND excluido = false ORDER BY fator"
                )
            )
        ).scalars().all()
        assert nomes == [n for n, _, _ in PRIORIDADES_PADRAO]
        assert nomes[0] == "Normal", "a primeira opção do seletor tem de ser a Normal"
        await s.rollback()


@pytest.mark.asyncio
async def test_seed_nao_recria_nada_quando_ja_ha_prioridade_ativa(admin_engine):
    """Idempotente, e respeita o catálogo do município: se já existe alguma
    prioridade ativa, o seed não acrescenta as suas por cima."""
    async with _sm(admin_engine)() as s:
        antes = await _ativas(s)
        assert antes >= 1
        assert await garantir_prioridades(s) == 0
        assert await garantir_prioridades(s) == 0
        assert await _ativas(s) == antes
        await s.rollback()
