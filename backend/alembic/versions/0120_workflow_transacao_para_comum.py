"""Move a transação `workflow` do módulo `protocolo` para `comum`.

Revision ID: 0120
Revises: 0119
Create Date: 2026-09-20

Item 2.2 do backlog (Transporte Regulado): editar/ler o DSL de um workflow de
transporte (`routers/workflow.py`) exigia a transação `workflow`, que só
estava ligada ao módulo `protocolo` — um tenant com só `transporte`
contratado não conseguia usar o motor genérico de workflow para as próprias
definições (`transporte-ocorrencia`/`transporte-alvara`/
`transporte-recadastramento`) sem também contratar `protocolo`. `workflow`
não é conteúdo de nenhum módulo específico — é infraestrutura do motor,
reaproveitada por protocolo (processo) e transporte (ocorrência/alvará/
convocação) por igual — por isso vai para `comum`, o módulo não-contratável
que nunca é bloqueado (spec da F1, ver 0073).

Só mover a transação NÃO bastava: as 5 rotas GET genéricas de
`routers/workflow.py` (`/workflow-definitions`, `/workflow-definitions/
{wf_id}`, `/workflow-definitions/{wf_id}/versoes`, `/workflow-instances`,
`/workflow-instances/{instance_id}`) tinham `require_modulo("protocolo")`
FIXO — um gate independente da transação, que continuaria bloqueando um
tenant só-transporte mesmo depois desta migration. A mesma mudança de código
que acompanha esta migration troca essas 5 rotas para
`require_modulo_qualquer("protocolo", "transporte")` (novo em
`auth/modulos.py`). As outras 3 rotas do arquivo que também usavam
`require_modulo("protocolo")` — `/tipo-processo-workflow` (mapeia
`tipo_processo`, conceito só de `processo`) e `/workflow-alertas` (o SELECT
já faz INNER JOIN em `Processo`, então é processo-específico na prática) —
ficaram como estavam, de propósito: não são infraestrutura genérica.

`app/cli/seed_bootstrap.py::MODULO_TRANSACOES` é só ADITIVO (nunca remove
vínculo): mudar o dict e rodar o seed de novo criaria o vínculo novo
(`comum`, `workflow`) mas deixaria o antigo (`protocolo`, `workflow`) para
trás. Isso NÃO seria inócuo — `services/modulos.py::codigos_bloqueados` marca
um código como bloqueado se ELE TIVER QUALQUER vínculo com um módulo
indisponível, então o vínculo velho continuaria bloqueando `workflow` (no
`require_permission("workflow", ...)` das rotas de escrita, que não têm
`require_modulo` nenhum) para tenants sem `protocolo`. A migration por isso
apaga o vínculo velho e insere o novo diretamente — não depende de o próximo
`seed_bootstrap` rodar para ter efeito completo.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0120"
down_revision: str | Sequence[str] | None = "0119"
branch_labels = None
depends_on = None

S = "aprimora_py"


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM {S}.modulo_transacao mt
        USING {S}.modulo m, utils.transacao t
        WHERE mt.id_modulo = m.id
          AND mt.id_transacao = t.id
          AND m.slug = 'protocolo'
          AND t.codigo = 'workflow'
        """
    )
    op.execute(
        f"""
        INSERT INTO {S}.modulo_transacao (id_modulo, id_transacao)
        SELECT m.id, t.id
          FROM {S}.modulo m, utils.transacao t
         WHERE m.slug = 'comum'
           AND t.codigo = 'workflow'
        ON CONFLICT (id_modulo, id_transacao) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM {S}.modulo_transacao mt
        USING {S}.modulo m, utils.transacao t
        WHERE mt.id_modulo = m.id
          AND mt.id_transacao = t.id
          AND m.slug = 'comum'
          AND t.codigo = 'workflow'
        """
    )
    op.execute(
        f"""
        INSERT INTO {S}.modulo_transacao (id_modulo, id_transacao)
        SELECT m.id, t.id
          FROM {S}.modulo m, utils.transacao t
         WHERE m.slug = 'protocolo'
           AND t.codigo = 'workflow'
        ON CONFLICT (id_modulo, id_transacao) DO NOTHING
        """
    )
