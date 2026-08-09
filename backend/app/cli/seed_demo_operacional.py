"""CLI de seed demonstrativo dos módulos operacionais — pagamentos, frota e
transporte regulado.

Complementa o `seed_demo`, que cobre protocolo/processos/serviços/anexos. Os
três módulos aqui não tinham seeder nenhum, e por isso a homologação ficava
vazia justamente na parte mais recente do produto (a conciliação bancária da
Onda B, por exemplo, subiu sem um único dado para exercitar).

Uso:
    docker exec aprimora-py-backend python -m app.cli.seed_demo_operacional \\
        status --tenant sobral --allow-non-demo
    ... apply --tenant sobral --allow-non-demo [--modulo pagamentos|frota|transporte|todos]
    ... reset --tenant sobral --allow-non-demo [--modulo ...]

Decisões de projeto:
    - **Passa pelos serviços, não por INSERT cru.** Os débitos percorrem o rito
      de verdade (enviar→validar→encaminhar→autorizar→liberar→pagar), então a
      máquina de 16 status, a segregação de funções, a alçada e o saldo saem
      coerentes — e os pagamentos geram movimentação de conta, que é o que
      alimenta a conciliação.
    - **`session.info["tenant_id"]`, não `SET LOCAL` manual.** Os serviços
      commitam internamente e `SET LOCAL` morre no commit; o listener
      `after_begin` de `database.py` reaplica a cada transação.
    - **Usuários em `@ops.demo.test`.** O `reset` do `seed_demo` apaga
      `utils.usuario` com e-mail `%@demo.test`; se os usuários operacionais
      caíssem nesse filtro, sumiriam levando junto as FKs dos débitos.
    - Marcadores para o `reset` limpar só o que é demo: prefixo `DEMO` em
      códigos/números, CPF/CNPJ nas faixas 99*/998*/997* e placas `DMO*`/`DMR*`,
      e grupo de permissão com nome `Demo — ...`.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..config import get_settings
# SEC-RLS-00B: operação ADMINISTRATIVA, não de runtime. A conexão vem de
# `MIGRATOR_DATABASE_URL` (papel `aprimora_migrator`) quando definida, e de
# `DATABASE_URL` enquanto não estiver — ver `app/database_admin.py`.
from ..database_admin import AdminSessionLocal as SessionLocal
from ..models import (
    Grupo,
    GrupoTransacao,
    Nivel,
    Sistema,
    Tenant,
    Transacao,
    UnidadeTrabalho,
    Usuario,
    UsuarioGrupo,
)

OPS_EMAIL_DOMAIN = "ops.demo.test"
OPS_PASSWORD = "Demo@12345"
DEMO_PREFIX = "DEMO"
MODULOS = ("pagamentos", "frota", "transporte")


# ---------------------------------------------------------------------------
# Catálogo de dados — fonte única
# ---------------------------------------------------------------------------

# (chave, nome, email_local, cargo)
USUARIOS_PAGAMENTOS = [
    ("solicitante", "Rita Nogueira", "pag.solicitante", "Solicitante de Despesa"),
    ("validador", "Paulo Meireles", "pag.validador", "Validador Setorial"),
    ("secretario", "Sônia Bastos", "pag.secretario", "Secretária de Pasta"),
    ("autorizador", "Otávio Prado", "pag.autorizador", "Ordenador de Despesa"),
    ("tesoureiro", "Teresa Cordeiro", "pag.tesoureiro", "Tesoureira"),
]

# chave (de USUARIOS_PAGAMENTOS) -> codigo de utils.transacao que o papel
# precisa pra enxergar sua fila. Sem isso o usuario e criado mas fica sem
# nenhum grupo de permissao — loga e nao ve nada gateado por
# require_permission/require_any_permission (ex.: a fila da tesouraria
# some pra pag.tesoureiro mesmo com o debito autorizado esperando).
TRANSACAO_POR_PAPEL_PAGAMENTOS = {
    "solicitante": "pagamento_solicitar",
    "validador": "pagamento_validar",
    "secretario": "pagamento_gerir",
    "autorizador": "pagamento_autorizar",
    "tesoureiro": "pagamento_pagar",
}

USUARIOS_OPERACAO = [
    ("frota_gestor", "Marcos Aurélio Pinto", "frota.gestor", "Gestor de Frota"),
    ("frota_solicitante", "Luciana Prates", "frota.solicitante", "Assistente Administrativa"),
]

# (codigo, descricao, criticidade)
NATUREZAS = [
    ("3390.30", "Material de Consumo", "MEDIA"),
    ("3390.39", "Outros Serviços de Terceiros — Pessoa Jurídica", "MEDIA"),
    ("4490.52", "Equipamentos e Material Permanente", "ALTA"),
    ("3190.11", "Vencimentos e Vantagens Fixas — Pessoal Civil", "URGENTE"),
]

# (codigo, descricao, grupos, esfera, tipo_vinculacao)
FONTES = [
    ("1500", "Recursos Ordinários (não vinculados)",
     ["CUSTEIO", "INVESTIMENTO", "OUTRAS"], "municipal", "livre"),
    ("1540", "Transferências do FUNDEB",
     ["PESSOAL", "CUSTEIO"], "federal", "vinculada"),
    ("1600", "Transferências Fundo a Fundo — Saúde",
     ["CUSTEIO", "INVESTIMENTO"], "federal", "vinculada"),
]

# (nome, banco, agencia, conta, digito, fonte_codigo, grupo, saldo_inicial, aporte)
CONTAS = [
    ("Conta Movimento — Recursos Ordinários", "Banco do Brasil", "1234-5", "10045", "7",
     "1500", "CUSTEIO", Decimal("120000.00"), Decimal("380000.00")),
    ("Conta Investimentos — Obras", "Banco do Brasil", "1234-5", "10046", "5",
     "1500", "INVESTIMENTO", Decimal("50000.00"), Decimal("450000.00")),
    ("Conta FUNDEB", "Caixa Econômica", "0987", "22310", "1",
     "1540", "PESSOAL", Decimal("200000.00"), Decimal("300000.00")),
    ("Conta Saúde — Fundo Municipal", "Caixa Econômica", "0987", "22311", "9",
     "1600", "CUSTEIO", Decimal("80000.00"), Decimal("220000.00")),
]

# (tipo_pessoa, cnpj_cpf, nome, situacao, motivo)
FORNECEDORES = [
    ("JURIDICA", "99.111.222/0001-05", "Construtora Ipê Amarelo Ltda", "REGULAR", None),
    ("JURIDICA", "99.333.444/0001-16", "Papelaria Central Comércio Ltda", "REGULAR", None),
    ("JURIDICA", "99.555.666/0001-27", "TecnoServiços Informática Ltda", "REGULAR", None),
    ("JURIDICA", "99.777.888/0001-38", "Alimentos Bom Prato Distribuidora", "PENDENTE",
     "Certidão negativa municipal vencida"),
    ("JURIDICA", "99.999.000/0001-49", "Transportes Rio Verde Ltda", "IRREGULAR",
     "Pendência no CADIN municipal"),
    ("FISICA", "99911122233", "José Antônio Ribeiro (MEI)", "REGULAR", None),
]

# (numero, fornecedor_idx, objeto, meses_vigencia, valor_total)
CONTRATOS = [
    ("012/2026", 0, "Reforma da Escola Municipal Vila Nova", 12, Decimal("480000.00")),
    ("027/2026", 1, "Fornecimento de material de expediente", 12, Decimal("96000.00")),
    ("035/2026", 2, "Suporte técnico e manutenção de equipamentos de TI", 24, Decimal("144000.00")),
]

# (nome, obrigatorio, natureza_codigo|None = aplica a todas)
CHECKLIST = [
    ("Nota fiscal ou documento equivalente", True, None),
    ("Atesto de recebimento do bem/serviço", True, None),
    ("Certidões de regularidade fiscal", False, None),
]

# Débitos: (descricao, fornecedor_idx, natureza_idx, fonte_idx, conta_idx,
#           contrato_idx|None, valor, n_parcelas, ate_onde)
# `ate_onde` diz até que ponto do rito o débito é levado.
DEBITOS = [
    ("Aquisição de material de expediente — lote 1", 1, 0, 0, 0, 1,
     Decimal("18400.00"), 2, "rascunho"),
    ("Serviço de dedetização das creches", 2, 1, 0, 0, None,
     Decimal("9600.00"), 1, "rascunho"),
    ("Reforma da quadra poliesportiva — 1ª medição", 0, 2, 0, 1, 0,
     Decimal("87500.00"), 1, "em_validacao"),
    ("Gêneros alimentícios para merenda — março", 3, 0, 1, 2, None,
     Decimal("42300.00"), 2, "em_validacao"),
    ("Locação de veículos para a Secretaria de Saúde", 4, 1, 2, 3, None,
     Decimal("15800.00"), 1, "devolvido"),
    ("Manutenção preventiva dos equipamentos de TI", 2, 1, 0, 0, 2,
     Decimal("12000.00"), 1, "validado"),
    ("Material de limpeza — unidades de saúde", 1, 0, 2, 3, None,
     Decimal("7350.00"), 1, "validado"),
    ("Reforma da Escola Vila Nova — 2ª medição", 0, 2, 0, 1, 0,
     Decimal("124000.00"), 1, "encaminhado"),
    ("Aquisição de mobiliário escolar", 1, 2, 1, 2, None,
     Decimal("63200.00"), 2, "encaminhado"),
    ("Serviços gráficos — campanha de vacinação", 5, 1, 2, 3, None,
     Decimal("8900.00"), 1, "autorizado"),
    ("Suprimentos de informática — 1º trimestre", 2, 0, 0, 0, 2,
     Decimal("21700.00"), 1, "autorizado"),
    ("Material de expediente — reposição", 1, 0, 0, 0, 1,
     Decimal("11250.00"), 1, "pago"),
    ("Manutenção elétrica do prédio da Prefeitura", 2, 1, 0, 0, None,
     Decimal("16480.00"), 1, "pago"),
    ("Aquisição de equipamentos de refrigeração", 0, 2, 2, 3, None,
     Decimal("34900.00"), 1, "suspenso"),
]

# Frota — (placa, marca, modelo, ano, cor, tipo, combustivel, situacao, km)
VEICULOS_FROTA = [
    ("DMO1A01", "Volkswagen", "Gol 1.6", 2021, "Branco", "automovel", "flex", "disponivel", 48230),
    ("DMO1A02", "Chevrolet", "Onix Plus", 2022, "Prata", "automovel", "flex", "disponivel", 31740),
    ("DMO1A03", "Fiat", "Strada Endurance", 2020, "Branco", "caminhonete", "flex", "disponivel", 76510),
    ("DMO1A04", "Renault", "Master 16 lugares", 2019, "Branco", "van", "diesel", "disponivel", 132480),
    ("DMO1A05", "Mercedes-Benz", "Sprinter Ambulância", 2023, "Branco", "ambulancia", "diesel", "disponivel", 18960),
    ("DMO1A06", "Volkswagen", "Constellation Caçamba", 2018, "Amarelo", "caminhao", "diesel", "manutencao", 214300),
    ("DMO1A07", "Toyota", "Hilux CD 4x4", 2022, "Prata", "caminhonete", "diesel", "disponivel", 42115),
    ("DMO1A08", "Iveco", "Daily Escolar", 2017, "Amarelo", "onibus", "diesel", "inativo", 298740),
]

# (nome, cpf, cnh, categoria, anos_validade, situacao)
MOTORISTAS = [
    ("Antônio Carlos Ferreira", "99811122233", "01234567890", "D", 2, "ativo"),
    ("Marli dos Santos Rocha", "99822233344", "01234567891", "AB", 3, "ativo"),
    ("Wagner Ribeiro Alves", "99833344455", "01234567892", "E", 1, "ativo"),
    ("Cleide Nunes Barbosa", "99844455566", "01234567893", "B", 4, "ativo"),
    ("Domingos Sávio Teixeira", "99855566677", "01234567894", "D", 2, "afastado"),
]

# (finalidade, destino, passageiros, precisa_motorista, dias_offset, ate_onde)
SOLICITACOES = [
    ("DEMO Transporte de equipe para vistoria de obra", "Distrito de Aprazível", 4, True, 3, "solicitada"),
    ("DEMO Entrega de merenda nas escolas rurais", "Zona rural — rota norte", 2, True, 2, "solicitada"),
    ("DEMO Deslocamento para capacitação SEDUC", "Fortaleza — CE", 6, True, 5, "aprovada"),
    ("DEMO Remoção de paciente para hospital regional", "Sobral — Santa Casa", 2, True, 0, "em_uso"),
    ("DEMO Visita técnica da equipe de meio ambiente", "Açude Jaibaras", 3, False, -4, "concluida"),
    ("DEMO Transporte de mobiliário entre secretarias", "Centro administrativo", 2, True, 1, "rejeitada"),
]

# Transporte regulado — (nome, cpf, tipo_servico, situacao, categoria_cnh)
PERMISSIONARIOS = [
    ("Raimundo Nonato da Silva", "99711122233", "taxi", "ativo", "B"),
    ("Francisca Edileuza Sousa", "99722233344", "taxi", "ativo", "B"),
    ("Genivaldo Pereira Lima", "99733344455", "mototaxi", "ativo", "A"),
    ("Antônia Célia Vasconcelos", "99744455566", "transporte_escolar", "ativo", "D"),
    ("Josué Martins Cavalcante", "99755566677", "mototaxi", "suspenso", "A"),
    ("Maria do Socorro Freitas", "99766677788", "transporte_escolar", "pendente", "D"),
]

# (placa, marca, modelo, ano, categoria, permissionario_idx, capacidade)
VEICULOS_REGULADOS = [
    ("DMR2B01", "Chevrolet", "Spin", 2021, "automovel", 0, 5),
    ("DMR2B02", "Fiat", "Cronos", 2022, "automovel", 1, 5),
    ("DMR2B03", "Honda", "CG 160 Fan", 2023, "motocicleta", 2, 2),
    ("DMR2B04", "Mercedes-Benz", "Sprinter Escolar", 2019, "van", 3, 20),
    ("DMR2B05", "Yamaha", "Factor 150", 2020, "motocicleta", 4, 2),
    ("DMR2B06", "Volkswagen", "Kombi Escolar", 2015, "van", 5, 12),
]

# (sufixo, permissionario_idx, tipo_servico, dias_ate_validade|None)
# Cobre os quatro estados de KPI: ativo, a_renovar_30d, vencido e indefinido.
ALVARAS = [
    ("001", 0, "taxi", 320),
    ("002", 1, "taxi", 210),
    ("003", 2, "mototaxi", 18),
    ("004", 3, "transporte_escolar", 25),
    ("005", 4, "mototaxi", -45),
    ("006", 5, "transporte_escolar", -12),
    ("007", 0, "taxi", None),
    ("008", 1, "taxi", 95),
]


# ---------------------------------------------------------------------------
# Infra
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _guard_tenant_slug(slug: str, allow_non_demo: bool) -> None:
    """Mesmo guard do `seed_demo`: escreve dados fictícios, então exige o flag
    explícito fora de um tenant `demo*`."""
    if not slug.startswith("demo") and not allow_non_demo:
        print(
            f"[seed_demo_operacional] RECUSADO: tenant '{slug}' não começa com 'demo'.\n"
            f"  Use --allow-non-demo se a intenção é mesmo semear neste tenant.",
            file=sys.stderr,
        )
        sys.exit(2)


async def _tenant_id(db: AsyncSession, slug: str) -> int:
    tid = (
        await db.execute(select(Tenant.id).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tid is None:
        print(f"[seed_demo_operacional] Tenant '{slug}' não existe.", file=sys.stderr)
        sys.exit(3)
    return tid


def _sessao(tenant_id: int) -> AsyncSession:
    """Sessão com o tenant fixado em `info` — o listener `after_begin` reaplica
    `SET LOCAL app.tenant_id` a cada transação, inclusive depois dos commits
    que os serviços fazem por conta própria."""
    db = SessionLocal()
    db.info["tenant_id"] = int(tenant_id)
    return db


async def _unidade_padrao(db: AsyncSession, tenant_id: int) -> int:
    """Primeira unidade do tenant — os contratos e as solicitações precisam de
    uma, e qualquer uma serve para fins de demonstração."""
    uid = (
        await db.execute(
            select(UnidadeTrabalho.id)
            .where(
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
            .order_by(UnidadeTrabalho.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if uid is None:
        print(
            "[seed_demo_operacional] Tenant sem unidade de trabalho. "
            "Rode antes: python -m app.cli.seed_demo apply --tenant <slug> --allow-non-demo",
            file=sys.stderr,
        )
        sys.exit(4)
    return uid


async def _get_or_create_usuario(
    db: AsyncSession, *, tenant_id: int, nome: str, email_local: str, cargo: str,
    cpf: str, id_unidade: int,
) -> tuple[int, bool]:
    email = f"{email_local}@{OPS_EMAIL_DOMAIN}"
    row = (
        await db.execute(
            select(Usuario.id).where(
                Usuario.tenant_id == tenant_id,
                Usuario.email == email,
                Usuario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    u = Usuario(
        tenant_id=tenant_id,
        nome=nome,
        email=email,
        cpf=cpf,
        senha="",
        senha_bcrypt=hash_password(OPS_PASSWORD),
        id_unidade_trabalho=id_unidade,
        ativo=True,
        excluido=False,
        cargo=cargo,
        app=get_settings().app_name,
        must_change_password=False,
    )
    db.add(u)
    await db.flush()
    return u.id, True


async def _garantir_grupo_demo(
    db: AsyncSession, *, tenant_id: int, app_name: str, codigo_transacao: str,
) -> int:
    """Get-or-create um grupo Operacional (nível valor=1) com grant total na
    transação informada, e devolve o id do grupo. Idempotente — seguro de
    rodar em toda chamada de `apply`, inclusive sobre usuário já existente
    de uma rodada anterior do seed.
    """
    transacao = (
        await db.execute(select(Transacao).where(Transacao.codigo == codigo_transacao))
    ).scalar_one()
    nome_grupo = f"Demo — {transacao.transacao}"

    grupo = (
        await db.execute(
            select(Grupo).where(
                Grupo.tenant_id == tenant_id,
                Grupo.grupo == nome_grupo,
                Grupo.excluido.is_(False),
            )
        )
    ).scalars().first()
    if grupo is None:
        nivel_operacional = (
            await db.execute(select(Nivel).where(Nivel.valor == 1).limit(1))
        ).scalar_one()
        sistema_app = (
            await db.execute(select(Sistema).where(Sistema.app == app_name).limit(1))
        ).scalar_one()
        grupo = Grupo(
            tenant_id=tenant_id, id_nivel=nivel_operacional.id,
            id_sistema=sistema_app.id, grupo=nome_grupo, excluido=False,
        )
        db.add(grupo)
        await db.flush()

    tem_grant = (
        await db.execute(
            select(GrupoTransacao.id).where(
                GrupoTransacao.id_grupo == grupo.id,
                GrupoTransacao.id_transacao == transacao.id,
                GrupoTransacao.excluido.is_(False),
            )
        )
    ).scalars().first()
    if tem_grant is None:
        db.add(GrupoTransacao(
            tenant_id=tenant_id, id_grupo=grupo.id, id_transacao=transacao.id,
            inserir=True, atualizar=True, excluir=True, excluido=False,
        ))
        await db.flush()

    return grupo.id


async def _vincular_usuario_grupo(
    db: AsyncSession, *, tenant_id: int, usuario_id: int, grupo_id: int, app_name: str,
) -> None:
    tem_vinculo = (
        await db.execute(
            select(UsuarioGrupo.id).where(
                UsuarioGrupo.tenant_id == tenant_id,
                UsuarioGrupo.id_usuario == usuario_id,
                UsuarioGrupo.id_grupo == grupo_id,
            )
        )
    ).scalars().first()
    if tem_vinculo is None:
        db.add(UsuarioGrupo(
            tenant_id=tenant_id, id_usuario=usuario_id, id_grupo=grupo_id,
            ativo=True, excluido=False, app=app_name,
        ))


async def _criar_usuarios(
    db: AsyncSession, *, tenant_id: int, id_unidade: int, especificacao: list[tuple],
    cpf_base: int, contagens: dict[str, int],
    transacao_por_chave: dict[str, str] | None = None,
) -> dict[str, int]:
    ids: dict[str, int] = {}
    app_name = get_settings().app_name
    for i, (chave, nome, email_local, cargo) in enumerate(especificacao):
        uid, criou = await _get_or_create_usuario(
            db, tenant_id=tenant_id, nome=nome, email_local=email_local,
            cargo=cargo, cpf=str(cpf_base + i)[:11], id_unidade=id_unidade,
        )
        ids[chave] = uid
        if criou:
            contagens["usuarios_criados"] += 1
        if transacao_por_chave and chave in transacao_por_chave:
            grupo_id = await _garantir_grupo_demo(
                db, tenant_id=tenant_id, app_name=app_name,
                codigo_transacao=transacao_por_chave[chave],
            )
            await _vincular_usuario_grupo(
                db, tenant_id=tenant_id, usuario_id=uid, grupo_id=grupo_id,
                app_name=app_name,
            )
    await db.commit()
    return ids


# ---------------------------------------------------------------------------
# Pagamentos
# ---------------------------------------------------------------------------


async def _apply_pagamentos(tenant_id: int, contagens: dict[str, int]) -> None:
    from ..schemas.pagamentos import (
        AlcadaCreate, ChecklistItemCreate, ContaCreate, ContratoCreate,
        DebitoCreate, FonteCreate, FornecedorCreate, ImportarExtratoIn,
        MovimentacaoCreate, NaturezaCreate, ParcelaCreate,
    )
    from ..services import pagamentos_autorizacao as aut_svc
    from ..services import pagamentos_cadastros as cad_svc
    from ..services import pagamentos_caixa as caixa_svc
    from ..services import pagamentos_checklist as chk_svc
    from ..services import pagamentos_conciliacao as conc_svc
    from ..services import pagamentos_debitos as deb_svc

    hoje = date.today()

    async with _sessao(tenant_id) as db:
        id_unidade = await _unidade_padrao(db, tenant_id)
        usuarios = await _criar_usuarios(
            db, tenant_id=tenant_id, id_unidade=id_unidade,
            especificacao=USUARIOS_PAGAMENTOS, cpf_base=99700000000,
            contagens=contagens,
            transacao_por_chave=TRANSACAO_POR_PAPEL_PAGAMENTOS,
        )

        # --- catálogos ---------------------------------------------------
        naturezas: list[int] = []
        existentes = {n.codigo: n.id for n in await cad_svc.listar_naturezas(db, tenant_id=tenant_id)}
        for codigo, descricao, crit in NATUREZAS:
            cod = f"{DEMO_PREFIX}-{codigo}"
            if cod in existentes:
                naturezas.append(existentes[cod])
                continue
            n = await cad_svc.criar_natureza(
                db, tenant_id=tenant_id,
                payload=NaturezaCreate(codigo=cod, descricao=descricao, criticidade_padrao=crit),
            )
            naturezas.append(n.id)
            contagens["naturezas"] += 1

        fontes: list[int] = []
        existentes = {f.codigo: f.id for f in await cad_svc.listar_fontes(db, tenant_id=tenant_id)}
        for codigo, descricao, grupos, esfera, vinc in FONTES:
            cod = f"{DEMO_PREFIX}-{codigo}"
            if cod in existentes:
                fontes.append(existentes[cod])
                continue
            f = await cad_svc.criar_fonte(
                db, tenant_id=tenant_id,
                payload=FonteCreate(
                    codigo=cod, descricao=descricao, grupos_despesa_permitidos=grupos,
                    exercicio=hoje.year, esfera_origem=esfera, tipo_vinculacao=vinc,
                    situacao="ATIVA", vigencia_inicio=date(hoje.year, 1, 1),
                    vigencia_fim=date(hoje.year, 12, 31),
                ),
            )
            fontes.append(f.id)
            contagens["fontes"] += 1

        contas: list[int] = []
        existentes = {c.nome: c.id for c in await cad_svc.listar_contas(db, tenant_id=tenant_id)}
        for nome, banco, ag, num, dig, fonte_cod, grupo, saldo_ini, _aporte in CONTAS:
            nome_demo = f"{DEMO_PREFIX} {nome}"
            if nome_demo in existentes:
                contas.append(existentes[nome_demo])
                continue
            idx_fonte = [c for c, *_ in FONTES].index(fonte_cod)
            c = await cad_svc.criar_conta(
                db, tenant_id=tenant_id,
                payload=ContaCreate(
                    nome=nome_demo, banco=banco, agencia=ag, conta=num, digito=dig,
                    id_fonte_recursos=fontes[idx_fonte], grupo_despesa=grupo,
                    saldo_inicial=saldo_ini, saldo_minimo_alerta=Decimal("10000.00"),
                    modo_movimentacao="PAGA", titularidade="Prefeitura Municipal",
                    data_abertura=date(hoje.year - 2, 1, 15),
                ),
            )
            contas.append(c.id)
            contagens["contas"] += 1

        fornecedores: list[int] = []
        existentes = {f.cnpj_cpf: f.id for f in await cad_svc.listar_fornecedores(db, tenant_id=tenant_id)}
        for tipo, doc, nome, situacao, motivo in FORNECEDORES:
            if doc in existentes:
                fornecedores.append(existentes[doc])
                continue
            f = await cad_svc.criar_fornecedor(
                db, tenant_id=tenant_id,
                payload=FornecedorCreate(
                    tipo_pessoa=tipo, cnpj_cpf=doc, nome=nome,
                    situacao_cadastral=situacao, motivo_pendencia=motivo,
                ),
                usuario_id=usuarios["solicitante"],
            )
            fornecedores.append(f.id)
            contagens["fornecedores"] += 1

        contratos: list[int] = []
        existentes = {c.numero: c.id for c in await cad_svc.listar_contratos(db, tenant_id=tenant_id)}
        for numero, forn_idx, objeto, meses, valor in CONTRATOS:
            num = f"{DEMO_PREFIX}-{numero}"
            if num in existentes:
                contratos.append(existentes[num])
                continue
            c = await cad_svc.criar_contrato(
                db, tenant_id=tenant_id,
                payload=ContratoCreate(
                    numero=num, id_fornecedor=fornecedores[forn_idx], id_unidade=id_unidade,
                    objeto=objeto, vigencia_inicio=hoje - timedelta(days=60),
                    vigencia_fim=hoje + timedelta(days=30 * meses), valor_total=valor,
                ),
            )
            contratos.append(c.id)
            contagens["contratos"] += 1

        # Alçada geral do ordenador — sem ela `autorizar_lote` recusa tudo.
        alcadas = await cad_svc.listar_alcadas(db, tenant_id=tenant_id)
        if not any(a.id_usuario == usuarios["autorizador"] and a.id_natureza is None
                   for a in alcadas):
            await cad_svc.criar_alcada(
                db, tenant_id=tenant_id,
                payload=AlcadaCreate(
                    id_usuario=usuarios["autorizador"], valor_maximo=Decimal("500000.00")
                ),
            )
            contagens["alcadas"] += 1

        itens_chk = {i.descricao: i.id for i in await chk_svc.listar_itens(db, tenant_id=tenant_id)}
        ids_checklist_obrigatorios: list[int] = []
        for ordem, (nome, obrigatorio, _nat) in enumerate(CHECKLIST):
            nome_demo = f"{DEMO_PREFIX} {nome}"
            if nome_demo in itens_chk:
                item_id = itens_chk[nome_demo]
            else:
                item = await chk_svc.criar_item(
                    db, tenant_id=tenant_id,
                    payload=ChecklistItemCreate(
                        descricao=nome_demo, obrigatorio=obrigatorio, ordem=ordem
                    ),
                )
                item_id = item.id
                contagens["checklist_itens"] += 1
            if obrigatorio:
                ids_checklist_obrigatorios.append(item_id)

        # --- aportes: dão saldo às contas antes de qualquer autorização ----
        for idx, (*_resto, aporte) in enumerate(CONTAS):
            extrato = await caixa_svc.listar_extrato(db, tenant_id=tenant_id, conta_id=contas[idx])
            if any(m.origem == "APORTE" for m in extrato):
                continue
            await caixa_svc.lancar_movimentacao(
                db, tenant_id=tenant_id, usuario_id=usuarios["tesoureiro"],
                payload=MovimentacaoCreate(
                    id_conta=contas[idx], tipo="ENTRADA", valor=aporte, origem="APORTE",
                    data=hoje - timedelta(days=45),
                    descricao=f"{DEMO_PREFIX} Repasse duodécimo",
                ),
            )
            contagens["movimentacoes"] += 1

    # --- débitos e o rito ------------------------------------------------
    # Sessão nova por débito: os serviços commitam, e assim uma falha isolada
    # não arrasta os anteriores.
    pagos: list[tuple[int, Decimal, str]] = []  # (id_conta, valor, favorecido)
    for i, (descricao, f_idx, n_idx, fo_idx, c_idx, ct_idx, valor, n_parc, ate) in enumerate(DEBITOS):
        desc = f"{DEMO_PREFIX} {descricao}"
        async with _sessao(tenant_id) as db:
            ja_existe = (
                await db.execute(
                    text(
                        "SELECT id FROM pagamentos.debito "
                        "WHERE tenant_id = :t AND descricao = :d AND excluido = false"
                    ),
                    {"t": tenant_id, "d": desc},
                )
            ).scalar_one_or_none()
            if ja_existe is not None:
                continue

            parcelas = _dividir(valor, n_parc, hoje)
            try:
                deb = await deb_svc.criar_debito(
                    db, tenant_id=tenant_id, usuario_id=usuarios["solicitante"],
                    payload=DebitoCreate(
                        id_fornecedor=fornecedores[f_idx], id_natureza=naturezas[n_idx],
                        id_unidade=id_unidade,
                        id_fonte_recursos=fontes[fo_idx], id_conta=contas[c_idx],
                        id_contrato=contratos[ct_idx] if ct_idx is not None else None,
                        valor_total=valor,
                        competencia=f"{hoje.year:04d}-{hoje.month:02d}",
                        numero_ne=f"{DEMO_PREFIX}NE{2026000 + i}",
                        numero_nf=f"{100000 + i * 37}",
                        descricao=desc,
                        parcelas=[
                            ParcelaCreate(numero=k + 1, valor=v, vencimento=venc)
                            for k, (v, venc) in enumerate(parcelas)
                        ],
                    ),
                )
            except Exception as e:  # noqa: BLE001 — seed não deve abortar por um débito
                print(f"  ! débito '{descricao}' não criado: {e}")
                continue
            contagens["debitos"] += 1

            await _levar_ao_estado(
                db, tenant_id=tenant_id, debito=deb, ate=ate, usuarios=usuarios,
                conta_pagadora=contas[c_idx], id_fonte=fontes[fo_idx],
                itens_obrigatorios=ids_checklist_obrigatorios, contagens=contagens,
                pagos=pagos, favorecido=FORNECEDORES[f_idx][2],
            )

    # --- conciliação bancária (Onda B) -----------------------------------
    if pagos:
        async with _sessao(tenant_id) as db:
            por_conta: dict[int, list[tuple[Decimal, str]]] = {}
            for id_conta, valor, favorecido in pagos:
                por_conta.setdefault(id_conta, []).append((valor, favorecido))
            for id_conta, linhas in por_conta.items():
                nome_arquivo = f"demo-extrato-conta-{id_conta}.csv"
                ja = await conc_svc.listar_extratos(db, tenant_id=tenant_id, id_conta=id_conta)
                if any(e.nome_arquivo == nome_arquivo for e in ja):
                    continue
                corpo = ["data;historico;documento;favorecido;valor;tipo"]
                for k, (valor, favorecido) in enumerate(linhas):
                    corpo.append(
                        f"{(hoje - timedelta(days=2)).strftime('%d/%m/%Y')};"
                        f"PAGAMENTO FORNECEDOR;DOC{9000 + k};{favorecido};{valor};DEBITO"
                    )
                # Uma linha sem contrapartida, de propósito: a tela de
                # conciliação fica mais útil com algo que não casa sozinho.
                corpo.append(
                    f"{(hoje - timedelta(days=1)).strftime('%d/%m/%Y')};"
                    f"TARIFA MANUTENCAO CONTA;TAR001;BANCO;89,90;DEBITO"
                )
                try:
                    await conc_svc.importar_extrato(
                        db, tenant_id=tenant_id, usuario_id=usuarios["tesoureiro"],
                        payload=ImportarExtratoIn(
                            id_conta=id_conta, nome_arquivo=nome_arquivo,
                            formato="CSV", conteudo="\n".join(corpo),
                        ),
                    )
                    contagens["extratos"] += 1
                except Exception as e:  # noqa: BLE001
                    print(f"  ! extrato da conta {id_conta} não importado: {e}")


def _dividir(total: Decimal, n: int, hoje: date) -> list[tuple[Decimal, date]]:
    """Divide em `n` parcelas fechando exatamente no total (a última absorve o
    resto do arredondamento — o envio ao gestor recusa se a soma divergir)."""
    base = (total / n).quantize(Decimal("0.01"))
    parcelas: list[tuple[Decimal, date]] = []
    acumulado = Decimal("0")
    for k in range(n):
        valor = base if k < n - 1 else (total - acumulado)
        acumulado += valor
        parcelas.append((valor, hoje + timedelta(days=15 * (k + 1))))
    return parcelas


async def _levar_ao_estado(
    db: AsyncSession, *, tenant_id: int, debito, ate: str, usuarios: dict[str, int],
    conta_pagadora: int, id_fonte: int, itens_obrigatorios: list[int],
    contagens: dict[str, int], pagos: list, favorecido: str,
) -> None:
    """Percorre o rito real até o estado pedido.

    Cada etapa é a mesma chamada de serviço que a tela faz, então a trilha em
    `pagamento_debito_historico` fica com autores e transições coerentes.
    """
    from ..schemas.pagamentos import GrupoAutorizacaoIn
    from ..services import pagamentos_autorizacao as aut_svc
    from ..services import pagamentos_checklist as chk_svc
    from ..services import pagamentos_debitos as deb_svc

    if ate == "rascunho":
        return

    for item_id in itens_obrigatorios:
        await chk_svc.marcar(
            db, tenant_id=tenant_id, debito_id=debito.id, id_checklist_item=item_id,
            usuario_id=usuarios["solicitante"], marcado=True,
            observacao="Conferido pelo seed de demonstração.",
        )
    await deb_svc.confirmar_liquidacao(
        db, tenant_id=tenant_id, debito_id=debito.id, usuario_id=usuarios["solicitante"]
    )
    debito = await deb_svc.enviar_para_gestor(
        db, tenant_id=tenant_id, debito_id=debito.id,
        usuario_id=usuarios["solicitante"], lock_version=debito.lock_version,
    )
    if ate == "em_validacao":
        return

    if ate == "devolvido":
        await deb_svc.solicitar_ajuste(
            db, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=usuarios["secretario"], lock_version=debito.lock_version,
            etapa="GESTOR",
            justificativa="Nota fiscal ilegível — reenviar digitalização.",
        )
        return

    debito = await deb_svc.gestor_autorizar(
        db, tenant_id=tenant_id, debito_id=debito.id,
        usuario_id=usuarios["secretario"], lock_version=debito.lock_version,
    )
    debito = await deb_svc.validar(
        db, tenant_id=tenant_id, debito_id=debito.id,
        usuario_id=usuarios["validador"], lock_version=debito.lock_version,
    )
    if ate == "validado":
        return

    if ate == "encaminhado":
        return

    if ate == "suspenso":
        await deb_svc.solicitar_ajuste(
            db, tenant_id=tenant_id, debito_id=debito.id,
            usuario_id=usuarios["autorizador"], lock_version=debito.lock_version,
            etapa="AUTORIDADE",
            justificativa="Aguardando parecer da controladoria sobre o enquadramento.",
        )
        return

    await aut_svc.autorizar_lote(
        db, tenant_id=tenant_id, usuario_id=usuarios["autorizador"],
        grupos=[GrupoAutorizacaoIn(
            id_fonte=id_fonte, id_conta_pagadora=conta_pagadora, debito_ids=[debito.id]
        )],
    )
    contagens["ordens_pagamento"] += 1
    if ate == "autorizado":
        return

    parcelas = await deb_svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=debito.id)
    for p in parcelas:
        await aut_svc.liberar_parcelas(
            db, tenant_id=tenant_id, usuario_id=usuarios["autorizador"], parcela_ids=[p.id]
        )
        await aut_svc.pagar_parcela(
            db, tenant_id=tenant_id, usuario_id=usuarios["tesoureiro"], parcela_id=p.id,
            data_pagamento=date.today() - timedelta(days=2), forma_pagamento="PIX",
        )
        contagens["parcelas_pagas"] += 1
        pagos.append((conta_pagadora, p.valor, favorecido))


# ---------------------------------------------------------------------------
# Frota
# ---------------------------------------------------------------------------


async def _apply_frota(tenant_id: int, contagens: dict[str, int]) -> None:
    from ..schemas.frota import (
        MotoristaCreate, SolicitacaoVeiculoCreate, SolicitacaoVeiculoDesignar,
        SolicitacaoVeiculoRegistrarRetorno, SolicitacaoVeiculoRegistrarSaida,
        VeiculoCreate,
    )
    from ..services import frota as frota_svc

    hoje = date.today()
    agora = datetime.now()

    async with _sessao(tenant_id) as db:
        id_unidade = await _unidade_padrao(db, tenant_id)
        usuarios = await _criar_usuarios(
            db, tenant_id=tenant_id, id_unidade=id_unidade,
            especificacao=USUARIOS_OPERACAO, cpf_base=99600000000, contagens=contagens,
        )

        veiculos: dict[str, int] = {}
        for placa, marca, modelo, ano, cor, tipo, comb, situacao, km in VEICULOS_FROTA:
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM frota.veiculo WHERE tenant_id = :t "
                        "AND placa = :p AND excluido = false"
                    ),
                    {"t": tenant_id, "p": placa},
                )
            ).scalar_one_or_none()
            if existe is not None:
                veiculos[placa] = existe
                continue
            v = await frota_svc.criar_veiculo(
                db, tenant_id=tenant_id,
                payload=VeiculoCreate(
                    placa=placa, marca=marca, modelo=modelo, ano_fabricacao=ano,
                    ano_modelo=ano, cor=cor, tipo_veiculo=tipo, tipo_combustivel=comb,
                    situacao=situacao, quilometragem_atual=km,
                    id_unidade_responsavel=id_unidade, forma_posse="proprio",
                    data_aquisicao=date(ano, 3, 10),
                ),
            )
            veiculos[placa] = v.id
            contagens["veiculos_frota"] += 1

        motoristas: list[int] = []
        for nome, cpf, cnh, cat, anos, situacao in MOTORISTAS:
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM frota.motorista WHERE tenant_id = :t "
                        "AND cpf = :c AND excluido = false"
                    ),
                    {"t": tenant_id, "c": cpf},
                )
            ).scalar_one_or_none()
            if existe is not None:
                motoristas.append(existe)
                continue
            m = await frota_svc.criar_motorista(
                db, tenant_id=tenant_id,
                payload=MotoristaCreate(
                    nome=nome, cpf=cpf, cnh_numero=cnh, cnh_categoria=cat,
                    cnh_validade=hoje + timedelta(days=365 * anos), situacao=situacao,
                    id_unidade=id_unidade, matricula=f"MAT{cpf[-5:]}",
                ),
            )
            motoristas.append(m.id)
            contagens["motoristas"] += 1

    # Só os disponíveis entram no rodízio de designação: o serviço recusa
    # veículo em manutenção ou inativo, e a frota demo tem os dois casos.
    placas = [v[0] for v in VEICULOS_FROTA if v[7] == "disponivel"]
    for i, (finalidade, destino, passageiros, precisa_mot, offset, ate) in enumerate(SOLICITACOES):
        async with _sessao(tenant_id) as db:
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM frota.solicitacao_veiculo WHERE tenant_id = :t "
                        "AND finalidade = :f AND excluido = false"
                    ),
                    {"t": tenant_id, "f": finalidade},
                )
            ).scalar_one_or_none()
            if existe is not None:
                continue
            saida = agora + timedelta(days=offset, hours=8)
            try:
                sol = await frota_svc.criar_solicitacao(
                    db, tenant_id=tenant_id,
                    id_usuario_solicitante=usuarios["frota_solicitante"],
                    payload=SolicitacaoVeiculoCreate(
                        id_unidade_solicitante=None, finalidade=finalidade, destino=destino,
                        data_saida_prevista=saida,
                        data_retorno_prevista=saida + timedelta(hours=9),
                        quantidade_passageiros=passageiros,
                        necessita_motorista=precisa_mot,
                    ),
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ! solicitação '{finalidade}' não criada: {e}")
                continue
            contagens["solicitacoes"] += 1

            if ate == "solicitada":
                continue
            if ate == "rejeitada":
                await frota_svc.rejeitar_solicitacao(
                    db, tenant_id=tenant_id, solicitacao_id=sol.id,
                    justificativa="Sem veículo disponível para a data solicitada.",
                )
                continue

            await frota_svc.aprovar_solicitacao(
                db, tenant_id=tenant_id, solicitacao_id=sol.id
            )
            if ate == "aprovada":
                continue

            # Veículo/motorista distintos por solicitação, para não colidir com
            # a regra de disponibilidade do serviço.
            placa = placas[(i + 2) % len(placas)]
            try:
                await frota_svc.designar_solicitacao(
                    db, tenant_id=tenant_id, solicitacao_id=sol.id,
                    id_usuario_designador=usuarios["frota_gestor"],
                    payload=SolicitacaoVeiculoDesignar(
                        id_veiculo=veiculos[placa],
                        id_motorista=motoristas[i % len(motoristas)] if precisa_mot else None,
                        observacoes_designacao="Designação automática do seed de demonstração.",
                    ),
                )
            except Exception as e:  # noqa: BLE001
                print(f"  ! designação de '{finalidade}' falhou: {e}")
                continue
            contagens["designacoes"] += 1

            km_ini = dict((p, k) for p, *_r, k in
                          ((v[0], v[-1]) for v in VEICULOS_FROTA)).get(placa, 0)
            await frota_svc.registrar_saida(
                db, tenant_id=tenant_id, solicitacao_id=sol.id,
                id_usuario_registro=usuarios["frota_gestor"],
                payload=SolicitacaoVeiculoRegistrarSaida(
                    km_saida=km_ini, observacoes_saida="Saída conferida na garagem."
                ),
            )
            if ate == "em_uso":
                continue

            await frota_svc.registrar_retorno(
                db, tenant_id=tenant_id, solicitacao_id=sol.id,
                id_usuario_registro=usuarios["frota_gestor"],
                payload=SolicitacaoVeiculoRegistrarRetorno(
                    km_retorno=km_ini + 180, observacoes_retorno="Veículo devolvido sem avarias."
                ),
            )
            contagens["viagens_concluidas"] += 1


# ---------------------------------------------------------------------------
# Transporte regulado
# ---------------------------------------------------------------------------


async def _apply_transporte(tenant_id: int, contagens: dict[str, int]) -> None:
    from ..schemas.transporte_regulado import (
        AlvaraCreate, PermissionarioCreate, VeiculoReguladoCreate,
    )
    from ..services import transporte_regulado as tr_svc

    hoje = date.today()

    async with _sessao(tenant_id) as db:
        permissionarios: list[int] = []
        for nome, cpf, tipo, situacao, cat in PERMISSIONARIOS:
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM transporte_regulado.permissionario WHERE tenant_id = :t "
                        "AND cpf = :c AND excluido = false"
                    ),
                    {"t": tenant_id, "c": cpf},
                )
            ).scalar_one_or_none()
            if existe is not None:
                permissionarios.append(existe)
                continue
            p = await tr_svc.criar_permissionario(
                db, tenant_id=tenant_id,
                payload=PermissionarioCreate(
                    nome=nome, cpf=cpf, tipo_servico=tipo, situacao=situacao,
                    cnh_numero=f"9{cpf[:10]}", cnh_categoria=cat,
                    cnh_validade=hoje + timedelta(days=540),
                    telefone="(88) 99999-0000",
                    email=f"{cpf}@{OPS_EMAIL_DOMAIN}",
                    numero_permissao=f"{DEMO_PREFIX}-PERM-{cpf[-4:]}",
                    data_inicio_permissao=hoje - timedelta(days=400),
                ),
            )
            permissionarios.append(p.id)
            contagens["permissionarios"] += 1

        for placa, marca, modelo, ano, categoria, perm_idx, capacidade in VEICULOS_REGULADOS:
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM transporte_regulado.veiculo WHERE tenant_id = :t "
                        "AND placa = :p AND excluido = false"
                    ),
                    {"t": tenant_id, "p": placa},
                )
            ).scalar_one_or_none()
            if existe is not None:
                continue
            try:
                await tr_svc.criar_veiculo(
                    db, tenant_id=tenant_id,
                    payload=VeiculoReguladoCreate(
                        id_permissionario=permissionarios[perm_idx], placa=placa,
                        marca=marca, modelo=modelo, ano_fabricacao=ano, ano_modelo=ano,
                        categoria=categoria, tipo_servico=PERMISSIONARIOS[perm_idx][2],
                        capacidade_passageiros=capacidade, tipo_combustivel="flex",
                        situacao="ativo", cor="Branco",
                    ),
                )
                contagens["veiculos_regulados"] += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! veículo regulado {placa} não criado: {e}")

        for sufixo, perm_idx, tipo, dias in ALVARAS:
            numero = f"{DEMO_PREFIX}-ALV-{sufixo}/{hoje.year}"
            existe = (
                await db.execute(
                    text(
                        "SELECT id FROM transporte_regulado.alvara WHERE tenant_id = :t "
                        "AND numero_alvara = :n AND excluido = false"
                    ),
                    {"t": tenant_id, "n": numero},
                )
            ).scalar_one_or_none()
            if existe is not None:
                continue
            validade = hoje + timedelta(days=dias) if dias is not None else None
            # Alvará vencido tem de começar antes de vencer — o schema valida
            # data_inicio <= data_validade.
            inicio = min(hoje - timedelta(days=365), validade) if validade else hoje - timedelta(days=365)
            try:
                await tr_svc.criar_alvara(
                    db, tenant_id=tenant_id,
                    payload=AlvaraCreate(
                        numero_alvara=numero, tipo_servico=tipo,
                        id_permissionario=permissionarios[perm_idx],
                        data_inicio=inicio, data_validade=validade,
                        observacoes="Alvará de demonstração.",
                    ),
                )
                contagens["alvaras"] += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! alvará {numero} não criado: {e}")


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

# Ordem importa: filho antes do pai. Cada entrada é (rótulo, SQL).
# Ordem derivada do grafo real de FKs (pg_constraint), não de suposição.
# Dois pontos não óbvios:
#   - `parcela` e `movimentacao_conta` se referenciam mutuamente; a circularidade
#     se quebra zerando `parcela.id_movimentacao` antes de apagar qualquer um.
#   - `movimentacao_conta` das demo não tem descrição 'DEMO %' quando nasce de
#     `pagar_parcela`, então o filtro alcança também tudo o que pertence às
#     contas demo.
_DEBITOS_DEMO = ("SELECT id FROM pagamentos.debito "
                 "WHERE tenant_id = :t AND descricao LIKE 'DEMO %'")
_CONTAS_DEMO = ("SELECT id FROM pagamentos.conta_bancaria "
                "WHERE tenant_id = :t AND nome LIKE 'DEMO %'")

RESET_PAGAMENTOS = [
    ("conciliacoes", f"""
        DELETE FROM pagamentos.conciliacao WHERE tenant_id = :t
          AND (id_parcela IN (SELECT id FROM pagamentos.parcela
                              WHERE id_debito IN ({_DEBITOS_DEMO}))
               OR id_movimentacao IN (SELECT id FROM pagamentos.movimentacao_conta
                                      WHERE id_conta IN ({_CONTAS_DEMO})))"""),
    ("lancamentos", """
        DELETE FROM pagamentos.lancamento_extrato WHERE tenant_id = :t
          AND id_extrato IN (SELECT id FROM pagamentos.extrato
                             WHERE tenant_id = :t AND nome_arquivo LIKE 'demo-%')"""),
    ("extratos", """
        DELETE FROM pagamentos.extrato WHERE tenant_id = :t
          AND nome_arquivo LIKE 'demo-%'"""),
    ("checklist_marcas", f"""
        DELETE FROM pagamentos.debito_checklist_marca WHERE tenant_id = :t
          AND id_debito IN ({_DEBITOS_DEMO})"""),
    ("historico_debitos", f"""
        DELETE FROM pagamentos.debito_historico WHERE tenant_id = :t
          AND id_debito IN ({_DEBITOS_DEMO})"""),
    ("ordem_pagamento_debito", f"""
        DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id = :t
          AND id_debito IN ({_DEBITOS_DEMO})"""),
    ("parcelas_desvinculadas", f"""
        UPDATE pagamentos.parcela SET id_movimentacao = NULL
         WHERE tenant_id = :t AND id_debito IN ({_DEBITOS_DEMO})"""),
    ("movimentacoes", f"""
        DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id = :t
          AND (descricao LIKE 'DEMO %' OR id_conta IN ({_CONTAS_DEMO})
               OR id_debito IN ({_DEBITOS_DEMO}))"""),
    ("parcelas", f"""
        DELETE FROM pagamentos.parcela WHERE tenant_id = :t
          AND id_debito IN ({_DEBITOS_DEMO})"""),
    ("ordens_pagamento", """
        DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id = :t
          AND NOT EXISTS (SELECT 1 FROM pagamentos.ordem_pagamento_debito od
                          WHERE od.id_ordem = pagamentos.ordem_pagamento.id)"""),
    ("debitos", """
        DELETE FROM pagamentos.debito WHERE tenant_id = :t
          AND descricao LIKE 'DEMO %'"""),
    ("saldo_historico", f"""
        DELETE FROM pagamentos.saldo_historico WHERE tenant_id = :t
          AND id_conta IN ({_CONTAS_DEMO})"""),
    ("bloqueios_saldo", f"""
        DELETE FROM pagamentos.bloqueio_saldo WHERE tenant_id = :t
          AND id_conta IN ({_CONTAS_DEMO})"""),
    ("conta_fonte_historico", f"""
        DELETE FROM pagamentos.conta_fonte_historico WHERE tenant_id = :t
          AND id_conta IN ({_CONTAS_DEMO})"""),
    ("checklist_itens", """
        DELETE FROM pagamentos.checklist_item WHERE tenant_id = :t
          AND descricao LIKE 'DEMO %'"""),
    ("alcadas", """
        DELETE FROM pagamentos.alcada WHERE tenant_id = :t
          AND id_usuario IN (SELECT id FROM utils.usuario WHERE tenant_id = :t
                             AND email LIKE '%@ops.demo.test')"""),
    ("contratos", """
        DELETE FROM pagamentos.contrato WHERE tenant_id = :t
          AND numero LIKE 'DEMO-%'"""),
    ("fornecedor_historico", """
        DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id = :t
          AND id_fornecedor IN (SELECT id FROM pagamentos.fornecedor
                                WHERE tenant_id = :t AND cnpj_cpf LIKE '99%')"""),
    ("fornecedores", """
        DELETE FROM pagamentos.fornecedor WHERE tenant_id = :t
          AND cnpj_cpf LIKE '99%'"""),
    ("contas", """
        DELETE FROM pagamentos.conta_bancaria WHERE tenant_id = :t
          AND nome LIKE 'DEMO %'"""),
    ("fontes", """
        DELETE FROM pagamentos.fonte_recursos WHERE tenant_id = :t
          AND codigo LIKE 'DEMO-%'"""),
    ("naturezas", """
        DELETE FROM pagamentos.natureza_despesa WHERE tenant_id = :t
          AND codigo LIKE 'DEMO-%'"""),
]

RESET_FROTA = [
    ("solicitacoes", """
        DELETE FROM frota.solicitacao_veiculo WHERE tenant_id = :t
          AND finalidade LIKE 'DEMO %'"""),
    ("motoristas", """
        DELETE FROM frota.motorista WHERE tenant_id = :t AND cpf LIKE '998%'"""),
    ("veiculos", """
        DELETE FROM frota.veiculo WHERE tenant_id = :t AND placa LIKE 'DMO%'"""),
]

RESET_TRANSPORTE = [
    ("alvara_veiculos", """
        DELETE FROM transporte_regulado.alvara_veiculo WHERE tenant_id = :t
          AND id_alvara IN (SELECT id FROM transporte_regulado.alvara WHERE tenant_id = :t
                            AND numero_alvara LIKE 'DEMO-ALV-%')"""),
    ("alvara_responsaveis", """
        DELETE FROM transporte_regulado.alvara_responsavel WHERE tenant_id = :t
          AND id_alvara IN (SELECT id FROM transporte_regulado.alvara WHERE tenant_id = :t
                            AND numero_alvara LIKE 'DEMO-ALV-%')"""),
    ("alvara_auditoria", """
        DELETE FROM transporte_regulado.alvara_auditoria WHERE tenant_id = :t
          AND id_alvara IN (SELECT id FROM transporte_regulado.alvara WHERE tenant_id = :t
                            AND numero_alvara LIKE 'DEMO-ALV-%')"""),
    ("alvaras", """
        DELETE FROM transporte_regulado.alvara WHERE tenant_id = :t
          AND numero_alvara LIKE 'DEMO-ALV-%'"""),
    ("veiculos_regulados", """
        DELETE FROM transporte_regulado.veiculo WHERE tenant_id = :t
          AND placa LIKE 'DMR%'"""),
    ("permissionarios", """
        DELETE FROM transporte_regulado.permissionario WHERE tenant_id = :t
          AND cpf LIKE '997%'"""),
]

RESET_USUARIOS = [
    # usuario_grupo referencia grupo E usuario — tem que sair antes dos dois.
    ("usuario_grupo_demo", """
        DELETE FROM utils.usuario_grupo WHERE tenant_id = :t
          AND id_grupo IN (SELECT id FROM utils.grupo WHERE tenant_id = :t
                           AND grupo LIKE 'Demo — %')"""),
    ("grupo_transacao_demo", """
        DELETE FROM utils.grupo_transacao WHERE tenant_id = :t
          AND id_grupo IN (SELECT id FROM utils.grupo WHERE tenant_id = :t
                           AND grupo LIKE 'Demo — %')"""),
    ("grupos_demo", """
        DELETE FROM utils.grupo WHERE tenant_id = :t
          AND grupo LIKE 'Demo — %'"""),
    ("usuarios_ops", """
        DELETE FROM utils.usuario WHERE tenant_id = :t
          AND email LIKE '%@ops.demo.test'"""),
]


async def _executar_reset(
    db: AsyncSession, tenant_id: int, blocos: list[tuple[str, str]],
    contagens: dict[str, int],
) -> None:
    for rotulo, sql in blocos:
        # SAVEPOINT por statement. Sem isso, um erro isolado (FK inesperada,
        # tabela ausente) faz rollback da transação inteira e desfaz tudo o que
        # já tinha sido apagado — o reset reportava sucesso sem ter apagado.
        try:
            async with db.begin_nested():
                res = await db.execute(text(sql), {"t": tenant_id})
                contagens[rotulo] = contagens.get(rotulo, 0) + (res.rowcount or 0)
        except Exception as e:  # noqa: BLE001 — um bloco não deve abortar o reset
            primeira_linha = str(e).splitlines()[0][:180]
            print(f"  ! reset '{rotulo}': {type(e).__name__}: {primeira_linha}")


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def _modulos_selecionados(args: argparse.Namespace) -> tuple[str, ...]:
    return MODULOS if args.modulo == "todos" else (args.modulo,)


async def _apply(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)

    contagens: dict[str, int] = {
        k: 0 for k in (
            "usuarios_criados", "naturezas", "fontes", "contas", "fornecedores",
            "contratos", "alcadas", "checklist_itens", "movimentacoes", "debitos",
            "ordens_pagamento", "parcelas_pagas", "extratos", "veiculos_frota",
            "motoristas", "solicitacoes", "designacoes", "viagens_concluidas",
            "permissionarios", "veiculos_regulados", "alvaras",
        )
    }
    selecionados = _modulos_selecionados(args)
    if "pagamentos" in selecionados:
        await _apply_pagamentos(tid, contagens)
    if "frota" in selecionados:
        await _apply_frota(tid, contagens)
    if "transporte" in selecionados:
        await _apply_transporte(tid, contagens)

    _resumo("APPLY", args.tenant, tid, contagens, selecionados)
    return 0


async def _reset(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    contagens: dict[str, int] = {}
    selecionados = _modulos_selecionados(args)
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)
    async with _sessao(tid) as db:
        if "pagamentos" in selecionados:
            await _executar_reset(db, tid, RESET_PAGAMENTOS, contagens)
        if "frota" in selecionados:
            await _executar_reset(db, tid, RESET_FROTA, contagens)
        if "transporte" in selecionados:
            await _executar_reset(db, tid, RESET_TRANSPORTE, contagens)
        # Usuários por último: os débitos e as solicitações apontam para eles.
        if set(selecionados) == set(MODULOS):
            await _executar_reset(db, tid, RESET_USUARIOS, contagens)
        await db.commit()

    _resumo("RESET", args.tenant, tid, contagens, selecionados)
    return 0


async def _status(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, allow_non_demo=True)  # status não muda nada
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)
    consultas = [
        ("Fornecedores demo", "SELECT count(*) FROM pagamentos.fornecedor "
                              "WHERE tenant_id=:t AND cnpj_cpf LIKE '99%' AND excluido=false"),
        ("Contas demo", "SELECT count(*) FROM pagamentos.conta_bancaria "
                        "WHERE tenant_id=:t AND nome LIKE 'DEMO %' AND excluido=false"),
        ("Débitos demo", "SELECT count(*) FROM pagamentos.debito "
                         "WHERE tenant_id=:t AND descricao LIKE 'DEMO %' AND excluido=false"),
        ("Extratos demo", "SELECT count(*) FROM pagamentos.extrato "
                          "WHERE tenant_id=:t AND nome_arquivo LIKE 'demo-%' AND excluido=false"),
        ("Veículos de frota demo", "SELECT count(*) FROM frota.veiculo "
                                   "WHERE tenant_id=:t AND placa LIKE 'DMO%' AND excluido=false"),
        ("Solicitações demo", "SELECT count(*) FROM frota.solicitacao_veiculo "
                              "WHERE tenant_id=:t AND finalidade LIKE 'DEMO %' AND excluido=false"),
        ("Permissionários demo", "SELECT count(*) FROM transporte_regulado.permissionario "
                                 "WHERE tenant_id=:t AND cpf LIKE '997%' AND excluido=false"),
        ("Alvarás demo", "SELECT count(*) FROM transporte_regulado.alvara "
                         "WHERE tenant_id=:t AND numero_alvara LIKE 'DEMO-ALV-%' AND excluido=false"),
    ]
    print()
    print("=" * 62)
    print(f"STATUS SEED OPERACIONAL — tenant '{args.tenant}' (id={tid})")
    print("=" * 62)
    async with _sessao(tid) as db:
        for rotulo, sql in consultas:
            try:
                n = (await db.execute(text(sql), {"t": tid})).scalar_one()
            except Exception as e:  # noqa: BLE001
                n = f"erro: {e}"
                await db.rollback()
            print(f"  {rotulo:28} {n}")
    print("=" * 62)
    print()
    return 0


def _resumo(acao: str, slug: str, tid: int, contagens: dict[str, Any],
            selecionados: tuple[str, ...]) -> None:
    print()
    print("=" * 62)
    print(f"SEED OPERACIONAL {acao} — tenant '{slug}' (id={tid})")
    print(f"módulos: {', '.join(selecionados)}")
    print("=" * 62)
    for k, v in contagens.items():
        print(f"  {k}: {v}")
    print("=" * 62)
    if acao == "APPLY":
        print()
        print(f"Usuários operacionais (senha {OPS_PASSWORD}):")
        for _chave, nome, email_local, cargo in USUARIOS_PAGAMENTOS + USUARIOS_OPERACAO:
            print(f"  {email_local}@{OPS_EMAIL_DOMAIN:22} {nome} — {cargo}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.cli.seed_demo_operacional", description=__doc__
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _args_comuns(p: argparse.ArgumentParser) -> None:
        p.add_argument("--tenant", required=True, help="slug do tenant alvo")
        p.add_argument(
            "--allow-non-demo", action="store_true",
            help="destrava slugs que não começam com 'demo'",
        )
        p.add_argument(
            "--modulo", choices=(*MODULOS, "todos"), default="todos",
            help="limita a um módulo (padrão: todos)",
        )

    p_status = sub.add_parser("status", help="Mostra o que já existe")
    _args_comuns(p_status)
    p_status.set_defaults(fn=_status)

    p_apply = sub.add_parser("apply", help="Cria os dados (idempotente)")
    _args_comuns(p_apply)
    p_apply.set_defaults(fn=_apply)

    p_reset = sub.add_parser("reset", help="Remove os dados demo dos módulos")
    _args_comuns(p_reset)
    p_reset.set_defaults(fn=_reset)

    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
