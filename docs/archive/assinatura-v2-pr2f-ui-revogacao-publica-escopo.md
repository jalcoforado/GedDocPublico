# PR 2f — Escopo Implementável: UI interna de gestão da validação pública

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Permitir que usuários autorizados **gerenciem pela interface interna** a
> validação pública da assinatura (ver código/URL/QR, copiar, revogar), sem
> depender de chamada técnica/manual ao endpoint. O núcleo backend já existe
> (PR2e); este PR é majoritariamente **frontend** + uma pequena extensão de
> contrato. **Nada será implementado até autorização.**

---

## 0. O que já existe (PR2e) — reaproveitar

- `codigo_validacao` em `assinatura_anexo` + exposto em `EvidenciasOut`.
- Endpoint **revogação manual** (autenticado, guard de sigilo, audit_log):
  `POST /api/v2/assinaturas/{id}/revogar-validacao-publica` (body `{motivo}`),
  evento `assinatura.validacao_publica_revogada`.
- `config.validacao_publica_url(slug, codigo)` + comprovante interno já imprime
  código + QR + URL.
- Endpoint público neutro + `validacaoPublicaComprovanteUrl(codigo)` no front.

> Logo: **não** reescrever serviço/endpoint de revogação nem auditoria — já
> prontos e testados. PR2f só **expõe na UI** e **adiciona o status/URL** no
> contrato de evidências.

## 1. Backend — extensão mínima do contrato de evidências

`EvidenciasOut` ganha 2 campos (aditivos, opcionais):

- `validacao_publica_url: str | None` — URL pública (quando houver código).
- `validacao_publica_status: str` — um de:
  | status | quando |
  |---|---|
  | `ativa` | código presente, com hash, status `assinada`, processo **ostensivo** agora, não revogada, anexo não desentranhado |
  | `revogada` | `validacao_publica_revogada = true` |
  | `bloqueada_sigilo` | processo **não-ostensivo** no estado atual |
  | `indisponivel` | anexo desentranhado ou assinatura não-`assinada` |
  | `nao_aplicavel` | sem `codigo_validacao` ou sem `documento_hash` (legado) |

- `consultar_evidencias` passa a receber `tenant_slug` (para montar a URL) e a
  ler `nivel_sigilo` (Processo) + `desentranhado_em` (AnexoProcesso) +
  `validacao_publica_revogada/codigo_validacao/documento_hash` (já na linha) para
  derivar o status. A **regra de derivação espelha os gates de
  `validar_publico`** (fonte única de verdade — extrair um helper puro
  `status_validacao_publica(...)` em `services/validacao_publica.py` e reusar
  nos dois lugares).
- O endpoint `GET /assinaturas/{id}/evidencias` já enforce sigilo
  (`assert_acesso_processo` → 404): **quem não tem acesso não vê nada** (nem
  código nem URL). Sem mudança aqui além de passar o `tenant_slug`.

> **Decisão:** estender `EvidenciasOut` (1 chamada para a UI) em vez de criar
> endpoint novo — a UI já vai buscar evidências para montar o painel.

## 2. Frontend — exibição do código/URL/QR/status

Componente novo (ex.: `components/ValidacaoPublicaCard.tsx`) renderizado por
**anexo assinado** dentro de `AssinaturasProcesso` (hoje cada anexo assinado tem
`ValidarAcao`). Carrega via `api.assinaturas.evidencias(aaId)`. Exibe:

- **Status** (badge): Ativa / Revogada / Indisponível / Não aplicável /
  Bloqueada por sigilo (mapa de label/intent em helper puro testável —
  `statusValidacaoPublica` em `lib/assinatura.ts`).
- **Código** de validação pública (monoespaçado).
- **URL pública** de validação.
- **QR Code**: reaproveitar o do **comprovante** (link "ver comprovante", que já
  embute o QR). *Se* houver caminho leve sem dependência nova, renderizar inline;
  senão, fica só o link do comprovante (decisão: QR inline é opcional).
- **Aviso** (texto verbatim):
  > "Este código permite validar publicamente a assinatura, mas a página pública
  > exibe apenas dados minimizados. Não compartilhe se o processo não puder ser
  > consultado publicamente."

Só mostra código/URL quando `status` ∈ {`ativa`, `revogada`} (há código). Em
`bloqueada_sigilo`/`indisponivel`/`nao_aplicavel`, exibe só o status explicativo,
**sem** vazar código/URL.

## 3. Frontend — copiar

Ações de copiar (`navigator.clipboard.writeText`) para **código** e **URL**, com
feedback simples ("copiado") via toast já existente. Fallback silencioso se a
clipboard API não estiver disponível.

## 4. Frontend — revogação manual

Botão **"Revogar validação pública"** (só quando `status === "ativa"`), gated por
`useAuth().can("processo", "atualizar")` (mesma permissão do endpoint). Fluxo:

- **Confirmação explícita** (componente `useConfirm`, intent `danger`) com texto:
  explica que, após revogada, a validação pública passa a retornar **resposta
  neutra**; que **não** apaga a assinatura, **não** apaga evidências internas e
  **não** invalida o hash interno — apenas revoga o acesso público por token.
- Campo **motivo opcional** (input simples, sem fluxo de aprovação).
- Chama `api.assinaturas.revogarValidacaoPublica(aaId, motivo?)` →
  `POST .../revogar-validacao-publica`. Em sucesso: invalida a query de
  evidências (status vira `revogada`) + toast.

## 5. Frontend — API client

- `api.assinaturas.revogarValidacaoPublica(aaId: number, motivo?: string)`.
- `EvidenciasAssinatura` += `validacao_publica_url?: string | null` +
  `validacao_publica_status?: string`.

## 6. Permissão / sigilo (resumo das garantias)

- **Não exibir** código/URL para quem não tem acesso ao processo: o endpoint de
  evidências já retorna **404** por sigilo (a UI nem recebe os dados).
- **Revogar** exige `processo:atualizar` (front esconde o botão; back valida).
- Processo deixou de ser ostensivo → `status = bloqueada_sigilo`: UI indica
  "indisponível/bloqueada por sigilo" e **não** mostra código/URL.

## 7. Arquivos prováveis

**Backend**
- `schemas/assinatura.py` — `EvidenciasOut` += 2 campos.
- `services/validacao_publica.py` — helper puro `status_validacao_publica(...)`.
- `services/assinaturas.py` — `consultar_evidencias` recebe `tenant_slug`,
  deriva status + URL.
- `routers/assinaturas.py` — passa `tenant_slug` ao `consultar_evidencias`
  (endpoint de evidências + comprovante já têm o slug).

**Frontend**
- `lib/api.ts` — método `revogarValidacaoPublica` + campos no tipo.
- `lib/assinatura.ts` — helper puro `statusValidacaoPublica` (label/intent).
- `components/ValidacaoPublicaCard.tsx` (novo) + integração em
  `components/AssinaturasProcesso.tsx`.

**Testes**
- `backend/tests/test_validacao_publica.py` (ou novo) + `frontend` (vitest).

## 8. Testes obrigatórios

**Backend (pytest)**
1. evidências de assinatura ativa ostensiva → `status="ativa"` + `url` presente.
2. após revogar → `status="revogada"`; e endpoint público retorna **neutro**
   (reaproveita o fluxo PR2e).
3. processo sigiloso → evidências negadas por sigilo (404) **e** (super-usuário/
   com acesso) `status="bloqueada_sigilo"` sem expor a validação pública.
4. assinatura legada (sem hash/código) → `status="nao_aplicavel"`, sem URL.
5. revogação gera `audit_log` `assinatura.validacao_publica_revogada` (já no PR2e;
   re-assertar no fluxo).

**Frontend (vitest + RTL)**
6. helper `statusValidacaoPublica` mapeia os 5 status (label/intent).
7. usuário autorizado (status ativa) vê código + URL; botão revogar visível.
8. usuário **sem** `processo:atualizar` → **não** vê botão revogar.
9. status `bloqueada_sigilo`/`nao_aplicavel` → **não** renderiza código/URL.
10. clicar revogar chama `api.assinaturas.revogarValidacaoPublica` (mockado) após
    confirmação.
11. copiar URL/código chama `navigator.clipboard.writeText` (mockado) + feedback.

**E2E** (opcional, leve): evidências expõem `validacao_publica_url`/`status`;
revogar → público neutro (boa parte já coberta no spec do PR2e).

## 9. Critérios de aceite

- Usuário autorizado vê **código + URL + status + aviso** na UI interna; QR via
  comprovante.
- Copiar código/URL funciona com feedback.
- Revogar exige confirmação, chama o endpoint, gera audit_log e muda o status
  para `revogada`; depois o público responde **neutro**.
- Revogação **não** apaga assinatura/evidências nem invalida o hash interno.
- Usuário sem acesso/permissão **não** vê código/URL nem botão de revogar.
- Processo não-ostensivo → UI indica bloqueio por sigilo, sem expor a validação.
- Sem regressão; pytest + vitest verdes.

## 10. Fora de escopo

Busca pública por número de processo; download público do documento; exposição
pública de evidências internas; gov.br; ICP-Brasil; carimbo de tempo externo;
assinatura qualificada; hash chain de audit_log; **workflow de aprovação para
revogação**; nova regra jurídica da assinatura; alterações no modelo probatório
já implementado.

## 11. Riscos / notas

- **QR inline**: se exigir dependência nova no front, **adiar** — usar o QR do
  comprovante (link). Decisão registrada no §2.
- **Derivação de status duplicada**: mitigado extraindo helper puro único
  (`status_validacao_publica`) reusado por `validar_publico` e
  `consultar_evidencias` — evita divergência de regra.
- **`consultar_evidencias` ganha `tenant_slug`**: ajustar os 2 callers + testes
  que a chamam (mudança de assinatura controlada).

---

> **Parar aqui.** Escopo fechado, nada implementado. Aguardando autorização
> explícita para iniciar (ordem sugerida: contrato de evidências → API client →
> componente UI → revogação/confirm → testes).
