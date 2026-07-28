"""Pagamentos Onda C — fatia C1.1: exportação da lista de débitos.

Trava as duas decisões que sustentam a escolha de NÃO adicionar `openpyxl`
para gerar XLSX:
  - separador `;` e BOM UTF-8, que é o que faz o Excel pt-BR abrir o arquivo
    com colunas separadas e acentos corretos;
  - valores monetários com vírgula decimal, senão o Excel os lê como texto.

E o recorte: exportar tem de devolver o MESMO conjunto que a listagem, com os
mesmos filtros — divergir aí é pior que não exportar.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate, NaturezaCreate,
    ParcelaCreate,
)
from app.services import pagamentos_cadastros as cad_svc
from app.services import pagamentos_debitos as deb_svc
from app.services import pagamentos_export as export
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cenario(engine):
    """Tenant com dois débitos em competências diferentes."""
    slug = f"expc1-{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Export C1", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    tid = tenant.id
    hoje = date.today()

    async with _sm(engine)() as db:
        nat = await cad_svc.criar_natureza(
            db, tenant_id=tid,
            payload=NaturezaCreate(codigo="C1-3390", descricao="Material de Consumo"),
        )
        fonte = await cad_svc.criar_fonte(
            db, tenant_id=tid,
            payload=FonteCreate(codigo="C1-1500", descricao="Recursos Ordinários",
                                grupos_despesa_permitidos=["CUSTEIO"]),
        )
        conta = await cad_svc.criar_conta(
            db, tenant_id=tid,
            payload=ContaCreate(nome="Conta C1", banco="BB", agencia="1", conta="1",
                                id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO"),
        )
        forn = await cad_svc.criar_fornecedor(
            db, tenant_id=tid,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf="11.222.333/0001-44",
                                     nome="Açaí & Cia Comércio Ltda"),
        )
    # O provisionamento cria o admin do tenant; é ele que assina os débitos.
    async with _sm(engine)() as db:
        usuario_id = (
            await db.execute(text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                             {"t": tid})
        ).scalar_one()

    ids = []
    for i, (competencia, valor) in enumerate(
        [(f"{hoje.year:04d}-01", Decimal("1234.56")), (f"{hoje.year:04d}-02", Decimal("99.90"))]
    ):
        async with _sm(engine)() as db:
            d = await deb_svc.criar_debito(
                db, tenant_id=tid, usuario_id=usuario_id,
                payload=DebitoCreate(
                    id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
                    id_conta=conta.id, valor_total=valor, competencia=competencia,
                    descricao=f"Compra de material {i}",
                    parcelas=[ParcelaCreate(numero=1, valor=valor,
                                            vencimento=hoje + timedelta(days=30))],
                ),
            )
            ids.append(d.id)
    return tid, ids, competencia


@pytest.mark.asyncio
async def test_csv_abre_no_excel_ptbr(admin_engine):
    """BOM + `;` + vírgula decimal. Sem isso o Excel pt-BR mostra uma coluna
    só, com acentos quebrados e valores como texto."""
    tid, _ids, _c = await _cenario(admin_engine)

    async with _sm(admin_engine)() as db:
        conteudo = await export.csv_debitos(db, tenant_id=tid)

    assert conteudo.startswith("﻿"), "faltou o BOM — Excel leria UTF-8 como ANSI"
    linhas = conteudo.lstrip("﻿").splitlines()
    assert linhas[0].split(";")[:3] == ["id", "status", "competencia"]
    assert "1234,56" in conteudo, "valor tem de sair com vírgula decimal"
    assert "1234.56" not in conteudo
    # Acento preservado (é o que o BOM protege).
    assert "Açaí & Cia Comércio Ltda" in conteudo


@pytest.mark.asyncio
async def test_csv_resolve_fks_em_nomes(admin_engine):
    """Exportar IDs crus seria inútil para quem abre a planilha."""
    tid, _ids, _c = await _cenario(admin_engine)

    async with _sm(admin_engine)() as db:
        conteudo = await export.csv_debitos(db, tenant_id=tid)

    assert "Material de Consumo" in conteudo
    assert "Recursos Ordinários" in conteudo


@pytest.mark.asyncio
async def test_csv_respeita_o_mesmo_filtro_da_listagem(admin_engine):
    """O que o usuário vê é o que ele baixa."""
    tid, _ids, competencia_2 = await _cenario(admin_engine)

    async with _sm(admin_engine)() as db:
        todos = await export.csv_debitos(db, tenant_id=tid)
        filtrado = await export.csv_debitos(db, tenant_id=tid, competencia=competencia_2)
        listagem = await deb_svc.listar_debitos(db, tenant_id=tid, competencia=competencia_2)

    def _linhas(csv_txt: str) -> int:
        return len(csv_txt.lstrip("﻿").strip().splitlines()) - 1  # -1 do cabeçalho

    assert _linhas(todos) == 2
    assert _linhas(filtrado) == len(listagem) == 1


@pytest.mark.asyncio
async def test_nome_do_arquivo_carrega_o_recorte(admin_engine):
    """Três arquivos `debitos.csv` na pasta de Downloads e ninguém sabe qual
    é qual."""
    assert export.nome_arquivo_debitos() == "debitos.csv"
    assert export.nome_arquivo_debitos(status_f="PAGO") == "debitos-pago.csv"
    assert (
        export.nome_arquivo_debitos(status_f="PAGO", competencia="2026-04")
        == "debitos-pago-2026-04.csv"
    )
