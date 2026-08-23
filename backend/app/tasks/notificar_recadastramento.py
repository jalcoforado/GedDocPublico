"""Task beat: notifica titulares de recadastramento em atraso/lembrete — Fase C2.

Para cada tenant ativo, para cada `RecadastramentoConvocacao` NÃO excluída com
situação em `SITUACOES_ABERTAS` (suspensa fica fora naturalmente — não está
naquele conjunto), decide **no máximo um** gatilho por rodada, a partir da
JANELA em que o prazo se encontra hoje:

- `prazo < hoje`            → janela "atraso"
- `hoje <= prazo <= hoje+N` → janela "lembrete" (N = `dias_antes`)
- `prazo > hoje+N`          → janela "convocacao"

As três janelas são MUTUAMENTE EXCLUSIVAS por construção (particionam o eixo
do prazo). Isso é deliberado, e diferente de uma cadeia "tenta atraso, se já
tem tenta lembrete, se já tem tenta convocacao": essa segunda leitura pareceria
mais fiel ao texto "atraso > lembrete > convocacao" da spec, mas quebra a
idempotência — rodar a task duas vezes no mesmo dia enviaria 'lembrete' logo
depois de já ter enviado 'atraso' para a mesma convocação vencida, porque
"sem registro de lembrete" também seria verdade. Com janela fixa pelo prazo,
uma convocação vencida SÓ disputa a janela de atraso nesta e em qualquer
rodada futura enquanto seguir vencida — nunca cai para lembrete/convocacao.

Dentro da janela, o gatilho só é emitido se ainda não existir
`RecadastramentoNotificacao(id_convocacao, gatilho)` — dedupe carregado em
UMA query para todas as convocações do tenant, não uma por convocação.

Sem e-mail do titular (permissionário OU empresa) → pula SEM registrar nada,
para a convocação ser reavaliada — e notificada — assim que o e-mail for
cadastrado. Com e-mail → `notificacoes.enviar` (que já commita) e grava o
`RecadastramentoNotificacao` com `id_usuario=None` (ninguém apertou botão).

Falha num tenant não derruba os demais — mesmo padrão de
`verificar_sla_workflows`.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import date, datetime, timedelta

from sqlalchemy import select

from ..models import (
    Empresa,
    Permissionario,
    RecadastramentoConvocacao,
    RecadastramentoNotificacao,
    Tenant,
)
from ..services.notificacoes import Destinatario, enviar as notificar_enviar
from ..services.transporte_regulado import SITUACOES_ABERTAS
from ._task_db import task_session_scope
from .celery_app import celery_app

logger = logging.getLogger("transporte.recadastramento")

LINK_RECADASTRAMENTO = "/m/transporte/recadastramento"


@celery_app.task(name="app.tasks.notificar_recadastramento.run", bind=True)
def run(self, dias_antes: int = 5, tenant_id: int | None = None) -> str:
    """dias_antes: janela de antecedência do lembrete (padrão 5 dias).
    tenant_id=None → varre todos os tenants ativos (modo beat).
    tenant_id=int → restringe a um tenant (dispatch manual / testes) — mesmo
    padrão de `verificar_sla_workflows.run`."""
    return asyncio.run(notificar_recadastramento(dias_antes, tenant_id))


def _mensagem(gatilho: str, prazo: date) -> tuple[str, str]:
    """(titulo, mensagem) — texto neutro, sem nome/CPF/CNPJ do titular."""
    prazo_fmt = prazo.strftime("%d/%m/%Y")
    if gatilho == "atraso":
        return (
            "Recadastramento em atraso",
            f"O prazo do seu recadastramento venceu em {prazo_fmt}. "
            "Regularize o quanto antes para evitar a suspensão do alvará.",
        )
    if gatilho == "lembrete":
        return (
            "Recadastramento: prazo se aproximando",
            f"O prazo do seu recadastramento é {prazo_fmt}. "
            "Conclua o quanto antes para evitar atraso.",
        )
    return (
        "Recadastramento: convocação",
        f"Você foi convocado para o recadastramento. Prazo: {prazo_fmt}.",
    )


def _janela(conv: RecadastramentoConvocacao, hoje: date, limite_lembrete: date) -> str:
    if conv.prazo < hoje:
        return "atraso"
    if conv.prazo <= limite_lembrete:
        return "lembrete"
    return "convocacao"


async def _processar_tenant(
    session_factory, tenant_id: int, dias_antes: int
) -> tuple[int, int]:
    """Retorna (convocacoes_avaliadas, notificacoes_enviadas)."""
    hoje = date.today()
    limite_lembrete = hoje + timedelta(days=dias_antes)

    async with session_factory() as db:
        convs = (
            await db.execute(
                select(RecadastramentoConvocacao).where(
                    RecadastramentoConvocacao.tenant_id == tenant_id,
                    RecadastramentoConvocacao.excluido.is_(False),
                    RecadastramentoConvocacao.situacao.in_(SITUACOES_ABERTAS),
                )
            )
        ).scalars().all()

        if not convs:
            return 0, 0

        conv_ids = [c.id for c in convs]

        # Dedup em LOTE: pares (id_convocacao, gatilho) já registrados,
        # numa query só — não uma por convocação.
        registrados = (
            await db.execute(
                select(
                    RecadastramentoNotificacao.id_convocacao,
                    RecadastramentoNotificacao.gatilho,
                ).where(
                    RecadastramentoNotificacao.tenant_id == tenant_id,
                    RecadastramentoNotificacao.id_convocacao.in_(conv_ids),
                    RecadastramentoNotificacao.gatilho.isnot(None),
                )
            )
        ).all()
        ja_notificado = {(cid, gat) for cid, gat in registrados}

        perm_ids = [c.id_permissionario for c in convs if c.id_permissionario]
        emp_ids = [c.id_empresa for c in convs if c.id_empresa]

        email_por_perm: dict[int, str | None] = {}
        if perm_ids:
            rows = (
                await db.execute(
                    select(Permissionario.id, Permissionario.email).where(
                        Permissionario.id.in_(perm_ids)
                    )
                )
            ).all()
            email_por_perm = dict(rows)

        email_por_emp: dict[int, str | None] = {}
        if emp_ids:
            rows = (
                await db.execute(
                    select(Empresa.id, Empresa.email).where(Empresa.id.in_(emp_ids))
                )
            ).all()
            email_por_emp = dict(rows)

    avaliadas = 0
    enviadas = 0

    for conv in convs:
        avaliadas += 1

        gatilho = _janela(conv, hoje, limite_lembrete)
        if (conv.id, gatilho) in ja_notificado:
            # Esta janela já foi avisada — nenhum fallback para a próxima
            # janela: ver docstring do módulo sobre idempotência.
            continue

        email = (
            email_por_perm.get(conv.id_permissionario)
            if conv.id_permissionario is not None
            else email_por_emp.get(conv.id_empresa)
        )
        if not email:
            # Sem e-mail: pula SEM registrar, para ser reavaliada (e
            # notificada) assim que o e-mail for cadastrado.
            continue

        titulo, mensagem = _mensagem(gatilho, conv.prazo)

        async with session_factory() as db:
            criadas = await notificar_enviar(
                db,
                tenant_id=tenant_id,
                destinatarios=[Destinatario(email=email)],
                canais=["email"],
                tipo="recadastramento.notificacao",
                titulo=titulo,
                mensagem=mensagem,
                link_url=LINK_RECADASTRAMENTO,
                payload={"id_convocacao": conv.id, "gatilho": gatilho},
            )
            if not criadas:
                continue

            if criadas[0].erro is not None:
                # `notificacoes.enviar` não levanta em falha de driver — grava
                # `erro` na Notificacao e retorna normalmente. Se registrássemos
                # o `RecadastramentoNotificacao` aqui, o dedupe da próxima
                # rodada trataria esta janela como "já avisada" para sempre,
                # mesmo o e-mail nunca tendo saído. NÃO registrar preserva o
                # gatilho para a rodada seguinte tentar de novo.
                logger.warning(
                    "recadastramento_notificacao_envio_falhou",
                    extra={
                        "tenant_id": tenant_id,
                        "id_convocacao": conv.id,
                        "gatilho": gatilho,
                        "erro": criadas[0].erro,
                    },
                )
                continue

            db.add(
                RecadastramentoNotificacao(
                    tenant_id=tenant_id,
                    id_convocacao=conv.id,
                    id_notificacao=criadas[0].id,
                    id_usuario=None,
                    gatilho=gatilho,
                    criado_em=datetime.utcnow(),
                )
            )
            await db.commit()
            enviadas += 1

    return avaliadas, enviadas


async def notificar_recadastramento(
    dias_antes: int = 5, tenant_id: int | None = None
) -> str:
    """Varre os tenants ativos e dispara os avisos da rodada.

    `tenant_id=None` (padrão de produção/beat) varre TODOS os tenants ativos.
    `tenant_id=<int>` restringe a um só — é o que os testes usam: abrir um
    engine por tenant ativo é caro, e o banco de dev acumula milhares de
    tenants de rodadas de teste anteriores (nunca desativados), então um
    scan completo por teste seria da ordem de minutos por chamada.

    Chamada diretamente pelos testes (sem passar por Celery) e pela task
    `run` acima (que só embrulha `asyncio.run`, igual às tasks vizinhas).
    """
    async with task_session_scope() as (_engine, raw_factory):
        async with raw_factory() as db:
            stmt = select(Tenant.id, Tenant.slug).where(Tenant.ativo.is_(True))
            if tenant_id is not None:
                stmt = stmt.where(Tenant.id == tenant_id)
            tenants = (await db.execute(stmt)).all()

    total_avaliadas = 0
    total_enviadas = 0
    erros: list[str] = []

    for tid, slug in tenants:
        try:
            async with task_session_scope(tenant_id=tid) as (_e, factory):
                avaliadas, enviadas = await _processar_tenant(factory, tid, dias_antes)
                total_avaliadas += avaliadas
                total_enviadas += enviadas
                logger.info(
                    "recadastramento_notificacao_tenant",
                    extra={
                        "tenant_id": tid,
                        "tenant_slug": slug,
                        "convocacoes_avaliadas": avaliadas,
                        "notificacoes_enviadas": enviadas,
                    },
                )
        except Exception as e:  # noqa: BLE001
            erros.append(f"tenant {slug} ({tid}): {e}")
            logger.warning(
                "recadastramento_notificacao_falhou_tenant",
                extra={"tenant_id": tid, "tenant_slug": slug, "erro": str(e)},
            )
            logger.debug(traceback.format_exc())

    sumario = (
        f"Notificação de recadastramento concluída — {len(tenants)} tenant(s)\n"
        f"Convocações avaliadas: {total_avaliadas}\n"
        f"Notificações enviadas: {total_enviadas}\n"
    )
    if erros:
        sumario += "Erros:\n" + "\n".join(f"  - {e}" for e in erros) + "\n"
    return sumario
