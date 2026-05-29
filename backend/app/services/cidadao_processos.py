"""Operações de processo do cidadão (usuário externo).

- listar: processos cujo manifestante tem o mesmo CPF/CNPJ do cidadão logado,
  dentro do tenant.
- detalhe: idem.
- abrir: cria/reusa Manifestante por CPF/CNPJ DENTRO do tenant; abre processo
  com `externo=true, publico=true`, sem `id_usuario`.

A unidade proprietária default vem da primeira unidade ativa do tenant — em
produção isso seria parametrizável (tabela `configuracoes`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Acao,
    Anexo,
    AnexoProcesso,
    Assunto,
    CcdClasse,
    EspecieDocumental,
    Manifestante,
    Movimentacao,
    Processo,
    Servico,
    Tenant,
    TipoManifestante,
    TipoProcesso,
    UnidadeTrabalho,
    UsuarioExterno,
)
from ..schemas.cidadao import (
    AbrirPorServicoRequest,
    AbrirProcessoCidadaoRequest,
    AnexoCidadaoOut,
    EspecieCidadaoOut,
    MovimentacaoCidadaoItem,
    ProcessoCidadaoDetail,
    ProcessoCidadaoListItem,
)
from .audit import log as audit_log

logger = logging.getLogger("cidadao_processos")

# Espécies expostas no portal cidadão (alinhado com seed 0015).
ESPECIES_PORTAL = ("REQUERIMENTO", "PETICAO", "DECLARACAO")
RATE_LIMIT_24H = 5


class CidadaoProcessoError(Exception):
    pass


def _base_select(tenant_id: int):
    LocalAtual = aliased(UnidadeTrabalho, name="la")
    return (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_nome"),
            LocalAtual.unidade_trabalho.label("local_nome"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
        .where(Processo.excluido.is_(False), Processo.tenant_id == tenant_id)
    )


async def listar_meus(
    db: AsyncSession, cidadao: UsuarioExterno, *, tenant_id: int
) -> list[ProcessoCidadaoListItem]:
    if not cidadao.cpf_cnpj:
        return []
    stmt = (
        _base_select(tenant_id)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .where(
            Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
            Manifestante.tenant_id == tenant_id,
        )
        .order_by(Processo.data_hora_abertura.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_row_to_list(r) for r in rows]


def _row_to_list(r) -> ProcessoCidadaoListItem:
    p: Processo = r[0]
    return ProcessoCidadaoListItem(
        id=p.id,
        numero_processo=p.numero_processo,
        nup=p.nup,
        data_hora_abertura=p.data_hora_abertura,
        assunto=r.assunto_nome,
        tipo_processo=r.tipo_nome,
        local_atual=r.local_nome,
        ativo=p.ativo,
        publico=p.publico,
    )


async def listar_especies_cidadao(
    db: AsyncSession, *, tenant_id: int
) -> list[EspecieCidadaoOut]:
    """Espécies expostas ao cidadão no portal (subset do seed P1)."""
    rows = (
        await db.execute(
            select(EspecieDocumental)
            .where(
                EspecieDocumental.tenant_id == tenant_id,
                EspecieDocumental.flag.in_(ESPECIES_PORTAL),
                EspecieDocumental.ativo.is_(True),
                EspecieDocumental.excluido.is_(False),
            )
            .order_by(EspecieDocumental.nome)
        )
    ).scalars().all()
    return [
        EspecieCidadaoOut(id=e.id, codigo=e.flag, nome=e.nome) for e in rows
    ]


async def get_meu_detail(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    processo_id: int,
    *,
    tenant_id: int,
) -> ProcessoCidadaoDetail | None:
    if not cidadao.cpf_cnpj:
        return None
    stmt = (
        _base_select(tenant_id)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .where(
            Processo.id == processo_id,
            Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
            Manifestante.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    p: Processo = row[0]
    base = _row_to_list(row)

    movs_stmt = (
        select(Movimentacao, Acao, UnidadeTrabalho)
        .join(Acao, Acao.id == Movimentacao.id_acao)
        .join(
            UnidadeTrabalho,
            UnidadeTrabalho.id == Movimentacao.id_unidade_responsavel,
            isouter=True,
        )
        .where(
            Movimentacao.id_processo == processo_id,
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.excluido.is_(False),
        )
        .order_by(Movimentacao.data_hora_movimentacao.desc())
    )
    movs = (await db.execute(movs_stmt)).all()
    movimentacoes = [
        MovimentacaoCidadaoItem(
            id=mov.id,
            data_hora_movimentacao=mov.data_hora_movimentacao,
            acao=acao.acao,
            unidade_responsavel=ut.unidade_trabalho if ut else None,
            despacho_publico=None,
        )
        for mov, acao, ut in movs
    ]

    # Anexos públicos do processo — cidadão não vê sigilosos.
    anexos_rows = (
        await db.execute(
            select(Anexo)
            .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
            .where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
                AnexoProcesso.desentranhado_em.is_(None),
                Anexo.publico.is_(True),
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
            .order_by(AnexoProcesso.ordem)
        )
    ).scalars().all()
    anexos = [
        AnexoCidadaoOut(
            id=a.id,
            descricao=a.descricao,
            e_doc=a.e_doc,
            qtd_paginas=a.qtd_paginas,
            publico=a.publico,
        )
        for a in anexos_rows
    ]

    especie_nome: str | None = None
    if p.id_especie_documental:
        especie_nome = (
            await db.execute(
                select(EspecieDocumental.nome).where(
                    EspecieDocumental.id == p.id_especie_documental
                )
            )
        ).scalar_one_or_none()

    ccd_codigo: str | None = None
    ccd_nome: str | None = None
    if p.id_ccd_classe:
        row = (
            await db.execute(
                select(CcdClasse.codigo, CcdClasse.nome).where(
                    CcdClasse.id == p.id_ccd_classe
                )
            )
        ).first()
        if row:
            ccd_codigo = row.codigo
            ccd_nome = row.nome

    return ProcessoCidadaoDetail(
        **base.model_dump(),
        observacao=p.observacao,
        corpo=p.corpo,
        especie_nome=especie_nome,
        ccd_codigo=ccd_codigo,
        ccd_nome=ccd_nome,
        movimentacoes=movimentacoes,
        anexos=anexos,
    )


async def _checar_rate_limit(db: AsyncSession, cpf_cnpj: str, tenant_id: int) -> None:
    """Anti-spam: máx N aberturas em 24h por CPF no tenant (canal portal).

    Compartilhado entre a abertura genérica e a abertura por serviço — ambas
    contam no mesmo limite (canal portal)."""
    desde = datetime.now() - timedelta(hours=24)
    qtd_24h = (
        await db.execute(
            select(func.count(Processo.id))
            .join(Manifestante, Manifestante.id == Processo.id_manifestante)
            .where(
                Manifestante.cpf_cnpj == cpf_cnpj,
                Manifestante.tenant_id == tenant_id,
                Processo.tenant_id == tenant_id,
                Processo.canal_entrada == "portal",
                Processo.data_hora_abertura >= desde,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one()
    if qtd_24h >= RATE_LIMIT_24H:
        raise CidadaoProcessoError(
            f"Limite de {RATE_LIMIT_24H} aberturas em 24h atingido. "
            "Aguarde antes de protocolar novamente."
        )


async def _resolver_ou_criar_manifestante(
    db: AsyncSession, cidadao: UsuarioExterno, tenant_id: int
) -> Manifestante:
    manifestante = (
        await db.execute(
            select(Manifestante).where(
                Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
                Manifestante.tenant_id == tenant_id,
                Manifestante.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if manifestante is not None:
        return manifestante

    tipo_pf = (
        await db.execute(
            select(TipoManifestante)
            .where(
                TipoManifestante.tenant_id == tenant_id,
                TipoManifestante.ativo.is_(True),
            )
            .order_by(TipoManifestante.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if tipo_pf is None:
        raise CidadaoProcessoError("Nenhum tipo de manifestante cadastrado")
    manifestante = Manifestante(
        tenant_id=tenant_id,
        id_tipo_manifestante=tipo_pf.id,
        cpf_cnpj=cidadao.cpf_cnpj,
        nome=cidadao.nome,
        email=cidadao.email,
        telefone_celular=cidadao.telefone,
        ativo=True,
        excluido=False,
    )
    db.add(manifestante)
    await db.flush()
    return manifestante


async def _criar_processo_publico(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    *,
    tenant_id: int,
    id_assunto: int,
    id_unidade: int,
    id_especie: int | None,
    nivel_sigilo: str,
    corpo: str | None,
    observacao: str | None,
    id_servico: int | None = None,
) -> Processo:
    """Núcleo de abertura pública (canal portal). NÃO comita — o caller controla
    a transação (permite auditar na mesma transação). Pressupõe rate-limit já
    checado e assunto/unidade já validados no tenant."""
    manifestante = await _resolver_ou_criar_manifestante(db, cidadao, tenant_id)

    numero = (
        await db.execute(text("SELECT protocolos.gerar_numero_processo_string() AS n"))
    ).first()
    if numero is None or not numero.n:
        raise CidadaoProcessoError("Falha ao gerar número de processo")
    numero_processo = numero.n

    # Acao é catálogo global — sem tenant_id.
    acao_abertura = (
        await db.execute(
            select(Acao).where(
                Acao.flag == "ABERTURA",
                Acao.ativo.is_(True),
                Acao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if acao_abertura is None:
        raise CidadaoProcessoError("Ação ABERTURA não cadastrada")

    now = datetime.now()

    # Auto-classificação CCD por palavras do assunto + corpo. Aceita só score
    # acima de 0.3 pra evitar classificar errado por match fraco.
    from .temporalidade import sugerir_ccd_por_assunto

    id_ccd: int | None = None
    sugestoes = await sugerir_ccd_por_assunto(
        db, tenant_id=tenant_id, id_assunto=id_assunto, texto_extra=corpo, limit=1
    )
    if sugestoes and sugestoes[0].score >= 0.3:
        id_ccd = sugestoes[0].id_ccd_classe

    processo = Processo(
        tenant_id=tenant_id,
        id_assunto=id_assunto,
        id_manifestante=manifestante.id,
        id_unidade_proprietaria=id_unidade,
        observacao=observacao,
        corpo=corpo,
        numero_processo=numero_processo,
        nivel_sigilo=nivel_sigilo,
        externo=True,
        virtual=True,
        data_hora_abertura=now,
        data_recepcao=now,
        canal_entrada="portal",
        id_especie_documental=id_especie,
        id_ccd_classe=id_ccd,
        id_local_atual=id_unidade,
        id_usuario=None,
        id_servico=id_servico,
        ativo=True,
        excluido=False,
        migrado=False,
    )
    db.add(processo)
    await db.flush()

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo.id,
        id_unidade_responsavel=id_unidade,
        id_acao=acao_abertura.id,
        id_usuario=None,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()
    processo.id_ultima_movimentacao = movimentacao.id

    # NUP federal — opt-in por tenant. Falha não bloqueia abertura.
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant and tenant.usar_nup_federal and tenant.codigo_orgao_nup:
        from .nup import NupError, gerar_nup

        try:
            nup_str, sequencial = await gerar_nup(db, tenant=tenant, ano=now.year)
            processo.nup = nup_str
            processo.numero_sequencial_orgao = sequencial
        except NupError:
            pass

    return processo


async def abrir_processo_cidadao(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    payload: AbrirProcessoCidadaoRequest,
    *,
    tenant_id: int,
) -> Processo:
    if not cidadao.cpf_cnpj or not cidadao.nome:
        raise CidadaoProcessoError("Cadastro do cidadão incompleto (CPF/nome)")

    await _checar_rate_limit(db, cidadao.cpf_cnpj, tenant_id)

    assunto = (
        await db.execute(
            select(Assunto).where(
                Assunto.id == payload.id_assunto,
                Assunto.tenant_id == tenant_id,
                Assunto.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if assunto is None:
        raise CidadaoProcessoError("Assunto inválido")

    # Espécie documental opcional — quando informada, precisa estar entre as
    # expostas ao portal cidadão (REQUERIMENTO/PETICAO/DECLARACAO).
    id_especie: int | None = None
    if payload.id_especie_documental is not None:
        esp = (
            await db.execute(
                select(EspecieDocumental).where(
                    EspecieDocumental.id == payload.id_especie_documental,
                    EspecieDocumental.tenant_id == tenant_id,
                    EspecieDocumental.flag.in_(ESPECIES_PORTAL),
                    EspecieDocumental.ativo.is_(True),
                )
            )
        ).scalar_one_or_none()
        if esp is None:
            raise CidadaoProcessoError("Espécie documental inválida")
        id_especie = esp.id

    unidade = (
        await db.execute(
            select(UnidadeTrabalho)
            .where(
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
            .order_by(UnidadeTrabalho.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if unidade is None:
        raise CidadaoProcessoError("Nenhuma unidade configurada")

    processo = await _criar_processo_publico(
        db,
        cidadao,
        tenant_id=tenant_id,
        id_assunto=payload.id_assunto,
        id_unidade=unidade.id,
        id_especie=id_especie,
        nivel_sigilo="ostensivo",
        corpo=payload.corpo,
        observacao=payload.observacao,
        id_servico=None,
    )
    await db.commit()
    await db.refresh(processo)
    return processo


async def abrir_processo_por_servico(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    servico: "Servico",
    payload: "AbrirPorServicoRequest",
    *,
    tenant_id: int,
) -> Processo:
    """Abre protocolo a partir de um serviço já validado como solicitável
    (ver services.servico.obter_servico_solicitavel). Aplica os defaults do
    serviço; o cidadão não escolhe classificação. Audita de forma minimizada."""
    if not cidadao.cpf_cnpj or not cidadao.nome:
        raise CidadaoProcessoError("Cadastro do cidadão incompleto (CPF/nome)")

    await _checar_rate_limit(db, cidadao.cpf_cnpj, tenant_id)

    # Espécie é opcional (D-E): se setada e válida no tenant, usa; senão abre sem.
    id_especie: int | None = None
    if servico.id_especie_documental_padrao is not None:
        esp = (
            await db.execute(
                select(EspecieDocumental.id).where(
                    EspecieDocumental.id == servico.id_especie_documental_padrao,
                    EspecieDocumental.tenant_id == tenant_id,
                    EspecieDocumental.excluido.is_(False),
                )
            )
        ).scalar_one_or_none()
        if esp is None:
            logger.warning(
                "servico_especie_invalida",
                extra={"tenant_id": tenant_id, "id_servico": servico.id},
            )
        else:
            id_especie = esp

    # Coerência de tipo (telemetria — não bloqueia): o tipo vem do assunto.
    if servico.id_tipo_processo_padrao is not None:
        tipo_do_assunto = (
            await db.execute(
                select(Assunto.id_tipo_processo).where(
                    Assunto.id == servico.id_assunto_padrao,
                    Assunto.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if tipo_do_assunto != servico.id_tipo_processo_padrao:
            logger.warning(
                "servico_tipo_incoerente",
                extra={
                    "tenant_id": tenant_id,
                    "id_servico": servico.id,
                    "tipo_servico": servico.id_tipo_processo_padrao,
                    "tipo_assunto": tipo_do_assunto,
                },
            )

    processo = await _criar_processo_publico(
        db,
        cidadao,
        tenant_id=tenant_id,
        id_assunto=servico.id_assunto_padrao,
        id_unidade=servico.id_unidade_responsavel,
        id_especie=id_especie,
        nivel_sigilo=servico.nivel_sigilo_padrao,
        corpo=payload.corpo,
        observacao=payload.observacao,
        id_servico=servico.id,
    )

    # Auditoria minimizada (sem CPF/nome/corpo/anexos) — mesma transação.
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=None,
        acao="processo.aberto_por_servico",
        entidade="processo",
        id_entidade=processo.id,
        payload={"id_servico": servico.id, "canal": "portal", "origem": "servico"},
    )

    await db.commit()
    await db.refresh(processo)
    return processo
