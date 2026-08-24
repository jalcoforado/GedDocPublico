r"""Solta os CHECKs de `situacao` que o workflow passa a arbitrar — P8 D1 (Task 3).

Revision ID: 0096
Revises: 0095
Create Date: 2026-08-23

Spec: `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-master.md`
(fase D, task 3, §Situação↔estado).

Até aqui `transporte_regulado.ocorrencia.situacao` tinha um CHECK
(`ck_ocorrencia_situacao`) enumerando os cinco valores válidos — "o CHECK do
banco é a rede", como o comentário de `SITUACOES_FINAIS_OCORRENCIA` em
`services/transporte_regulado.py` registrava. A partir desta task o DSL de
`SEMENTES["transporte-ocorrencia"]` (`services/transporte_workflow.py`) é
quem arbitra transição válida — e o DSL é POR TENANT, editável. Um CHECK de
banco fixo nos cinco valores originais barraria qualquer tenant que
adicionasse um estado novo ao próprio workflow (ex.: `escalada`), então a
rede tem de sair daqui.

Confirmado com `\d transporte_regulado.ocorrencia` /
`\d transporte_regulado.recadastramento_convocacao` antes de escrever esta
migration:

- `ocorrencia` tem `ck_ocorrencia_situacao` — dropado aqui.
- `recadastramento_convocacao` NÃO tem CHECK de `situacao` hoje (só
  `ck_recadconv_vinculo_exclusivo`, que não é sobre `situacao` e não é
  tocado). O `DROP CONSTRAINT IF EXISTS` cobre os dois casos sem quebrar se
  algum dia um for adicionado e removido de novo — e deixa esta migration
  seguinte-prova caso a Task 5 (convocação no workflow) precise do mesmo
  padrão antes de nomear um CHECK que nunca existiu.

O CHECK de `situacao` de `permissionario`/`empresa`/`vistoria` NÃO é tocado
— esses fluxos não entram no workflow (fora do escopo da fase D).

## Downgrade

Recria `ck_ocorrencia_situacao` com o conjunto ORIGINAL de cinco valores
(`registrada`, `em_apuracao`, `procedente`, `improcedente`, `arquivada`).
Antes de recriar, confere se alguma linha tem `situacao` fora desse
conjunto — um tenant que já tiver estendido o próprio DSL com um estado
novo (ex.: `escalada`) e usado esse estado numa ocorrência real torna o
downgrade inseguro: recriar o CHECK deixaria a tabela com uma linha que o
violaria (Postgres nem aceitaria `ADD CONSTRAINT` nesse caso — o `RAISE
EXCEPTION` aqui só adianta o diagnóstico e nomeia a causa, em vez de deixar
o operador ler um erro genérico de `duplicate key`/`check constraint
violated`). Mesmo padrão de "erro alto, decisão humana" da 0094/0095 — não
apagar nem reescrever a linha por trás do operador.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0096"
down_revision: str | Sequence[str] | None = "0095"
branch_labels = None
depends_on = None

S = "transporte_regulado"

_VALORES_ORIGINAIS_OCORRENCIA = (
    "registrada", "em_apuracao", "procedente", "improcedente", "arquivada",
)


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.ocorrencia DROP CONSTRAINT IF EXISTS ck_ocorrencia_situacao"
    )
    op.execute(
        f"ALTER TABLE {S}.recadastramento_convocacao "
        f"DROP CONSTRAINT IF EXISTS ck_recadconv_situacao"
    )


def downgrade() -> None:
    lista = ", ".join(f"'{v}'" for v in _VALORES_ORIGINAIS_OCORRENCIA)
    # A lista entre aspas (`lista`) vai só na cláusula `IN (...)`. Embuti-la
    # também dentro do literal de string da mensagem `RAISE EXCEPTION`
    # quebraria a string (aspas simples fecham o literal no meio) — por
    # isso a mensagem cita o conjunto sem aspas, valores separados só por
    # vírgula.
    lista_msg = ", ".join(_VALORES_ORIGINAIS_OCORRENCIA)
    op.execute(
        f"""
        DO $$
        DECLARE
            n_fora integer;
        BEGIN
            SELECT count(*) INTO n_fora
            FROM {S}.ocorrencia
            WHERE situacao NOT IN ({lista});

            IF n_fora > 0 THEN
                RAISE EXCEPTION
                    'downgrade 0096 abortado: % linha(s) de ocorrencia com '
                    'situacao fora do conjunto original ({lista_msg}) — algum '
                    'tenant estendeu o DSL do workflow com estado novo; não '
                    'é seguro recriar ck_ocorrencia_situacao', n_fora;
            END IF;
        END $$;
        """
    )
    op.execute(
        f"ALTER TABLE {S}.ocorrencia ADD CONSTRAINT ck_ocorrencia_situacao "
        f"CHECK (situacao IN ({lista}))"
    )
    # `recadastramento_convocacao` não tinha CHECK antes desta migration —
    # não recriar nenhum aqui preservaria o estado pré-upgrade fielmente;
    # nada a fazer.
