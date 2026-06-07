"""CLI de seed demonstrativo — DEMO-1.

Cria dados de apresentação comercial num tenant dedicado (`demo`), usando
apenas dados fictícios (e-mails `.test`, CPFs reservados, nomes inventados).
Tudo idempotente — re-rodar `apply` é seguro.

Uso:
    docker exec aprimora-py-backend python -m app.cli.seed_demo status --tenant demo
    docker exec aprimora-py-backend python -m app.cli.seed_demo apply  --tenant demo
    docker exec aprimora-py-backend python -m app.cli.seed_demo reset  --tenant demo

Segurança:
    - Por padrão, recusa rodar `apply`/`reset` em qualquer tenant cujo slug NÃO
      comece com `demo` (use `--allow-non-demo` para destravar; existe para
      facilitar dev, não para usar em produção).
    - Senhas demo são fixas (`Demo@12345`) e os usuários nascem **sem**
      `must_change_password` — apresentação não pode parar no fluxo SEC-1.

Detalhes:
    - O tenant `demo` é criado com `provisionar_tenant` (mesmo serviço que o
      CLI `tenant create` usa); admin inicial é `admin@demo.test`.
    - Os 12 processos da demo cobrem todos os estados de prazo / checklist /
      complementação / anexo. Datas são offsets relativos a `now()` para
      manter realismo perene; rode `apply` de novo se a janela passar.
    - Cada processo demo grava marcador no campo `numero_origem`
      (`demo-<slug>-<seq>`) — é por isso que `reset` consegue limpar só o
      demo sem tocar em outros dados do tenant.
    - Anexos PDF são gerados em RAM via `reportlab` (já dep do projeto),
      gravados em `uploads/`, com rodapé "DOCUMENTO DEMO — não usar".
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..database import SessionLocal
from ..models import (
    Acao,
    Anexo,
    AnexoProcesso,
    Assunto,
    ComplementacaoDocumental,
    EspecieDocumental,
    Grupo,
    Manifestante,
    Movimentacao,
    Processo,
    Servico,
    Tenant,
    TipoAnexo,
    TipoManifestante,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
    UsuarioGrupo,
)
from ..services.provisioning_tenant import (
    ProvisioningError,
    provisionar_tenant,
)

DEMO_SLUG_PREFIX = "demo"
DEMO_PASSWORD = "Demo@12345"
DEMO_EMAIL_DOMAIN = "demo.test"
DEMO_CIDADAO_EMAIL_DOMAIN = "cidadao.demo.test"
DEMO_ORIGEM_PREFIX = "demo-"


# ---------------------------------------------------------------------------
# Catálogo de dados — fonte única
# ---------------------------------------------------------------------------

UNIDADES = [
    # ("nome", "sigla")
    ("Secretaria de Obras", "SOB"),
    ("Secretaria de Meio Ambiente", "SMA"),
    ("Secretaria de Administração", "SAD"),
    ("Departamento de Iluminação Pública", "DIP"),
]

SERVIDORES = [
    # ("nome", "email_local", "lotacao_sigla", "cargo")
    ("Ana Costa", "ana.obras", "SOB", "Analista de Obras"),
    ("Bruno Lima", "bruno.protocolo", "PG", "Servidor de Protocolo"),
    ("Carla Souza", "carla.ambiente", "SMA", "Analista Ambiental"),
]

SERVICOS: list[dict[str, Any]] = [
    {
        "slug": "demo-poda-arvore",
        "nome": "Solicitação de Poda de Árvore",
        "descricao_curta": "Pedido de poda ou remoção de árvore em via pública.",
        "descricao_detalhada": (
            "Solicite a poda de árvore que esteja oferecendo risco, "
            "interferindo em fiação elétrica ou prejudicando a iluminação "
            "pública. A equipe de Meio Ambiente fará vistoria antes do serviço."
        ),
        "instrucoes_cidadao": (
            "Anexe foto da árvore com referência de tamanho (pessoa ou veículo "
            "ao lado) e comprovante de residência."
        ),
        "documentos_exigidos": [
            {"nome": "Foto da árvore", "obrigatorio": True},
            {"nome": "Comprovante de residência", "obrigatorio": True},
        ],
        "prazo_estimado_dias": 10,
        "categoria": "Meio Ambiente",
        "destaque": True,
        "ordem_exibicao": 10,
        "unidade_sigla": "SMA",
    },
    {
        "slug": "demo-alvara-funcionamento",
        "nome": "Alvará de Funcionamento",
        "descricao_curta": "Solicitação de alvará para abertura ou regularização de estabelecimento comercial.",
        "descricao_detalhada": (
            "Emissão de alvará de funcionamento para estabelecimentos "
            "comerciais. Aplica-se a novos negócios e a renovações."
        ),
        "instrucoes_cidadao": (
            "Tenha em mãos CNPJ, contrato social e planta baixa do "
            "estabelecimento. O processo é analisado por Administração."
        ),
        "documentos_exigidos": [
            {"nome": "CNPJ", "obrigatorio": True},
            {"nome": "Contrato social", "obrigatorio": True},
            {"nome": "Planta baixa", "obrigatorio": True},
        ],
        "prazo_estimado_dias": 30,
        "categoria": "Empresas",
        "destaque": True,
        "ordem_exibicao": 20,
        "unidade_sigla": "SAD",
    },
    {
        "slug": "demo-iluminacao-publica",
        "nome": "Solicitação de Iluminação Pública",
        "descricao_curta": "Reparo ou implantação de ponto de iluminação pública.",
        "descricao_detalhada": (
            "Solicite reparo de poste apagado, troca de lâmpada queimada ou "
            "implantação de novo ponto de iluminação."
        ),
        "instrucoes_cidadao": (
            "Informe o endereço completo e, se possível, o número do poste."
        ),
        "documentos_exigidos": None,
        "prazo_estimado_dias": 15,
        "categoria": "Infraestrutura",
        "destaque": False,
        "ordem_exibicao": 30,
        "unidade_sigla": "DIP",
    },
    {
        "slug": "demo-ouvidoria",
        "nome": "Manifestação à Ouvidoria",
        "descricao_curta": "Reclamação, sugestão, elogio ou denúncia.",
        "descricao_detalhada": (
            "Canal aberto para o cidadão registrar manifestação geral. "
            "Toda manifestação recebe número de protocolo e prazo de retorno."
        ),
        "instrucoes_cidadao": (
            "Descreva o ocorrido com o máximo de detalhes. Identificação é "
            "opcional para denúncias."
        ),
        "documentos_exigidos": None,
        "prazo_estimado_dias": 20,
        "categoria": "Atendimento",
        "destaque": True,
        "ordem_exibicao": 5,
        "unidade_sigla": "PG",
    },
    {
        "slug": "demo-evento-publico",
        "nome": "Licença para Evento Público",
        "descricao_curta": "Autorização para realização de evento em via ou local público.",
        "descricao_detalhada": (
            "Autorização prévia para eventos com público estimado em via "
            "pública, praças ou logradouros municipais. Prazo curto: 3 dias."
        ),
        "instrucoes_cidadao": (
            "Anexe termo de responsabilidade e plano de segurança do evento "
            "(rota de fuga, equipe, atendimento médico)."
        ),
        "documentos_exigidos": [
            {"nome": "Termo de responsabilidade", "obrigatorio": True},
            {"nome": "Plano de segurança", "obrigatorio": True},
        ],
        "prazo_estimado_dias": 3,
        "categoria": "Eventos",
        "destaque": True,
        "ordem_exibicao": 15,
        "unidade_sigla": "SAD",
    },
    {
        "slug": "demo-certidao-administrativa",
        "nome": "Certidão Administrativa",
        "descricao_curta": "Emissão de certidão de regularidade administrativa.",
        "descricao_detalhada": (
            "Certidão atestando regularidade do cidadão perante o município "
            "(tributos, restrições)."
        ),
        "instrucoes_cidadao": (
            "Anexe documento de identidade. A certidão é emitida em PDF "
            "assinado digitalmente."
        ),
        "documentos_exigidos": [
            {"nome": "Documento de identidade", "obrigatorio": True},
        ],
        "prazo_estimado_dias": 5,
        "categoria": "Administração",
        "destaque": False,
        "ordem_exibicao": 25,
        "unidade_sigla": "SAD",
    },
]

# CPFs com prefixo 999 (gerados com dígito verificador válido — necessário
# pra passar pelo backend caso ele valide; reservados na prática).
MANIFESTANTES = [
    # (nome, cpf, email_local)
    ("Maria Silva Aparecida", "99900000017", "maria.silva"),
    ("João Santos Oliveira", "99900000025", "joao.santos"),
    ("Ana Pereira Souza", "99900000033", "ana.pereira"),
    ("Carlos Lima Costa", "99900000041", "carlos.lima"),
    ("Beatriz Almeida Ramos", "99900000050", "beatriz.almeida"),
    ("Eduardo Rocha Nunes", "99900000068", "eduardo.rocha"),
    ("Fernanda Dias Moraes", "99900000076", "fernanda.dias"),
    ("Gabriel Castro Pinto", "99900000084", "gabriel.castro"),
    ("Helena Vasconcelos Lopes", "99900000092", "helena.lopes"),
    ("Igor Mendes Barbosa", "99900000106", "igor.mendes"),
    ("Julia Carvalho Tavares", "99900000114", "julia.carvalho"),
    ("Lucas Ferreira Andrade", "99900000122", "lucas.ferreira"),
]

# Processos: cada um cobre um cenário do dashboard / fluxo.
# `dias_atras` define quando o processo foi aberto (offset relativo a now()).
# `numero_origem` é o identificador estável do seed (idempotência + reset).
PROCESSOS: list[dict[str, Any]] = [
    # 1. Recém-aberto: poda, sem mov adicional, dentro do prazo.
    {
        "origem": "demo-poda-001",
        "servico_slug": "demo-poda-arvore",
        "manifestante_idx": 0,
        "dias_atras": 0,
        "estado": "aberto",
        "anexar_docs": False,
        "complementacao": None,
    },
    # 2. Alvará com docs incompletos (1 dos 3 anexados).
    {
        "origem": "demo-alvara-002",
        "servico_slug": "demo-alvara-funcionamento",
        "manifestante_idx": 1,
        "dias_atras": 3,
        "estado": "aberto",
        "anexar_docs": "parcial",  # vincula só 1 dos 3 docs exigidos
        "complementacao": None,
    },
    # 3. Alvará com checklist completo (3 dos 3).
    {
        "origem": "demo-alvara-003",
        "servico_slug": "demo-alvara-funcionamento",
        "manifestante_idx": 2,
        "dias_atras": 5,
        "estado": "aberto",
        "anexar_docs": "total",
        "complementacao": None,
    },
    # 4. Poda com complementação ABERTA aguardando cidadão.
    {
        "origem": "demo-poda-004",
        "servico_slug": "demo-poda-arvore",
        "manifestante_idx": 3,
        "dias_atras": 2,
        "estado": "aberto",
        "anexar_docs": False,
        "complementacao": "aberta",
    },
    # 5. Poda com complementação RESPONDIDA.
    {
        "origem": "demo-poda-005",
        "servico_slug": "demo-poda-arvore",
        "manifestante_idx": 4,
        "dias_atras": 4,
        "estado": "aberto",
        "anexar_docs": "total",
        "complementacao": "respondida",
    },
    # 6. Iluminação — dentro do prazo (verde). Aberto há 5d, prazo 15d.
    {
        "origem": "demo-ilum-006",
        "servico_slug": "demo-iluminacao-publica",
        "manifestante_idx": 5,
        "dias_atras": 5,
        "estado": "aberto",
        "anexar_docs": False,
        "complementacao": None,
    },
    # 7. Evento — VENCENDO. Aberto há 2d, prazo 3d (faltam 1d).
    {
        "origem": "demo-evento-007",
        "servico_slug": "demo-evento-publico",
        "manifestante_idx": 6,
        "dias_atras": 2,
        "estado": "aberto",
        "anexar_docs": "total",
        "complementacao": None,
    },
    # 8. Ouvidoria — ATRASADO. Aberto há 25d, prazo 20d.
    {
        "origem": "demo-ouv-008",
        "servico_slug": "demo-ouvidoria",
        "manifestante_idx": 7,
        "dias_atras": 25,
        "estado": "aberto",
        "anexar_docs": False,
        "complementacao": None,
    },
    # 9. Certidão — CONCLUÍDO NO PRAZO. Aberto há 4d, prazo 5d, fechado há 1d.
    {
        "origem": "demo-cert-009",
        "servico_slug": "demo-certidao-administrativa",
        "manifestante_idx": 8,
        "dias_atras": 4,
        "estado": "concluido",
        "concluido_dias_atras": 1,
        "anexar_docs": "total",
        "complementacao": None,
    },
    # 10. Poda — CONCLUÍDO ATRASADO. Aberto há 20d, prazo 10d, fechado há 2d.
    {
        "origem": "demo-poda-010",
        "servico_slug": "demo-poda-arvore",
        "manifestante_idx": 9,
        "dias_atras": 20,
        "estado": "concluido",
        "concluido_dias_atras": 2,
        "anexar_docs": "total",
        "complementacao": None,
    },
    # 11. Certidão — concluído + 1 anexo (servirá pra demo de assinatura manual).
    {
        "origem": "demo-cert-011",
        "servico_slug": "demo-certidao-administrativa",
        "manifestante_idx": 10,
        "dias_atras": 3,
        "estado": "concluido",
        "concluido_dias_atras": 0,
        "anexar_docs": "total",
        "complementacao": None,
        "marcar_para_assinatura": True,
    },
    # 12. Alvará com anexos PDFs.
    {
        "origem": "demo-alvara-012",
        "servico_slug": "demo-alvara-funcionamento",
        "manifestante_idx": 11,
        "dias_atras": 7,
        "estado": "aberto",
        "anexar_docs": "total",
        "complementacao": None,
    },
]


# ---------------------------------------------------------------------------
# Salvaguardas
# ---------------------------------------------------------------------------


def _guard_tenant_slug(slug: str, allow_non_demo: bool) -> None:
    """Recusa rodar em slug que não comece com `demo` salvo override."""
    if not slug.startswith(DEMO_SLUG_PREFIX) and not allow_non_demo:
        print(
            f"[ERRO] tenant slug '{slug}' não começa com 'demo'. Para evitar "
            "estragar tenants reais, este comando recusa rodar fora de slugs "
            "demo-* sem `--allow-non-demo`."
        )
        sys.exit(2)


async def _set_local_tenant(db: AsyncSession, tenant_id: int) -> None:
    """SET LOCAL app.tenant_id — necessário para inserts tenant-scoped sob RLS."""
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))


# ---------------------------------------------------------------------------
# Geração de PDF demo (reportlab — já dep do projeto)
# ---------------------------------------------------------------------------


def _gerar_pdf_demo(titulo: str, corpo: str) -> bytes:
    """PDF sintético pequeno (~3 KB), com rodapé claro de demo."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=titulo)
    story = [
        Paragraph(titulo, styles["Title"]),
        Spacer(1, 12),
        Paragraph(corpo, styles["BodyText"]),
        Spacer(1, 30),
        Paragraph(
            "<b>DOCUMENTO DEMO — não usar em produção</b>", styles["Italic"]
        ),
    ]
    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Idempotência: helpers de "pega ou cria"
# ---------------------------------------------------------------------------


async def _get_or_create_tipo_unidade(
    db: AsyncSession, *, tenant_id: int, nome: str, codigo: str
) -> tuple[int, bool]:
    from ..models import TipoUnidadeTrabalho

    row = (
        await db.execute(
            select(TipoUnidadeTrabalho.id).where(
                TipoUnidadeTrabalho.tenant_id == tenant_id,
                TipoUnidadeTrabalho.tipo_unidade_trabalho == nome,
                TipoUnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    tu = TipoUnidadeTrabalho(
        tenant_id=tenant_id, tipo_unidade_trabalho=nome, codigo=codigo
    )
    db.add(tu)
    await db.flush()
    return tu.id, True


async def _get_or_create_unidade(
    db: AsyncSession,
    *,
    tenant_id: int,
    nome: str,
    sigla: str,
    id_tipo_unidade: int,
) -> tuple[int, bool]:
    row = (
        await db.execute(
            select(UnidadeTrabalho.id).where(
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.unidade_trabalho == nome,
                UnidadeTrabalho.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    u = UnidadeTrabalho(
        tenant_id=tenant_id,
        unidade_trabalho=nome,
        sigla=sigla,
        id_tipo_unidade_trabalho=id_tipo_unidade,
        excluido=False,
    )
    db.add(u)
    await db.flush()
    return u.id, True


async def _get_or_create_tipo_processo(
    db: AsyncSession, *, tenant_id: int, nome: str
) -> tuple[int, bool]:
    row = (
        await db.execute(
            select(TipoProcesso.id).where(
                TipoProcesso.tenant_id == tenant_id,
                TipoProcesso.tipo_processo == nome,
                TipoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    tp = TipoProcesso(
        tenant_id=tenant_id, tipo_processo=nome, exige_processo_pai=False
    )
    db.add(tp)
    await db.flush()
    return tp.id, True


async def _get_or_create_assunto(
    db: AsyncSession, *, tenant_id: int, nome: str, id_tipo_processo: int
) -> tuple[int, bool]:
    row = (
        await db.execute(
            select(Assunto.id).where(
                Assunto.tenant_id == tenant_id,
                Assunto.assunto == nome,
                Assunto.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    a = Assunto(
        tenant_id=tenant_id,
        assunto=nome,
        id_tipo_processo=id_tipo_processo,
        exige_processo_pai=False,
    )
    db.add(a)
    await db.flush()
    return a.id, True


async def _get_or_create_tipo_anexo(
    db: AsyncSession, *, tenant_id: int, nome: str
) -> tuple[int, bool]:
    row = (
        await db.execute(
            select(TipoAnexo.id).where(
                TipoAnexo.tenant_id == tenant_id,
                TipoAnexo.tipo_anexo == nome,
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    ta = TipoAnexo(tenant_id=tenant_id, tipo_anexo=nome, excluido=False)
    db.add(ta)
    await db.flush()
    return ta.id, True


async def _get_or_create_servidor(
    db: AsyncSession,
    *,
    tenant_id: int,
    nome: str,
    email: str,
    cpf: str,
    cargo: str,
    id_unidade: int,
    grupo_su_id: int | None = None,
) -> tuple[int, bool]:
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
        senha="",  # MD5 desabilitado
        senha_bcrypt=hash_password(DEMO_PASSWORD),
        id_unidade_trabalho=id_unidade,
        ativo=True,
        excluido=False,
        cargo=cargo,
        app="sistemas",
        # Demo NÃO força troca — apresentação não pode parar no fluxo SEC-1.
        must_change_password=False,
    )
    db.add(u)
    await db.flush()
    return u.id, True


async def _get_or_create_manifestante(
    db: AsyncSession,
    *,
    tenant_id: int,
    nome: str,
    cpf: str,
    email: str,
    id_tipo_manifestante: int,
) -> tuple[int, bool]:
    row = (
        await db.execute(
            select(Manifestante.id).where(
                Manifestante.tenant_id == tenant_id,
                Manifestante.cpf_cnpj == cpf,
            )
        )
    ).scalar_one_or_none()
    if row:
        return row, False
    m = Manifestante(
        tenant_id=tenant_id,
        id_tipo_manifestante=id_tipo_manifestante,
        cpf_cnpj=cpf,
        nome=nome,
        email=email,
        ativo=True,
        excluido=False,
    )
    db.add(m)
    await db.flush()
    return m.id, True


async def _get_or_create_servico(
    db: AsyncSession,
    *,
    tenant_id: int,
    spec: dict[str, Any],
    id_unidade: int,
    id_assunto: int,
    id_tipo_processo: int,
    id_especie: int | None,
) -> tuple[int, bool]:
    """Cria ou atualiza serviço pelo slug — campos descritivos são re-aplicados
    para o seed manter a "fonte da verdade", mas `ativo` e `excluido` jamais
    são mexidos por re-execução."""
    docs = spec.get("documentos_exigidos")
    # Adiciona `key` estável (igual ao service de domínio, mas inline para
    # evitar import circular do HTTP).
    if docs:
        docs_norm = []
        seen: set[str] = set()
        for d in docs:
            key = d.get("key") or _slugify(d["nome"])
            base = key
            n = 2
            while key in seen:
                key = f"{base}-{n}"
                n += 1
            seen.add(key)
            docs_norm.append({**d, "key": key})
        docs = docs_norm

    row = (
        await db.execute(
            select(Servico).where(
                Servico.tenant_id == tenant_id,
                Servico.slug == spec["slug"],
                Servico.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        s = Servico(
            tenant_id=tenant_id,
            nome=spec["nome"],
            slug=spec["slug"],
            descricao_curta=spec.get("descricao_curta"),
            descricao_detalhada=spec.get("descricao_detalhada"),
            instrucoes_cidadao=spec.get("instrucoes_cidadao"),
            documentos_exigidos=docs,
            prazo_estimado_dias=spec.get("prazo_estimado_dias"),
            id_unidade_responsavel=id_unidade,
            id_assunto_padrao=id_assunto,
            id_tipo_processo_padrao=id_tipo_processo,
            id_especie_documental_padrao=id_especie,
            nivel_sigilo_padrao="ostensivo",
            canal_entrada_permitido="portal",
            ativo=True,
            excluido=False,
            destaque=spec.get("destaque", False),
            ordem_exibicao=spec.get("ordem_exibicao", 0),
            categoria=spec.get("categoria"),
            criado_em=datetime.utcnow(),
        )
        db.add(s)
        await db.flush()
        return s.id, True

    # Re-aplica campos descritivos (caso o seed source tenha sido atualizado).
    row.nome = spec["nome"]
    row.descricao_curta = spec.get("descricao_curta")
    row.descricao_detalhada = spec.get("descricao_detalhada")
    row.instrucoes_cidadao = spec.get("instrucoes_cidadao")
    row.documentos_exigidos = docs
    row.prazo_estimado_dias = spec.get("prazo_estimado_dias")
    row.id_unidade_responsavel = id_unidade
    row.id_assunto_padrao = id_assunto
    row.id_tipo_processo_padrao = id_tipo_processo
    row.destaque = spec.get("destaque", False)
    row.ordem_exibicao = spec.get("ordem_exibicao", 0)
    row.categoria = spec.get("categoria")
    row.atualizado_em = datetime.utcnow()
    return row.id, False


def _slugify(s: str) -> str:
    import re

    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "item"


async def _get_or_create_processo(
    db: AsyncSession,
    *,
    tenant_id: int,
    spec: dict[str, Any],
    id_servico: int,
    id_assunto: int,
    id_manifestante: int,
    id_unidade_proprietaria: int,
    id_usuario_abertura: int,
    acao_abertura_id: int,
) -> tuple[int, bool]:
    """Cria processo demo OU retorna o existente (idempotência via numero_origem).
    Retorna (id_processo, criou_novo)."""
    existente = (
        await db.execute(
            select(Processo).where(
                Processo.tenant_id == tenant_id,
                Processo.numero_origem == spec["origem"],
            )
        )
    ).scalar_one_or_none()
    if existente is not None:
        return existente.id, False

    # Datas calculadas como offset relativo a now() — realismo perene.
    now = datetime.utcnow()
    data_abertura = now - timedelta(days=spec["dias_atras"])

    # Número do processo: prefixo demo + tenant_id para uniqueness global
    # (a constraint `processo_numero_processo_key` é única em todo o banco,
    # não por tenant; incluir tenant_id evita colisão entre tenants demo
    # distintos rodando o seed no mesmo banco — útil em pytest).
    seq = spec["origem"].rsplit("-", 1)[-1]
    numero_processo = f"DEMO-T{tenant_id}-{data_abertura.year}-{seq}"

    p = Processo(
        tenant_id=tenant_id,
        id_assunto=id_assunto,
        id_manifestante=id_manifestante,
        id_unidade_proprietaria=id_unidade_proprietaria,
        observacao=f"[seed-demo] {spec.get('servico_slug', '')}",
        corpo=None,
        numero_origem=spec["origem"],
        numero_processo=numero_processo,
        nivel_sigilo="ostensivo",
        externo=False,
        virtual=True,
        data_hora_abertura=data_abertura,
        id_local_atual=id_unidade_proprietaria,
        id_usuario=id_usuario_abertura,
        ativo=spec["estado"] != "concluido",
        excluido=False,
        migrado=False,
        id_servico=id_servico,
        prazo_servico_dias_snapshot=spec.get("prazo_servico_dias"),
    )
    db.add(p)
    await db.flush()

    # Movimentação de abertura.
    mov = Movimentacao(
        tenant_id=tenant_id,
        id_processo=p.id,
        id_unidade_responsavel=id_unidade_proprietaria,
        id_acao=acao_abertura_id,
        id_usuario=id_usuario_abertura,
        data_hora_movimentacao=data_abertura,
        ativo=True,
        excluido=False,
    )
    db.add(mov)
    await db.flush()
    p.id_ultima_movimentacao = mov.id
    return p.id, True


async def _vincular_anexos(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    servico: Servico,
    modo: str,  # "parcial" | "total" | False
    id_usuario: int,
    id_tipo_anexo: int,
    id_movimentacao: int,
) -> int:
    """Cria anexos sintéticos vinculados a `documento_exigido_key`. Idempotente
    por (processo_id, descricao)."""
    if not modo or not servico.documentos_exigidos:
        return 0
    docs = servico.documentos_exigidos
    alvos = docs if modo == "total" else docs[:1]
    criados = 0
    for d in alvos:
        descricao = f"[demo] {d['nome']}"
        ja = (
            await db.execute(
                select(Anexo.id)
                .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
                .where(
                    AnexoProcesso.id_processo == processo_id,
                    Anexo.descricao == descricao,
                )
            )
        ).scalar_one_or_none()
        if ja:
            continue
        # Gera PDF físico em uploads/ pra demonstrar viewer (~3 KB).
        pdf_bytes = _gerar_pdf_demo(d["nome"], f"Conteúdo demo para: {d['nome']}.")
        upload_dir = "/app/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        path = f"{upload_dir}/demo-{processo_id}-{_slugify(d['nome'])}.pdf"
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        a = Anexo(
            tenant_id=tenant_id,
            id_tipo_anexo=id_tipo_anexo,
            publico=False,
            id_usuario=id_usuario,
            ativo=True,
            excluido=False,
            descricao=descricao,
            qtd_paginas=1,
            documento_exigido_key=d.get("key"),
        )
        db.add(a)
        await db.flush()
        ap = AnexoProcesso(
            tenant_id=tenant_id,
            id_processo=processo_id,
            id_anexo=a.id,
            id_movimentacao=id_movimentacao,
            id_usuario=id_usuario,
            ativo=True,
            excluido=False,
            ordem=1,
            anexo_herdado=False,
        )
        db.add(ap)
        criados += 1
    return criados


async def _criar_complementacao(
    db: AsyncSession,
    *,
    tenant_id: int,
    processo_id: int,
    servico: Servico,
    modo: str,  # "aberta" | "respondida"
    id_usuario: int,
) -> bool:
    """Cria complementação demo. Idempotente (1 só por processo demo)."""
    if not modo or not servico.documentos_exigidos:
        return False
    ja = (
        await db.execute(
            select(ComplementacaoDocumental.id).where(
                ComplementacaoDocumental.tenant_id == tenant_id,
                ComplementacaoDocumental.id_processo == processo_id,
                ComplementacaoDocumental.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ja:
        return False

    docs = servico.documentos_exigidos[:1]  # solicita 1 doc na demo
    now = datetime.utcnow()
    c = ComplementacaoDocumental(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_usuario_solicitante=id_usuario,
        status="aberta" if modo == "aberta" else "respondida",
        mensagem=(
            f"Por favor, anexe novamente: {docs[0]['nome']}. "
            "(Solicitação gerada pelo seed demo.)"
        ),
        documentos_solicitados=[
            {"key": docs[0]["key"], "nome": docs[0]["nome"]}
        ],
        criado_em=now - timedelta(days=1),
        respondido_em=now if modo == "respondida" else None,
    )
    db.add(c)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Tenant — bootstrap (cria se não existe)
# ---------------------------------------------------------------------------


async def _get_or_create_tenant(
    db: AsyncSession, *, slug: str
) -> tuple[int, bool]:
    """Retorna (tenant_id, criou_novo). Se criar, usa provisionar_tenant que
    já cuida do admin + grupo SU + unidade + catálogos mínimos."""
    existente = (
        await db.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if existente is not None:
        return existente.id, False

    try:
        tenant, _ = await provisionar_tenant(
            db,
            slug=slug,
            nome="Prefeitura Demo (apresentação Aprimora)",
            admin_email=f"admin@{DEMO_EMAIL_DOMAIN}",
            admin_nome="Admin Demo",
            admin_cpf="99900000017",  # mesmo padrão dos manifestantes
            plano="basico",
            cor_primaria="#1e3a5f",
            senha=DEMO_PASSWORD,
        )
    except ProvisioningError as e:
        print(f"[ERRO] provisionar_tenant: {e}")
        sys.exit(3)

    # Admin demo NÃO deve forçar troca — apresentação contínua.
    await db.execute(
        text(
            "UPDATE utils.usuario SET must_change_password = false "
            "WHERE tenant_id = :t AND email = :e"
        ),
        {"t": tenant.id, "e": f"admin@{DEMO_EMAIL_DOMAIN}"},
    )
    return tenant.id, True


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


async def _apply(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)

    contagens: dict[str, int] = {
        "tenant_criado": 0,
        "unidades_criadas": 0,
        "servidores_criados": 0,
        "tipos_catalogo_criados": 0,
        "servicos_criados_ou_atualizados": 0,
        "manifestantes_criados": 0,
        "processos_criados": 0,
        "anexos_criados": 0,
        "complementacoes_criadas": 0,
    }

    async with SessionLocal() as db:
        # Fase 1: tenant (FORA da fronteira RLS — cria e comita)
        tenant_id, criou_tenant = await _get_or_create_tenant(db, slug=args.tenant)
        if criou_tenant:
            contagens["tenant_criado"] = 1
        await db.commit()

    # A partir daqui, qualquer insert tenant-scoped exige SET LOCAL na MESMA
    # transação. Abre nova session.
    async with SessionLocal() as db:
        await _set_local_tenant(db, tenant_id)

        # Fase 2: tipos catálogo
        tipo_unidade_id, criou_tu = await _get_or_create_tipo_unidade(
            db, tenant_id=tenant_id, nome="Secretaria", codigo="SEC"
        )
        if criou_tu:
            contagens["tipos_catalogo_criados"] += 1
        unidades_by_sigla: dict[str, int] = {}
        # Protocolo Geral já vem do provisioning; pega o id.
        pg_id = (
            await db.execute(
                select(UnidadeTrabalho.id).where(
                    UnidadeTrabalho.tenant_id == tenant_id,
                    UnidadeTrabalho.unidade_trabalho == "Protocolo Geral",
                    UnidadeTrabalho.excluido.is_(False),
                )
            )
        ).scalar_one()
        unidades_by_sigla["PG"] = pg_id

        for nome, sigla in UNIDADES:
            uid, criou = await _get_or_create_unidade(
                db,
                tenant_id=tenant_id,
                nome=nome,
                sigla=sigla,
                id_tipo_unidade=tipo_unidade_id,
            )
            if criou:
                contagens["unidades_criadas"] += 1
            unidades_by_sigla[sigla] = uid

        tp_id, criou_tp = await _get_or_create_tipo_processo(
            db, tenant_id=tenant_id, nome="Solicitação"
        )
        if criou_tp:
            contagens["tipos_catalogo_criados"] += 1
        assunto_id, criou_assunto = await _get_or_create_assunto(
            db,
            tenant_id=tenant_id,
            nome="Demanda Cidadã",
            id_tipo_processo=tp_id,
        )
        if criou_assunto:
            contagens["tipos_catalogo_criados"] += 1
        tipo_anexo_id, criou_ta = await _get_or_create_tipo_anexo(
            db, tenant_id=tenant_id, nome="Documento Geral"
        )
        if criou_ta:
            contagens["tipos_catalogo_criados"] += 1

        tipo_manif_pf = (
            await db.execute(
                select(TipoManifestante.id).where(
                    TipoManifestante.tenant_id == tenant_id,
                    TipoManifestante.tipo_manifestante == "Pessoa Física",
                    TipoManifestante.excluido.is_(False),
                )
            )
        ).scalar_one()

        # Fase 3: servidores (admin já existe). CPF derivado do email_local de
        # forma determinística — deve ser estável entre runs para preservar
        # idempotência. CPFs do range "999..." reservados para demo.
        cpf_servidor_base = 99800000000
        for i, (nome, email_local, lotacao_sigla, cargo) in enumerate(SERVIDORES):
            email = f"{email_local}@{DEMO_EMAIL_DOMAIN}"
            cpf = str(cpf_servidor_base + i)[:11]
            uid, criou = await _get_or_create_servidor(
                db,
                tenant_id=tenant_id,
                nome=nome,
                email=email,
                cpf=cpf,
                cargo=cargo,
                id_unidade=unidades_by_sigla.get(lotacao_sigla, pg_id),
            )
            if criou:
                contagens["servidores_criados"] += 1

        admin_id = (
            await db.execute(
                select(Usuario.id).where(
                    Usuario.tenant_id == tenant_id,
                    Usuario.email == f"admin@{DEMO_EMAIL_DOMAIN}",
                )
            )
        ).scalar_one()

        # Fase 4: serviços (idempotente: cria novo OU atualiza descritivos)
        servicos_by_slug: dict[str, int] = {}
        for spec in SERVICOS:
            unidade_id = unidades_by_sigla.get(spec["unidade_sigla"], pg_id)
            sid, criou = await _get_or_create_servico(
                db,
                tenant_id=tenant_id,
                spec=spec,
                id_unidade=unidade_id,
                id_assunto=assunto_id,
                id_tipo_processo=tp_id,
                id_especie=None,
            )
            servicos_by_slug[spec["slug"]] = sid
            if criou:
                contagens["servicos_criados_ou_atualizados"] += 1

        # Fase 5: manifestantes
        for nome, cpf, email_local in MANIFESTANTES:
            _, criou = await _get_or_create_manifestante(
                db,
                tenant_id=tenant_id,
                nome=nome,
                cpf=cpf,
                email=f"{email_local}@{DEMO_CIDADAO_EMAIL_DOMAIN}",
                id_tipo_manifestante=tipo_manif_pf,
            )
            if criou:
                contagens["manifestantes_criados"] += 1

        await db.commit()

    # Fase 6: processos (com complementação + anexos). Nova session para
    # garantir SET LOCAL fresco.
    async with SessionLocal() as db:
        await _set_local_tenant(db, tenant_id)

        # Ação ABERTURA (catálogo global)
        acao_abertura_id = (
            await db.execute(
                select(Acao.id).where(
                    Acao.flag == "ABERTURA",
                    Acao.ativo.is_(True),
                    Acao.excluido.is_(False),
                )
            )
        ).scalar_one()

        # Carrega ids resolvidos da fase anterior
        servicos_by_slug = {
            s.slug: s
            for s in (
                await db.execute(
                    select(Servico).where(
                        Servico.tenant_id == tenant_id,
                        Servico.slug.like(f"{DEMO_SLUG_PREFIX}-%"),
                        Servico.excluido.is_(False),
                    )
                )
            ).scalars()
        }
        manifestantes_ids = [
            m.id
            for m in (
                await db.execute(
                    select(Manifestante)
                    .where(Manifestante.tenant_id == tenant_id)
                    .order_by(Manifestante.id)
                )
            ).scalars()
        ]
        pg_id = (
            await db.execute(
                select(UnidadeTrabalho.id).where(
                    UnidadeTrabalho.tenant_id == tenant_id,
                    UnidadeTrabalho.unidade_trabalho == "Protocolo Geral",
                )
            )
        ).scalar_one()
        admin_id = (
            await db.execute(
                select(Usuario.id).where(
                    Usuario.tenant_id == tenant_id,
                    Usuario.email == f"admin@{DEMO_EMAIL_DOMAIN}",
                )
            )
        ).scalar_one()
        assunto_id = (
            await db.execute(
                select(Assunto.id).where(
                    Assunto.tenant_id == tenant_id,
                    Assunto.assunto == "Demanda Cidadã",
                )
            )
        ).scalar_one()
        tipo_anexo_id = (
            await db.execute(
                select(TipoAnexo.id).where(
                    TipoAnexo.tenant_id == tenant_id,
                    TipoAnexo.tipo_anexo == "Documento Geral",
                )
            )
        ).scalar_one()

        for spec in PROCESSOS:
            servico = servicos_by_slug[spec["servico_slug"]]
            # snapshot do prazo no momento da abertura (PR 5b)
            spec_local = dict(spec)
            spec_local["prazo_servico_dias"] = servico.prazo_estimado_dias

            pid, criou = await _get_or_create_processo(
                db,
                tenant_id=tenant_id,
                spec=spec_local,
                id_servico=servico.id,
                id_assunto=assunto_id,
                id_manifestante=manifestantes_ids[spec["manifestante_idx"]],
                id_unidade_proprietaria=pg_id,
                id_usuario_abertura=admin_id,
                acao_abertura_id=acao_abertura_id,
            )
            if criou:
                contagens["processos_criados"] += 1

            # Recupera id_ultima_movimentacao (abertura) para os anexos
            mov_id = (
                await db.execute(
                    select(Processo.id_ultima_movimentacao).where(
                        Processo.id == pid
                    )
                )
            ).scalar_one()

            # Anexos
            n_anex = await _vincular_anexos(
                db,
                tenant_id=tenant_id,
                processo_id=pid,
                servico=servico,
                modo=spec.get("anexar_docs", False),
                id_usuario=admin_id,
                id_tipo_anexo=tipo_anexo_id,
                id_movimentacao=mov_id,
            )
            contagens["anexos_criados"] += n_anex

            # Complementação
            if await _criar_complementacao(
                db,
                tenant_id=tenant_id,
                processo_id=pid,
                servico=servico,
                modo=spec.get("complementacao"),
                id_usuario=admin_id,
            ):
                contagens["complementacoes_criadas"] += 1

        await db.commit()

    _print_resumo("APPLY", args.tenant, tenant_id, contagens)
    return 0


async def _reset(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)

    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == args.tenant))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"[ok] tenant '{args.tenant}' não existe — nada a limpar.")
            return 0
        tid = tenant.id

    contagens = {
        "processos": 0,
        "anexos": 0,
        "complementacoes": 0,
        "servicos": 0,
        "manifestantes": 0,
        "servidores_extra": 0,
        "audit_log": 0,
        "movimentacoes": 0,
    }

    async with SessionLocal() as db:
        await _set_local_tenant(db, tid)

        # Subselects dos ids alvo
        proc_ids = [
            r
            for (r,) in (
                await db.execute(
                    select(Processo.id).where(
                        Processo.tenant_id == tid,
                        Processo.numero_origem.like(f"{DEMO_ORIGEM_PREFIX}%"),
                    )
                )
            )
        ]

        if proc_ids:
            # Anexos do processo demo
            anexo_ids = [
                r
                for (r,) in (
                    await db.execute(
                        select(AnexoProcesso.id_anexo).where(
                            AnexoProcesso.id_processo.in_(proc_ids)
                        )
                    )
                )
            ]
            contagens["anexos"] = len(anexo_ids)
            await db.execute(
                delete(AnexoProcesso).where(
                    AnexoProcesso.id_processo.in_(proc_ids)
                )
            )
            if anexo_ids:
                await db.execute(delete(Anexo).where(Anexo.id.in_(anexo_ids)))

            contagens["complementacoes"] = (
                await db.execute(
                    delete(ComplementacaoDocumental).where(
                        ComplementacaoDocumental.id_processo.in_(proc_ids)
                    )
                )
            ).rowcount

            # processo.id_ultima_movimentacao tem FK pra movimentacao.id —
            # zerar antes de apagar movimentações pra evitar FK violation.
            await db.execute(
                text(
                    "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL "
                    "WHERE id = ANY(:ids)"
                ),
                {"ids": proc_ids},
            )

            contagens["movimentacoes"] = (
                await db.execute(
                    delete(Movimentacao).where(
                        Movimentacao.id_processo.in_(proc_ids)
                    )
                )
            ).rowcount

            contagens["audit_log"] = (
                await db.execute(
                    text(
                        "DELETE FROM aprimora_py.audit_log "
                        "WHERE tenant_id=:t AND entidade='processo' "
                        "  AND id_entidade = ANY(:ids)"
                    ),
                    {"t": tid, "ids": proc_ids},
                )
            ).rowcount

            contagens["processos"] = (
                await db.execute(
                    delete(Processo).where(Processo.id.in_(proc_ids))
                )
            ).rowcount

        # Serviços demo
        contagens["servicos"] = (
            await db.execute(
                delete(Servico).where(
                    Servico.tenant_id == tid,
                    Servico.slug.like(f"{DEMO_SLUG_PREFIX}-%"),
                )
            )
        ).rowcount

        # Manifestantes (apenas os com cpf 999*)
        contagens["manifestantes"] = (
            await db.execute(
                delete(Manifestante).where(
                    Manifestante.tenant_id == tid,
                    Manifestante.cpf_cnpj.like("999%"),
                )
            )
        ).rowcount

        # Servidores extras (manter admin@demo.test). audit_log deles também.
        servidor_extra_ids = [
            r
            for (r,) in (
                await db.execute(
                    select(Usuario.id).where(
                        Usuario.tenant_id == tid,
                        Usuario.email.like(f"%@{DEMO_EMAIL_DOMAIN}"),
                        Usuario.email != f"admin@{DEMO_EMAIL_DOMAIN}",
                    )
                )
            )
        ]
        if servidor_extra_ids:
            await db.execute(
                text(
                    "DELETE FROM aprimora_py.audit_log "
                    "WHERE tenant_id=:t AND id_usuario = ANY(:ids)"
                ),
                {"t": tid, "ids": servidor_extra_ids},
            )
            await db.execute(
                delete(UsuarioGrupo).where(
                    UsuarioGrupo.id_usuario.in_(servidor_extra_ids)
                )
            )
            contagens["servidores_extra"] = (
                await db.execute(
                    delete(Usuario).where(Usuario.id.in_(servidor_extra_ids))
                )
            ).rowcount

        await db.commit()

    _print_resumo("RESET", args.tenant, tid, contagens)
    return 0


async def _status(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == args.tenant))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"tenant '{args.tenant}': AUSENTE")
            return 0
        tid = tenant.id

        contagens = {
            "tenant_id": tid,
            "tenant_nome": tenant.nome,
            "servicos_demo": (
                await db.execute(
                    select(Servico).where(
                        Servico.tenant_id == tid,
                        Servico.slug.like(f"{DEMO_SLUG_PREFIX}-%"),
                        Servico.excluido.is_(False),
                    )
                )
            ).scalars().unique(),
            "processos_demo": (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM protocolos.processo "
                        "WHERE tenant_id=:t AND numero_origem LIKE :p"
                    ),
                    {"t": tid, "p": f"{DEMO_ORIGEM_PREFIX}%"},
                )
            ).scalar_one(),
            "manifestantes_demo": (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM protocolos.manifestante "
                        "WHERE tenant_id=:t AND cpf_cnpj LIKE '999%'"
                    ),
                    {"t": tid},
                )
            ).scalar_one(),
            "servidores_demo": (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM utils.usuario "
                        "WHERE tenant_id=:t AND email LIKE :p "
                        "  AND ativo=true AND excluido=false"
                    ),
                    {"t": tid, "p": f"%@{DEMO_EMAIL_DOMAIN}"},
                )
            ).scalar_one(),
        }

    servicos_list = list(contagens["servicos_demo"])
    print()
    print("=" * 60)
    print(f"STATUS SEED DEMO — tenant '{args.tenant}' (id={tid})")
    print("=" * 60)
    print(f"  Tenant:                {contagens['tenant_nome']}")
    print(f"  Serviços demo:         {len(servicos_list)} / {len(SERVICOS)} esperados")
    for s in servicos_list:
        print(f"    - {s.slug:35} (prazo {s.prazo_estimado_dias}d)")
    print(f"  Processos demo:        {contagens['processos_demo']} / {len(PROCESSOS)} esperados")
    print(f"  Manifestantes demo:    {contagens['manifestantes_demo']} / {len(MANIFESTANTES)} esperados")
    print(f"  Servidores demo:       {contagens['servidores_demo']} (admin + extras)")
    print()
    print("  Próximos passos:")
    print(f"    python -m app.cli.seed_demo apply --tenant {args.tenant}")
    print(f"    python -m app.cli.seed_demo reset --tenant {args.tenant}")
    print("=" * 60)
    return 0


def _print_resumo(
    acao: str, tenant_slug: str, tenant_id: int, contagens: dict[str, int]
) -> None:
    print()
    print("=" * 60)
    print(f"SEED DEMO {acao} — tenant '{tenant_slug}' (id={tenant_id})")
    print("=" * 60)
    for k, v in contagens.items():
        print(f"  {k}: {v}")
    print("=" * 60)
    if acao == "APPLY":
        print()
        print("Credenciais demo (gravar no roteiro):")
        print(f"  URL:    http://{tenant_slug}.aprimora.local:8090/login")
        print(f"  Email:  admin@{DEMO_EMAIL_DOMAIN}")
        print(f"  Senha:  {DEMO_PASSWORD}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli.seed_demo", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _add_tenant_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--tenant", required=True, help="slug do tenant alvo (ex.: demo)")
        p.add_argument(
            "--allow-non-demo",
            action="store_true",
            help="destrava operação em slugs que não começam com 'demo' (cuidado)",
        )

    p_status = sub.add_parser("status", help="Mostra o estado atual do seed demo")
    _add_tenant_args(p_status)
    p_status.set_defaults(fn=_status)

    p_apply = sub.add_parser("apply", help="Cria/atualiza dados demo (idempotente)")
    _add_tenant_args(p_apply)
    p_apply.set_defaults(fn=_apply)

    p_reset = sub.add_parser("reset", help="Remove dados demo do tenant alvo")
    _add_tenant_args(p_reset)
    p_reset.set_defaults(fn=_reset)

    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
