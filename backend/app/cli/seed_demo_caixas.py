"""Demonstração das caixas de trabalho de protocolo.

O `seed_demo` abre processos e para aí: nenhum é encaminhado, arquivado ou
enviado para assinatura. Na tela, quatro das sete caixas ficavam em zero
(Externos, Arquivados, Aguardando assinatura, Enviado para assinatura), e
Entrada, Saída e Recusados só tinham o que alguém tramitasse à mão. Sem prazo em nenhum
encaminhamento, o destaque de prazo da caixa também não tinha o que mostrar.

Este módulo põe ao menos um processo em cada caixa de QUEM ABRE A DEMONSTRAÇÃO
— o administrador do tenant, o mesmo usuário que o `seed_demo` usa para abrir
os processos. As caixas de unidade são relativas à lotação dele; as de
assinatura, à pessoa.

Regras da casa:

- **Passa pelos serviços** (`encaminhar`, `receber`, `recusar_encaminhamento`,
  `arquivar`, `solicitar_assinatura`): são eles que gravam a movimentação que as caixas
  leem. Montar as linhas à mão reproduziria o estado de hoje e envelheceria
  com a primeira mudança de regra.
- **Não depende de nome de unidade.** O `seed_itaitinga` renomeia "Protocolo
  Geral"; aqui a unidade é a de lotação do administrador, e a contraparte é
  outra unidade ativa qualquer do tenant.
- **Idempotente pelo `numero_origem`** (`demo-caixa-NNN`), que é também o que
  o `reset` do `seed_demo` usa para achar os processos.
- **Falha de um item vira aviso**, não aborta: faltar a segunda unidade ou um
  colega para assinar deixa aquela caixa vazia e segue com as demais.

Uso isolado (o `apply` completo também o chama):

    docker exec aprimora-py-backend python -m app.cli.seed_demo caixas \
        --tenant sobral --allow-non-demo
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database_admin import AdminSessionLocal
from ..models import (
    Acao,
    Anexo,
    AnexoProcesso,
    Assunto,
    Encaminhamento,
    Manifestante,
    Prioridade,
    Processo,
    TipoAnexo,
    UnidadeTrabalho,
    Usuario,
)

# Prefixo próprio DENTRO do prefixo do seed (`demo-`): o `reset` os alcança, e
# dá para contar só estes.
ORIGEM_PREFIXO = "demo-caixa-"

# rótulo → o que o processo demonstra. `dias_atras` recua a abertura;
# `prazo_servico_dias` é o prazo do serviço contado dela.
CAIXAS: list[dict[str, Any]] = [
    # Externo, com o prazo do serviço nos últimos dias: aparece "vencendo".
    {"origem": "demo-caixa-101", "passo": "externo", "dias_atras": 27,
     "prazo_servico_dias": 30},
    {"origem": "demo-caixa-102", "passo": "arquivado", "dias_atras": 20,
     "prazo_servico_dias": 30},
    {"origem": "demo-caixa-103", "passo": "aguardando_assinatura", "dias_atras": 4},
    {"origem": "demo-caixa-104", "passo": "enviado_para_assinatura", "dias_atras": 6},
    # Chegando de outra unidade, com prazo para amanhã.
    {"origem": "demo-caixa-105", "passo": "entrada", "dias_atras": 8, "prazo_em_dias": 1},
    # Saindo para outra unidade, com folga.
    {"origem": "demo-caixa-106", "passo": "saida", "dias_atras": 5, "prazo_em_dias": 10},
    # Recebido de outra unidade com o prazo do encaminhamento já vencido.
    {"origem": "demo-caixa-107", "passo": "analise_atrasada", "dias_atras": 15,
     "prazo_em_dias": -3},
    # Enviado a outra unidade, que recusou: volta à minha mesa, em "Recusados".
    {"origem": "demo-caixa-108", "passo": "recusado", "dias_atras": 3, "prazo_em_dias": 7},
]


def _sessao(tenant_id: int) -> AsyncSession:
    """Tenant em `info`: o listener `after_begin` reaplica o `SET LOCAL` a cada
    transação, inclusive depois dos commits que os serviços fazem sozinhos."""
    db = AdminSessionLocal()
    db.info["tenant_id"] = int(tenant_id)
    return db


async def _contexto(db: AsyncSession, tenant_id: int) -> dict[str, Any] | str:
    """Resolve quem é "eu", as duas unidades e os catálogos. Devolve uma frase
    quando falta o mínimo para montar qualquer caixa."""
    from .seed_demo import _resolver_admin_id

    eu = (await db.execute(
        select(Usuario).where(Usuario.id == await _resolver_admin_id(db, tenant_id))
    )).scalar_one()
    if eu.id_unidade_trabalho is None:
        return (f"o usuário {eu.email} não tem unidade de lotação; as caixas são "
                "relativas a ela")

    outra = (await db.execute(
        select(UnidadeTrabalho.id).where(
            UnidadeTrabalho.tenant_id == tenant_id,
            UnidadeTrabalho.id != eu.id_unidade_trabalho,
            UnidadeTrabalho.excluido.is_(False),
        ).order_by(UnidadeTrabalho.id).limit(1)
    )).scalar_one_or_none()

    colega = (await db.execute(
        select(Usuario.id).where(
            Usuario.tenant_id == tenant_id, Usuario.id != eu.id,
            Usuario.excluido.is_(False), Usuario.ativo.is_(True),
        ).order_by(Usuario.id).limit(1)
    )).scalar_one_or_none()

    assunto = (await db.execute(
        select(Assunto.id).where(Assunto.tenant_id == tenant_id, Assunto.excluido.is_(False))
        .order_by((Assunto.assunto == "Demanda Cidadã").desc(), Assunto.id).limit(1)
    )).scalar_one_or_none()
    manifestante = (await db.execute(
        select(Manifestante.id).where(
            Manifestante.tenant_id == tenant_id, Manifestante.excluido.is_(False))
        .order_by(Manifestante.id).limit(1)
    )).scalar_one_or_none()
    abertura = (await db.execute(
        select(Acao.id).where(
            Acao.flag == "ABERTURA", Acao.ativo.is_(True), Acao.excluido.is_(False))
    )).scalar_one_or_none()
    if assunto is None or manifestante is None or abertura is None:
        return "faltam assunto, manifestante ou a ação ABERTURA; rode o `apply` completo antes"

    prioridade = (await db.execute(
        select(Prioridade.id).where(Prioridade.excluido.is_(False), Prioridade.ativo.is_(True))
        .order_by(Prioridade.fator, Prioridade.id).limit(1)
    )).scalar_one_or_none()
    tipo_anexo = (await db.execute(
        select(TipoAnexo.id).where(TipoAnexo.tenant_id == tenant_id, TipoAnexo.excluido.is_(False))
        .order_by(TipoAnexo.id).limit(1)
    )).scalar_one_or_none()

    return {
        "eu": eu.id, "minha_unidade": eu.id_unidade_trabalho, "outra_unidade": outra,
        "colega": colega, "assunto": assunto, "manifestante": manifestante,
        "abertura": abertura, "prioridade": prioridade, "tipo_anexo": tipo_anexo,
    }


async def _documento(db: AsyncSession, *, tenant_id: int, processo_id: int, ctx: dict) -> int:
    """Um documento do processo, para ter o que assinar."""
    mov_id = (await db.execute(
        select(Processo.id_ultima_movimentacao).where(Processo.id == processo_id)
    )).scalar_one()
    anexo = Anexo(
        tenant_id=tenant_id, id_tipo_anexo=ctx["tipo_anexo"], publico=False,
        id_usuario=ctx["eu"], ativo=True, excluido=False,
        descricao="[demo] Parecer para assinatura", qtd_paginas=1,
    )
    db.add(anexo)
    await db.flush()
    db.add(AnexoProcesso(
        tenant_id=tenant_id, id_processo=processo_id, id_anexo=anexo.id,
        id_movimentacao=mov_id, id_usuario=ctx["eu"], ativo=True, excluido=False,
        ordem=1, anexo_herdado=False,
    ))
    await db.commit()
    return anexo.id


async def _executar_passo(db: AsyncSession, *, tenant_id: int, processo_id: int,
                          spec: dict[str, Any], ctx: dict[str, Any]) -> None:
    from ..schemas.assinatura import SolicitarAssinaturaRequest
    from ..schemas.processo import (
        ArquivarRequest,
        EncaminharRequest,
        RecusarEncaminhamentoRequest,
    )
    from ..services import acoes_processo as acoes
    from ..services import assinaturas

    passo = spec["passo"]
    comum = {"tenant_id": tenant_id, "is_super_usuario": True}

    def _encaminhamento(destino: int) -> EncaminharRequest:
        return EncaminharRequest(
            id_unidade_destino=destino, id_prioridade=ctx["prioridade"],
            data_prazo=date.today() + timedelta(days=spec["prazo_em_dias"]),
            despacho="[demo] Encaminhado para análise.",
        )

    if passo == "externo":
        await db.execute(
            text("UPDATE protocolos.processo SET externo = true WHERE id = :p"),
            {"p": processo_id})
        await db.commit()
    elif passo == "arquivado":
        await acoes.arquivar(
            db, processo_id, ArquivarRequest(motivo="[demo] Demanda atendida."),
            usuario_id=ctx["eu"], **comum)
        await db.commit()
    elif passo in ("aguardando_assinatura", "enviado_para_assinatura"):
        # Aguardando: o colega pede, eu assino. Enviado: eu peço, o colega assina.
        eu_assino = passo == "aguardando_assinatura"
        solicitante, assinante = (
            (ctx["colega"], ctx["eu"]) if eu_assino else (ctx["eu"], ctx["colega"]))
        anexo_id = await _documento(db, tenant_id=tenant_id, processo_id=processo_id, ctx=ctx)
        await assinaturas.solicitar_assinatura(
            db, processo_id,
            SolicitarAssinaturaRequest(id_assinantes=[assinante], id_anexos=[anexo_id]),
            tenant_id=tenant_id, usuario_id=solicitante,
            unidade_solicitante_id=ctx["minha_unidade"])
    elif passo in ("saida", "recusado"):
        await acoes.encaminhar(
            db, processo_id, _encaminhamento(ctx["outra_unidade"]),
            usuario_id=ctx["eu"], **comum)
        if passo == "recusado":
            await acoes.recusar_encaminhamento(
                db, processo_id,
                RecusarEncaminhamentoRequest(
                    motivo="[demo] Assunto não é da competência desta unidade."),
                tenant_id=tenant_id, usuario_id=ctx["colega"] or ctx["eu"])
    elif passo in ("entrada", "analise_atrasada"):
        # O processo nasce na outra unidade e vem para a minha.
        await acoes.encaminhar(
            db, processo_id, _encaminhamento(ctx["minha_unidade"]),
            usuario_id=ctx["colega"] or ctx["eu"], **comum)
        if passo == "analise_atrasada":
            await acoes.receber(db, processo_id, usuario_id=ctx["eu"], **comum)
    else:  # pragma: no cover — erro de quem editar CAIXAS
        raise ValueError(f"passo desconhecido: {passo}")


def _o_que_falta(spec: dict[str, Any], ctx: dict[str, Any]) -> str | None:
    passo = spec["passo"]
    if passo in ("entrada", "saida", "analise_atrasada", "recusado"):
        if ctx["outra_unidade"] is None:
            return "o tenant só tem uma unidade ativa"
        if ctx["prioridade"] is None:
            return "o catálogo de prioridades está vazio (rode o seed_bootstrap)"
    if passo in ("aguardando_assinatura", "enviado_para_assinatura"):
        if ctx["colega"] is None:
            return "não há um segundo usuário ativo para a outra ponta da assinatura"
        if ctx["tipo_anexo"] is None:
            return "o tenant não tem tipo de anexo cadastrado"
    return None


async def aplicar(tenant_id: int) -> dict[str, int]:
    """Garante os processos de `CAIXAS`. Devolve quantos criou e quantos pulou."""
    from .seed_demo import _get_or_create_processo

    contagens = {"caixas_processos_criados": 0, "caixas_itens_pulados": 0}

    async with _sessao(tenant_id) as db:
        ctx = await _contexto(db, tenant_id)
        if isinstance(ctx, str):
            print(f"[aviso] caixas de demonstração não montadas: {ctx}.")
            contagens["caixas_itens_pulados"] = len(CAIXAS)
            return contagens

    for spec in CAIXAS:
        falta = _o_que_falta(spec, ctx)
        if falta:
            print(f"[aviso] caixa '{spec['passo']}' pulada: {falta}.")
            contagens["caixas_itens_pulados"] += 1
            continue

        nasce_fora = spec["passo"] in ("entrada", "analise_atrasada")
        unidade = ctx["outra_unidade"] if nasce_fora else ctx["minha_unidade"]
        async with _sessao(tenant_id) as db:
            pid, criou = await _get_or_create_processo(
                db, tenant_id=tenant_id,
                spec={"origem": spec["origem"], "dias_atras": spec["dias_atras"],
                      "estado": "aberto", "servico_slug": f"caixa {spec['passo']}",
                      "prazo_servico_dias": spec.get("prazo_servico_dias")},
                id_servico=None, id_assunto=ctx["assunto"],
                id_manifestante=ctx["manifestante"], id_unidade_proprietaria=unidade,
                id_usuario_abertura=ctx["eu"], acao_abertura_id=ctx["abertura"],
            )
            await db.commit()
            if not criou:
                continue
            contagens["caixas_processos_criados"] += 1
            try:
                await _executar_passo(
                    db, tenant_id=tenant_id, processo_id=pid, spec=spec, ctx=ctx)
            except Exception as exc:  # noqa: BLE001 — demonstração: avisa e segue
                await db.rollback()
                print(f"[aviso] caixa '{spec['passo']}': o processo foi criado, mas o "
                      f"passo falhou ({type(exc).__name__}: {exc}).")
    return contagens


async def limpar_tramitacao(db: AsyncSession, proc_ids: list[int]) -> None:
    """Apaga o que a tramitação de demonstração pendura nos processos, na ordem
    das FKs. É chamado pelo `reset` do `seed_demo` ANTES de ele apagar anexos e
    movimentações: assinatura aponta para anexo, encaminhamento e despacho para
    movimentação, e a movimentação de arquivamento para `arquivamento`."""
    if not proc_ids:
        return
    ids = {"ids": proc_ids}
    await db.execute(text(
        "DELETE FROM protocolos.assinatura_anexo WHERE id_processo = ANY(:ids)"), ids)
    await db.execute(text(
        "DELETE FROM protocolos.usuario_assinatura WHERE id_solicitacao_assinatura IN "
        "(SELECT id FROM protocolos.solicitacao_assinatura WHERE id_processo = ANY(:ids))"), ids)
    await db.execute(text(
        "DELETE FROM protocolos.solicitacao_assinatura WHERE id_processo = ANY(:ids)"), ids)
    await db.execute(delete(Encaminhamento).where(Encaminhamento.id_processo.in_(proc_ids)))
    await db.execute(text(
        "DELETE FROM protocolos.despacho WHERE id_processo = ANY(:ids)"), ids)
    arquivamentos = [r for (r,) in (await db.execute(text(
        "SELECT id_arquivamento FROM protocolos.movimentacao "
        "WHERE id_processo = ANY(:ids) AND id_arquivamento IS NOT NULL"), ids))]
    if arquivamentos:
        await db.execute(text(
            "UPDATE protocolos.movimentacao SET id_arquivamento = NULL "
            "WHERE id_processo = ANY(:ids)"), ids)
        await db.execute(text(
            "DELETE FROM protocolos.arquivamento WHERE id = ANY(:a)"), {"a": arquivamentos})
