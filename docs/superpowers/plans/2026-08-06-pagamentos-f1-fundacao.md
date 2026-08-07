# Pagamentos F1 — Fundação do fluxo: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar o `status` monolítico de 16 valores em três dimensões independentes, inserir a etapa do Gestor da Pasta antes da validação financeira e retirar da validação financeira qualquer poder de encerrar a solicitação.

**Architecture:** Um módulo novo de domínio (`pagamentos_estados.py`) concentra os três enums, as transições permitidas e a derivação do `status` legado — que sobrevive como coluna calculada até a F5. As transições continuam exclusivamente em `services/pagamentos_debitos.py`, que ganha as funções do gestor e perde a rejeição a partir da validação. Uma migration acrescenta as colunas, faz o backfill pelo mapa do §4.5 da spec e cria a transação `pagamento_gerir`. No frontend, cada etapa do fluxo vira item de menu e o detalhe passa a mostrar as três dimensões, um stepper de cinco etapas e um bloco de próxima ação.

**Tech Stack:** FastAPI · SQLAlchemy 2 async · Alembic · Postgres com RLS · pytest/pytest-asyncio · Next.js 15 App Router · React 19 · Tailwind · vitest

**Spec:** `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md`
**Branch:** `refactor/pagamentos-fluxo` (já criada, spec commitada em `afffdbe`)
**Base:** `main` em `89cc0e6`; head Alembic `0084`

---

## Global Constraints

- **Idioma:** código, comentários, docstrings, mensagens de erro e commits em **português (pt-BR)**.
- **Head Alembic único.** A migration desta fatia é `0085`, `down_revision = "0084"`. Conferir com `docker exec aprimora-py-backend alembic heads` antes e depois.
- **`autogenerate` está desligado.** Toda migration é escrita à mão.
- **Coluna nova em tabela existente herda RLS e grants** — não repetir o boilerplate. Tabela nova exigiria; esta fatia não cria tabela nenhuma.
- **Suíte verde = `2 failed / N passed`** com exatamente estas duas, que não são regressão: `test_jwt_compat::test_emitted_token_has_required_claims` e `test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`. N era 1149 em 2026-08-05.
- **Comando da suíte:** `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q`. Leva ~14 min e estoura o teto de 600 s da ferramenta — **rodar em segundo plano desde o começo**.
- **Um arquivo:** `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_x.py -v`
- **Não rodar dois pytest concorrentes contra o mesmo Postgres, nem editar a árvore com a suíte de pé.** O backend roda com bind-mount do working tree; as duas coisas produzem falha falsa.
- **Type-check obrigatório antes de commitar frontend:** `cd frontend && npx tsc --noEmit`.
- **Nunca rodar `npm run lint`** — o projeto não tem ESLint e `next lint` trava.
- **Teste HTTP com usuário comum em toda rota nova.** O bypass de super-usuário em `auth/perms.py` retorna antes do `getattr(item, action)`; defeito que só aparece para não-SU passa por toda a bateria. Padrão em `test_permissoes_modulo.py::_cria_usuario_comum`. O tenant precisa contratar o módulo `pagamentos`, senão o gate barra antes com 403.
- **Nada de id de FK cravado no teste.** O CI roda em banco limpo; use ids que o próprio teste provisiona.
- **`tenant_id` sempre vem do caller** (`require_tenant_id`), nunca do payload.
- **Transação nova em `utils.transacao` exige entrada em `MODULO_TRANSACOES`** (`app/cli/seed_bootstrap.py`), senão `tests/test_guarda_modularizacao.py` reprova.
- **Rota literal antes da paramétrica.** `tests/test_guarda_ordem_rotas.py` varre e reprova.
- **`Paginated<X>` em `api.ts`** onde o `response_model` for paginado.
- **Commits frequentes**, um por task, em português, sem `--no-verify`.

---

## Estrutura de arquivos

**Criar:**

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/services/pagamentos_estados.py` | Domínio puro: os três enums, as transições legais, a derivação do `status` legado, o rótulo humano e o responsável de cada etapa. Sem I/O, sem SQLAlchemy. |
| `backend/app/services/pagamentos_guardas.py` | `assert_segregacao` e `assert_lock_version`. Puro exceto pelo objeto `Debito`. |
| `backend/alembic/versions/0085_pagamentos_tres_dimensoes.py` | Colunas, backfill, `id_unidade`, `categoria` de contrato, transação `pagamento_gerir`. |
| `backend/tests/test_pagamentos_estados.py` | Unitários do domínio. |
| `backend/tests/test_pagamentos_fluxo_gestor.py` | Etapa do gestor ponta a ponta. |
| `backend/tests/test_pagamentos_validacao_sem_rejeicao.py` | A regra central, provada por inversão. |
| `backend/tests/test_pagamentos_segregacao.py` | Segregação de funções, inclusive com super-usuário. |
| `backend/tests/test_pagamentos_concorrencia.py` | Conflito de `lock_version`. |
| `backend/tests/test_guarda_status_legado.py` | Guarda: lista fechada de consumidores de `Debito.status`. |
| `frontend/components/pagamentos/SituacoesDebito.tsx` | As três dimensões como bloco reutilizável. |
| `frontend/components/pagamentos/EtapasFluxo.tsx` | Stepper das cinco etapas. Substitui `RitoPagamento`. |
| `frontend/components/pagamentos/ProximaAcao.tsx` | Bloco "o que precisa ser feito agora". |
| `frontend/components/pagamentos/situacoes.ts` | Rótulos e intents das três dimensões. |
| `frontend/app/(app)/m/pagamentos/gestor/page.tsx` | Tela da etapa do gestor. |
| `frontend/app/(app)/m/pagamentos/validacao/page.tsx` | Tela da etapa de validação financeira. |
| `frontend/components/pagamentos/ListaEtapa.tsx` | Lista compartilhada pelas telas de etapa. |
| `frontend/__tests__/pagamentos-situacoes.test.tsx` | Rótulos e stepper. |

**Modificar:**

| Arquivo | O quê |
|---|---|
| `backend/app/models/pagamentos.py:157-188` | 8 colunas novas em `Debito`; `categoria` em `Contrato`. |
| `backend/app/schemas/pagamentos.py:321-399` | Os três `Literal`, `DebitoOut`, `DebitoCreate` (`id_unidade`), payloads com `lock_version`. |
| `backend/app/services/pagamentos_debitos.py` | Transições novas; `_registrar_transicao` grava as três dimensões; rejeição sai da validação. |
| `backend/app/routers/pagamentos_debitos.py` | Endpoints do gestor; 410 nos descontinuados; `pagamento_gerir`. |
| `backend/app/cli/seed_bootstrap.py:62-77` | `pagamento_gerir` em `MODULO_TRANSACOES`. |
| `frontend/lib/api.ts` | Tipos das três dimensões, `id_unidade`, `lock_version`, métodos do gestor. |
| `frontend/lib/menus/pagamentos.ts` | Menu por etapa. |
| `frontend/__tests__/menus.test.tsx` | `PERMISSOES_ESPERADAS`. |
| `frontend/app/(app)/m/pagamentos/contas-a-pagar/[id]/page.tsx` | Cabeçalho, stepper, próxima ação, ações contextuais. |
| `frontend/components/pagamentos/statusDebito.ts` | Marcado como legado; abas migradas. |

**Não tocar nesta fatia:** `pagamentos_conciliacao.py`, `pagamentos_excecoes.py`, `pagamentos_caixa.py`, `pagamentos_export.py`, `pagamentos_filas.py`. Eles leem `Debito.status`, que continua correto por derivação. Migram na F5.

---

## Task 1: Domínio dos três estados

**Files:**
- Create: `backend/app/services/pagamentos_estados.py`
- Test: `backend/tests/test_pagamentos_estados.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `TRAMITACAO: frozenset[str]`, `FILA: frozenset[str]`, `PAGAMENTO: frozenset[str]`
  - `TRANSICOES_TRAMITACAO: dict[str, frozenset[str]]`
  - `ETAPA_POR_TRAMITACAO: dict[str, str]` — etapa do stepper (`UNIDADE|GESTOR|VALIDACAO|AUTORIDADE|TESOURARIA`)
  - `TERMINAIS: frozenset[str]`
  - `status_legado(tramitacao: str, fila: str, pagamento: str) -> str`
  - `transicao_permitida(atual: str, novo: str) -> bool`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_pagamentos_estados.py`:

```python
"""Domínio das três dimensões de situação do débito (spec §4.1).

Testes puros — não tocam banco. O que eles travam é a propriedade que a F1
inteira depende: as três dimensões são independentes, e o `status` legado é
função delas, não o contrário.
"""
from app.services import pagamentos_estados as est


def test_as_tres_dimensoes_nao_compartilham_valor():
    """Valor repetido entre dimensões faria o status legado ficar ambíguo."""
    assert not (est.TRAMITACAO & est.FILA)
    assert not (est.FILA & est.PAGAMENTO)
    # TRAMITACAO e PAGAMENTO compartilham 'CANCELADA' de propósito: cancelar a
    # solicitação cancela a execução. É o único par permitido.
    assert (est.TRAMITACAO & est.PAGAMENTO) == {"CANCELADA"}


def test_toda_tramitacao_tem_etapa_no_stepper():
    assert set(est.ETAPA_POR_TRAMITACAO) == est.TRAMITACAO


def test_terminais_nao_tem_saida():
    for t in est.TERMINAIS:
        assert est.TRANSICOES_TRAMITACAO[t] == frozenset()


def test_validacao_nao_alcanca_nenhum_terminal():
    """A regra central da fatia (spec §3.1): a validação financeira não encerra."""
    saidas = est.TRANSICOES_TRAMITACAO["AGUARDANDO_VALIDACAO"]
    assert saidas & est.TERMINAIS == frozenset()
    assert saidas == frozenset({"AGUARDANDO_AUTORIDADE", "AJUSTE_VALIDACAO"})


def test_gestor_alcanca_rejeicao_e_autoridade_alcanca_indeferimento():
    assert "REJEITADA_GESTOR" in est.TRANSICOES_TRAMITACAO["AGUARDANDO_GESTOR"]
    assert "INDEFERIDA_AUTORIDADE" in est.TRANSICOES_TRAMITACAO["AGUARDANDO_AUTORIDADE"]


def test_status_legado_cobre_toda_combinacao_alcancavel():
    """Nenhuma combinação atingível pode cair no fallback silencioso."""
    for tram in est.TRAMITACAO:
        for fila in est.FILA:
            for pag in est.PAGAMENTO:
                assert status_valido(est.status_legado(tram, fila, pag))


def status_valido(s: str) -> bool:
    return s in {
        "RASCUNHO", "EM_VALIDACAO", "DEVOLVIDO", "VALIDADO", "ENVIADO_SECRETARIO",
        "AGUARDANDO_AUTORIZACAO", "AUTORIZADO", "ENVIADO_TESOURARIA",
        "EM_PROCESSAMENTO", "PAGO_PARCIAL", "PAGO", "CONCILIADO", "REJEITADO",
        "SUSPENSO", "CANCELADO", "ESTORNADO",
    }


def test_status_legado_prioriza_execucao_sobre_tramitacao():
    """Autorizada e paga → PAGO. A execução, quando começou, manda no legado."""
    assert est.status_legado("AUTORIZADA", "CONCLUIDA", "PAGA") == "PAGO"
    assert est.status_legado("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL") == "PAGO_PARCIAL"
    assert est.status_legado("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA") == "AUTORIZADO"


def test_status_legado_das_etapas_pre_autorizacao():
    assert est.status_legado("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA") == "RASCUNHO"
    assert est.status_legado("AGUARDANDO_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "EM_VALIDACAO"
    assert est.status_legado("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA") == "EM_VALIDACAO"
    assert est.status_legado("AJUSTE_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "DEVOLVIDO"
    assert est.status_legado("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA") == "ENVIADO_SECRETARIO"
    assert est.status_legado("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA") == "REJEITADO"
    assert est.status_legado("INDEFERIDA_AUTORIDADE", "NAO_REGISTRADA", "NAO_INICIADA") == "REJEITADO"
    assert est.status_legado("CANCELADA", "RETIRADA", "CANCELADA") == "CANCELADO"


def test_transicao_permitida():
    assert est.transicao_permitida("RASCUNHO", "AGUARDANDO_GESTOR")
    assert not est.transicao_permitida("RASCUNHO", "AGUARDANDO_AUTORIDADE")
    assert not est.transicao_permitida("AGUARDANDO_VALIDACAO", "REJEITADA_GESTOR")
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_estados.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.pagamentos_estados'`.

- [ ] **Step 3: Implementar**

Criar `backend/app/services/pagamentos_estados.py`:

```python
"""As três dimensões de situação do débito — domínio puro (spec §4.1).

Até a F1 um único `Debito.status` de 16 valores respondia por três perguntas
independentes: onde está a decisão, onde está na fila cronológica e onde está a
execução. Como os valores eram mutuamente exclusivos, um débito `PAGO_PARCIAL`
não conseguia dizer sua situação de tramitação e nenhum conseguia dizer sua
posição na fila.

Este módulo não toca banco e não importa SQLAlchemy de propósito: é a única
parte do fluxo que dá para exercitar sem arreio, e é onde as regras que não
podem se perder ficam legíveis.

`status_legado()` deriva o valor antigo das três dimensões. A coluna `status`
continua existindo e mantida em sincronia até a F5, porque
`pagamentos_conciliacao`, `pagamentos_excecoes`, `pagamentos_caixa`,
`pagamentos_export`, `pagamentos_filas` e o frontend inteiro a leem. Migrar
todos na mesma fatia daria um diff que ninguém revisa com atenção.
"""
from __future__ import annotations

# ---------------------------------------------------------------- tramitação
RASCUNHO = "RASCUNHO"
AGUARDANDO_GESTOR = "AGUARDANDO_GESTOR"
AJUSTE_GESTOR = "AJUSTE_GESTOR"
AGUARDANDO_VALIDACAO = "AGUARDANDO_VALIDACAO"
AJUSTE_VALIDACAO = "AJUSTE_VALIDACAO"
AGUARDANDO_AUTORIDADE = "AGUARDANDO_AUTORIDADE"
AJUSTE_AUTORIDADE = "AJUSTE_AUTORIDADE"
AUTORIZADA = "AUTORIZADA"
REJEITADA_GESTOR = "REJEITADA_GESTOR"
INDEFERIDA_AUTORIDADE = "INDEFERIDA_AUTORIDADE"
CANCELADA = "CANCELADA"

TRAMITACAO = frozenset({
    RASCUNHO, AGUARDANDO_GESTOR, AJUSTE_GESTOR, AGUARDANDO_VALIDACAO,
    AJUSTE_VALIDACAO, AGUARDANDO_AUTORIDADE, AJUSTE_AUTORIDADE, AUTORIZADA,
    REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA,
})

TERMINAIS = frozenset({REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA})

# Grafo do rito. `AUTORIZADA` é terminal para a TRAMITAÇÃO — o que vem depois é
# execução, que é outra dimensão.
#
# A linha que carrega a fatia é a de AGUARDANDO_VALIDACAO: duas saídas, nenhuma
# terminal. Acrescentar um terminal aqui reabre exatamente o defeito que a F1
# fecha, e `test_validacao_nao_alcanca_nenhum_terminal` reprova.
TRANSICOES_TRAMITACAO: dict[str, frozenset[str]] = {
    RASCUNHO:              frozenset({AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_GESTOR:     frozenset({AGUARDANDO_VALIDACAO, AJUSTE_GESTOR,
                                      REJEITADA_GESTOR, CANCELADA}),
    AJUSTE_GESTOR:         frozenset({AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_VALIDACAO:  frozenset({AGUARDANDO_AUTORIDADE, AJUSTE_VALIDACAO}),
    AJUSTE_VALIDACAO:      frozenset({AGUARDANDO_VALIDACAO, AGUARDANDO_GESTOR, CANCELADA}),
    AGUARDANDO_AUTORIDADE: frozenset({AUTORIZADA, AJUSTE_AUTORIDADE,
                                      INDEFERIDA_AUTORIDADE, CANCELADA}),
    AJUSTE_AUTORIDADE:     frozenset({AGUARDANDO_AUTORIDADE, AGUARDANDO_GESTOR, CANCELADA}),
    AUTORIZADA:            frozenset({CANCELADA}),
    REJEITADA_GESTOR:      frozenset(),
    INDEFERIDA_AUTORIDADE: frozenset(),
    CANCELADA:             frozenset(),
}

# Etapa do stepper de cinco passos.
ETAPA_POR_TRAMITACAO: dict[str, str] = {
    RASCUNHO:              "UNIDADE",
    AGUARDANDO_GESTOR:     "GESTOR",
    AJUSTE_GESTOR:         "UNIDADE",
    AGUARDANDO_VALIDACAO:  "VALIDACAO",
    AJUSTE_VALIDACAO:      "UNIDADE",
    AGUARDANDO_AUTORIDADE: "AUTORIDADE",
    AJUSTE_AUTORIDADE:     "UNIDADE",
    AUTORIZADA:            "TESOURARIA",
    REJEITADA_GESTOR:      "GESTOR",
    INDEFERIDA_AUTORIDADE: "AUTORIDADE",
    CANCELADA:             "UNIDADE",
}

# --------------------------------------------------------------------- fila
NAO_REGISTRADA = "NAO_REGISTRADA"
REGISTRADA = "REGISTRADA"
BLOQUEADA = "BLOQUEADA"
ELEGIVEL = "ELEGIVEL"
AGUARDANDO_DISPONIBILIDADE = "AGUARDANDO_DISPONIBILIDADE"
EXCECAO_AUTORIZADA = "EXCECAO_AUTORIZADA"
CONCLUIDA = "CONCLUIDA"
RETIRADA = "RETIRADA"

FILA = frozenset({
    NAO_REGISTRADA, REGISTRADA, BLOQUEADA, ELEGIVEL,
    AGUARDANDO_DISPONIBILIDADE, EXCECAO_AUTORIZADA, CONCLUIDA, RETIRADA,
})

# ---------------------------------------------------------------- pagamento
NAO_INICIADA = "NAO_INICIADA"
PROGRAMADA = "PROGRAMADA"
ENVIADA_BANCO = "ENVIADA_BANCO"
EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
PAGA_PARCIAL = "PAGA_PARCIAL"
PAGA = "PAGA"
FALHOU = "FALHOU"
PAG_CANCELADA = "CANCELADA"
ESTORNADA = "ESTORNADA"

PAGAMENTO = frozenset({
    NAO_INICIADA, PROGRAMADA, ENVIADA_BANCO, EM_PROCESSAMENTO,
    PAGA_PARCIAL, PAGA, FALHOU, PAG_CANCELADA, ESTORNADA,
})


def transicao_permitida(atual: str, novo: str) -> bool:
    return novo in TRANSICOES_TRAMITACAO.get(atual, frozenset())


# --------------------------------------------------- derivação do status legado
_LEGADO_TRAMITACAO = {
    RASCUNHO: "RASCUNHO",
    AGUARDANDO_GESTOR: "EM_VALIDACAO",
    AGUARDANDO_VALIDACAO: "EM_VALIDACAO",
    AJUSTE_GESTOR: "DEVOLVIDO",
    AJUSTE_VALIDACAO: "DEVOLVIDO",
    AJUSTE_AUTORIDADE: "DEVOLVIDO",
    AGUARDANDO_AUTORIDADE: "ENVIADO_SECRETARIO",
    AUTORIZADA: "AUTORIZADO",
    REJEITADA_GESTOR: "REJEITADO",
    INDEFERIDA_AUTORIDADE: "REJEITADO",
    CANCELADA: "CANCELADO",
}

# Quando a execução começou, ela manda no valor legado — era assim que o campo
# único se comportava, e os consumidores que ainda o leem contam com isso.
_LEGADO_PAGAMENTO = {
    PROGRAMADA: "ENVIADO_TESOURARIA",
    ENVIADA_BANCO: "EM_PROCESSAMENTO",
    EM_PROCESSAMENTO: "EM_PROCESSAMENTO",
    PAGA_PARCIAL: "PAGO_PARCIAL",
    PAGA: "PAGO",
    FALHOU: "EM_PROCESSAMENTO",
    ESTORNADA: "ESTORNADO",
}


def status_legado(tramitacao: str, fila: str, pagamento: str) -> str:
    """Valor de `Debito.status` correspondente às três dimensões.

    Precedência: cancelamento > execução iniciada > bloqueio de fila >
    tramitação. Cancelamento vem primeiro porque `CANCELADO` é o único estado
    que o legado trata como absoluto.
    """
    if tramitacao == CANCELADA:
        return "CANCELADO"
    if pagamento in _LEGADO_PAGAMENTO:
        return _LEGADO_PAGAMENTO[pagamento]
    if fila == BLOQUEADA and tramitacao not in TERMINAIS:
        return "SUSPENSO"
    return _LEGADO_TRAMITACAO[tramitacao]
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_estados.py -v
```

Esperado: 9 passed.

- [ ] **Step 5: Provar a guarda por inversão**

Trocar temporariamente a linha de `AGUARDANDO_VALIDACAO` em `TRANSICOES_TRAMITACAO` para incluir `REJEITADA_GESTOR`. Rodar de novo: `test_validacao_nao_alcanca_nenhum_terminal` **tem de ficar vermelho**. Desfazer.

Guarda verde só significa alguma coisa depois de invertida.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pagamentos_estados.py backend/tests/test_pagamentos_estados.py
git commit -m "feat(pagamentos): dominio das tres dimensoes de situacao (F1, Tarefa 1)"
```

---

## Task 2: Migration 0085

**Files:**
- Create: `backend/alembic/versions/0085_pagamentos_tres_dimensoes.py`
- Modify: `backend/app/cli/seed_bootstrap.py:62-77`
- Test: `backend/tests/test_pagamentos_migration_0085.py`

**Interfaces:**
- Consumes: `pagamentos_estados` (Task 1) para o mapa inverso do backfill.
- Produces: colunas `situacao_tramitacao`, `situacao_fila`, `situacao_pagamento`, `id_unidade`, `versao`, `lock_version`, `id_gestor_decisor`, `id_validador` em `pagamentos.debito`; `categoria` em `pagamentos.contrato`; transação `pagamento_gerir`.

- [ ] **Step 1: Medir o volume antes de escrever o backfill**

```bash
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c \
  "SELECT status, count(*) FROM pagamentos.debito WHERE excluido = false GROUP BY status ORDER BY 2 DESC;"
```

Anotar o resultado no corpo do PR. Se vier vazio, o backfill continua sendo escrito — o CI roda em banco limpo, mas homologação recebe dados a qualquer momento.

- [ ] **Step 2: Escrever o teste que falha**

Criar `backend/tests/test_pagamentos_migration_0085.py`:

```python
"""A migration 0085 e o mapeamento do §4.5 da spec.

O que este arquivo protege não é a migration em si (o CI já a roda em banco
limpo) e sim o CONTRATO: toda combinação que o backfill produz tem de ser
válida nas três dimensões, e o `status` derivado dela tem de bater com o
`status` que a linha já tinha. Se não bater, o backfill perdeu informação.
"""
import pytest
from sqlalchemy import text

from app.services import pagamentos_estados as est

# Espelha o mapa do §4.5 da spec. Mudou lá, muda aqui, e o teste abaixo
# confere que o resultado continua consistente.
MAPA = {
    "RASCUNHO":               ("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "EM_VALIDACAO":           ("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "DEVOLVIDO":              ("AJUSTE_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "VALIDADO":               ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "ENVIADO_SECRETARIO":     ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AGUARDANDO_AUTORIZACAO": ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AUTORIZADO":             ("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA"),
    "ENVIADO_TESOURARIA":     ("AUTORIZADA", "ELEGIVEL", "PROGRAMADA"),
    "EM_PROCESSAMENTO":       ("AUTORIZADA", "ELEGIVEL", "EM_PROCESSAMENTO"),
    "PAGO_PARCIAL":           ("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL"),
    "PAGO":                   ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "CONCILIADO":             ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "REJEITADO":              ("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA"),
    "SUSPENSO":               ("AJUSTE_VALIDACAO", "BLOQUEADA", "NAO_INICIADA"),
    "CANCELADO":              ("CANCELADA", "RETIRADA", "CANCELADA"),
    "ESTORNADO":              ("AUTORIZADA", "ELEGIVEL", "ESTORNADA"),
}


def test_mapa_cobre_os_dezesseis_status_legados():
    from app.schemas.pagamentos import StatusDebito
    legados = set(StatusDebito.__args__)
    assert set(MAPA) == legados


def test_toda_combinacao_do_mapa_e_valida():
    for legado, (tram, fila, pag) in MAPA.items():
        assert tram in est.TRAMITACAO, legado
        assert fila in est.FILA, legado
        assert pag in est.PAGAMENTO, legado


def test_backfill_nao_perde_informacao():
    """O status derivado do trio tem de reproduzir o status de origem.

    As três exceções são deliberadas e estão registradas na spec §4.5:
    VALIDADO e AGUARDANDO_AUTORIZACAO colapsam em ENVIADO_SECRETARIO (os três
    significavam 'na fila da autoridade'), e CONCILIADO colapsa em PAGO (a
    conciliação vira atributo da parcela).
    """
    colapsos = {"VALIDADO": "ENVIADO_SECRETARIO",
                "AGUARDANDO_AUTORIZACAO": "ENVIADO_SECRETARIO",
                "CONCILIADO": "PAGO"}
    for legado, (tram, fila, pag) in MAPA.items():
        esperado = colapsos.get(legado, legado)
        assert est.status_legado(tram, fila, pag) == esperado, legado


@pytest.mark.asyncio
async def test_colunas_existem_e_sao_not_null(admin_session):
    sql = text("""
        SELECT column_name, is_nullable FROM information_schema.columns
        WHERE table_schema = 'pagamentos' AND table_name = 'debito'
          AND column_name IN ('situacao_tramitacao','situacao_fila',
                              'situacao_pagamento','id_unidade','versao','lock_version')
    """)
    achadas = {r[0]: r[1] for r in (await admin_session.execute(sql)).all()}
    assert len(achadas) == 6, f"faltam colunas: {achadas}"
    for coluna, nulavel in achadas.items():
        assert nulavel == "NO", f"{coluna} deveria ser NOT NULL"


@pytest.mark.asyncio
async def test_transacao_pagamento_gerir_existe(admin_session):
    row = (await admin_session.execute(text(
        "SELECT codigo FROM utils.transacao WHERE codigo = 'pagamento_gerir'"
    ))).first()
    assert row is not None, "a migration 0085 deve criar a transação pagamento_gerir"
```

- [ ] **Step 3: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_migration_0085.py -v
```

Esperado: os dois últimos falham (colunas e transação não existem). Os três primeiros já passam — são puros e validam o mapa.

- [ ] **Step 4: Escrever a migration**

Criar `backend/alembic/versions/0085_pagamentos_tres_dimensoes.py`:

```python
"""Pagamentos F1 — as três dimensões de situação, unidade e versionamento.

Revision ID: 0085
Revises: 0084
Create Date: 2026-08-06

Spec: `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` §4.

Só ADD COLUMN em tabela existente — **RLS e grants são herdados**, não se
repete o boilerplate. Não há tabela nova nesta fatia.

Três coisas merecem atenção de quem revisar:

1. **`id_unidade` nasce nullable e termina NOT NULL na MESMA migration.** O
   backfill roda no meio. Deixar a janela aberta entre duas migrations criaria
   um intervalo em que o código novo grava NULL e o `SET NOT NULL` da migration
   seguinte falha com dado em produção.

2. **`categoria` de contrato NÃO vira NOT NULL.** Fica nullable com default
   'SERVICOS' para linhas existentes. Obrigar o ente a classificar 100% dos
   contratos no dia do deploy trava o módulo inteiro; a tela de contratos
   alerta e o operador classifica ao longo do tempo.

3. **`status` continua existindo e continua correto.** Ele passa a ser derivado
   das três dimensões (`services/pagamentos_estados.status_legado`), e todos os
   consumidores que ainda o leem seguem funcionando. A coluna morre na F5.

O `downgrade` recalcula nada: como `status` nunca deixou de ser mantido, basta
derrubar as colunas novas. É por isso que manter a coluna legada durante F1–F4
não é só conservadorismo — é o que torna esta migration reversível de verdade.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0085"
down_revision: str | Sequence[str] | None = "0084"
branch_labels = None
depends_on = None

S = "pagamentos"

# Espelha o §4.5 da spec e o MAPA de tests/test_pagamentos_migration_0085.py.
MAPA_BACKFILL: dict[str, tuple[str, str, str]] = {
    "RASCUNHO":               ("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "EM_VALIDACAO":           ("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "DEVOLVIDO":              ("AJUSTE_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "VALIDADO":               ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "ENVIADO_SECRETARIO":     ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AGUARDANDO_AUTORIZACAO": ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AUTORIZADO":             ("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA"),
    "ENVIADO_TESOURARIA":     ("AUTORIZADA", "ELEGIVEL", "PROGRAMADA"),
    "EM_PROCESSAMENTO":       ("AUTORIZADA", "ELEGIVEL", "EM_PROCESSAMENTO"),
    "PAGO_PARCIAL":           ("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL"),
    "PAGO":                   ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "CONCILIADO":             ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "REJEITADO":              ("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA"),
    "SUSPENSO":               ("AJUSTE_VALIDACAO", "BLOQUEADA", "NAO_INICIADA"),
    "CANCELADO":              ("CANCELADA", "RETIRADA", "CANCELADA"),
    "ESTORNADO":              ("AUTORIZADA", "ELEGIVEL", "ESTORNADA"),
}


def upgrade() -> None:
    # ---------------------------------------------- 1. colunas das dimensões
    op.add_column(f"debito", sa.Column("situacao_tramitacao", sa.String(30),
                  nullable=True), schema=S)
    op.add_column("debito", sa.Column("situacao_fila", sa.String(30),
                  nullable=True), schema=S)
    op.add_column("debito", sa.Column("situacao_pagamento", sa.String(20),
                  nullable=True), schema=S)

    for legado, (tram, fila, pag) in MAPA_BACKFILL.items():
        op.execute(
            f"UPDATE {S}.debito SET situacao_tramitacao = '{tram}', "
            f"situacao_fila = '{fila}', situacao_pagamento = '{pag}' "
            f"WHERE status = '{legado}'"
        )
    # Rede de segurança: linha com status fora do enum (dado sujo do legado)
    # vira rascunho em vez de derrubar o SET NOT NULL abaixo.
    op.execute(
        f"UPDATE {S}.debito SET situacao_tramitacao = 'RASCUNHO', "
        f"situacao_fila = 'NAO_REGISTRADA', situacao_pagamento = 'NAO_INICIADA' "
        f"WHERE situacao_tramitacao IS NULL"
    )

    for coluna in ("situacao_tramitacao", "situacao_fila", "situacao_pagamento"):
        op.alter_column("debito", coluna, nullable=False, schema=S)

    # ------------------------------------------------------- 2. id_unidade
    op.add_column("debito", sa.Column("id_unidade", sa.Integer(), nullable=True), schema=S)
    op.create_foreign_key("fk_debito_unidade", "debito", "unidade_trabalho",
                          ["id_unidade"], ["id"], source_schema=S,
                          referent_schema="utils")
    # Backfill em duas passadas: contrato quando há, unidade do solicitante
    # quando não. A segunda é fallback e precisa ficar visível no PR — anote
    # quantas linhas ela resolveu.
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = c.id_unidade
        FROM {S}.contrato c
        WHERE d.id_contrato = c.id AND d.id_unidade IS NULL
    """)
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = u.id_unidade_trabalho
        FROM utils.usuario u
        WHERE d.id_usuario_solicitante = u.id AND d.id_unidade IS NULL
          AND u.id_unidade_trabalho IS NOT NULL
    """)
    # Último recurso: a menor unidade do tenant. Débito sem unidade nenhuma
    # tornaria a coluna inviável como NOT NULL e quebraria a chave da fila na F3.
    op.execute(f"""
        UPDATE {S}.debito d SET id_unidade = (
            SELECT MIN(u.id) FROM utils.unidade_trabalho u
            WHERE u.tenant_id = d.tenant_id AND u.excluido = false
        ) WHERE d.id_unidade IS NULL
    """)
    op.execute(f"DELETE FROM {S}.debito WHERE id_unidade IS NULL AND excluido = true")
    op.alter_column("debito", "id_unidade", nullable=False, schema=S)
    op.create_index("ix_debito_unidade", "debito", ["tenant_id", "id_unidade"], schema=S)

    # ------------------------------- 3. versionamento e concorrência
    op.add_column("debito", sa.Column("versao", sa.Integer(), nullable=False,
                  server_default="1"), schema=S)
    op.add_column("debito", sa.Column("lock_version", sa.Integer(), nullable=False,
                  server_default="0"), schema=S)

    # ------------------------------- 4. quem decidiu em cada etapa
    op.add_column("debito", sa.Column("id_gestor_decisor", sa.Integer(), nullable=True), schema=S)
    op.add_column("debito", sa.Column("id_validador", sa.Integer(), nullable=True), schema=S)
    op.create_foreign_key("fk_debito_gestor", "debito", "usuario",
                          ["id_gestor_decisor"], ["id"], source_schema=S,
                          referent_schema="utils")
    op.create_foreign_key("fk_debito_validador", "debito", "usuario",
                          ["id_validador"], ["id"], source_schema=S,
                          referent_schema="utils")
    # Backfill do validador a partir da trilha — a informação já existe.
    op.execute(f"""
        UPDATE {S}.debito d SET id_validador = h.id_usuario
        FROM (
            SELECT DISTINCT ON (id_debito) id_debito, id_usuario
            FROM {S}.debito_historico WHERE acao = 'VALIDADO'
            ORDER BY id_debito, criado_em DESC
        ) h WHERE h.id_debito = d.id
    """)

    # --------------------------------------- 5. categoria do contrato
    op.add_column("contrato", sa.Column("categoria", sa.String(20), nullable=True), schema=S)
    op.execute(f"UPDATE {S}.contrato SET categoria = 'SERVICOS' WHERE categoria IS NULL")
    op.create_check_constraint(
        "ck_contrato_categoria", "contrato",
        "categoria IS NULL OR categoria IN ('BENS','LOCACOES','SERVICOS','OBRAS')",
        schema=S)

    # ----------------------------- 6. transação do Gestor da Pasta
    op.execute("""
        INSERT INTO utils.transacao (transacao, codigo)
        SELECT 'Gestão da pasta (pagamentos)', 'pagamento_gerir'
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.transacao WHERE codigo = 'pagamento_gerir'
        )
    """)
    # Quem hoje encaminha é quem mais se aproxima do gestor. Sem esta concessão
    # a etapa nova nasce sem ninguém que a exerça, e o fluxo trava na primeira
    # solicitação enviada.
    op.execute("""
        INSERT INTO utils.grupo_transacao (id_grupo, id_transacao, inserir, atualizar, excluir)
        SELECT gt.id_grupo, novo.id, gt.inserir, gt.atualizar, gt.excluir
        FROM utils.grupo_transacao gt
        JOIN utils.transacao antiga ON antiga.id = gt.id_transacao
                                   AND antiga.codigo = 'pagamento_encaminhar'
        CROSS JOIN (SELECT id FROM utils.transacao WHERE codigo = 'pagamento_gerir') novo
        WHERE NOT EXISTS (
            SELECT 1 FROM utils.grupo_transacao x
            WHERE x.id_grupo = gt.id_grupo AND x.id_transacao = novo.id
        )
    """)


def downgrade() -> None:
    op.drop_constraint("ck_contrato_categoria", "contrato", schema=S, type_="check")
    op.drop_column("contrato", "categoria", schema=S)
    op.drop_constraint("fk_debito_validador", "debito", schema=S, type_="foreignkey")
    op.drop_constraint("fk_debito_gestor", "debito", schema=S, type_="foreignkey")
    op.drop_column("debito", "id_validador", schema=S)
    op.drop_column("debito", "id_gestor_decisor", schema=S)
    op.drop_column("debito", "lock_version", schema=S)
    op.drop_column("debito", "versao", schema=S)
    op.drop_index("ix_debito_unidade", table_name="debito", schema=S)
    op.drop_constraint("fk_debito_unidade", "debito", schema=S, type_="foreignkey")
    op.drop_column("debito", "id_unidade", schema=S)
    op.drop_column("debito", "situacao_pagamento", schema=S)
    op.drop_column("debito", "situacao_fila", schema=S)
    op.drop_column("debito", "situacao_tramitacao", schema=S)
    # `pagamento_gerir` e suas concessões NÃO são removidas: apagar concessão
    # de permissão num downgrade é destrutivo e irreversível na prática.
```

**Antes de escrever:** conferir o nome real da coluna de unidade em `utils.usuario` e o nome real da tabela de concessão (`utils.grupo_transacao` e suas colunas). Rodar:

```bash
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c "\d utils.usuario" | grep -i unidade
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c "\d utils.grupo_transacao"
```

Ajustar o SQL ao que existir. **Não assumir os nomes acima** — eles vêm do schema legado do PHP e são a fonte mais provável de erro nesta task.

- [ ] **Step 5: Declarar a transação no mapa de módulos**

Em `backend/app/cli/seed_bootstrap.py`, no dicionário `MODULO_TRANSACOES`, trocar a tupla de `"pagamentos"` por:

```python
    "pagamentos": (
        "pagamento_cadastro", "pagamento_solicitar", "pagamento_autorizar",
        "pagamento_pagar", "pagamento_aprovar", "pagamento_validar",
        "pagamento_encaminhar", "pagamento_auditar", "pagamento_gerir",
    ),
```

`pagamento_aprovar` e `pagamento_encaminhar` **continuam na lista**: as concessões existem em banco e a guarda de modularização exige que toda transação do sistema tenha módulo. Elas saem na F5, junto com a coluna legada.

- [ ] **Step 6: Aplicar e conferir**

```
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic heads
docker exec aprimora-py-backend alembic downgrade -1
docker exec aprimora-py-backend alembic upgrade head
```

Esperado: head único `0085`; downgrade e upgrade sem erro.

- [ ] **Step 7: Rodar os testes**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_migration_0085.py tests/test_guarda_modularizacao.py -v
```

Esperado: todos passam.

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/0085_pagamentos_tres_dimensoes.py \
        backend/app/cli/seed_bootstrap.py \
        backend/tests/test_pagamentos_migration_0085.py
git commit -m "feat(pagamentos): migration das tres dimensoes, unidade e pagamento_gerir (F1, Tarefa 2)"
```

---

## Task 3: Model, schemas e sincronia do status legado

**Files:**
- Modify: `backend/app/models/pagamentos.py:157-188` e a classe `Contrato` (121-135)
- Modify: `backend/app/schemas/pagamentos.py:321-399`
- Modify: `backend/app/services/pagamentos_debitos.py:53-61, 86-113, 404-417`
- Test: `backend/tests/test_pagamentos_status_derivado.py`

**Interfaces:**
- Consumes: `pagamentos_estados` (Task 1); colunas da Task 2.
- Produces:
  - `Debito.situacao_tramitacao/situacao_fila/situacao_pagamento/id_unidade/versao/lock_version/id_gestor_decisor/id_validador`
  - `Contrato.categoria`
  - Schemas `SituacaoTramitacao`, `SituacaoFila`, `SituacaoPagamento` (Literal)
  - `DebitoOut` com as três dimensões + `id_unidade` + `versao` + `lock_version`
  - `pagamentos_debitos._sincronizar_status_legado(d: Debito) -> None`
  - `_registrar_transicao(db, *, debito, acao, usuario_id, tramitacao=None, fila=None, pagamento=None, justificativa=None, ip=None) -> None`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_pagamentos_status_derivado.py`:

```python
"""O `status` legado é FUNÇÃO das três dimensões — nunca o contrário.

Este é o teste que segura a premissa nº 1 da spec: manter a coluna legada
derivada durante F1–F4 é seguro. Se ele ficar vermelho, a resposta não é
remendar o mapa: é acelerar a F5 e apagar a coluna.
"""
import pytest
from sqlalchemy import select

from app.models import Debito
from app.services import pagamentos_estados as est
from app.services import pagamentos_debitos as svc


def test_sincronizar_status_legado_e_pura_derivacao():
    d = Debito(situacao_tramitacao="AUTORIZADA", situacao_fila="ELEGIVEL",
               situacao_pagamento="NAO_INICIADA", status="LIXO")
    svc._sincronizar_status_legado(d)
    assert d.status == "AUTORIZADO"

    d.situacao_pagamento = "PAGA"
    d.situacao_fila = "CONCLUIDA"
    svc._sincronizar_status_legado(d)
    assert d.status == "PAGO"


def test_toda_transicao_do_novo_fluxo_produz_status_legado_valido():
    """Percorre o grafo inteiro e confere o legado em cada nó alcançável."""
    from app.schemas.pagamentos import StatusDebito
    validos = set(StatusDebito.__args__)
    for origem, destinos in est.TRANSICOES_TRAMITACAO.items():
        for destino in destinos:
            d = Debito(situacao_tramitacao=destino, situacao_fila="NAO_REGISTRADA",
                       situacao_pagamento="NAO_INICIADA", status="")
            svc._sincronizar_status_legado(d)
            assert d.status in validos, f"{origem} -> {destino} deu '{d.status}'"
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_status_derivado.py -v
```

Esperado: `AttributeError: module 'app.services.pagamentos_debitos' has no attribute '_sincronizar_status_legado'`.

- [ ] **Step 3: Acrescentar as colunas ao model**

Em `backend/app/models/pagamentos.py`, na classe `Debito`, logo depois de
`status: Mapped[str] = ...`:

```python
    # --- as três dimensões (F1, spec §4.1) ---------------------------------
    # `status` acima passa a ser DERIVADO destas três
    # (services/pagamentos_estados.status_legado) e sobrevive só até a F5,
    # porque conciliação, exceções, caixa, export, filas e o frontend inteiro
    # ainda o leem.
    situacao_tramitacao: Mapped[str] = mapped_column(
        String(30), nullable=False, default="RASCUNHO")
    situacao_fila: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NAO_REGISTRADA")
    situacao_pagamento: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NAO_INICIADA")
    # Unidade administrativa de origem. Antes da F1 só existia via contrato —
    # débito sem contrato não tinha unidade nenhuma, o que inviabilizava tanto o
    # papel "Unidade Setorial" quanto a chave da fila cronológica da F3.
    id_unidade: Mapped[int] = mapped_column(
        ForeignKey("utils.unidade_trabalho.id"), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    id_gestor_decisor: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True)
    id_validador: Mapped[int | None] = mapped_column(
        ForeignKey("utils.usuario.id"), nullable=True)
```

Na classe `Contrato`, depois de `valor_total`:

```python
    # Categoria para a fila cronológica (F3). Nullable de propósito: obrigar o
    # ente a classificar todo o histórico no dia do deploy travaria o módulo.
    categoria: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 4: Acrescentar os schemas**

Em `backend/app/schemas/pagamentos.py`, logo depois da linha de `StatusDebito`:

```python
# --- as três dimensões (F1, spec §4.1) -------------------------------------
SituacaoTramitacao = Literal[
    "RASCUNHO", "AGUARDANDO_GESTOR", "AJUSTE_GESTOR", "AGUARDANDO_VALIDACAO",
    "AJUSTE_VALIDACAO", "AGUARDANDO_AUTORIDADE", "AJUSTE_AUTORIDADE",
    "AUTORIZADA", "REJEITADA_GESTOR", "INDEFERIDA_AUTORIDADE", "CANCELADA"]
SituacaoFila = Literal[
    "NAO_REGISTRADA", "REGISTRADA", "BLOQUEADA", "ELEGIVEL",
    "AGUARDANDO_DISPONIBILIDADE", "EXCECAO_AUTORIZADA", "CONCLUIDA", "RETIRADA"]
SituacaoPagamento = Literal[
    "NAO_INICIADA", "PROGRAMADA", "ENVIADA_BANCO", "EM_PROCESSAMENTO",
    "PAGA_PARCIAL", "PAGA", "FALHOU", "CANCELADA", "ESTORNADA"]
CategoriaContrato = Literal["BENS", "LOCACOES", "SERVICOS", "OBRAS"]
```

Em `DebitoCreate`, acrescentar depois de `id_contrato`:

```python
    id_unidade: int                  # unidade setorial de origem (F1)
```

Em `DebitoOut`, acrescentar depois de `status: StatusDebito`:

```python
    # `status` acima é legado e derivado; estes três são a verdade (F1).
    situacao_tramitacao: SituacaoTramitacao
    situacao_fila: SituacaoFila
    situacao_pagamento: SituacaoPagamento
    id_unidade: int
    versao: int = 1
    lock_version: int = 0
    id_gestor_decisor: int | None = None
    id_validador: int | None = None
```

Em `DebitoUpdate`, acrescentar `id_unidade: int | None = None`.

Acrescentar ao final do bloco de payloads:

```python
class DecisaoIn(BaseModel):
    """Payload das decisões do rito. `lock_version` é obrigatório: sem ele não
    há como distinguir 'decidiu sobre o estado que viu' de 'decidiu sobre um
    estado que outro usuário já mudou' (spec §6.3)."""
    lock_version: int


class DecisaoJustificadaIn(DecisaoIn):
    justificativa: str = Field(min_length=1, max_length=255)
```

- [ ] **Step 5: Implementar a sincronia e ajustar as transições existentes**

Em `backend/app/services/pagamentos_debitos.py`, no topo dos imports:

```python
from . import pagamentos_estados as est
```

Substituir `_registrar_transicao` inteira por:

```python
def _sincronizar_status_legado(d: Debito) -> None:
    """Recalcula `Debito.status` a partir das três dimensões.

    Ponto ÚNICO de escrita da coluna legada. Havendo dois, eles divergem — é
    exatamente o risco registrado na spec §4.2, e a mitigação é este ser o
    único. Nenhum outro lugar do código pode atribuir a `d.status`.
    """
    d.status = est.status_legado(
        d.situacao_tramitacao, d.situacao_fila, d.situacao_pagamento)


def _registrar_transicao(db, *, debito: Debito, acao: str, usuario_id: int | None,
                         tramitacao: str | None = None, fila: str | None = None,
                         pagamento: str | None = None,
                         justificativa: str | None = None,
                         ip: str | None = None) -> None:
    """Aplica a mudança nas dimensões informadas, deriva o status legado e grava
    a trilha — tudo na MESMA transação do caller.

    Passar `tramitacao` exige que a transição seja legal no grafo. As outras
    duas dimensões não têm grafo nesta fatia: a fila é responsabilidade da F3 e
    a execução, da F4.
    """
    if tramitacao is not None and tramitacao != debito.situacao_tramitacao:
        if not est.transicao_permitida(debito.situacao_tramitacao, tramitacao):
            raise PagamentoDebitoError(
                f"Transição inválida: de '{debito.situacao_tramitacao}' "
                f"não se vai para '{tramitacao}'.", status.HTTP_409_CONFLICT)
    status_anterior = debito.status
    if tramitacao is not None:
        debito.situacao_tramitacao = tramitacao
    if fila is not None:
        debito.situacao_fila = fila
    if pagamento is not None:
        debito.situacao_pagamento = pagamento
    _sincronizar_status_legado(debito)
    debito.lock_version = (debito.lock_version or 0) + 1
    db.add(DebitoHistorico(
        tenant_id=debito.tenant_id, id_debito=debito.id,
        status_anterior=status_anterior if acao != "CRIADO" else None,
        status_novo=debito.status, acao=acao, justificativa=justificativa,
        id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
```

Em `criar_debito`, trocar `status="RASCUNHO"` por:

```python
               situacao_tramitacao=est.RASCUNHO, situacao_fila=est.NAO_REGISTRADA,
               situacao_pagamento=est.NAO_INICIADA, status="RASCUNHO",
               id_unidade=payload.id_unidade,
```

e a chamada final por:

```python
    _registrar_transicao(db, debito=d, acao="CRIADO", usuario_id=usuario_id)
```

Em `debito_out`, acrescentar ao dicionário:

```python
        "situacao_tramitacao": d.situacao_tramitacao,
        "situacao_fila": d.situacao_fila,
        "situacao_pagamento": d.situacao_pagamento,
        "id_unidade": d.id_unidade, "versao": d.versao,
        "lock_version": d.lock_version,
        "id_gestor_decisor": d.id_gestor_decisor, "id_validador": d.id_validador,
```

Em `_validar_refs`, acrescentar a validação same-tenant da unidade — **FK do Postgres não filtra por tenant**:

```python
    await cad.obter_unidade(db, tenant_id=tenant_id, unidade_id=payload.id_unidade)
```

Se `cad.obter_unidade` não existir em `pagamentos_cadastros.py`, criá-la seguindo o padrão das irmãs (`obter_fornecedor`, `obter_fonte`): carrega por id filtrando `tenant_id` e `excluido.is_(False)`, e levanta 404 quando não achar.

- [ ] **Step 6: Rodar os testes**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_status_derivado.py tests/test_pagamentos_debitos.py -v
```

Esperado: os novos passam. Os antigos de `test_pagamentos_debitos.py` vão falhar em massa por falta de `id_unidade` no payload — **isso é esperado nesta etapa** e é consertado na Task 6, quando as transições novas existirem. Anotar quantos falharam.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/pagamentos.py backend/app/schemas/pagamentos.py \
        backend/app/services/pagamentos_debitos.py backend/app/services/pagamentos_cadastros.py \
        backend/tests/test_pagamentos_status_derivado.py
git commit -m "feat(pagamentos): model e schemas das tres dimensoes, status legado derivado (F1, Tarefa 3)"
```

---

## Task 4: Segregação de funções e concorrência

**Files:**
- Create: `backend/app/services/pagamentos_guardas.py`
- Test: `backend/tests/test_pagamentos_segregacao.py`, `backend/tests/test_pagamentos_concorrencia.py`

**Interfaces:**
- Consumes: `Debito` (Task 3).
- Produces:
  - `assert_segregacao(debito: Debito, usuario_id: int, ato: str) -> None` — `ato ∈ {"GERIR","VALIDAR","AUTORIZAR","PAGAR"}`; levanta `SegregacaoError` (403)
  - `assert_lock_version(debito: Debito, esperado: int) -> None` — levanta `ConflitoDeEdicaoError` (409)
  - `SegregacaoError`, `ConflitoDeEdicaoError` (subclasses de `HTTPException`)

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_pagamentos_segregacao.py`:

```python
"""Segregação de funções (spec §6.2).

A regra: a mesma pessoa não exerce dois atos decisórios sobre o mesmo débito.
Antes da F1 existia só solicitante ≠ validador.

O teste que mais importa é o do super-usuário. Segregação de funções NÃO é
permissão — é controle interno —, então o bypass de SU do `auth/perms.py` não
se aplica aqui. É exceção deliberada ao padrão do projeto, registrada na spec
§6.2 e na premissa nº 6.
"""
import pytest

from app.models import Debito
from app.services.pagamentos_guardas import SegregacaoError, assert_segregacao


def _debito(**kw) -> Debito:
    base = dict(id_usuario_solicitante=10, id_gestor_decisor=None, id_validador=None)
    base.update(kw)
    return Debito(**base)


def test_solicitante_nao_gere():
    with pytest.raises(SegregacaoError) as e:
        assert_segregacao(_debito(), usuario_id=10, ato="GERIR")
    assert e.value.status_code == 403


def test_solicitante_nao_valida():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(), usuario_id=10, ato="VALIDAR")


def test_gestor_nao_valida():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="VALIDAR")


def test_gestor_nao_autoriza():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="AUTORIZAR")


def test_validador_nao_autoriza():
    with pytest.raises(SegregacaoError):
        assert_segregacao(_debito(id_validador=30), usuario_id=30, ato="AUTORIZAR")


def test_terceiro_pode():
    assert_segregacao(_debito(id_gestor_decisor=20, id_validador=30),
                      usuario_id=40, ato="AUTORIZAR")


def test_pagar_e_impedido_para_todos_os_anteriores():
    d = _debito(id_gestor_decisor=20, id_validador=30)
    for uid in (10, 20, 30):
        with pytest.raises(SegregacaoError):
            assert_segregacao(d, usuario_id=uid, ato="PAGAR")
    assert_segregacao(d, usuario_id=99, ato="PAGAR")


def test_mensagem_diz_qual_ato_a_pessoa_ja_exerceu():
    """Erro de segregação sem dizer o motivo vira chamado de suporte."""
    with pytest.raises(SegregacaoError) as e:
        assert_segregacao(_debito(id_gestor_decisor=20), usuario_id=20, ato="VALIDAR")
    assert "gestor" in str(e.value.detail).lower()
```

Criar `backend/tests/test_pagamentos_concorrencia.py`:

```python
"""Concorrência otimista nas decisões (spec §6.3, cenário 21 do pedido)."""
import pytest

from app.models import Debito
from app.services.pagamentos_guardas import ConflitoDeEdicaoError, assert_lock_version


def test_versao_igual_passa():
    assert_lock_version(Debito(lock_version=7), esperado=7)


def test_versao_diferente_e_conflito_409():
    with pytest.raises(ConflitoDeEdicaoError) as e:
        assert_lock_version(Debito(lock_version=8), esperado=7)
    assert e.value.status_code == 409


def test_mensagem_orienta_a_recarregar():
    """'Conflito' sozinho não diz o que fazer (spec §12)."""
    with pytest.raises(ConflitoDeEdicaoError) as e:
        assert_lock_version(Debito(lock_version=8), esperado=7)
    assert "recarregue" in str(e.value.detail).lower()
```

- [ ] **Step 2: Rodar e confirmar que falham**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_segregacao.py tests/test_pagamentos_concorrencia.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.services.pagamentos_guardas'`.

- [ ] **Step 3: Implementar**

Criar `backend/app/services/pagamentos_guardas.py`:

```python
"""Guardas transversais do rito de pagamento: segregação e concorrência.

Vivem fora de `pagamentos_debitos.py` porque valem para toda transição e porque
são a parte do fluxo que dá para exercitar sem banco.

**Segregação de funções não é permissão.** Permissão responde "este perfil pode
fazer isto?"; segregação responde "esta PESSOA já fez algo que a impede de fazer
isto neste débito?". Por isso a checagem mora no serviço, não no `Depends`, e
por isso o bypass de super-usuário do `auth/perms.py` não a alcança — decisão
deliberada, registrada na spec §6.2.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from ..models import Debito


class SegregacaoError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflitoDeEdicaoError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


# Para cada ato, os papéis já exercidos que o impedem. Ordem = ordem do rito.
_IMPEDIMENTOS: dict[str, tuple[tuple[str, str], ...]] = {
    "GERIR":     (("id_usuario_solicitante", "solicitou"),),
    "VALIDAR":   (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta")),
    "AUTORIZAR": (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta"),
                  ("id_validador", "validou a conformidade")),
    "PAGAR":     (("id_usuario_solicitante", "solicitou"),
                  ("id_gestor_decisor", "decidiu como gestor da pasta"),
                  ("id_validador", "validou a conformidade")),
}

_NOME_DO_ATO = {
    "GERIR": "decidir como gestor", "VALIDAR": "validar",
    "AUTORIZAR": "autorizar", "PAGAR": "executar o pagamento",
}


def assert_segregacao(debito: Debito, *, usuario_id: int, ato: str) -> None:
    """Levanta 403 se o usuário já exerceu, neste débito, um papel incompatível."""
    for campo, feito in _IMPEDIMENTOS[ato]:
        if getattr(debito, campo, None) == usuario_id:
            raise SegregacaoError(
                f"Segregação de funções: você {feito} esta solicitação e por isso "
                f"não pode {_NOME_DO_ATO[ato]}. Outro servidor precisa fazê-lo.")


def assert_lock_version(debito: Debito, *, esperado: int) -> None:
    """Levanta 409 quando o débito mudou desde que o usuário carregou a tela."""
    atual = debito.lock_version or 0
    if atual != esperado:
        raise ConflitoDeEdicaoError(
            "Esta solicitação foi atualizada por outro usuário depois que você "
            "abriu a tela. Recarregue para ver o estado atual antes de decidir.")
```

Atenção à chamada: os testes usam `assert_segregacao(d, usuario_id=..., ato=...)` com `d` posicional e o resto nomeado. Manter a assinatura exatamente assim.

- [ ] **Step 4: Rodar e confirmar que passam**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_segregacao.py tests/test_pagamentos_concorrencia.py -v
```

Esperado: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pagamentos_guardas.py \
        backend/tests/test_pagamentos_segregacao.py backend/tests/test_pagamentos_concorrencia.py
git commit -m "feat(pagamentos): segregacao de funcoes e lock otimista (F1, Tarefa 4)"
```

---

## Task 5: Transições do gestor da pasta

**Files:**
- Modify: `backend/app/services/pagamentos_debitos.py:270-401`
- Test: `backend/tests/test_pagamentos_fluxo_gestor.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4.
- Produces, todas em `pagamentos_debitos`:
  - `enviar_para_gestor(db, *, tenant_id, debito_id, usuario_id, lock_version, ip=None) -> Debito`
  - `gestor_autorizar(db, *, tenant_id, debito_id, usuario_id, lock_version, ip=None) -> Debito`
  - `gestor_rejeitar(db, *, tenant_id, debito_id, usuario_id, lock_version, justificativa, ip=None) -> Debito`
  - `solicitar_ajuste(db, *, tenant_id, debito_id, usuario_id, lock_version, etapa, justificativa, ip=None) -> Debito` — `etapa ∈ {"GESTOR","VALIDACAO","AUTORIDADE"}`
  - `responder_ajuste(db, *, tenant_id, debito_id, usuario_id, lock_version, ip=None) -> Debito`

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_pagamentos_fluxo_gestor.py`. O arreio de tenant/usuário segue `test_permissoes_modulo.py::_cria_usuario_comum`; **ler aquele arquivo antes de escrever este** e reaproveitar o helper em vez de reinventá-lo.

```python
"""A etapa do Gestor da Pasta (spec §3.1, §4.1) — cenários 2, 3, 4, 5 e 6 do pedido.

Antes da F1 esta etapa não existia como decisão: `encaminhar()` movia
VALIDADO → ENVIADO_SECRETARIO e mais nada. O gestor não autorizava, não
devolvia e não rejeitava.
"""
import pytest

from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
from app.services.pagamentos_guardas import ConflitoDeEdicaoError, SegregacaoError


@pytest.mark.asyncio
async def test_enviar_leva_rascunho_para_o_gestor(arreio_debito):
    """Cenário 2: unidade envia para o gestor — NÃO para a validação."""
    d, ctx = arreio_debito
    assert d.situacao_tramitacao == est.RASCUNHO
    d = await svc.enviar_para_gestor(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
        usuario_id=ctx.solicitante_id, lock_version=d.lock_version)
    assert d.situacao_tramitacao == est.AGUARDANDO_GESTOR
    assert d.status == "EM_VALIDACAO"  # legado derivado


@pytest.mark.asyncio
async def test_gestor_autoriza_e_segue_para_validacao(arreio_debito_no_gestor):
    """Cenário 3."""
    d, ctx = arreio_debito_no_gestor
    d = await svc.gestor_autorizar(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
        usuario_id=ctx.gestor_id, lock_version=d.lock_version)
    assert d.situacao_tramitacao == est.AGUARDANDO_VALIDACAO
    assert d.id_gestor_decisor == ctx.gestor_id


@pytest.mark.asyncio
async def test_gestor_solicita_ajuste_e_volta_para_a_unidade(arreio_debito_no_gestor):
    """Cenário 4: motivo obrigatório e retorno à unidade."""
    d, ctx = arreio_debito_no_gestor
    d = await svc.solicitar_ajuste(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.gestor_id,
        lock_version=d.lock_version, etapa="GESTOR",
        justificativa="Falta o atesto do fiscal do contrato.")
    assert d.situacao_tramitacao == est.AJUSTE_GESTOR


@pytest.mark.asyncio
async def test_unidade_corrige_e_reenvia_ao_gestor(arreio_debito_no_gestor):
    """Cenário 5: depois da correção volta ao GESTOR, não à validação."""
    d, ctx = arreio_debito_no_gestor
    d = await svc.solicitar_ajuste(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.gestor_id,
        lock_version=d.lock_version, etapa="GESTOR", justificativa="Corrigir NF.")
    d = await svc.responder_ajuste(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
        usuario_id=ctx.solicitante_id, lock_version=d.lock_version)
    assert d.situacao_tramitacao == est.AGUARDANDO_GESTOR


@pytest.mark.asyncio
async def test_gestor_rejeita_com_justificativa_e_encerra(arreio_debito_no_gestor):
    """Cenário 6: encerra e a decisão fica no histórico."""
    d, ctx = arreio_debito_no_gestor
    d = await svc.gestor_rejeitar(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.gestor_id,
        lock_version=d.lock_version, justificativa="Despesa sem interesse público.")
    assert d.situacao_tramitacao == est.REJEITADA_GESTOR
    assert d.status == "REJEITADO"
    hist = await svc.listar_historico(ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id)
    assert any(h.justificativa == "Despesa sem interesse público." for h in hist)


@pytest.mark.asyncio
async def test_solicitante_nao_pode_ser_o_gestor(arreio_debito_no_gestor):
    d, ctx = arreio_debito_no_gestor
    with pytest.raises(SegregacaoError):
        await svc.gestor_autorizar(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
            usuario_id=ctx.solicitante_id, lock_version=d.lock_version)


@pytest.mark.asyncio
async def test_lock_version_defasada_da_409(arreio_debito_no_gestor):
    """Cenário 21: dois usuários decidindo a mesma etapa."""
    d, ctx = arreio_debito_no_gestor
    with pytest.raises(ConflitoDeEdicaoError):
        await svc.gestor_autorizar(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
            usuario_id=ctx.gestor_id, lock_version=d.lock_version - 1)


@pytest.mark.asyncio
async def test_ajuste_sem_justificativa_e_recusado(arreio_debito_no_gestor):
    d, ctx = arreio_debito_no_gestor
    with pytest.raises(svc.PagamentoDebitoError):
        await svc.solicitar_ajuste(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.gestor_id,
            lock_version=d.lock_version, etapa="GESTOR", justificativa="   ")
```

As fixtures `arreio_debito` e `arreio_debito_no_gestor` são criadas neste mesmo arquivo. Elas provisionam tenant, unidade, fornecedor, natureza, fonte, o débito com parcelas e três usuários distintos (solicitante, gestor, validador). **Nenhum id cravado** — todos vêm do que a fixture cria. Se `listar_historico` não existir em `pagamentos_debitos`, criá-la: consulta `DebitoHistorico` por `tenant_id` e `id_debito`, ordenada por `criado_em`.

- [ ] **Step 2: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_fluxo_gestor.py -v
```

Esperado: `AttributeError: module 'app.services.pagamentos_debitos' has no attribute 'enviar_para_gestor'`.

- [ ] **Step 3: Implementar as transições**

Em `backend/app/services/pagamentos_debitos.py`, substituir `enviar_validacao` e acrescentar as demais:

```python
_ETAPA_DO_AJUSTE = {
    "GESTOR": est.AJUSTE_GESTOR,
    "VALIDACAO": est.AJUSTE_VALIDACAO,
    "AUTORIDADE": est.AJUSTE_AUTORIDADE,
}
# Para onde volta depois de respondido. Nesta fatia o retorno é sempre à etapa
# que pediu — a regra de "alteração material volta ao gestor" chega na F2, junto
# com o versionamento que sabe distinguir material de não material.
_RETORNO_DO_AJUSTE = {
    est.AJUSTE_GESTOR: est.AGUARDANDO_GESTOR,
    est.AJUSTE_VALIDACAO: est.AGUARDANDO_VALIDACAO,
    est.AJUSTE_AUTORIDADE: est.AGUARDANDO_AUTORIDADE,
}


async def _carregar_para_decisao(db, *, tenant_id: int, debito_id: int,
                                 lock_version: int) -> Debito:
    """Carrega com lock de linha e confere a versão otimista.

    O `for_update` é o que impede duas decisões concorrentes de lerem o mesmo
    `lock_version` e passarem as duas pela conferência.
    """
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id, for_update=True)
    grd.assert_lock_version(d, esperado=lock_version)
    return d


async def enviar_para_gestor(db: AsyncSession, *, tenant_id: int, debito_id: int,
                             usuario_id: int, lock_version: int,
                             ip: str | None = None) -> Debito:
    """Unidade setorial envia a solicitação ao gestor da pasta.

    Sucede `enviar_validacao`, que mandava direto para a conferência documental
    — pulando o juízo de mérito, que é do gestor.
    """
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao not in (est.RASCUNHO, est.AJUSTE_GESTOR,
                                     est.AJUSTE_VALIDACAO, est.AJUSTE_AUTORIDADE):
        raise PagamentoDebitoError(
            f"Só se envia solicitação em rascunho ou em ajuste "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if not parcelas:
        raise PagamentoDebitoError("Débito sem parcelas.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != d.valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({d.valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    _registrar_transicao(db, debito=d, acao="ENVIADO", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_GESTOR, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def gestor_autorizar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int,
                           ip: str | None = None) -> Debito:
    """Gestor da pasta autoriza o mérito e a conveniência da despesa."""
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_GESTOR:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando o gestor "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="GERIR")
    d.id_gestor_decisor = usuario_id
    _registrar_transicao(db, debito=d, acao="AUTORIZADO_GESTOR", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_VALIDACAO, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def gestor_rejeitar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                          usuario_id: int, lock_version: int, justificativa: str,
                          ip: str | None = None) -> Debito:
    """Gestor rejeita a despesa. Encerra o processo; a decisão fica no histórico."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("A rejeição exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_GESTOR:
        raise PagamentoDebitoError(
            f"Só o gestor rejeita, e só enquanto a solicitação o aguarda "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="GERIR")
    d.id_gestor_decisor = usuario_id
    _registrar_transicao(db, debito=d, acao="REJEITADO_GESTOR", usuario_id=usuario_id,
                         tramitacao=est.REJEITADA_GESTOR, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def solicitar_ajuste(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int, etapa: str,
                           justificativa: str, ip: str | None = None) -> Debito:
    """Devolve para correção, a partir de qualquer das três etapas decisórias.

    Na F1 o ajuste é só a mudança de estado mais a justificativa no histórico.
    A entidade `pedido_ajuste` — com responsável designado, prazo, situação e
    resposta — é a F2.
    """
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError(
            "O pedido de ajuste exige que se diga o que precisa ser corrigido.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    destino = _ETAPA_DO_AJUSTE.get(etapa)
    if destino is None:
        raise PagamentoDebitoError(f"Etapa desconhecida: '{etapa}'.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    _registrar_transicao(db, debito=d, acao="AJUSTE_SOLICITADO", usuario_id=usuario_id,
                         tramitacao=destino, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def responder_ajuste(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int,
                           ip: str | None = None) -> Debito:
    """Unidade responde o ajuste; volta à etapa que o pediu."""
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    destino = _RETORNO_DO_AJUSTE.get(d.situacao_tramitacao)
    if destino is None:
        raise PagamentoDebitoError(
            f"Esta solicitação não tem ajuste pendente "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    _registrar_transicao(db, debito=d, acao="AJUSTE_RESPONDIDO", usuario_id=usuario_id,
                         tramitacao=destino, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d
```

Acrescentar aos imports do arquivo:

```python
from . import pagamentos_guardas as grd
```

- [ ] **Step 4: Rodar e confirmar que passam**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_fluxo_gestor.py -v
```

Esperado: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pagamentos_debitos.py backend/tests/test_pagamentos_fluxo_gestor.py
git commit -m "feat(pagamentos): etapa do gestor da pasta com decisao real (F1, Tarefa 5)"
```

---

## Task 6: Validação financeira sem poder de encerrar, e a etapa da autoridade

**Files:**
- Modify: `backend/app/services/pagamentos_debitos.py` (`validar`, `rejeitar`, `suspender`, `reativar`, `encaminhar`, `cancelar`, `confirmar_liquidacao`)
- Modify: `backend/tests/test_pagamentos_debitos.py` (acertar os testes antigos)
- Test: `backend/tests/test_pagamentos_validacao_sem_rejeicao.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4, 5.
- Produces:
  - `validar(db, *, tenant_id, debito_id, usuario_id, lock_version, ip=None) -> Debito`
  - `autoridade_aprovar(db, *, tenant_id, debito_id, usuario_id, lock_version, ip=None) -> Debito`
  - `autoridade_indeferir(db, *, tenant_id, debito_id, usuario_id, lock_version, justificativa, ip=None) -> Debito`
  - `rejeitar`, `suspender`, `reativar`, `encaminhar` **removidas**

- [ ] **Step 1: Escrever o teste que falha — a regra central da fatia**

Criar `backend/tests/test_pagamentos_validacao_sem_rejeicao.py`:

```python
"""A validação financeira NÃO encerra a solicitação (spec §3.1; cenário 9).

Este é o teste mais importante da F1. Antes dela, `rejeitar()` aceitava
`EM_VALIDACAO` entre as origens e o endpoint era gateado por `PERM_VALIDAR` —
ou seja, quem conferia nota fiscal podia matar o processo.

Os testes são escritos por INVERSÃO: cada um TENTA encerrar a partir da
validação e exige que não consiga. Um teste que apenas verificasse o caminho
feliz continuaria verde com a rejeição de volta no código.
"""
import pytest

from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est


def test_o_servico_nao_expoe_mais_funcao_de_rejeicao_generica():
    """A função `rejeitar` foi substituída por decisões nomeadas por etapa.

    Enquanto ela existir com o nome genérico, alguém a religa num router e a
    validação volta a encerrar sem que nenhum teste de comportamento perceba.
    """
    assert not hasattr(svc, "rejeitar"), (
        "use gestor_rejeitar / autoridade_indeferir — não uma rejeição genérica")
    assert not hasattr(svc, "suspender")
    assert not hasattr(svc, "encaminhar")


def test_o_grafo_nao_liga_validacao_a_nenhum_terminal():
    saidas = est.TRANSICOES_TRAMITACAO[est.AGUARDANDO_VALIDACAO]
    assert saidas & est.TERMINAIS == frozenset()


@pytest.mark.asyncio
async def test_validador_nao_consegue_rejeitar_pelo_gestor(arreio_debito_na_validacao):
    """Tentar usar a rejeição do gestor a partir da validação dá 409."""
    d, ctx = arreio_debito_na_validacao
    with pytest.raises(svc.PagamentoDebitoError) as e:
        await svc.gestor_rejeitar(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.gestor_id,
            lock_version=d.lock_version, justificativa="tentativa indevida")
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_validador_nao_consegue_indeferir_pela_autoridade(arreio_debito_na_validacao):
    d, ctx = arreio_debito_na_validacao
    with pytest.raises(svc.PagamentoDebitoError) as e:
        await svc.autoridade_indeferir(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
            usuario_id=ctx.autoridade_id, lock_version=d.lock_version,
            justificativa="tentativa indevida")
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_validador_nao_consegue_cancelar(arreio_debito_na_validacao):
    """Cancelar é ato da unidade solicitante, não da conferência."""
    d, ctx = arreio_debito_na_validacao
    with pytest.raises(svc.PagamentoDebitoError):
        await svc.cancelar(
            ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.validador_id,
            lock_version=d.lock_version, justificativa="tentativa indevida")


@pytest.mark.asyncio
async def test_as_duas_unicas_saidas_da_validacao_funcionam(arreio_debito_na_validacao):
    """Cenários 7 e 8: validar e solicitar ajustes — e mais nada."""
    d, ctx = arreio_debito_na_validacao
    ajustada = await svc.solicitar_ajuste(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.validador_id,
        lock_version=d.lock_version, etapa="VALIDACAO",
        justificativa="Nota fiscal ilegível.")
    assert ajustada.situacao_tramitacao == est.AJUSTE_VALIDACAO

    voltou = await svc.responder_ajuste(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id,
        usuario_id=ctx.solicitante_id, lock_version=ajustada.lock_version)
    validada = await svc.validar(
        ctx.db, tenant_id=ctx.tenant_id, debito_id=d.id, usuario_id=ctx.validador_id,
        lock_version=voltou.lock_version)
    assert validada.situacao_tramitacao == est.AGUARDANDO_AUTORIDADE
    assert validada.id_validador == ctx.validador_id
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_validacao_sem_rejeicao.py -v
```

Esperado: `test_o_servico_nao_expoe_mais_funcao_de_rejeicao_generica` falha (as funções ainda existem) e os assíncronos falham por falta de `autoridade_indeferir`.

- [ ] **Step 3: Reescrever `validar`, remover as funções que dão poder de encerrar e acrescentar a autoridade**

Em `backend/app/services/pagamentos_debitos.py`:

**Apagar por completo** `rejeitar`, `suspender`, `reativar` e `encaminhar`. Elas não são renomeadas nem mantidas como alias: enquanto existirem, alguém as religa num router.

Substituir `validar` por:

```python
async def validar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                  usuario_id: int, lock_version: int, ip: str | None = None) -> Debito:
    """Validação financeira atesta a conformidade documental, contábil e fiscal.

    **Esta etapa tem duas saídas e nenhuma delas encerra a solicitação**
    (spec §3.1): validar → autoridade, ou solicitar ajustes → correção. Achou
    inconformidade? `solicitar_ajuste(etapa="VALIDACAO")`. Não há rejeição
    aqui, e `test_pagamentos_validacao_sem_rejeicao.py` prova isso por inversão.
    """
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_VALIDACAO:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando validação "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="VALIDAR")
    if not d.liquidacao_confirmada:
        raise PagamentoDebitoError(
            "Não é possível validar sem confirmação de liquidação (RF-VAL-02/RN-01).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    from .pagamentos_checklist import checklist_pendente
    pendentes = await checklist_pendente(db, tenant_id=tenant_id, debito_id=debito_id)
    if pendentes:
        raise PagamentoDebitoError(
            "Checklist documental incompleto: " + ", ".join(pendentes) + " (RF-VAL-01).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    d.id_validador = usuario_id
    _registrar_transicao(db, debito=d, acao="VALIDADO", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_AUTORIDADE, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def autoridade_aprovar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                             usuario_id: int, lock_version: int,
                             ip: str | None = None) -> Debito:
    """Autoridade competente aprova e ordena o pagamento.

    Encerra a TRAMITAÇÃO com êxito. A reserva de saldo e a escolha da conta
    pagadora continuam em `pagamentos_autorizacao.autorizar_lote`, que não é
    tocado nesta fatia — esta função move a tramitação, aquela move dinheiro.
    """
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_AUTORIDADE:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando a autoridade "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="AUTORIZAR")
    _registrar_transicao(db, debito=d, acao="AUTORIZADO", usuario_id=usuario_id,
                         tramitacao=est.AUTORIZADA, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def autoridade_indeferir(db: AsyncSession, *, tenant_id: int, debito_id: int,
                               usuario_id: int, lock_version: int, justificativa: str,
                               ip: str | None = None) -> Debito:
    """Autoridade não aprova. Encerra o processo; a decisão vai para a trilha."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("O indeferimento exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_AUTORIDADE:
        raise PagamentoDebitoError(
            f"Só a autoridade indefere, e só enquanto a solicitação a aguarda "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="AUTORIZAR")
    _registrar_transicao(db, debito=d, acao="INDEFERIDO", usuario_id=usuario_id,
                         tramitacao=est.INDEFERIDA_AUTORIDADE,
                         justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d
```

Reescrever `cancelar` para receber `lock_version`, exigir que quem cancela seja o solicitante (ou tenha `pagamento_cadastro`, checado no router) e usar o grafo:

```python
async def cancelar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   lock_version: int, justificativa: str, ip: str | None = None) -> Debito:
    """Cancela a solicitação. Ato da unidade solicitante, em qualquer etapa
    anterior à execução."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("O cancelamento exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if not est.transicao_permitida(d.situacao_tramitacao, est.CANCELADA):
        raise PagamentoDebitoError(
            f"Solicitação em '{d.situacao_tramitacao}' não pode ser cancelada.",
            status.HTTP_409_CONFLICT)
    if usuario_id != d.id_usuario_solicitante:
        raise PagamentoDebitoError(
            "Só a unidade solicitante cancela a própria solicitação.",
            status.HTTP_403_FORBIDDEN)
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if any(p.status == "PAGA" for p in parcelas):
        raise PagamentoDebitoError(
            "Débito com parcela paga não pode ser cancelado — estorne antes.",
            status.HTTP_409_CONFLICT)
    for p in parcelas:
        p.status = "CANCELADA"; p.atualizado_em = _utcnow()
    _registrar_transicao(db, debito=d, acao="CANCELADO", usuario_id=usuario_id,
                         tramitacao=est.CANCELADA, fila=est.RETIRADA,
                         pagamento=est.PAG_CANCELADA, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d
```

Em `confirmar_liquidacao`, trocar a lista de status aceitos por situações de tramitação:

```python
    if d.situacao_tramitacao in est.TERMINAIS or d.situacao_tramitacao == est.AUTORIZADA:
        raise PagamentoDebitoError(
            "A liquidação se confirma antes da autorização.", status.HTTP_409_CONFLICT)
```

e o `db.add(DebitoHistorico(...))` de dentro dela por
`_registrar_transicao(db, debito=d, acao="LIQUIDADO", usuario_id=usuario_id, justificativa=..., ip=ip)`
— sem passar dimensão nenhuma, porque a liquidação não muda etapa nesta fatia. **A entrada na fila cronológica é a F3.**

Em `editar_debito` e `excluir_debito`, trocar as checagens de `d.status` por `d.situacao_tramitacao`, usando `est.RASCUNHO` e os três `AJUSTE_*` como editáveis.

Em `detectar_duplicidade`, trocar
`Debito.status.notin_(("REJEITADO", "CANCELADO"))` por
`Debito.situacao_tramitacao.notin_(tuple(est.TERMINAIS))`.

- [ ] **Step 4: Acertar os testes antigos**

`backend/tests/test_pagamentos_debitos.py` referencia `enviar_validacao`, `encaminhar`, `rejeitar`, `suspender`, `reativar` e monta payloads sem `id_unidade`. Atualizar:

- `enviar_validacao` → `enviar_para_gestor`
- o par `validar` + `encaminhar` → `gestor_autorizar` + `validar`
- `rejeitar` a partir da validação → **apagar o teste**; a capacidade deixou de existir e o novo arquivo cobre a ausência
- `rejeitar` a partir do gestor → `gestor_rejeitar`
- `suspender`/`reativar` → `solicitar_ajuste(etapa="VALIDACAO")` + `responder_ajuste`
- todo `DebitoCreate(...)` ganha `id_unidade=<id que a fixture criou>`
- toda chamada de decisão ganha `lock_version=d.lock_version`

Mesmo tratamento em `test_pagamentos_autorizacao.py`, `test_pagamentos_liberacao.py`, `test_pagamentos_filas.py`, `test_pagamentos_dashboard.py`, `test_pagamentos_excecoes_c12.py` e `test_pagamentos_validacoes_v2.py`, onde houver.

- [ ] **Step 5: Rodar o bloco de pagamentos inteiro**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/ -k pagamentos -v
```

Esperado: tudo verde. Se `pagamentos_excecoes.py` ou `pagamentos_filas.py` quebrarem, **não migrá-los para as três dimensões** — conferir por que o `status` derivado não está entregando o valor que eles esperam, e corrigir a derivação. Migrá-los é F5.

- [ ] **Step 6: Provar por inversão**

Reintroduzir `est.REJEITADA_GESTOR` nas saídas de `AGUARDANDO_VALIDACAO` e conferir que `test_o_grafo_nao_liga_validacao_a_nenhum_terminal` e `test_validador_nao_consegue_rejeitar_pelo_gestor` ficam **vermelhos**. Desfazer.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/pagamentos_debitos.py backend/tests/
git commit -m "feat(pagamentos): validacao financeira sem poder de encerrar; etapa da autoridade (F1, Tarefa 6)"
```

---

## Task 7: Routers, permissões e endpoints descontinuados

**Files:**
- Modify: `backend/app/routers/pagamentos_debitos.py:40-45, 154-272`
- Test: `backend/tests/test_pagamentos_http_fluxo.py`

**Interfaces:**
- Consumes: Tasks 5, 6.
- Produces: `POST /api/v2/pagamentos/debitos/{id}/enviar`, `/gestor/autorizar`, `/gestor/rejeitar`, `/validar`, `/autoridade/aprovar`, `/autoridade/indeferir`, `/ajuste/solicitar`, `/ajuste/responder`, `/cancelar`; `410 Gone` em `/aprovar` e `/encaminhar`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_pagamentos_http_fluxo.py`. **Todos os casos com usuário comum**, nunca super-usuário — o bypass de SU em `auth/perms.py` retorna antes do `getattr(item, action)` e esconde `action` inexistente. Reaproveitar `_cria_usuario_comum` de `test_permissoes_modulo.py`; o tenant precisa contratar o módulo `pagamentos`.

```python
"""O rito pelo HTTP, com usuário comum (spec §6.1; cenário 20 do pedido).

Todo caso aqui usa usuário COMUM, nunca super-usuário. O bypass de SU em
`auth/perms.py` retorna antes do `getattr(item, action)`, então `action`
inexistente vira AttributeError → HTTP 500 apenas para o operador de verdade —
foi assim que 10 rotas do transporte passaram por toda a bateria devolvendo 500
em produção.
"""
import pytest


@pytest.mark.asyncio
async def test_gestor_autoriza_pelo_http(cliente_gestor, debito_no_gestor):
    r = await cliente_gestor.post(
        f"/api/v2/pagamentos/debitos/{debito_no_gestor.id}/gestor/autorizar",
        json={"lock_version": debito_no_gestor.lock_version})
    assert r.status_code == 200, r.text
    assert r.json()["situacao_tramitacao"] == "AGUARDANDO_VALIDACAO"


@pytest.mark.asyncio
async def test_quem_so_valida_nao_autoriza_como_gestor(cliente_validador, debito_no_gestor):
    """A permissão do gestor é `pagamento_gerir`; `pagamento_validar` não serve."""
    r = await cliente_validador.post(
        f"/api/v2/pagamentos/debitos/{debito_no_gestor.id}/gestor/autorizar",
        json={"lock_version": debito_no_gestor.lock_version})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_nao_existe_rota_de_rejeicao_na_validacao(cliente_validador, debito_na_validacao):
    """Nenhum caminho HTTP leva a validação a um estado terminal."""
    for rota in ("gestor/rejeitar", "autoridade/indeferir"):
        r = await cliente_validador.post(
            f"/api/v2/pagamentos/debitos/{debito_na_validacao.id}/{rota}",
            json={"lock_version": debito_na_validacao.lock_version,
                  "justificativa": "tentativa"})
        assert r.status_code in (403, 409), f"{rota} devolveu {r.status_code}"


@pytest.mark.asyncio
async def test_lock_version_defasada_da_409_pelo_http(cliente_gestor, debito_no_gestor):
    r = await cliente_gestor.post(
        f"/api/v2/pagamentos/debitos/{debito_no_gestor.id}/gestor/autorizar",
        json={"lock_version": debito_no_gestor.lock_version - 1})
    assert r.status_code == 409
    assert "recarregue" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_endpoints_descontinuados_devolvem_410(cliente_validador, debito_no_gestor):
    """410, não 404: cliente antigo recebendo 404 parece bug de rota."""
    for rota in ("aprovar", "encaminhar"):
        r = await cliente_validador.post(
            f"/api/v2/pagamentos/debitos/{debito_no_gestor.id}/{rota}", json={})
        assert r.status_code == 410, f"{rota} devolveu {r.status_code}"
        assert "gestor/autorizar" in r.json()["detail"] or "validar" in r.json()["detail"]


@pytest.mark.asyncio
async def test_ajuste_sem_justificativa_da_422(cliente_gestor, debito_no_gestor):
    r = await cliente_gestor.post(
        f"/api/v2/pagamentos/debitos/{debito_no_gestor.id}/ajuste/solicitar",
        json={"lock_version": debito_no_gestor.lock_version,
              "etapa": "GESTOR", "justificativa": ""})
    assert r.status_code == 422
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_http_fluxo.py -v
```

Esperado: 404 em todas as rotas novas.

- [ ] **Step 3: Implementar os endpoints**

Em `backend/app/routers/pagamentos_debitos.py`, atualizar as constantes de permissão:

```python
PERMS_LEITURA = ("pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
                 "pagamento_autorizar", "pagamento_pagar", "pagamento_auditar",
                 "pagamento_cadastro")
```

Remover `PERM_VALIDAR` e `PERM_ENCAMINHAR` — permissão por etapa passa a ser
única e explícita, sem tupla de aliases.

**Apagar** os handlers `validar` (o antigo), `aprovar`, `encaminhar`, `devolver`,
`rejeitar`, `suspender` e `reativar`, e pôr no lugar:

```python
# --- rito: uma rota por decisão, uma permissão por etapa (F1, spec §6.1) ----
# Rotas literais ANTES de qualquer paramétrica irmã: o FastAPI casa na ordem de
# declaração, e a paramétrica engoliria a literal com 422 sem chegar no handler
# (aconteceu três vezes no transporte). `tests/test_guarda_ordem_rotas.py` varre.

@debitos_router.post("/{debito_id}/enviar", response_model=DebitoOut)
async def enviar(debito_id: int, payload: DecisaoIn, request: Request,
                 usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                 tenant_id: int = Depends(require_tenant_id),
                 db: AsyncSession = Depends(get_db)):
    d = await svc.enviar_para_gestor(db, tenant_id=tenant_id, debito_id=debito_id,
                                     usuario_id=usuario.id,
                                     lock_version=payload.lock_version, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/gestor/autorizar", response_model=DebitoOut)
async def gestor_autorizar(debito_id: int, payload: DecisaoIn, request: Request,
                           usuario: Usuario = Depends(require_permission("pagamento_gerir")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    d = await svc.gestor_autorizar(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id,
                                   lock_version=payload.lock_version, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/gestor/rejeitar", response_model=DebitoOut)
async def gestor_rejeitar(debito_id: int, payload: DecisaoJustificadaIn, request: Request,
                          usuario: Usuario = Depends(require_permission("pagamento_gerir")),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    d = await svc.gestor_rejeitar(db, tenant_id=tenant_id, debito_id=debito_id,
                                  usuario_id=usuario.id, lock_version=payload.lock_version,
                                  justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/validar", response_model=DebitoOut)
async def validar(debito_id: int, payload: DecisaoIn, request: Request,
                  usuario: Usuario = Depends(require_permission("pagamento_validar")),
                  tenant_id: int = Depends(require_tenant_id),
                  db: AsyncSession = Depends(get_db)):
    """Valida a conformidade. NÃO existe rota irmã de rejeição nesta etapa —
    inconformidade se resolve por `/ajuste/solicitar` (spec §3.1)."""
    d = await svc.validar(db, tenant_id=tenant_id, debito_id=debito_id,
                          usuario_id=usuario.id, lock_version=payload.lock_version,
                          ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/autoridade/aprovar", response_model=DebitoOut)
async def autoridade_aprovar(debito_id: int, payload: DecisaoIn, request: Request,
                             usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    d = await svc.autoridade_aprovar(db, tenant_id=tenant_id, debito_id=debito_id,
                                     usuario_id=usuario.id,
                                     lock_version=payload.lock_version, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/autoridade/indeferir", response_model=DebitoOut)
async def autoridade_indeferir(debito_id: int, payload: DecisaoJustificadaIn, request: Request,
                               usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                               tenant_id: int = Depends(require_tenant_id),
                               db: AsyncSession = Depends(get_db)):
    d = await svc.autoridade_indeferir(db, tenant_id=tenant_id, debito_id=debito_id,
                                       usuario_id=usuario.id, lock_version=payload.lock_version,
                                       justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/ajuste/solicitar", response_model=DebitoOut)
async def solicitar_ajuste(debito_id: int, payload: SolicitarAjusteIn, request: Request,
                           usuario: Usuario = Depends(require_any_permission(
                               "pagamento_gerir", "pagamento_validar", "pagamento_autorizar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    d = await svc.solicitar_ajuste(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, lock_version=payload.lock_version,
                                   etapa=payload.etapa, justificativa=payload.justificativa,
                                   ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/ajuste/responder", response_model=DebitoOut)
async def responder_ajuste(debito_id: int, payload: DecisaoIn, request: Request,
                           usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    d = await svc.responder_ajuste(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id,
                                   lock_version=payload.lock_version, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


# --- descontinuados (F1) ----------------------------------------------------
# 410 e não 404: quem chamar isto é cliente antigo, e 404 o mandaria procurar
# erro de rota. A mensagem aponta o substituto.

@debitos_router.post("/{debito_id}/aprovar", status_code=410)
async def aprovar_descontinuado(debito_id: int):
    raise HTTPException(410, detail=(
        "Endpoint descontinuado na F1. '/aprovar' era alias da validação "
        "documental. Use POST /{id}/gestor/autorizar (mérito da despesa) ou "
        "POST /{id}/validar (conformidade)."))


@debitos_router.post("/{debito_id}/encaminhar", status_code=410)
async def encaminhar_descontinuado(debito_id: int):
    raise HTTPException(410, detail=(
        "Endpoint descontinuado na F1. O encaminhamento sem decisão deu lugar "
        "à etapa do gestor da pasta: use POST /{id}/gestor/autorizar."))
```

Acrescentar em `schemas/pagamentos.py`:

```python
class SolicitarAjusteIn(DecisaoJustificadaIn):
    etapa: Literal["GESTOR", "VALIDACAO", "AUTORIDADE"]
```

Atualizar a rota `/cancelar` para receber `DecisaoJustificadaIn` e repassar `lock_version`.

- [ ] **Step 4: Rodar**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_http_fluxo.py tests/test_guarda_ordem_rotas.py -v
```

Esperado: tudo verde.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/pagamentos_debitos.py backend/app/schemas/pagamentos.py \
        backend/tests/test_pagamentos_http_fluxo.py
git commit -m "feat(pagamentos): endpoints por etapa, permissao propria do gestor, 410 nos descontinuados (F1, Tarefa 7)"
```

---

## Task 8: Guarda do status legado

**Files:**
- Create: `backend/tests/test_guarda_status_legado.py`

**Interfaces:**
- Consumes: Tasks 3, 6.
- Produces: nada em runtime — é guarda estrutural.

- [ ] **Step 1: Escrever a guarda**

Criar `backend/tests/test_guarda_status_legado.py`:

```python
"""Guarda: a coluna `Debito.status` é legada e a lista de quem a lê só ENCOLHE.

A spec §4.2 aceita manter a coluna derivada durante F1–F4 porque migrar seis
serviços e o frontend na mesma fatia daria um diff que ninguém revisa. O preço
dessa escolha é o risco de consumidor NOVO nascer acoplado ao campo antigo — e
é isso que esta guarda impede.

Consumidor novo? Use as três dimensões. Consumidor daqui saiu? Tire da lista.
A lista nunca cresce; na F5 ela fica vazia e o arquivo morre junto com a coluna.

Usa `ast`, não regex. A primeira versão da guarda de MD5 foi escrita em regex e
deu cinco falsos positivos de duas espécies — leu o próprio docstring como
código e confundiu argumento nomeado com gravação de coluna. Guarda que grita
no caso legítimo é desligada por quem tropeça nela, e aí não guarda mais nada.
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "app"

# Consumidores tolerados de `Debito.status`, com a fatia que os remove.
# NUNCA acrescentar linha aqui. Só remover.
CONSUMIDORES_LEGADOS = {
    "services/pagamentos_debitos.py",    # _sincronizar_status_legado — o único ESCRITOR
    "services/pagamentos_conciliacao.py",  # F5
    "services/pagamentos_excecoes.py",     # F5
    "services/pagamentos_caixa.py",        # F5
    "services/pagamentos_export.py",       # F5
    "services/pagamentos_filas.py",        # F5
    "services/pagamentos_dashboard.py",    # F5
    "services/pagamentos_autorizacao.py",  # F5
    "routers/pagamentos_debitos.py",       # F5
    "models/pagamentos.py",                # a declaração da coluna
    "schemas/pagamentos.py",               # StatusDebito
}


def _le_status_de_debito(caminho: Path) -> bool:
    """True se o arquivo referencia `Debito.status` ou `d.status` de um débito.

    Conservador de propósito: qualquer atributo `.status` sobre um nome que
    pareça débito conta. Falso positivo aqui custa uma linha na lista; falso
    negativo deixa passar acoplamento novo.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes_de_debito = {"Debito", "debito", "d", "deb"}
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Attribute) and no.attr == "status"
                and isinstance(no.value, ast.Name)
                and no.value.id in nomes_de_debito):
            return True
    return False


def test_nenhum_consumidor_novo_de_status_legado():
    achados = {
        str(p.relative_to(RAIZ)).replace("\\", "/")
        for p in RAIZ.rglob("*.py") if _le_status_de_debito(p)
    }
    novos = achados - CONSUMIDORES_LEGADOS
    assert not novos, (
        f"Estes arquivos passaram a ler o `status` legado do débito: {sorted(novos)}. "
        f"Use situacao_tramitacao / situacao_fila / situacao_pagamento. "
        f"A coluna `status` é derivada e some na F5.")


def test_a_lista_nao_tem_arquivo_que_ja_saiu():
    """Entrada obsoleta na lista mascara acoplamento novo no mesmo arquivo."""
    achados = {
        str(p.relative_to(RAIZ)).replace("\\", "/")
        for p in RAIZ.rglob("*.py") if _le_status_de_debito(p)
    }
    obsoletos = CONSUMIDORES_LEGADOS - achados
    assert not obsoletos, (
        f"Estes arquivos não leem mais o status legado — tire-os da lista: "
        f"{sorted(obsoletos)}")


def test_so_um_lugar_escreve_a_coluna_legada():
    """Dois escritores divergem. É o risco registrado na spec §4.2."""
    escritores = set()
    for p in RAIZ.rglob("*.py"):
        arvore = ast.parse(p.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Assign):
                continue
            for alvo in no.targets:
                if (isinstance(alvo, ast.Attribute) and alvo.attr == "status"
                        and isinstance(alvo.value, ast.Name)
                        and alvo.value.id in {"d", "debito", "deb"}):
                    escritores.add(str(p.relative_to(RAIZ)).replace("\\", "/"))
    assert escritores == {"services/pagamentos_debitos.py"}, (
        f"`Debito.status` só pode ser escrito por _sincronizar_status_legado; "
        f"escritores encontrados: {sorted(escritores)}")
```

- [ ] **Step 2: Rodar**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_status_legado.py -v
```

Ajustar `CONSUMIDORES_LEGADOS` ao que a varredura realmente achar — a lista acima é o palpite inicial, e o teste é a autoridade.

- [ ] **Step 3: Provar por inversão**

Acrescentar `d.status = "PAGO"` em `services/pagamentos_caixa.py`. Rodar: `test_so_um_lugar_escreve_a_coluna_legada` **tem de ficar vermelho**. Desfazer.

Acrescentar uma leitura de `Debito.status` em `services/pagamentos_bloqueios.py` (que não está na lista). Rodar: `test_nenhum_consumidor_novo_de_status_legado` **tem de ficar vermelho**. Desfazer.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_guarda_status_legado.py
git commit -m "test(pagamentos): guarda do status legado, provada por inversao (F1, Tarefa 8)"
```

---

## Task 9: Suíte completa do backend

**Files:** nenhum novo.

- [ ] **Step 1: Rodar a suíte inteira em segundo plano**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q
```

~14 min. **Rodar em background desde o começo** — estoura o teto de 600 s da ferramenta. Não editar a árvore enquanto roda.

- [ ] **Step 2: Conferir o resultado**

Esperado: `2 failed / N passed`, com exatamente as duas conhecidas (`test_jwt_compat::test_emitted_token_has_required_claims` e `test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`). Qualquer terceira é regressão da F1.

- [ ] **Step 3: Rodar sob o papel restrito**

```
docker exec -e PYTEST_DB_HOST=db \
  -e DATABASE_URL=postgresql+asyncpg://aprimora_app:ged_password_secure_local@db:5432/ged_saas_db \
  aprimora-py-backend pytest -q -k pagamentos
```

Esperado: idêntico ao papel padrão. Diferença aqui significa grant faltando — corrigir a policy ou o grant, **nunca** dando `BYPASSRLS`.

- [ ] **Step 4: Commit se houve conserto**

```bash
git add -A backend/
git commit -m "fix(pagamentos): acerta regressoes da suite apos a F1 (F1, Tarefa 9)"
```

---

## Task 10: Frontend — tipos, menu por etapa e rótulos

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/menus/pagamentos.ts`, `frontend/__tests__/menus.test.tsx`
- Create: `frontend/components/pagamentos/situacoes.ts`, `frontend/__tests__/pagamentos-situacoes.test.tsx`

**Interfaces:**
- Consumes: `DebitoOut` da Task 3.
- Produces:
  - `SituacaoTramitacao`, `SituacaoFila`, `SituacaoPagamento`, `CategoriaContrato` em `api.ts`
  - `api.pagamentos.gestorAutorizar/gestorRejeitar/validar/autoridadeAprovar/autoridadeIndeferir/solicitarAjuste/responderAjuste/enviar`
  - `TRAMITACAO_ROTULO`, `FILA_ROTULO`, `PAGAMENTO_ROTULO`, `ETAPA_POR_TRAMITACAO`, `ETAPAS` em `situacoes.ts`

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/__tests__/pagamentos-situacoes.test.tsx`:

```tsx
/**
 * Rótulos das três dimensões (spec §6 do pedido: nada de enum técnico na tela).
 */
import { describe, expect, it } from "vitest";

import {
  ETAPAS,
  ETAPA_POR_TRAMITACAO,
  FILA_ROTULO,
  PAGAMENTO_ROTULO,
  TRAMITACAO_ROTULO,
} from "@/components/pagamentos/situacoes";

describe("rótulos das situações", () => {
  it("nenhum rótulo vaza enum técnico", () => {
    const todos = [
      ...Object.values(TRAMITACAO_ROTULO),
      ...Object.values(FILA_ROTULO),
      ...Object.values(PAGAMENTO_ROTULO),
    ].map((r) => r.label);
    for (const label of todos) {
      expect(label).not.toMatch(/_/);
      expect(label).not.toMatch(/^[A-Z]+$/);
    }
  });

  it("toda tramitação tem etapa no stepper", () => {
    for (const chave of Object.keys(TRAMITACAO_ROTULO)) {
      expect(ETAPA_POR_TRAMITACAO[chave]).toBeDefined();
      expect(ETAPAS.map((e) => e.key)).toContain(ETAPA_POR_TRAMITACAO[chave]);
    }
  });

  it("o stepper tem exatamente as cinco etapas do fluxo", () => {
    expect(ETAPAS.map((e) => e.key)).toEqual([
      "UNIDADE", "GESTOR", "VALIDACAO", "AUTORIDADE", "TESOURARIA",
    ]);
  });

  it("nenhuma situação depende só de cor para ser distinguida", () => {
    for (const r of Object.values(TRAMITACAO_ROTULO)) {
      expect(r.label.length).toBeGreaterThan(0);
      expect(r.icone).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
cd frontend && npx vitest run __tests__/pagamentos-situacoes.test.tsx
```

Esperado: módulo não encontrado.

- [ ] **Step 3: Criar os rótulos**

Criar `frontend/components/pagamentos/situacoes.ts`:

```ts
import type { SituacaoFila, SituacaoPagamento, SituacaoTramitacao } from "@/lib/api";

export type Intent = "neutral" | "warning" | "info" | "success" | "danger";

/** Um rótulo tem SEMPRE texto e ícone — status que se distingue só por cor é
 *  inacessível (spec §13 do pedido). */
export interface Rotulo {
  label: string;
  intent: Intent;
  icone: string;
}

export const TRAMITACAO_ROTULO: Record<SituacaoTramitacao, Rotulo> = {
  RASCUNHO:              { label: "Rascunho", intent: "neutral", icone: "pencil" },
  AGUARDANDO_GESTOR:     { label: "Aguardando o gestor da pasta", intent: "warning", icone: "clock" },
  AJUSTE_GESTOR:         { label: "Ajuste solicitado pelo gestor", intent: "warning", icone: "reply" },
  AGUARDANDO_VALIDACAO:  { label: "Aguardando validação financeira", intent: "warning", icone: "clock" },
  AJUSTE_VALIDACAO:      { label: "Ajuste solicitado pela unidade financeira", intent: "warning", icone: "reply" },
  AGUARDANDO_AUTORIDADE: { label: "Aguardando a autoridade competente", intent: "warning", icone: "clock" },
  AJUSTE_AUTORIDADE:     { label: "Ajuste solicitado pela autoridade", intent: "warning", icone: "reply" },
  AUTORIZADA:            { label: "Autorizada para pagamento", intent: "success", icone: "check" },
  REJEITADA_GESTOR:      { label: "Rejeitada pelo gestor", intent: "danger", icone: "x" },
  INDEFERIDA_AUTORIDADE: { label: "Indeferida pela autoridade", intent: "danger", icone: "x" },
  CANCELADA:             { label: "Cancelada", intent: "neutral", icone: "ban" },
};

export const FILA_ROTULO: Record<SituacaoFila, Rotulo> = {
  NAO_REGISTRADA:             { label: "Não registrada", intent: "neutral", icone: "minus" },
  REGISTRADA:                 { label: "Registrada", intent: "info", icone: "list" },
  BLOQUEADA:                  { label: "Bloqueada", intent: "danger", icone: "lock" },
  ELEGIVEL:                   { label: "Elegível para pagamento", intent: "success", icone: "check" },
  AGUARDANDO_DISPONIBILIDADE: { label: "Aguardando disponibilidade financeira", intent: "warning", icone: "wallet" },
  EXCECAO_AUTORIZADA:         { label: "Exceção autorizada", intent: "warning", icone: "flag" },
  CONCLUIDA:                  { label: "Concluída", intent: "success", icone: "check" },
  RETIRADA:                   { label: "Retirada da fila", intent: "neutral", icone: "minus" },
};

export const PAGAMENTO_ROTULO: Record<SituacaoPagamento, Rotulo> = {
  NAO_INICIADA:     { label: "Não iniciado", intent: "neutral", icone: "minus" },
  PROGRAMADA:       { label: "Programado", intent: "info", icone: "calendar" },
  ENVIADA_BANCO:    { label: "Enviado ao banco", intent: "info", icone: "send" },
  EM_PROCESSAMENTO: { label: "Em processamento", intent: "warning", icone: "loader" },
  PAGA_PARCIAL:     { label: "Pago parcialmente", intent: "warning", icone: "half" },
  PAGA:             { label: "Pago", intent: "success", icone: "check" },
  FALHOU:           { label: "Falhou no banco", intent: "danger", icone: "alert" },
  CANCELADA:        { label: "Cancelado", intent: "neutral", icone: "ban" },
  ESTORNADA:        { label: "Estornado", intent: "danger", icone: "undo" },
};

export type EtapaFluxo = "UNIDADE" | "GESTOR" | "VALIDACAO" | "AUTORIDADE" | "TESOURARIA";

export const ETAPAS: { key: EtapaFluxo; label: string; curto: string }[] = [
  { key: "UNIDADE",    label: "Unidade setorial",     curto: "Unidade" },
  { key: "GESTOR",     label: "Gestor da pasta",      curto: "Gestor" },
  { key: "VALIDACAO",  label: "Validação financeira", curto: "Validação" },
  { key: "AUTORIDADE", label: "Autoridade competente", curto: "Autoridade" },
  { key: "TESOURARIA", label: "Tesouraria",           curto: "Tesouraria" },
];

/** Espelha `ETAPA_POR_TRAMITACAO` de `services/pagamentos_estados.py`.
 *  Divergir daqui faz o stepper acender a etapa errada. */
export const ETAPA_POR_TRAMITACAO: Record<SituacaoTramitacao, EtapaFluxo> = {
  RASCUNHO: "UNIDADE",
  AGUARDANDO_GESTOR: "GESTOR",
  AJUSTE_GESTOR: "UNIDADE",
  AGUARDANDO_VALIDACAO: "VALIDACAO",
  AJUSTE_VALIDACAO: "UNIDADE",
  AGUARDANDO_AUTORIDADE: "AUTORIDADE",
  AJUSTE_AUTORIDADE: "UNIDADE",
  AUTORIZADA: "TESOURARIA",
  REJEITADA_GESTOR: "GESTOR",
  INDEFERIDA_AUTORIDADE: "AUTORIDADE",
  CANCELADA: "UNIDADE",
};
```

- [ ] **Step 4: Estender `api.ts`**

Acrescentar os tipos junto de `StatusDebito` e os campos novos em `Debito`. Acrescentar os métodos ao objeto de pagamentos, cada um recebendo `lockVersion`:

```ts
export type SituacaoTramitacao =
  | "RASCUNHO" | "AGUARDANDO_GESTOR" | "AJUSTE_GESTOR" | "AGUARDANDO_VALIDACAO"
  | "AJUSTE_VALIDACAO" | "AGUARDANDO_AUTORIDADE" | "AJUSTE_AUTORIDADE"
  | "AUTORIZADA" | "REJEITADA_GESTOR" | "INDEFERIDA_AUTORIDADE" | "CANCELADA";

export type SituacaoFila =
  | "NAO_REGISTRADA" | "REGISTRADA" | "BLOQUEADA" | "ELEGIVEL"
  | "AGUARDANDO_DISPONIBILIDADE" | "EXCECAO_AUTORIZADA" | "CONCLUIDA" | "RETIRADA";

export type SituacaoPagamento =
  | "NAO_INICIADA" | "PROGRAMADA" | "ENVIADA_BANCO" | "EM_PROCESSAMENTO"
  | "PAGA_PARCIAL" | "PAGA" | "FALHOU" | "CANCELADA" | "ESTORNADA";

export type CategoriaContrato = "BENS" | "LOCACOES" | "SERVICOS" | "OBRAS";
```

Na interface do débito, acrescentar `situacao_tramitacao`, `situacao_fila`, `situacao_pagamento`, `id_unidade`, `versao`, `lock_version`, `id_gestor_decisor`, `id_validador`, e marcar `status` com um comentário de legado.

Os métodos seguem o padrão já usado no arquivo:

```ts
    gestorAutorizar: (id: number, lockVersion: number) =>
      request<Debito>(`/pagamentos/debitos/${id}/gestor/autorizar`, {
        method: "POST", body: JSON.stringify({ lock_version: lockVersion }),
      }),
    gestorRejeitar: (id: number, lockVersion: number, justificativa: string) =>
      request<Debito>(`/pagamentos/debitos/${id}/gestor/rejeitar`, {
        method: "POST",
        body: JSON.stringify({ lock_version: lockVersion, justificativa }),
      }),
```

…e assim para `enviar`, `validar`, `autoridadeAprovar`, `autoridadeIndeferir`, `solicitarAjuste` (que leva também `etapa`) e `responderAjuste`. **Remover** `aprovar` e `encaminhar`.

- [ ] **Step 5: Reescrever o menu**

Substituir a lista de `items` em `frontend/lib/menus/pagamentos.ts`. Cada etapa do fluxo vira um item, na ordem do rito:

```ts
      items: [
        { label: "Visão geral", href: "/m/pagamentos", icon: LayoutDashboard,
          anyOf: ["pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
                  "pagamento_autorizar", "pagamento_pagar", "pagamento_auditar",
                  "pagamento_cadastro"] },
        { label: "Minha caixa de trabalho", href: "/m/pagamentos/caixa-de-trabalho", icon: Inbox,
          anyOf: ["pagamento_solicitar", "pagamento_gerir", "pagamento_validar",
                  "pagamento_autorizar", "pagamento_pagar"] },
        { label: "Minhas solicitações", href: "/m/pagamentos/solicitacoes", icon: ClipboardList,
          perm: "pagamento_solicitar" },
        // --- uma tela por etapa do rito ---
        { label: "Análise do gestor", href: "/m/pagamentos/gestor", icon: UserCheck,
          perm: "pagamento_gerir" },
        { label: "Validação financeira", href: "/m/pagamentos/validacao", icon: SearchCheck,
          perm: "pagamento_validar" },
        { label: "Autorização", href: "/m/pagamentos/autorizacao", icon: ShieldCheck,
          perm: "pagamento_autorizar" },
        { label: "Tesouraria", href: "/m/pagamentos/tesouraria", icon: Banknote,
          perm: "pagamento_pagar" },
        // --- transversais do módulo ---
        { label: "Conciliação", href: "/m/pagamentos/conciliacao", icon: Landmark,
          anyOf: ["pagamento_pagar", "pagamento_autorizar", "pagamento_auditar",
                  "pagamento_cadastro"] },
        { label: "Caixa", href: "/m/pagamentos/caixa", icon: Wallet, perm: "pagamento_cadastro" },
        { /* Cadastros — bloco inalterado */ },
      ],
```

`Dashboard` sai (funde em Visão geral) e `Contas a pagar` vira `Minhas solicitações`.

**A rota `/m/pagamentos/contas-a-pagar` precisa de 308 para `/m/pagamentos/solicitacoes`** em `next.config` (`redirects()`), porque `notificacao.link_url` já gravou URLs para ela e é registro permanente. `__tests__/rotas-modulo.test.ts` reprova prefixo em `ROTA_MODULO` sem regra em `redirects()`. **Conferir com `curl -I` antes de considerar pronto** — 308 é cache de navegador e destino errado não se conserta com redeploy.

Atualizar `PERMISSOES_ESPERADAS` em `frontend/__tests__/menus.test.tsx` com os itens novos.

- [ ] **Step 6: Rodar e type-check**

```
cd frontend && npx vitest run __tests__/pagamentos-situacoes.test.tsx __tests__/menus.test.tsx __tests__/rotas-modulo.test.ts
cd frontend && npx tsc --noEmit
```

Esperado: verde nos três, e `tsc` limpo. Se o `tsc` reclamar de rota apagada, apagar `.next/types/app/(app)/m/pagamentos/<rota-antiga>` — não é erro real.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/menus/pagamentos.ts frontend/next.config.* \
        frontend/components/pagamentos/situacoes.ts frontend/__tests__/
git commit -m "feat(pagamentos): tipos das tres dimensoes, menu por etapa do rito (F1, Tarefa 10)"
```

---

## Task 11: Frontend — stepper, situações e próxima ação

**Files:**
- Create: `frontend/components/pagamentos/EtapasFluxo.tsx`, `SituacoesDebito.tsx`, `ProximaAcao.tsx`
- Delete: `frontend/components/pagamentos/RitoPagamento.tsx`
- Modify: `frontend/app/(app)/m/pagamentos/contas-a-pagar/[id]/page.tsx`

**Interfaces:**
- Consumes: `situacoes.ts` e os tipos da Task 10.
- Produces:
  - `<EtapasFluxo tramitacao={...} />`
  - `<SituacoesDebito tramitacao fila pagamento posicaoFila? />`
  - `<ProximaAcao debito={...} perfil={...} />` — devolve a frase e as ações permitidas

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/__tests__/pagamentos-detalhe.test.tsx`:

```tsx
/**
 * O detalhe responde, sem o usuário abrir outra tela: em que etapa está, quem é
 * o responsável e qual é a próxima ação (spec §10.5 do pedido).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EtapasFluxo } from "@/components/pagamentos/EtapasFluxo";
import { ProximaAcao } from "@/components/pagamentos/ProximaAcao";
import { SituacoesDebito } from "@/components/pagamentos/SituacoesDebito";

describe("EtapasFluxo", () => {
  it("marca a etapa atual e as concluídas", () => {
    render(<EtapasFluxo tramitacao="AGUARDANDO_AUTORIDADE" />);
    const atual = screen.getByTestId("etapa-AUTORIDADE");
    expect(atual).toHaveAttribute("data-estado", "atual");
    expect(screen.getByTestId("etapa-GESTOR")).toHaveAttribute("data-estado", "concluida");
    expect(screen.getByTestId("etapa-TESOURARIA")).toHaveAttribute("data-estado", "futura");
  });

  it("distingue etapa com ajuste pendente", () => {
    render(<EtapasFluxo tramitacao="AJUSTE_VALIDACAO" />);
    expect(screen.getByTestId("etapa-UNIDADE")).toHaveAttribute("data-estado", "ajuste");
  });

  it("distingue etapa encerrada por decisão", () => {
    render(<EtapasFluxo tramitacao="REJEITADA_GESTOR" />);
    expect(screen.getByTestId("etapa-GESTOR")).toHaveAttribute("data-estado", "encerrada");
  });

  it("cada etapa tem texto, não só cor", () => {
    render(<EtapasFluxo tramitacao="AGUARDANDO_GESTOR" />);
    for (const nome of ["Unidade", "Gestor", "Validação", "Autoridade", "Tesouraria"]) {
      expect(screen.getByText(nome)).toBeInTheDocument();
    }
  });
});

describe("SituacoesDebito", () => {
  it("mostra as três dimensões em português", () => {
    render(<SituacoesDebito tramitacao="AUTORIZADA" fila="BLOQUEADA" pagamento="NAO_INICIADA" />);
    expect(screen.getByText("Autorizada para pagamento")).toBeInTheDocument();
    expect(screen.getByText("Bloqueada")).toBeInTheDocument();
    expect(screen.getByText("Não iniciado")).toBeInTheDocument();
  });
});

describe("ProximaAcao", () => {
  it("diz ao gestor, em uma frase, o que se espera dele", () => {
    render(<ProximaAcao tramitacao="AGUARDANDO_GESTOR" perfis={["pagamento_gerir"]} />);
    expect(screen.getByText(/aguarda sua análise/i)).toBeInTheDocument();
  });

  it("para quem não é o responsável, explica de quem se espera", () => {
    render(<ProximaAcao tramitacao="AGUARDANDO_GESTOR" perfis={["pagamento_solicitar"]} />);
    expect(screen.getByText(/gestor da pasta/i)).toBeInTheDocument();
  });

  it("não oferece rejeição na etapa de validação", () => {
    render(<ProximaAcao tramitacao="AGUARDANDO_VALIDACAO" perfis={["pagamento_validar"]} />);
    expect(screen.getByRole("button", { name: /validar conformidade/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /solicitar ajustes/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /rejeitar/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /não validar/i })).toBeNull();
  });

  it("oferece as três decisões ao gestor", () => {
    render(<ProximaAcao tramitacao="AGUARDANDO_GESTOR" perfis={["pagamento_gerir"]} />);
    for (const nome of [/autorizar solicitação/i, /solicitar ajustes/i, /rejeitar solicitação/i]) {
      expect(screen.getByRole("button", { name: nome })).toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
cd frontend && npx vitest run __tests__/pagamentos-detalhe.test.tsx
```

- [ ] **Step 3: Implementar os três componentes**

`EtapasFluxo.tsx` renderiza `ETAPAS` e resolve o estado de cada uma comparando índices contra `ETAPA_POR_TRAMITACAO[tramitacao]`, com `data-estado` ∈ `concluida | atual | futura | ajuste | encerrada`. Estado `ajuste` quando a tramitação começa com `AJUSTE_`; `encerrada` quando está em `REJEITADA_GESTOR | INDEFERIDA_AUTORIDADE | CANCELADA`. **Cada etapa carrega ícone e texto**, nunca só cor.

`SituacoesDebito.tsx` renderiza as três linhas rotuladas *Tramitação:*, *Ordem cronológica:*, *Pagamento:*, cada uma com o `Rotulo` correspondente.

`ProximaAcao.tsx` mapeia `(tramitacao, perfis)` para uma frase e uma lista de ações, com a primária destacada:

```ts
const ACOES_POR_ETAPA: Record<SituacaoTramitacao, {
  transacao: string | null;
  fraseResponsavel: string;   // quando o usuário É o responsável
  fraseTerceiro: string;      // quando não é
  acoes: { chave: string; label: string; primaria?: boolean; destrutiva?: boolean }[];
}> = {
  AGUARDANDO_GESTOR: {
    transacao: "pagamento_gerir",
    fraseResponsavel: "Esta solicitação aguarda sua análise como gestor da pasta.",
    fraseTerceiro: "Esta solicitação aguarda a análise do gestor da pasta.",
    acoes: [
      { chave: "gestor/autorizar", label: "Autorizar solicitação", primaria: true },
      { chave: "ajuste/solicitar", label: "Solicitar ajustes" },
      { chave: "gestor/rejeitar", label: "Rejeitar solicitação", destrutiva: true },
    ],
  },
  AGUARDANDO_VALIDACAO: {
    transacao: "pagamento_validar",
    fraseResponsavel: "Esta solicitação aguarda sua conferência de conformidade.",
    fraseTerceiro: "Esta solicitação aguarda a validação da unidade financeira.",
    // Duas ações, e é assim de propósito: esta etapa não encerra a solicitação
    // (spec §3.1). Acrescentar "Rejeitar" aqui contraria a regra central da F1.
    acoes: [
      { chave: "validar", label: "Validar conformidade", primaria: true },
      { chave: "ajuste/solicitar", label: "Solicitar ajustes" },
    ],
  },
  AGUARDANDO_AUTORIDADE: {
    transacao: "pagamento_autorizar",
    fraseResponsavel: "Esta solicitação aguarda sua aprovação e ordenação de pagamento.",
    fraseTerceiro: "Esta solicitação aguarda a autoridade competente.",
    acoes: [
      { chave: "autoridade/aprovar", label: "Aprovar e ordenar pagamento", primaria: true },
      { chave: "ajuste/solicitar", label: "Solicitar ajustes" },
      { chave: "autoridade/indeferir", label: "Não aprovar", destrutiva: true },
    ],
  },
  RASCUNHO: {
    transacao: "pagamento_solicitar",
    fraseResponsavel: "Rascunho. Complete os dados e envie para o gestor da pasta.",
    fraseTerceiro: "Esta solicitação ainda é um rascunho da unidade setorial.",
    acoes: [
      { chave: "enviar", label: "Enviar para o gestor", primaria: true },
      { chave: "cancelar", label: "Cancelar solicitação", destrutiva: true },
    ],
  },
  AJUSTE_GESTOR: {
    transacao: "pagamento_solicitar",
    fraseResponsavel: "O gestor da pasta pediu correções. Veja o motivo no histórico, corrija e reenvie.",
    fraseTerceiro: "Aguardando a unidade setorial responder ao ajuste pedido pelo gestor.",
    acoes: [
      { chave: "ajuste/responder", label: "Reenviar ao gestor", primaria: true },
      { chave: "cancelar", label: "Cancelar solicitação", destrutiva: true },
    ],
  },
  AJUSTE_VALIDACAO: {
    transacao: "pagamento_solicitar",
    fraseResponsavel: "A unidade financeira apontou inconformidade. Corrija e reenvie para nova validação.",
    fraseTerceiro: "Aguardando a unidade setorial responder ao ajuste pedido pela validação financeira.",
    acoes: [
      { chave: "ajuste/responder", label: "Reenviar para validação", primaria: true },
      { chave: "cancelar", label: "Cancelar solicitação", destrutiva: true },
    ],
  },
  AJUSTE_AUTORIDADE: {
    transacao: "pagamento_solicitar",
    fraseResponsavel: "A autoridade pediu correções. Corrija e reenvie para nova apreciação.",
    fraseTerceiro: "Aguardando a unidade setorial responder ao ajuste pedido pela autoridade.",
    acoes: [
      { chave: "ajuste/responder", label: "Reenviar à autoridade", primaria: true },
      { chave: "cancelar", label: "Cancelar solicitação", destrutiva: true },
    ],
  },
  AUTORIZADA: {
    // Sem transação responsável: a tramitação acabou. O que resta é execução,
    // e ela é governada pela fila (F3) e pela tesouraria (F4).
    transacao: null,
    fraseResponsavel: "Autorizada. O pagamento segue para a tesouraria conforme a ordem cronológica.",
    fraseTerceiro: "Autorizada. O pagamento segue para a tesouraria conforme a ordem cronológica.",
    acoes: [],
  },
  REJEITADA_GESTOR: {
    transacao: null,
    fraseResponsavel: "Rejeitada pelo gestor da pasta. O motivo está no histórico.",
    fraseTerceiro: "Rejeitada pelo gestor da pasta. O motivo está no histórico.",
    acoes: [],
  },
  INDEFERIDA_AUTORIDADE: {
    transacao: null,
    fraseResponsavel: "Indeferida pela autoridade competente. O motivo está no histórico.",
    fraseTerceiro: "Indeferida pela autoridade competente. O motivo está no histórico.",
    acoes: [],
  },
  CANCELADA: {
    transacao: null,
    fraseResponsavel: "Cancelada pela unidade solicitante. O motivo está no histórico.",
    fraseTerceiro: "Cancelada pela unidade solicitante. O motivo está no histórico.",
    acoes: [],
  },
};
```

O componente escolhe a frase comparando `transacao` com os `perfis` recebidos, e
só renderiza os botões quando o usuário tem a transação da etapa. Ação que o
perfil não pode executar é **ocultada**; o que aparece no lugar é a frase de
terceiro, que explica de quem se espera a ação — botão cinza sem motivo é pior
que botão ausente (spec §8 do pedido).

- [ ] **Step 4: Ligar no detalhe**

Em `frontend/app/(app)/m/pagamentos/contas-a-pagar/[id]/page.tsx` (725 linhas), acrescentar no topo do conteúdo, nesta ordem: cabeçalho resumido (número, fornecedor, valor, unidade, criação) → `<SituacoesDebito>` → `<EtapasFluxo>` → `<ProximaAcao>` → o corpo existente.

**Nesta task o corpo não é reorganizado em abas** — isso é F5. O que a F1 entrega é a resposta imediata a "onde estou e o que faço agora", no topo da página.

Trocar as chamadas de `api.pagamentos.aprovar/encaminhar` pelas novas, passando `lock_version` do débito carregado. No 409, **recarregar o débito e mostrar o estado novo** — nunca repetir a ação.

Apagar `RitoPagamento.tsx` e suas importações. Ele mostrava passos que não são as etapas do fluxo.

- [ ] **Step 5: Rodar e type-check**

```
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Esperado: verde e limpo. Se o servidor de dev estiver de pé segurando arquivos no Windows, matar pela porta antes de mover/apagar:
`Get-NetTCPConnection -LocalPort 3000 | ... | Stop-Process -Force`.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/pagamentos/ frontend/app/\(app\)/m/pagamentos/ frontend/__tests__/
git rm frontend/components/pagamentos/RitoPagamento.tsx
git commit -m "feat(pagamentos): stepper das cinco etapas, tres dimensoes e proxima acao no detalhe (F1, Tarefa 11)"
```

---

## Task 12: Telas de etapa

**Files:**
- Create: `frontend/components/pagamentos/ListaEtapa.tsx`, `frontend/app/(app)/m/pagamentos/gestor/page.tsx`, `frontend/app/(app)/m/pagamentos/validacao/page.tsx`
- Modify: `frontend/app/(app)/m/pagamentos/contas-a-pagar/page.tsx` → mover para `solicitacoes/`

**Interfaces:**
- Consumes: Tasks 10 e 11.
- Produces: `<ListaEtapa etapa={...} />`, consumido pelas quatro telas de etapa.

- [ ] **Step 1: Escrever o teste que falha**

Criar `frontend/__tests__/pagamentos-lista-etapa.test.tsx`:

```tsx
/**
 * A lista de uma etapa mostra só o que aquela etapa decide, e explica o vazio
 * em vez de exibir uma tabela em branco (spec §12 do pedido).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ListaEtapa } from "@/components/pagamentos/ListaEtapa";

const ITEM = {
  id: 41,
  nome_fornecedor: "Construtora Aurora Ltda",
  id_unidade: 3,
  nome_unidade: "Secretaria de Obras",
  valor_total: "148320.00",
  situacao_tramitacao: "AGUARDANDO_GESTOR" as const,
  situacao_fila: "NAO_REGISTRADA" as const,
  situacao_pagamento: "NAO_INICIADA" as const,
  atualizado_em: "2026-07-28T10:00:00",
  lock_version: 3,
};

describe("ListaEtapa", () => {
  it("mostra o essencial de cada item", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[ITEM]} carregando={false} erro={null} />);
    expect(screen.getByText("Construtora Aurora Ltda")).toBeInTheDocument();
    expect(screen.getByText("Secretaria de Obras")).toBeInTheDocument();
    expect(screen.getByText(/148\.320,00/)).toBeInTheDocument();
  });

  it("mostra há quanto tempo o item aguarda", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[ITEM]} carregando={false} erro={null} />);
    expect(screen.getByTestId("tempo-aguardando-41")).toHaveTextContent(/dia|hora/i);
  });

  it("mostra a próxima ação esperada, não o enum", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[ITEM]} carregando={false} erro={null} />);
    expect(screen.queryByText("AGUARDANDO_GESTOR")).toBeNull();
    expect(screen.getByText(/analisar/i)).toBeInTheDocument();
  });

  it("explica o estado vazio em vez de mostrar tabela em branco", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[]} carregando={false} erro={null} />);
    expect(screen.getByText(/nenhuma solicitação aguarda/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("no erro, diz o que aconteceu e o que fazer", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[]} carregando={false}
                       erro="Falha de rede" />);
    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent(/não foi possível carregar/i);
    expect(screen.getByRole("button", { name: /tentar novamente/i })).toBeInTheDocument();
  });

  it("carregando mostra skeleton, não tabela vazia", () => {
    render(<ListaEtapa etapa="GESTOR" itens={[]} carregando erro={null} />);
    expect(screen.getByTestId("lista-etapa-skeleton")).toBeInTheDocument();
    expect(screen.queryByText(/nenhuma solicitação aguarda/i)).toBeNull();
  });

  it("a coluna de posição na fila fica vazia até a F3, sem quebrar", () => {
    render(<ListaEtapa etapa="AUTORIDADE" itens={[
      { ...ITEM, situacao_tramitacao: "AGUARDANDO_AUTORIDADE" as const },
    ]} carregando={false} erro={null} />);
    expect(screen.getByTestId("posicao-fila-41")).toHaveTextContent("—");
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
cd frontend && npx vitest run __tests__/pagamentos-lista-etapa.test.tsx
```

- [ ] **Step 3: Implementar `ListaEtapa`**

Componente único parametrizado por etapa, com colunas próprias por etapa. Quatro cópias divergiriam — é a mesma razão pela qual `canSeeItem` é compartilhado entre Sidebar e Ctrl+K.

Colunas comuns: número, fornecedor, unidade, valor, tempo aguardando, próxima ação. A de validação acrescenta situação do checklist; a de autoridade, líquido e posição na fila (posição chega vazia até a F3 — exibir "—", não erro).

- [ ] **Step 4: Criar as duas telas novas e mover a lista**

`gestor/page.tsx` e `validacao/page.tsx` são casca fina sobre `ListaEtapa`. `autorizacao/page.tsx` e `tesouraria/page.tsx` já existem e ficam como estão nesta fatia.

Mover `contas-a-pagar/page.tsx` → `solicitacoes/page.tsx` com `git mv`, ajustando os `href`. **O detalhe continua em `contas-a-pagar/[id]/`** nesta fatia: mover a rota de detalhe exigiria mais um 308 e mexeria em `notificacao.link_url`. Fica para a F5, junto com a limpeza.

Toda tela nova precisa de link chegando até ela no **mesmo PR** — a guarda de página órfã de `__tests__/rotas-modulo.test.ts` reprova o contrário. Os links vêm do menu (Task 10).

- [ ] **Step 5: Rodar tudo**

```
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Esperado: verde, com `rotas-modulo.test.ts` passando (sem órfã, sem chave órfã em `KEYWORDS_POR_HREF`).

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(pagamentos): telas de etapa do gestor e da validacao (F1, Tarefa 12)"
```

---

## Task 13: Verificação final da fatia

- [ ] **Step 1: Suíte completa do backend, em segundo plano**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q
```

Esperado: `2 failed / N passed` com as duas conhecidas. Registrar N.

- [ ] **Step 2: Suíte sob o papel restrito**

```
docker exec -e PYTEST_DB_HOST=db \
  -e DATABASE_URL=postgresql+asyncpg://aprimora_app:ged_password_secure_local@db:5432/ged_saas_db \
  aprimora-py-backend pytest -q
```

Esperado: resultado idêntico ao anterior.

- [ ] **Step 3: Frontend**

```
cd frontend && npm test
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Migration reversível**

```
docker exec aprimora-py-backend alembic downgrade -1
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic heads
```

- [ ] **Step 5: Percorrer o fluxo como cada perfil**

Subir pelo `:8090` (nunca `:3100` — devolve 404 no login) e percorrer: criar rascunho → enviar → gestor autoriza → validação valida → autoridade aprova. Depois o caminho de ajuste em cada etapa. Conferir que a tela de validação **não tem botão de rejeitar**.

- [ ] **Step 6: Atualizar a documentação**

- `docs/BACKLOG-PENDENCIAS.md` — entrada da F1: o que entrou, o que ficou para F2–F5, e o volume medido no Step 1 da Task 2.
- `CLAUDE.md` — seção do módulo de pagamentos: as três dimensões, a regra da validação sem rejeição, o `status` legado derivado e a guarda que o protege.

- [ ] **Step 7: Commit final**

```bash
git add -A
git commit -m "docs(pagamentos): fecha a F1 no backlog e registra as tres dimensoes no CLAUDE.md"
```

---

## Fora do escopo desta fatia

Pedidos de ajuste como entidade, versionamento, invalidação de aprovações (F2) · ordem cronológica, bloqueios, exceção autorizada (F3) · lote de pagamento, retenções, reprocesso (F4) · visão geral com indicadores, caixa de trabalho, abas do detalhe, remoção da coluna `status` (F5).
