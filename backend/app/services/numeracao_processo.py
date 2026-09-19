"""Numeração de processo — extraído em E3 (benchmark SUiTE).

Reaproveitado entre a abertura (processo não-rascunho, numera na hora) e a
emissão diferida no primeiro `encaminhar()` de um rascunho
(`services/acoes_processo.py`). Ver
`docs/superpowers/specs/2026-09-19-e3-rascunho-sem-numero-design.md`.
"""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Processo, Tenant


class NumeracaoError(Exception):
    pass


async def gerar_numero_processo(db: AsyncSession) -> str:
    """Sequencial global via protocolos.numero_processo (nextval — atômico,
    concorrência já garantida pelo Postgres, sem lock de aplicação)."""
    numero_row = (
        await db.execute(text("SELECT protocolos.gerar_numero_processo_string() AS num"))
    ).first()
    if numero_row is None or not numero_row.num:
        raise NumeracaoError("Falha ao gerar número de processo")
    return numero_row.num


async def emitir_numero(
    db: AsyncSession,
    processo: Processo,
    *,
    tenant: Tenant,
    usuario_id: int,
    now: datetime,
) -> None:
    """Atribui numero_processo (+ nup se `usar_nup_federal`) a um processo
    que ainda não tem número. Idempotente: não faz nada se já tiver —
    chamador não precisa checar `situacao` antes de chamar.

    Não commita — quem chama controla a transação.
    """
    if processo.numero_processo is not None:
        return

    processo.numero_processo = await gerar_numero_processo(db)

    if tenant.usar_nup_federal and tenant.codigo_orgao_nup:
        from .nup import NupError, gerar_nup

        try:
            nup_str, sequencial = await gerar_nup(db, tenant=tenant, ano=now.year)
            processo.nup = nup_str
            processo.numero_sequencial_orgao = sequencial
        except NupError as e:
            # Mesma política de abertura_processo.py: falha de NUP não
            # bloqueia a numeração em si — registra audit como warning.
            from .audit import log as audit_log_warn

            await audit_log_warn(
                db,
                tenant_id=tenant.id,
                id_usuario=usuario_id,
                acao="processo.nup_falhou",
                entidade="processo",
                id_entidade=processo.id,
                payload={"erro": str(e)},
            )
