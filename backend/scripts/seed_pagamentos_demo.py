"""Seed de dados demo do módulo Pagamentos — 12 meses, ~200 débitos, workflow real.

Uso (dentro do container backend):
    python -m scripts.seed_pagamentos_demo --tenant sobral [--reset]

`--reset` apaga TODOS os dados do módulo pagamentos daquele tenant (fornecedores,
naturezas, fontes, contas, contratos, débitos/parcelas/histórico, ordens de
pagamento, movimentações) em ordem FK-correta e re-semeia do zero. Os usuários
demo (admin/aprovador/autorizador) e o tenant NÃO são apagados.

Sem `--reset`, se já existir massa demo (marcador: natureza `3.3.90.30` ativa
no tenant), o script aborta — rode com `--reset` para limpar e re-semear.

random.seed(42) fixo — reexecuções com --reset produzem a mesma massa
(exceto por elementos ancorados em "hoje", como vencidas/próx. 7-30 dias).

Todo o workflow passa pelos services de domínio (nunca INSERT bruto em
tabelas de negócio) para gerar trilha de auditoria, OPs e movimentações
legítimas. As únicas exceções são a criação/limpeza de usuários demo.
"""
from __future__ import annotations

import argparse
import asyncio
import calendar
import os
import random
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    Grupo, NaturezaDespesa, Nivel, Tenant, UnidadeTrabalho, Usuario, UsuarioGrupo,
)
from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, ContratoCreate, DebitoCreate, FonteCreate,
    FornecedorCreate, MovimentacaoCreate, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_debitos as deb

random.seed(42)

MARCADOR_CODIGO = "3.3.90.30"

# ============================================================================
# Massa de dados literal (spec §1)
# ============================================================================

FORNECEDORES: list[tuple[str, str]] = [
    ("Construtora Rio Acaraú Ltda", "JURIDICA"),
    ("Engenharia Vale do Coreaú S.A.", "JURIDICA"),
    ("Distribuidora Sertão Alimentos Ltda", "JURIDICA"),
    ("Mercado Central Atacadista Eireli", "JURIDICA"),
    ("Laboratório Nova Vida Diagnósticos Ltda", "JURIDICA"),
    ("Farmácia Popular do Ceará Ltda", "JURIDICA"),
    ("Gráfica Municipal Impressos Ltda", "JURIDICA"),
    ("TecnoSistemas Informática Ltda", "JURIDICA"),
    ("DataSoft Soluções em TI Eireli", "JURIDICA"),
    ("Transportadora Litoral Norte Ltda", "JURIDICA"),
    ("Viação São Francisco Transportes Ltda", "JURIDICA"),
    ("Engeobras Construções e Reformas Ltda", "JURIDICA"),
    ("Limpa Cidade Serviços Urbanos Ltda", "JURIDICA"),
    ("EcoLimp Coleta e Limpeza Urbana Eireli", "JURIDICA"),
    ("Posto Combustíveis Acaraú Ltda", "JURIDICA"),
    ("Auto Posto Régia Ltda", "JURIDICA"),
    ("Distribuidora de Medicamentos Ceará Ltda", "JURIDICA"),
    ("Laboratório Análises Clínicas Sobral Ltda", "JURIDICA"),
    ("Papelaria Escolar Nordeste Ltda", "JURIDICA"),
    ("Móveis e Equipamentos Sertanejo Ltda", "JURIDICA"),
    ("Construtora Horizonte Ltda", "JURIDICA"),
    ("Pavimentadora Vale Verde Ltda", "JURIDICA"),
    ("Distribuidora Hospitalar Cariri Ltda", "JURIDICA"),
    ("Uniformes e Confecções Sobral Ltda", "JURIDICA"),
    ("Alimentos Escolares Nordeste Eireli", "JURIDICA"),
    ("Padaria e Panificadora Central Ltda", "JURIDICA"),
    ("Segurança Patrimonial Vale do Acaraú Ltda", "JURIDICA"),
    ("Vigilância Ostensiva Ceará Norte Ltda", "JURIDICA"),
    ("Manutenção Predial Sobral Ltda", "JURIDICA"),
    ("Refrigeração e Climatização Norte Ltda", "JURIDICA"),
    ("Editora e Gráfica Rio Coreaú Ltda", "JURIDICA"),
    ("Consultoria Jurídica Municipal Assoc.", "JURIDICA"),
    ("Assessoria Contábil Pública Ltda", "JURIDICA"),
    ("Locadora de Veículos Sertão Ltda", "JURIDICA"),
    ("Materiais de Construção Vale do Acaraú Ltda", "JURIDICA"),
]
FORNECEDOR_SITUACAO: dict[int, tuple[str, str]] = {
    5: ("PENDENTE", "Certidão de regularidade fiscal (CND) vencida."),
    17: ("PENDENTE", "Cadastro de dados bancários incompleto."),
    23: ("IRREGULAR", "Inadimplência trabalhista apurada em diligência (CNDT)."),
}


def _cnpj(idx: int) -> str:
    n = f"{10000000000000 + idx * 137 + 91:014d}"
    return f"{n[0:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:14]}"


NATUREZAS: list[dict] = [
    {"codigo": "3.3.90.30", "descricao": "Material de consumo", "criticidade_padrao": "MEDIA"},
    {"codigo": "3.3.90.39", "descricao": "Outros serviços de terceiros — pessoa jurídica", "criticidade_padrao": "MEDIA"},
    {"codigo": "3.3.90.36", "descricao": "Outros serviços de terceiros — pessoa física", "criticidade_padrao": "MEDIA"},
    {"codigo": "4.4.90.51", "descricao": "Obras e instalações", "criticidade_padrao": "ALTA"},
    {"codigo": "4.4.90.52", "descricao": "Equipamentos e material permanente", "criticidade_padrao": "ALTA"},
    {"codigo": "3.3.90.14", "descricao": "Diárias — civil", "criticidade_padrao": "BAIXA"},
    {"codigo": "3.3.90.33", "descricao": "Passagens e despesas com locomoção", "criticidade_padrao": "BAIXA"},
    {"codigo": "3.3.90.40", "descricao": "Serviços de tecnologia da informação", "criticidade_padrao": "MEDIA"},
    {"codigo": "3.3.90.46", "descricao": "Auxílio-alimentação", "criticidade_padrao": "MEDIA"},
    {"codigo": "3.3.90.47", "descricao": "Obrigações tributárias e contributivas", "criticidade_padrao": "URGENTE"},
    {"codigo": "3.1.90.11", "descricao": "Vencimentos e vantagens fixas — pessoal civil", "criticidade_padrao": "URGENTE"},
    {"codigo": "3.3.90.92", "descricao": "Despesas de exercícios anteriores", "criticidade_padrao": "BAIXA"},
]

FONTES: list[dict] = [
    {"codigo": "1.500", "descricao": "Recursos próprios não vinculados", "grupos_despesa_permitidos": []},
    {"codigo": "1.540", "descricao": "FUNDEB", "grupos_despesa_permitidos": ["PESSOAL", "CUSTEIO"]},
    {"codigo": "1.600", "descricao": "Receitas do SUS", "grupos_despesa_permitidos": ["CUSTEIO", "INVESTIMENTO"]},
    {"codigo": "1.621", "descricao": "Transferências FNDE", "grupos_despesa_permitidos": ["CUSTEIO", "INVESTIMENTO"]},
    {"codigo": "1.700", "descricao": "Convênios e transferências voluntárias", "grupos_despesa_permitidos": ["INVESTIMENTO", "CUSTEIO"]},
]

# porte: (min, max) da entrada mensal de APORTE; RECEITA usa ~60% da faixa.
CONTAS: list[dict] = [
    {"nome": "Conta Movimento", "banco": "001", "agencia": "1234-5", "conta": "10.001-1",
     "fonte_codigo": "1.500", "grupo_despesa": "CUSTEIO", "saldo_inicial": Decimal("800000.00"),
     "saldo_minimo_alerta": Decimal("100000.00"), "porte": (250000, 500000), "restrita": False,
     "receita_nome": "FPM"},
    {"nome": "Conta Folha", "banco": "001", "agencia": "1234-5", "conta": "10.002-2",
     "fonte_codigo": "1.500", "grupo_despesa": "PESSOAL", "saldo_inicial": Decimal("1200000.00"),
     "saldo_minimo_alerta": Decimal("200000.00"), "porte": (400000, 600000), "restrita": False,
     "receita_nome": "FPM"},
    {"nome": "Conta FUNDEB", "banco": "104", "agencia": "5678-9", "conta": "20.010-3",
     "fonte_codigo": "1.540", "grupo_despesa": "CUSTEIO", "saldo_inicial": Decimal("600000.00"),
     "saldo_minimo_alerta": Decimal("80000.00"), "porte": (150000, 350000), "restrita": False,
     "receita_nome": "FUNDEB"},
    {"nome": "Conta FMS Saúde", "banco": "104", "agencia": "5678-9", "conta": "20.011-4",
     "fonte_codigo": "1.600", "grupo_despesa": "CUSTEIO", "saldo_inicial": Decimal("500000.00"),
     "saldo_minimo_alerta": Decimal("80000.00"), "porte": (150000, 350000), "restrita": False,
     "receita_nome": "SUS"},
    {"nome": "Conta Obras/Convênios", "banco": "033", "agencia": "9012-3", "conta": "30.020-5",
     "fonte_codigo": "1.700", "grupo_despesa": "INVESTIMENTO", "saldo_inicial": Decimal("300000.00"),
     "saldo_minimo_alerta": Decimal("350000.00"), "porte": (0, 0), "restrita": True,
     "receita_nome": "Convênio"},
    {"nome": "Conta Reserva", "banco": "001", "agencia": "1234-5", "conta": "10.003-3",
     "fonte_codigo": "1.500", "grupo_despesa": "OUTRAS", "saldo_inicial": Decimal("2000000.00"),
     "saldo_minimo_alerta": Decimal("300000.00"), "porte": (80000, 200000), "restrita": False,
     "receita_nome": "FPM"},
]

CONTRATOS_OBJETO = [
    "Fornecimento de material de consumo para almoxarifado central",
    "Prestação de serviços de manutenção predial",
    "Fornecimento de merenda escolar",
    "Serviços de tecnologia da informação e suporte",
    "Obras de pavimentação de vias públicas",
    "Fornecimento de medicamentos para rede de saúde",
    "Serviços de limpeza urbana e coleta de resíduos",
    "Locação de veículos para transporte de servidores",
    "Serviços de vigilância patrimonial",
    "Fornecimento de combustíveis para frota municipal",
]

JUSTIFICATIVAS_URGENCIA = [
    "Prazo contratual em risco de multa.",
    "Serviço essencial sem cobertura de estoque.",
    "Risco de interrupção de atendimento à população.",
    "Determinação judicial com prazo exíguo.",
]
JUSTIFICATIVAS_REJEICAO = [
    "Sem dotação orçamentária suficiente.",
    "Nota fiscal divergente do empenho.",
    "Documentação incompleta para liquidação.",
    "Valor acima do praticado em pesquisa de mercado.",
]
JUSTIFICATIVAS_CANCELAMENTO = [
    "Solicitação cancelada pelo requisitante.",
    "Item substituído por outro processo de compra.",
    "Fornecedor não confirmou a entrega/prestação.",
    "Erro de lançamento — duplicidade identificada.",
]
FORMAS_PAGAMENTO = ["PIX", "PIX", "PIX", "TED", "TED", "BOLETO", "DINHEIRO", "OUTRO"]

STATUS_KEYS = ["PAGO", "PAGO_PARCIAL", "AUTORIZADO", "APROVADO",
               "AGUARDANDO_APROVACAO", "RASCUNHO", "REJEITADO", "CANCELADO"]
# Pesos calibrados para o AGREGADO dos 12 meses bater na distribuição da spec §1
# (~65% PAGO, ~8% PAGO_PARCIAL, ~8% AUTORIZADO, ~6% APROVADO, ~5% AGUARDANDO,
# ~4% RASCUNHO, ~4% REJEITADO+CANCELADO): agregado = (10*ANTIGO + RECENTE + ATUAL)/12.
PESOS_ANTIGO = [72, 8, 6, 4, 3, 3, 1, 3]
PESOS_RECENTE = [48, 12, 20, 8, 4, 2, 3, 3]
PESOS_ATUAL = [12, 4, 16, 20, 22, 18, 5, 3]


# ============================================================================
# Helpers de data
# ============================================================================

def _utcnow() -> datetime:
    return datetime.utcnow()


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def mes_range(n: int = 12) -> list[date]:
    hoje = date.today()
    fim = hoje.replace(day=1)
    inicio = add_months(fim, -(n - 1))
    return [add_months(inicio, i) for i in range(n)]


MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro"]


def competencia(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _q2(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ============================================================================
# Engine / sessão (padrão de backend/tests/conftest.py)
# ============================================================================

DB_HOST = os.environ.get("PYTEST_DB_HOST", "ged-saas-project-db-1")
DB_PORT = os.environ.get("PYTEST_DB_PORT", "5432")
DB_NAME = os.environ.get("PYTEST_DB_NAME", "ged_saas_db")
DB_PASS = os.environ.get("PYTEST_DB_PASS", "ged_password_secure_local")
ADMIN_URL = f"postgresql+asyncpg://ged_user:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ============================================================================
# Passo 1 — tenant / atores
# ============================================================================

async def resolve_tenant(db: AsyncSession, slug: str) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
    if tenant is None:
        raise SystemExit(f"Tenant '{slug}' não existe em aprimora_py.tenant.")
    return tenant


async def resolve_admin_id(db: AsyncSession, tenant_id: int) -> int:
    uid = (await db.execute(select(Usuario.id).where(
        Usuario.tenant_id == tenant_id, Usuario.email == "admin@local.test",
        Usuario.excluido.is_(False)))).scalar_one_or_none()
    if uid:
        return uid
    uid = (await db.execute(
        select(Usuario.id).join(UsuarioGrupo, UsuarioGrupo.id_usuario == Usuario.id)
        .join(Grupo, Grupo.id == UsuarioGrupo.id_grupo)
        .join(Nivel, Nivel.id == Grupo.id_nivel)
        .where(Usuario.tenant_id == tenant_id, Usuario.excluido.is_(False),
               UsuarioGrupo.excluido.is_(False), UsuarioGrupo.ativo.is_(True),
               Nivel.valor == 0)
        .order_by(Usuario.id).limit(1))).scalar_one_or_none()
    if uid:
        return uid
    uid = (await db.execute(select(Usuario.id).where(
        Usuario.tenant_id == tenant_id, Usuario.excluido.is_(False))
        .order_by(Usuario.id).limit(1))).scalar_one_or_none()
    if uid is None:
        raise SystemExit(f"Tenant {tenant_id} não tem nenhum usuário — não é possível semear.")
    return uid


async def admin_grupo_id(db: AsyncSession, tenant_id: int, admin_id: int) -> int | None:
    return (await db.execute(select(UsuarioGrupo.id_grupo).where(
        UsuarioGrupo.tenant_id == tenant_id, UsuarioGrupo.id_usuario == admin_id,
        UsuarioGrupo.excluido.is_(False)).order_by(UsuarioGrupo.id).limit(1))).scalar_one_or_none()


async def ensure_actor(db: AsyncSession, *, tenant_id: int, email: str, nome: str,
                        admin: Usuario, admin_grupo: int | None) -> int:
    """Garante um usuário demo (clonando senha/senha_bcrypt/unidade do admin)."""
    uid = (await db.execute(select(Usuario.id).where(
        Usuario.tenant_id == tenant_id, Usuario.email == email,
        Usuario.excluido.is_(False)))).scalar_one_or_none()
    if uid:
        print(f"  ator '{email}' já existe (id={uid}).")
        return uid
    # CPF fictício determinístico: RNG local semeado pelo e-mail — não consome o
    # stream global do random.seed(42) (que deve ficar idêntico com/sem atores já criados).
    rng = random.Random(email)
    cpf = "".join(str(rng.randint(0, 9)) for _ in range(11))
    res = await db.execute(text(
        """INSERT INTO utils.usuario
             (tenant_id, nome, email, senha, senha_bcrypt, cpf, id_unidade_trabalho,
              ativo, excluido, must_change_password, data_criacao)
           VALUES (:t, :n, :e, :senha, :senha_bcrypt, :cpf, :uni, true, false, false, :dc)
           RETURNING id"""),
        {"t": tenant_id, "n": nome, "e": email, "senha": admin.senha,
         "senha_bcrypt": admin.senha_bcrypt, "cpf": cpf,
         "uni": admin.id_unidade_trabalho, "dc": _utcnow()})
    uid = res.scalar_one()
    if admin_grupo is not None:
        await db.execute(text(
            """INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
               VALUES (:t, :u, :g, true, false, :app)"""),
            {"t": tenant_id, "u": uid, "g": admin_grupo, "app": "sistemas"})
    await db.commit()
    print(f"  ator '{email}' criado (id={uid}), clonado de admin (id={admin.id}).")
    return uid


async def ensure_alcada_geral(db: AsyncSession, *, tenant_id: int, usuario_id: int, valor: str) -> None:
    try:
        await cad.criar_alcada(db, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=usuario_id, id_natureza=None, valor_maximo=Decimal(valor)))
        print(f"  alçada geral R$ {valor} criada para usuário {usuario_id}.")
    except Exception as exc:  # HTTPException 409 se já existir
        status_code = getattr(exc, "status_code", None)
        if status_code == 409:
            print(f"  alçada geral já existia para usuário {usuario_id} (409 ignorado).")
        else:
            raise


# ============================================================================
# Marcador de idempotência / --reset
# ============================================================================

async def marca_existe(db: AsyncSession, tenant_id: int) -> bool:
    r = (await db.execute(select(NaturezaDespesa.id).where(
        NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.codigo == MARCADOR_CODIGO,
        NaturezaDespesa.excluido.is_(False)))).scalar_one_or_none()
    return r is not None


async def reset_modulo(db: AsyncSession, tenant_id: int) -> None:
    print(f"--reset: apagando dados do módulo pagamentos do tenant {tenant_id}...")
    stmts = [
        "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
        "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
        "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
        "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
        "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
        "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
        "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
        "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
        "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
        "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
        "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
        "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
        "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
        "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
    ]
    for stmt in stmts:
        r = await db.execute(text(stmt), {"t": tenant_id})
        print(f"  {stmt.split('WHERE')[0].strip()} -> {r.rowcount} linha(s)")
    await db.commit()


# ============================================================================
# Passo 2 — cadastros base
# ============================================================================

async def seed_cadastros(db: AsyncSession, *, tenant_id: int, admin_id: int) -> dict:
    print("Semeando cadastros base...")
    fornecedores = []
    for i, (nome, tipo) in enumerate(FORNECEDORES):
        situacao, motivo = FORNECEDOR_SITUACAO.get(i, ("REGULAR", None))
        f = await cad.criar_fornecedor(db, tenant_id=tenant_id, usuario_id=admin_id, payload=FornecedorCreate(
            tipo_pessoa=tipo, cnpj_cpf=_cnpj(i), nome=nome,
            situacao_cadastral=situacao, motivo_pendencia=motivo))
        fornecedores.append(f)
    print(f"  {len(fornecedores)} fornecedores.")

    naturezas = []
    for n in NATUREZAS:
        naturezas.append(await cad.criar_natureza(db, tenant_id=tenant_id, payload=NaturezaCreate(**n)))
    print(f"  {len(naturezas)} naturezas.")

    fontes_por_codigo: dict[str, object] = {}
    for fo in FONTES:
        fonte = await cad.criar_fonte(db, tenant_id=tenant_id, payload=FonteCreate(**fo))
        fontes_por_codigo[fo["codigo"]] = fonte
    print(f"  {len(fontes_por_codigo)} fontes.")

    contas = []
    for c in CONTAS:
        fonte = fontes_por_codigo[c["fonte_codigo"]]
        conta = await cad.criar_conta(db, tenant_id=tenant_id, payload=ContaCreate(
            nome=c["nome"], banco=c["banco"], agencia=c["agencia"], conta=c["conta"],
            id_fonte_recursos=fonte.id, grupo_despesa=c["grupo_despesa"],
            saldo_minimo_alerta=c["saldo_minimo_alerta"], saldo_inicial=c["saldo_inicial"]))
        contas.append({**c, "obj": conta})
    print(f"  {len(contas)} contas.")

    unidade = (await db.execute(select(UnidadeTrabalho).where(
        UnidadeTrabalho.tenant_id == tenant_id, UnidadeTrabalho.excluido.is_(False))
        .order_by(UnidadeTrabalho.id).limit(1))).scalar_one_or_none()
    if unidade is None:
        raise SystemExit(f"Tenant {tenant_id} não tem unidade_trabalho — não é possível criar contratos.")

    contratos = []
    hoje = date.today()
    for i, objeto in enumerate(CONTRATOS_OBJETO):
        forn = fornecedores[i]
        c = await cad.criar_contrato(db, tenant_id=tenant_id, payload=ContratoCreate(
            numero=f"CT-{2024 + (i % 2)}-{i + 1:03d}", id_fornecedor=forn.id, id_unidade=unidade.id,
            objeto=objeto, vigencia_inicio=add_months(hoje, -18 + i),
            vigencia_fim=add_months(hoje, 12 + i), valor_total=_q2(random.randint(80_000, 900_000))))
        contratos.append(c)
    print(f"  {len(contratos)} contratos.")

    return {
        "fornecedores": fornecedores, "naturezas": naturezas,
        "fontes": fontes_por_codigo, "contas": contas, "contratos": contratos,
        "contrato_por_fornecedor": {c.id_fornecedor: c for c in contratos},
    }


# ============================================================================
# Passo 3 — linha do tempo (12 meses)
# ============================================================================

async def garantir_saldo(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                          conta_id: int, necessario: Decimal, data_ref: date) -> None:
    saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    if saldo.disponivel < necessario:
        falta = _q2((necessario - saldo.disponivel) * Decimal("1.2"))
        await caixa.lancar_movimentacao(db, tenant_id=tenant_id, usuario_id=usuario_id, payload=MovimentacaoCreate(
            id_conta=conta_id, tipo="ENTRADA", origem="RECEITA", valor=falta, data=data_ref,
            descricao="Suplementação orçamentária"))


def sortear_valor() -> Decimal:
    r = random.random()
    if r < 0.60:
        v = random.uniform(800, 5000)
    elif r < 0.85:
        v = random.uniform(5000, 30000)
    elif r < 0.95:
        v = random.uniform(30000, 100000)
    else:
        v = random.uniform(100000, 250000)
    return _q2(v)


def sortear_status(mes_idx: int, n_meses: int) -> str:
    if mes_idx == n_meses - 1:
        pesos = PESOS_ATUAL
    elif mes_idx == n_meses - 2:
        pesos = PESOS_RECENTE
    else:
        pesos = PESOS_ANTIGO
    return random.choices(STATUS_KEYS, weights=pesos, k=1)[0]


def sortear_parcelas(status: str) -> int:
    if status == "PAGO_PARCIAL":
        return random.choices([2, 3, 4], weights=[50, 30, 20], k=1)[0]
    return random.choices([1, 2, 3, 4], weights=[55, 25, 12, 8], k=1)[0]


def montar_parcelas(valor_total: Decimal, n: int, comp: date) -> list[ParcelaCreate]:
    venc1 = comp + timedelta(days=30)
    parte = _q2(valor_total / n)
    valores = [parte] * (n - 1)
    valores.append(valor_total - parte * (n - 1))
    parcelas = []
    for i, v in enumerate(valores):
        parcelas.append(ParcelaCreate(numero=i + 1, valor=v, vencimento=add_months(venc1, i)))
    return parcelas


async def seed_timeline(db: AsyncSession, *, tenant_id: int, cadastros: dict,
                         admin_id: int, aprovador_id: int, autorizador_id: int) -> dict:
    print("Semeando linha do tempo (12 meses)...")
    meses = mes_range(12)
    hoje = date.today()
    contas = cadastros["contas"]
    contas_livres = [c for c in contas if not c["restrita"]]
    fornecedores = cadastros["fornecedores"]
    naturezas = cadastros["naturezas"]
    contrato_por_forn = cadastros["contrato_por_fornecedor"]

    stats = {k: 0 for k in STATUS_KEYS}
    total_debitos = 0

    for mes_idx, mes in enumerate(meses):
        comp = competencia(mes)
        nome_mes = f"{MESES_PT[mes.month - 1]}/{mes.year}"

        # --- entradas do mês (contas não-restritas) ---
        for c in contas_livres:
            data_entrada = mes.replace(day=random.randint(1, 5))
            lo, hi = c["porte"]
            await caixa.lancar_movimentacao(db, tenant_id=tenant_id, usuario_id=admin_id, payload=MovimentacaoCreate(
                id_conta=c["obj"].id, tipo="ENTRADA", origem="APORTE",
                valor=_q2(random.randint(lo, hi)), data=data_entrada,
                descricao=f"Duodécimo {nome_mes}"))
            for _ in range(random.randint(1, 2)):
                data_receita = mes.replace(day=random.randint(1, 5))
                await caixa.lancar_movimentacao(db, tenant_id=tenant_id, usuario_id=admin_id,
                    payload=MovimentacaoCreate(
                        id_conta=c["obj"].id, tipo="ENTRADA", origem="RECEITA",
                        valor=_q2(random.randint(int(lo * 0.4), int(hi * 0.6))), data=data_receita,
                        descricao=f"Transferência {c['receita_nome']} {nome_mes}"))

        # --- débitos do mês ---
        n_debitos = random.randint(15, 20)
        for _ in range(n_debitos):
            status_alvo = sortear_status(mes_idx, len(meses))
            forn_idx = random.randrange(len(fornecedores))
            forn = fornecedores[forn_idx]
            nat = random.choice(naturezas)

            precisa_autorizar = status_alvo in ("AUTORIZADO", "PAGO_PARCIAL", "PAGO")
            pool = contas_livres if precisa_autorizar else contas
            conta = random.choice(pool)

            contrato = contrato_por_forn.get(forn.id)
            id_contrato = contrato.id if (contrato and random.random() < 0.3) else None

            valor = sortear_valor()
            n_parc = sortear_parcelas(status_alvo)
            parcelas = montar_parcelas(valor, n_parc, mes)

            urgente = random.random() < 0.12
            just_urg = random.choice(JUSTIFICATIVAS_URGENCIA) if urgente else None

            payload = DebitoCreate(
                id_fornecedor=forn.id, id_natureza=nat.id, id_conta=conta["obj"].id,
                id_contrato=id_contrato, valor_total=valor, competencia=comp,
                criticidade=nat.criticidade_padrao, urgente=urgente,
                justificativa_urgencia=just_urg,
                descricao=f"Despesa {nat.descricao.lower()} — {forn.nome}"[:255],
                parcelas=parcelas,
            )
            d = await deb.criar_debito(db, tenant_id=tenant_id, usuario_id=admin_id, payload=payload)
            total_debitos += 1

            if status_alvo == "CANCELADO":
                await deb.cancelar(db, tenant_id=tenant_id, debito_id=d.id, usuario_id=admin_id,
                                   justificativa=random.choice(JUSTIFICATIVAS_CANCELAMENTO))
                stats["CANCELADO"] += 1
                continue
            if status_alvo == "RASCUNHO":
                stats["RASCUNHO"] += 1
                continue

            await deb.enviar_aprovacao(db, tenant_id=tenant_id, debito_id=d.id, usuario_id=admin_id)
            if status_alvo == "AGUARDANDO_APROVACAO":
                stats["AGUARDANDO_APROVACAO"] += 1
                continue
            if status_alvo == "REJEITADO":
                await deb.rejeitar(db, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador_id,
                                   justificativa=random.choice(JUSTIFICATIVAS_REJEICAO))
                stats["REJEITADO"] += 1
                continue

            await deb.aprovar(db, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador_id)
            if status_alvo == "APROVADO":
                stats["APROVADO"] += 1
                continue

            await garantir_saldo(db, tenant_id=tenant_id, usuario_id=admin_id,
                                 conta_id=conta["obj"].id, necessario=d.valor_total, data_ref=mes)
            await aut.autorizar_lote(db, tenant_id=tenant_id, usuario_id=autorizador_id,
                                     debito_ids=[d.id])
            if status_alvo == "AUTORIZADO":
                # Fila do ordenador (A_PAGAR não liberadas) x fila da tesouraria (LIBERADA
                # pendente): ~55% dos AUTORIZADO ficam liberados-e-não-pagos (demo da fila
                # de liberação); o restante fica A_PAGAR sem liberação (fila do ordenador).
                if random.random() < 0.35:
                    todas_parcelas = await deb.listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
                    if todas_parcelas:
                        await aut.liberar_parcelas(
                            db, tenant_id=tenant_id, usuario_id=autorizador_id,
                            parcela_ids=[p.id for p in todas_parcelas],
                            data_prevista=todas_parcelas[0].vencimento)
                stats["AUTORIZADO"] += 1
                continue

            todas_parcelas = await deb.listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
            if status_alvo == "PAGO_PARCIAL":
                n_pagar = max(1, len(todas_parcelas) - 1)
                a_pagar = todas_parcelas[:n_pagar]
            else:
                a_pagar = todas_parcelas
            # Segundo ato do rito: libera cada parcela (data_prevista = seu vencimento)
            # antes de pagar — pagar_parcela agora exige status LIBERADA.
            # Sem re-checar saldo aqui: autorizar_lote já validou o disponível e as
            # parcelas A_PAGAR/LIBERADA ficam reservadas via "comprometido" — pagar só
            # converte comprometido em saída, sem reduzir o disponível além do já contabilizado.
            for p in a_pagar:
                await aut.liberar_parcelas(db, tenant_id=tenant_id, usuario_id=autorizador_id,
                                           parcela_ids=[p.id], data_prevista=p.vencimento)
                dt = p.vencimento + timedelta(days=random.randint(-5, 5))
                dt = min(dt, hoje)
                await aut.pagar_parcela(db, tenant_id=tenant_id, usuario_id=autorizador_id,
                                        parcela_id=p.id, forma_pagamento=random.choice(FORMAS_PAGAMENTO),
                                        data_pagamento=dt)
            stats[status_alvo] += 1

        print(f"  {nome_mes}: +{n_debitos} débitos (acumulado {total_debitos}).")

    return {"stats": stats, "total_debitos": total_debitos, "meses": meses}


# ============================================================================
# Passo 4 — resumo final
# ============================================================================

async def imprimir_resumo(db: AsyncSession, *, tenant_id: int, cadastros: dict, stats: dict) -> None:
    print("\n" + "=" * 72)
    print("RESUMO DO SEED")
    print("=" * 72)
    print(f"Fornecedores: {len(cadastros['fornecedores'])}")
    print(f"Naturezas:    {len(cadastros['naturezas'])}")
    print(f"Fontes:       {len(cadastros['fontes'])}")
    print(f"Contas:       {len(cadastros['contas'])}")
    print(f"Contratos:    {len(cadastros['contratos'])}")

    total = stats["total_debitos"]
    print(f"\nDébitos totais: {total}")
    for k in STATUS_KEYS:
        v = stats["stats"][k]
        pct = (v / total * 100) if total else 0
        print(f"  {k:22s} {v:4d}  ({pct:5.1f}%)")

    print("\nSaldo por conta:")
    saldos_negativos = 0
    contas_abaixo_minimo = 0
    for c in cadastros["contas"]:
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=c["obj"].id)
        minimo = c["saldo_minimo_alerta"]
        abaixo = saldo.saldo_atual < minimo
        if abaixo:
            contas_abaixo_minimo += 1
        if saldo.saldo_atual < 0:
            saldos_negativos += 1
        print(f"  {c['nome']:24s} saldo={saldo.saldo_atual:>14,.2f}  "
              f"comprometido={saldo.comprometido:>12,.2f}  disponivel={saldo.disponivel:>14,.2f}"
              f"  {'[ABAIXO DO MÍNIMO]' if abaixo else ''}")

    r = await db.execute(text(
        "SELECT count(*) FROM pagamentos.parcela p JOIN pagamentos.debito d ON d.id = p.id_debito "
        "WHERE p.tenant_id=:t AND p.status='A_PAGAR' AND p.vencimento < :hoje AND p.excluido = false"),
        {"t": tenant_id, "hoje": date.today()})
    vencidas = r.scalar_one()
    print(f"\nParcelas vencidas (A_PAGAR, vencimento < hoje): {vencidas}")

    print("\nParcelas por estado:")
    r = await db.execute(text(
        "SELECT p.status, count(*) FROM pagamentos.parcela p "
        "WHERE p.tenant_id=:t AND p.excluido = false GROUP BY p.status"), {"t": tenant_id})
    parcela_counts = {row[0]: row[1] for row in r.all()}
    for k in ("A_PAGAR", "LIBERADA", "PAGA", "CANCELADA"):
        print(f"  {k:12s} {parcela_counts.get(k, 0):4d}")

    r = await db.execute(text(
        "SELECT count(*) FROM pagamentos.parcela p "
        "WHERE p.tenant_id=:t AND p.status='LIBERADA' AND p.excluido = false"), {"t": tenant_id})
    liberadas_pendentes = r.scalar_one()

    r = await db.execute(text(
        "SELECT count(*) FROM pagamentos.parcela p JOIN pagamentos.debito d ON d.id = p.id_debito "
        "WHERE p.tenant_id=:t AND p.status='A_PAGAR' AND d.status IN ('AUTORIZADO','PAGO_PARCIAL') "
        "AND p.excluido = false"), {"t": tenant_id})
    a_pagar_liberaveis = r.scalar_one()

    print("\nAsserts:")
    ok = True
    if saldos_negativos > 0:
        print(f"  [FALHA] {saldos_negativos} conta(s) com saldo negativo.")
        ok = False
    else:
        print("  [OK] nenhuma conta com saldo negativo.")
    if contas_abaixo_minimo >= 1:
        print(f"  [OK] {contas_abaixo_minimo} conta(s) abaixo do mínimo.")
    else:
        print("  [FALHA] nenhuma conta abaixo do mínimo.")
        ok = False
    if vencidas >= 3:
        print(f"  [OK] {vencidas} parcela(s) vencida(s).")
    else:
        print(f"  [FALHA] apenas {vencidas} parcela(s) vencida(s) (esperado >= 3).")
        ok = False
    if total >= 200:
        print(f"  [OK] {total} débitos (esperado >= 200).")
    else:
        print(f"  [FALHA] apenas {total} débitos (esperado >= 200).")
        ok = False
    if liberadas_pendentes >= 10:
        print(f"  [OK] {liberadas_pendentes} parcela(s) LIBERADA(S) pendente(s) (esperado >= 10).")
    else:
        print(f"  [FALHA] apenas {liberadas_pendentes} parcela(s) LIBERADA(S) pendente(s) (esperado >= 10).")
        ok = False
    if a_pagar_liberaveis >= 20:
        print(f"  [OK] {a_pagar_liberaveis} parcela(s) A_PAGAR liberável(eis) (esperado >= 20).")
    else:
        print(f"  [FALHA] apenas {a_pagar_liberaveis} parcela(s) A_PAGAR liberável(eis) (esperado >= 20).")
        ok = False

    print("=" * 72)
    if not ok:
        raise SystemExit("Seed concluído mas asserts do resumo falharam — ver acima.")


# ============================================================================
# Main
# ============================================================================

async def run(tenant_slug: str, reset: bool) -> None:
    engine = create_async_engine(ADMIN_URL)
    try:
        async with _sm(engine)() as db:
            tenant = await resolve_tenant(db, tenant_slug)
            print(f"Tenant '{tenant_slug}' resolvido: id={tenant.id}.")

            ja_semeado = await marca_existe(db, tenant.id)
            if ja_semeado and not reset:
                raise SystemExit(
                    f"Massa demo já existe no tenant '{tenant_slug}' (natureza {MARCADOR_CODIGO} "
                    "encontrada). Rode novamente com --reset para limpar e re-semear.")
            if reset:
                await reset_modulo(db, tenant.id)

            admin_id = await resolve_admin_id(db, tenant.id)
            admin = (await db.execute(select(Usuario).where(Usuario.id == admin_id))).scalar_one()
            grupo_admin = await admin_grupo_id(db, tenant.id, admin_id)
            print(f"Admin do tenant: id={admin_id} ({admin.email}).")

            aprovador_id = await ensure_actor(db, tenant_id=tenant.id, email="aprovador.pag@local.test",
                                              nome="Aprovador Pagamentos (demo)", admin=admin, admin_grupo=grupo_admin)
            autorizador_id = await ensure_actor(db, tenant_id=tenant.id, email="autorizador.pag@local.test",
                                                nome="Autorizador Pagamentos (demo)", admin=admin, admin_grupo=grupo_admin)
            await ensure_alcada_geral(db, tenant_id=tenant.id, usuario_id=autorizador_id, valor="500000.00")

            cadastros = await seed_cadastros(db, tenant_id=tenant.id, admin_id=admin_id)
            resultado = await seed_timeline(db, tenant_id=tenant.id, cadastros=cadastros,
                                            admin_id=admin_id, aprovador_id=aprovador_id,
                                            autorizador_id=autorizador_id)
            await imprimir_resumo(db, tenant_id=tenant.id, cadastros=cadastros, stats=resultado)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug do tenant (aprimora_py.tenant.slug)")
    parser.add_argument("--reset", action="store_true",
                        help="Apaga a massa demo existente do módulo pagamentos e re-semeia.")
    args = parser.parse_args()
    asyncio.run(run(args.tenant, args.reset))


if __name__ == "__main__":
    main()
