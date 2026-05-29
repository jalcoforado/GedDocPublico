# PR 4b — Escopo Implementável: Abertura de protocolo por serviço

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](servicos-pr4b-abertura-por-servico-escopo.md) com as **6
> decisões (D-A…D-F)** fechadas. Torna o portal de serviços (PR 4a) um **fluxo
> real** de abertura, **autenticado** e usando os **defaults** do serviço.
> **Nada será alterado em código até autorização explícita.**

---

## 1. Objetivo

Cidadão **logado** abre um protocolo a partir de um serviço **ativo e bem
configurado** do portal; o backend aplica os defaults do serviço (unidade,
assunto, espécie, sigilo, canal) — o cidadão **não** escolhe classificação. Vínculo
`processo.id_servico` para rastreabilidade futura.

**Decisões fechadas:** D-A autenticado (reusa fluxo cidadão) · D-B `id_servico` no
`processo` · D-C obrigatórios = assunto + unidade + canal `portal` + ativo (**sem
fallback** de unidade) · D-D anexos só pós-abertura (endpoint existente) · D-E
espécie opcional · D-F auditoria minimizada.

## 2. Migration `0025_processo_id_servico`

- `op.add_column("processo", Column("id_servico", Integer, ForeignKey("protocolos.servico.id"), nullable=True), schema="protocolos")`.
- `op.create_index("ix_processo_tenant_servico", "processo", ["tenant_id", "id_servico"], schema="protocolos")`.
- `processo` já tem RLS (0006) e GRANTs por schema — coluna nova herda; **sem**
  novas policies, **sem** nova transação de permissão (fluxo público/cidadão).
- Compatibilidade: processos existentes ficam `id_servico = NULL` (a maioria; é o
  estado normal de protocolo não originado de serviço).
- `downgrade`: drop index + drop column.
- Modelo `Processo`: `id_servico: Mapped[int | None] = mapped_column(ForeignKey("protocolos.servico.id"), nullable=True)`.

CI (`stamp 0020 → upgrade head`) roda a 0025 em banco limpo. Validar round-trip.

## 3. Backend

### 3.1 Refactor mínimo (DRY, sem mudar o legado)
Extrair de `services/cidadao_processos.py::abrir_processo_cidadao` helpers internos
reusados pelos **dois** fluxos (legado e por serviço), preservando o comportamento atual:
- `_checar_rate_limit(db, cpf, tenant_id)` — 5/24h canal `portal`.
- `_resolver_ou_criar_manifestante(db, cidadao, tenant_id)` — manifestante por CPF.
- `_gerar_numero(db)` — `protocolos.gerar_numero_processo_string()`.
- `_criar_movimentacao_abertura(db, processo, unidade_id, tenant_id, now)` — ABERTURA.
- `_aplicar_nup(db, processo, tenant_id, now)` — NUP opt-in.

### 3.2 `abrir_processo_por_servico(db, cidadao, servico, payload, *, tenant_id) -> Processo`
- Pré-condições (já validadas ao resolver o serviço — §3.3): serviço ativo/não
  excluído, `canal_entrada_permitido == 'portal'`, `id_assunto_padrao` e
  `id_unidade_responsavel` preenchidos.
- Valida **same-tenant**: assunto (`id_assunto_padrao`, ativo, do tenant), unidade
  (`id_unidade_responsavel`, não excluída, do tenant); espécie (`id_especie_documental_padrao`,
  se setada, válida/do tenant — senão abre sem espécie, D-E).
- `id_tipo_processo_padrao`: o tipo do processo deriva do assunto (FK
  `assunto.id_tipo_processo`); se o serviço tiver `id_tipo_processo_padrao` e ele
  **divergir** do tipo do assunto, registra log técnico (incoerência de
  configuração) mas **não** bloqueia — coluna de tipo não existe no `processo`.
- Cria `Processo` com: `id_assunto = servico.id_assunto_padrao`,
  `id_unidade_proprietaria = id_local_atual = servico.id_unidade_responsavel`,
  `id_especie_documental = servico.id_especie_documental_padrao`,
  `nivel_sigilo = servico.nivel_sigilo_padrao`, `canal_entrada = 'portal'`,
  `id_servico = servico.id`, `corpo = payload.corpo`, `observacao = payload.observacao`,
  `externo = True`, `virtual = True`, `data_recepcao = now`, `id_usuario = None`.
- Reusa rate-limit, manifestante, número, movimentação ABERTURA, NUP, auto-CCD.
- Auditoria minimizada (§7) na mesma transação.

### 3.3 Resolver serviço solicitável — `obter_servico_solicitavel(db, *, tenant_id, slug)`
- `servico` por `slug + tenant_id`, `ativo = true`, `excluido = false` → senão
  **404 neutro** ("Serviço não encontrado").
- Se encontrado mas **não solicitável** (`canal != 'portal'` OU sem
  `id_assunto_padrao` OU sem `id_unidade_responsavel`) → **409** com mensagem
  neutra ao cidadão ("Solicitação online indisponível para este serviço") **+ log
  técnico** ao operador com o motivo (não cria processo).

## 4. Endpoint

`POST /api/v2/cidadao/servicos/{slug}/abrir` — em `routers/cidadao.py`.
- Deps: `get_current_cidadao` + `require_tenant_id` (cookie `aprimora_cidadao_token`).
- Body `AbrirPorServicoRequest { corpo: str (min_length=10), observacao: str | None }`.
  **Não** aceita `tenant_id`, nem unidade/assunto/tipo/espécie/sigilo (campos
  inexistentes no schema → impossível sobrescrever).
- Resolve via `obter_servico_solicitavel` (erros controlados §3.3); chama
  `abrir_processo_por_servico`; retorna `ProcessoCidadaoDetail` (mesma resposta de
  `POST /cidadao/processos`, reusa `get_meu_detail`) → frontend mostra comprovante.

## 5. Portal público — `solicitar_habilitado` calculado + `texto_confirmacao`

Em `services/servico.py::_to_public` (hoje `solicitar_habilitado=False` fixo):
```
solicitar_habilitado = (
    servico.canal_entrada_permitido == "portal"
    and servico.id_assunto_padrao is not None
    and servico.id_unidade_responsavel is not None
)
```
(`ativo/não excluído` já garantidos por `listar_publico`/`obter_publico`.)

Adicionar `texto_confirmacao: str | None` ao **`ServicoPublicOut`** — é mensagem
voltada ao cidadão (segura); usada na confirmação/tela final. Continua **sem**
expor ids internos, `nivel_sigilo_padrao`, `canal_entrada_permitido`, `ativo`,
`excluido`.

## 6. Frontend (cidadão)

- **`cidadao/servicos/[slug]/page.tsx`** *(novo, público)* — detalhe via
  `portalApi.servico(slug)`: descrição, instruções, **documentos exigidos
  (orientação)**, prazo, unidade. Botão **"Solicitar serviço"** quando
  `solicitar_habilitado`; senão desabilitado "Solicitação indisponível".
- **`cidadao/servicos/[slug]/solicitar/page.tsx`** *(novo, exige login)* — form
  simples: descrição (`corpo`, mín. 10) + observação opcional; reexibe documentos;
  **passo de confirmação** (mostra `texto_confirmacao` se houver) → `POST .../abrir`
  → redireciona para `/cidadao/processos/[id]` (comprovante existente). Sem login →
  fluxo de login do portal (padrão `/cidadao/*`).
- **`cidadao/servicos/page.tsx`** (lista, PR 4a): botão linka para
  `/cidadao/servicos/{slug}` quando `solicitar_habilitado`; senão desabilitado.
- `lib/api.ts`: `portalApi.abrirPorServico(slug, { corpo, observacao })`
  (request com cookie de cidadão; reusa o helper `requestCidadao`).

## 7. Auditoria (minimizada — D-F)

`services/audit.log`: `acao="processo.aberto_por_servico"`, `entidade="processo"`,
`id_entidade=<id_processo>`, `id_usuario=None`,
`payload={ "id_servico", "canal": "portal", "origem": "servico" }`
(`tenant_id` e `timestamp` já são colunas do `audit_log`).
**Não** registra CPF, nome, e-mail, `corpo`, anexos ou qualquer dado pessoal.

## 8. Segurança

- Tenant pelo **Host** (`require_tenant_id`); `tenant_id` **nunca** do payload.
- Serviço resolvido dentro do tenant; outro tenant → **404 neutro** (sem cross-tenant).
- Inativo/excluído → 404; canal ≠ `portal` ou mal configurado → 409 controlado +
  log; **não cria processo**.
- Cidadão **não** escolhe unidade/assunto/tipo/espécie/sigilo (ausentes no schema).
- Defaults internos não expostos (projeção pública segura; `texto_confirmacao` é
  citizen-facing por design).
- **Rate-limit** 5/24h por CPF (canal `portal`) reusado.
- `nivel_sigilo` vem do serviço — cidadão não altera.

## 9. Testes obrigatórios

**Backend (pytest):**
- abre por serviço ativo+configurado → processo com defaults (assunto/unidade/
  espécie/sigilo) e **`id_servico` setado**.
- serviço **inativo/excluído** → recusado (404), sem processo.
- serviço de **outro tenant** → 404.
- `canal != 'portal'` → recusado (409).
- **sem `id_assunto_padrao`** → recusado (409), sem processo.
- **sem `id_unidade_responsavel`** → recusado (409), sem processo (**sem fallback**).
- defaults aplicados corretamente (assunto/unidade/tipo-coerência/espécie/sigilo).
- payload **não** sobrescreve unidade/assunto/tipo/sigilo.
- **rate-limit** continua funcionando (6ª abertura/24h → erro controlado).
- auditoria `processo.aberto_por_servico` registrada, **sem dados pessoais**.
- processos antigos com `id_servico = NULL` continuam válidos (listagem/detalhe).
- migration 0025 aplica em banco limpo; round-trip.

**Frontend (vitest):**
- serviço habilitado → botão "Solicitar serviço"; indisponível → desabilitado.
- detalhe exibe documentos exigidos como orientação.
- form de solicitação envia (`abrirPorServico`) e navega para o comprovante.

## 10. Fora de escopo

abertura anônima · formulário dinâmico por serviço · upload obrigatório dentro da
abertura · validação automática de documentos · pendência/complementação (→ PR 4c)
· SLA completo · workflow builder · avaliação do serviço · gov.br · pagamento/taxa
· e-mail · WhatsApp · **dashboard por serviço** · busca avançada · categorias
complexas · importação em massa.

## 11. Critérios de aceite

- Migration 0025 (`processo.id_servico` + índice) aplicada/testada; round-trip OK;
  processos antigos intactos.
- Abertura por serviço autenticada, aplica defaults server-side, grava `id_servico`,
  reusa rate-limit/movimentação/NUP.
- Solicitável só com assunto + unidade + canal `portal` + ativo (**sem fallback**);
  mal configurado → 409 controlado + log, sem criar processo.
- `solicitar_habilitado` calculado; botão público aponta para o fluxo real;
  inativo continua oculto.
- Cidadão não sobrescreve classificação; tenant pelo Host; cross-tenant 404.
- Auditoria minimizada (sem dados pessoais).
- Anexos só pós-abertura via endpoint existente (sem upload no form).
- Testes backend + frontend passando; sem regressão.
- Relatório final: arquivos, testes, riscos, próximos passos (gancho p/ PR 4c —
  complementação documental — e dashboard por serviço).

## 12. Dívida técnica / notas

- `id_tipo_processo_padrao` do serviço é validado por coerência (vs tipo do
  assunto) mas não persistido no `processo` (tipo vem do assunto) — telemetria.
- Anexos obrigatórios, validação e pendência documental ficam para o **PR 4c**.
- `processo.id_servico` habilita o **dashboard por serviço** (PR futuro) — fora daqui.
