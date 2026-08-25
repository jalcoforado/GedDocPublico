# PR 4b — Escopo técnico: Abertura de protocolo por serviço

**Autor:** Jorge + assistente · **Status:** PROPOSTA (aguardando autorização — nada implementado)

> Transforma a vitrine do PR 4a em **fluxo real**: o cidadão abre um protocolo a
> partir de um serviço ativo do portal, usando os **defaults** do serviço. Funcional
> mas controlado — **sem** formulário dinâmico, upload obrigatório avançado,
> complementação documental ou SLA. Gerar primeiro este doc; **não implementar**.

---

## 1. Objetivo

Permitir abertura de solicitação/protocolo a partir de um `protocolos.servico`
ativo, aplicando server-side os defaults configurados (unidade, tipo, assunto,
espécie, sigilo, canal). O cidadão **não** escolhe esses campos — só descreve o
pedido.

## 2. Achados no código (o que será reusado, não recriado)

| Necessidade | Já existe | Decisão |
|---|---|---|
| Abertura pública de processo | [`services/cidadao_processos.py`](../backend/app/services/cidadao_processos.py) → `abrir_processo_cidadao` (autenticado, manifestante por CPF, rate-limit 5/24h `portal`, número via `protocolos.gerar_numero_processo_string()`, movimentação `ABERTURA`, NUP opt-in) | **Reusar o núcleo** — extrair helper comum |
| Endpoint cidadão | [`routers/cidadao.py`](../backend/app/routers/cidadao.py) (`POST /cidadao/processos`, cookie `aprimora_cidadao_token`, `get_current_cidadao` + `require_tenant_id`) | **Novo endpoint** irmão `POST /cidadao/servicos/{slug}/abrir` |
| Detalhe público do serviço | `GET /portal/servicos/{slug}` (PR 4a) já existe | **Reusar** na página de detalhe |
| Projeção pública | `ServicoPublicOut.solicitar_habilitado` (hoje **constante `false`**) | **Calcular** (§5) |
| Comprovante/visualização | Página `/cidadao/processos/[id]` + `ProcessoCidadaoDetail` já existem | **Reusar** como tela final |
| Anexos do cidadão | `POST /cidadao/processos/{id}/anexos` já existe | **Reusar** opcionalmente pós-abertura (D-D) |
| Auditoria | [`services/audit.py`](../backend/app/services/audit.py) `log()` (payload JSONB, `id_usuario` nullable) | **Reusar** com payload minimizado (§7) |
| RLS em `processo` | já habilitada (migration 0006) | nova coluna herda RLS |

**`protocolos.processo` NÃO tem `id_servico`.** Última migration = `0024` → **nova = `0025`**.
`nivel_sigilo` é a fonte da verdade (coluna `publico` é `Computed`); `canal_entrada` é varchar.

## 3. Modelo — migration `0025_processo_id_servico`

- `ALTER TABLE protocolos.processo ADD COLUMN id_servico integer NULL
  REFERENCES protocolos.servico(id)` (FK nullable; **soft-link** — não bloqueia
  processos sem serviço, que continuam sendo a maioria).
- Índice `ix_processo_tenant_servico (tenant_id, id_servico)` — rastreabilidade
  p/ dashboard por serviço (PR futuro).
- `processo` já tem RLS; nada a fazer em policies. GRANTs idem (coluna nova herda).
- **Sem** nova transação de permissão (fluxo é público/cidadão, não RBAC interno).
- Modelo `Processo`: adicionar `id_servico: Mapped[int | None]`.

> Decisão D-B (vínculo): **coluna `id_servico` no `processo`** — preferida pela
> rastreabilidade direta (filtro/contagem por serviço no dashboard). Sem tabela
> intermediária nem metadados.

## 4. Fluxo de abertura por serviço

### 4.1 Backend — `services/servico_abertura.py` (novo) + reuso
- **Refactor mínimo:** extrair de `abrir_processo_cidadao` os blocos reusáveis
  (rate-limit, resolver/criar manifestante por CPF, gerar número, criar
  `ABERTURA`, NUP) para helpers internos; `abrir_processo_cidadao` e o novo
  `abrir_processo_por_servico` chamam os mesmos helpers. Mantém o fluxo legado
  estável.
- `abrir_processo_por_servico(db, cidadao, servico, payload, *, tenant_id)`:
  - **defaults do serviço** (cidadão não escolhe):
    `id_assunto = servico.id_assunto_padrao`;
    unidade = `servico.id_unidade_responsavel` (ou 1ª unidade ativa — fallback, D-C);
    `id_especie_documental = servico.id_especie_documental_padrao` (se setado/válido);
    `nivel_sigilo = servico.nivel_sigilo_padrao`; `canal_entrada = 'portal'`;
    `id_servico = servico.id`.
  - `payload` (cidadão) = **só** `corpo` (descrição) e `observacao?`. Não há
    campos de assunto/unidade/tipo/sigilo no schema → impossível sobrescrever.
  - reaproveita rate-limit 5/24h (`canal_entrada='portal'`) — compartilhado com o
    fluxo atual.
  - `tipo_processo`: derivado do assunto (FK `assunto.id_tipo_processo`); o
    `id_tipo_processo_padrao` do serviço serve para **validação/coerência** (se
    setado, deve bater com o do assunto) e telemetria — não há coluna de tipo no
    `processo` (o tipo vem via assunto).

### 4.2 Endpoint
`POST /api/v2/cidadao/servicos/{slug}/abrir` — `get_current_cidadao` +
`require_tenant_id`. Body `AbrirPorServicoRequest { corpo: str, observacao?: str }`.
Resolve o serviço por **slug no tenant do Host**; valida (§6); aplica defaults;
cria processo; retorna `ProcessoCidadaoDetail` (frontend mostra o comprovante).

### 4.3 Frontend
- **`cidadao/servicos/[slug]/page.tsx`** *(novo, público)* — detalhe do serviço
  (consome `portalApi.servico(slug)`): instruções, documentos exigidos (orientação),
  prazo, unidade. Botão **"Solicitar serviço"** quando `solicitar_habilitado`;
  senão "Solicitação indisponível".
- **`cidadao/servicos/[slug]/solicitar/page.tsx`** *(novo, exige login)* — form
  simples: descrição (`corpo`) + observação opcional; reexibe instruções e
  documentos; **passo de confirmação** antes do envio; on submit → `POST .../abrir`
  → redireciona para `/cidadao/processos/[id]` (comprovante existente). Sem login →
  fluxo de login do portal (padrão das telas `/cidadao/*`).
- **`cidadao/servicos/page.tsx`** (lista, PR 4a): botão passa a **linkar** para o
  detalhe quando `solicitar_habilitado`; senão permanece desabilitado.
- `lib/api.ts`: `portalApi.abrirPorServico(slug, { corpo, observacao })`
  (request com cookie de cidadão).

## 5. Portal público — `solicitar_habilitado` calculado

Em `_to_public` (PR 4a, hoje `False` fixo): calcular
`solicitar_habilitado = (servico.canal_entrada_permitido == 'portal') and
(servico.id_assunto_padrao is not None)`.

- Serviço **ativo e bem configurado** (canal portal + assunto padrão) → `true`,
  botão real.
- Serviço **ativo mas mal configurado** (sem assunto padrão ou canal ≠ portal) →
  aparece, mas `false` ("Solicitação indisponível") — mais seguro que esconder.
- Serviço **inativo/excluído** → continua **fora** da listagem pública (PR 4a).

## 6. Segurança

- Tenant pelo **Host** (`require_tenant_id`); `tenant_id` **nunca** do payload.
- Serviço resolvido **dentro do tenant** (slug + `tenant_id`): serviço de outro
  tenant → **404** (sem cross-tenant).
- Recusa abertura (erro **controlado** ao cidadão + **log técnico** ao operador):
  serviço inexistente/inativo/excluído (404); `canal_entrada_permitido != 'portal'`
  (400/409); default obrigatório ausente (assunto) → "serviço temporariamente
  indisponível" (409) + log `servico mal configurado`.
- Cidadão **não** escolhe unidade/assunto/tipo/espécie/sigilo (não estão no
  schema do request).
- Defaults internos **não** expostos (a projeção pública do PR 4a já é segura;
  o endpoint de abertura não retorna defaults internos).
- **Rate-limit**: reusa o limite 5/24h por CPF (canal `portal`) já existente.
- **`nivel_sigilo`** vem do serviço; o cidadão não eleva/rebaixa sigilo.

## 7. Auditoria (minimizada)

`audit_log` (reuso de `services/audit.log`): `acao="processo.aberto_por_servico"`,
`entidade="processo"`, `id_entidade=<id_processo>`, `id_usuario=None` (cidadão é
`UsuarioExterno`), `payload={ "id_servico", "canal": "portal" }`.
**Não** registrar CPF, nome, e-mail ou corpo (dados pessoais minimizados).

## 8. Testes obrigatórios

**Backend (pytest):**
- cidadão abre por serviço ativo → processo criado com os defaults do serviço
  (assunto/unidade/espécie/sigilo) e `id_servico` setado.
- serviço **inativo/excluído** → erro controlado (não cria processo).
- serviço de **outro tenant** → 404 (sem cross-tenant).
- serviço com `canal_entrada_permitido != 'portal'` → recusado.
- payload **não** consegue sobrescrever unidade/assunto/tipo/sigilo (campos
  inexistentes no schema; processo reflete só os defaults do serviço).
- serviço **mal configurado** (sem `id_assunto_padrao`) → erro controlado 409.
- `solicitar_habilitado` = `true` quando canal portal + assunto padrão; `false`
  quando mal configurado.
- evento de auditoria `processo.aberto_por_servico` registrado, sem dados pessoais.
- migration 0025 aplica em banco limpo (`stamp 0020 → upgrade head`); round-trip.

**Frontend (vitest):**
- detalhe público exibe instruções + documentos como orientação.
- botão "Solicitar serviço" habilitado quando `solicitar_habilitado`, desabilitado
  quando não.
- fluxo de solicitação (form → confirmação → submit) chama `abrirPorServico` e
  navega para o comprovante.

## 9. Decisões abertas (para o Jorge confirmar antes de implementar)

- **D-A — Autenticação:** abertura **autenticada** reusando o fluxo cidadão atual
  (login/cadastro + manifestante por CPF). *Recomendado* (item 2 do brief implica
  isso; evita capturar manifestante anônimo + antispam do zero). Alternativa
  (anônimo) abriria escopo — fora.
- **D-B — Vínculo:** coluna **`id_servico` no `processo`** (recomendado, melhor p/
  dashboard). OK?
- **D-C — Defaults obrigatórios:** obrigatório = `id_assunto_padrao` (sem ele →
  erro controlado). Unidade: usa `id_unidade_responsavel`; se nulo, **fallback** p/
  1ª unidade ativa (recomendado, mantém robusto). Ou exigir unidade também?
- **D-D — Anexos:** *Recomendado* permitir anexo **opcional pós-abertura** via
  endpoint existente (`/cidadao/processos/{id}/anexos`), sem upload no próprio form
  do 4b. Ou deixar anexos totalmente fora do 4b.
- **D-E — Espécie:** usar `id_especie_documental_padrao` do serviço; se nulo, abre
  sem espécie (não exige). OK?
- **D-F — Auditoria:** incluir evento minimizado (§7). *Recomendado* sim.

## 10. Fora de escopo

formulário dinâmico por serviço · upload documental obrigatório avançado ·
validação automática de documentos · pendência/complementação documental · SLA
operacional completo · workflow builder · avaliação do serviço · gov.br ·
pagamento/taxa · protocolo por e-mail · WhatsApp · **dashboard por serviço** ·
busca avançada · categorias complexas · importação em massa.

## 11. Critérios de aceite

- Migration 0025 (`processo.id_servico`) aplicada/testada; round-trip OK.
- Abertura por serviço aplica defaults server-side; `id_servico` registrado.
- Cidadão não sobrescreve unidade/assunto/tipo/sigilo; tenant pelo Host;
  cross-tenant 404; mal configurado → erro controlado + log.
- `solicitar_habilitado` calculado; botão público aponta para o fluxo real;
  inativo continua oculto.
- Auditoria minimizada registrada.
- Testes backend + frontend passando; sem regressão.
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos, testes, riscos, próximos passos (gancho p/ dashboard
  por serviço).
