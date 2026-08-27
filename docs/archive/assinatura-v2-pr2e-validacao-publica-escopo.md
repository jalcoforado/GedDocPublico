# PR 2e — Escopo Implementável: Validação Pública de Assinatura (código/token)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Permitir que um terceiro **sem login** valide a autenticidade/integridade de
> uma assinatura via um **código público**, sem expor conteúdo do documento nem
> metadados sensíveis, e sem vazar a existência de processos sigilosos.
>
> A proposta técnica foi aprovada e as **decisões humanas (§16) estão fechadas**
> abaixo. Este documento define o que será implementado. **Nada será alterado em
> código até autorização explícita.**

---

## 1. Decisões fechadas (resolvem o §16 da proposta)

| # | Decisão | Resolução |
|---|---|---|
| 1 | Nome do servidor signatário | **Exibir nome completo**, sem máscara, apenas para ostensivo + validável. Minimização aplicada (ver §6). |
| 2 | Número do processo | **Exibir apenas se ostensivo**; sigiloso/restrito → resposta neutra indistinguível. |
| 3 | Token | **Perpétuo por padrão**, opaco, ≥128 bits, não-enumerável, armazenado, revogável. Campo `validacao_expira_em` nullable previsto, mas **sem expiração** na regra inicial. |
| 4 | QR Code | **Incluir.** reportlab tem QR nativo (`reportlab.graphics.barcode.qr`) — **sem nova dependência**. Aponta para a URL pública. (Se algo crescer inesperadamente, vira pendência PR 2f.) |

## 2. Modelo de dados — migration `0021_validacao_publica_assinatura`

Colunas novas em `aprimora_py.assinatura_anexo`:

| Coluna | Tipo | Notas |
|---|---|---|
| `codigo_validacao` | `text` | **único**, índice; gerado por `secrets.token_urlsafe(16)` (~22 chars, 128 bits). |
| `validacao_publica_revogada` | `boolean` not null default `false` | revogação **manual**. |
| `validacao_revogada_motivo` | `text` null | |
| `validacao_revogada_em` | `timestamptz` null | |
| `validacao_revogada_por` | `bigint` null | FK lógica p/ `utils.usuario`. |
| `validacao_expira_em` | `timestamptz` null | reservado; **sem uso na regra inicial** (sempre null). |

- Índice **único** em `codigo_validacao` (global, cross-tenant — o token é a chave de
  lookup pública).
- **Backfill** das linhas já assinadas: a própria migration roda um passo Python
  (Alembic) gerando `codigo_validacao` com o **mesmo gerador** (`secrets.token_urlsafe`)
  para cada `assinatura_anexo` existente sem código. Idempotente.

## 3. Geração e revogação de token

- **Geração:** no ato da assinatura, em `services/assinaturas.assinar` (mesmo ponto
  que já grava hash/evidências). `codigo_validacao = secrets.token_urlsafe(16)`.
- **Revogação manual:** seta `validacao_publica_revogada=true` (+ motivo/quem/quando).
  Endpoint/serviço interno autenticado (reusar guard de sigilo). *Mínimo necessário:*
  função de serviço `revogar_validacao_publica(...)`; UI de revogação pode ficar para
  depois (não bloqueia este PR).
- **Revogação automática = avaliação LAZY no momento da consulta** (não há triggers
  eager espalhados pelo código). A cada validação pública o serviço re-checa o estado
  **atual** e responde neutro se qualquer condição falhar:
  - assinatura não está mais `assinada` (recusada/cancelada);
  - anexo desentranhado/removido;
  - processo **não é mais ostensivo** (re-check via `services/sigilo`);
  - `validacao_publica_revogada=true`.
  > Isso atende as condições de revogação automática da decisão 3 **sem** tocar nos
  > fluxos de recusar/cancelar/desentranhar/sigilo — diff pequeno e correto por
  > construção (o estado é sempre lido na hora).

## 4. Endpoint público (anônimo, sem tenant)

Rotas montadas **sem dependência de auth** e **sem contexto de tenant**, sob prefixo
dedicado `/publico/` (facilita o `limit_req` do nginx):

- `GET /publico/validacao/{codigo}` → JSON (matriz §7).
- `GET /publico/validacao/{codigo}/comprovante.pdf` → PDF público (§8).

**Lookup sem RLS (ponto técnico crítico):** sem JWT não há `app.tenant_id`, então
a busca por `codigo_validacao` precisa rodar numa sessão/role **não sujeita a RLS**
(o token é a credencial). Fluxo: localizar a linha pelo token (lookup global) →
derivar `tenant_id` da linha → **re-avaliar sigilo** com aquele tenant via
`services/sigilo`. *A implementação deve verificar se a role de runtime do app sofre
RLS e, se sim, prover um bypass restrito só a este lookup por token.* (Ver §16.)

## 5. Visibilidade / sigilo

- **Só** assinaturas de processo **ostensivo** são validáveis publicamente.
- `interno/reservado/secreto/ultrassecreto` → **resposta neutra**, idêntica à de
  token inexistente/revogado. Re-checagem do nível **atual** a cada request.

## 6. Minimização (LGPD) — o que exibir × ocultar

**Exibir** (ostensivo + válido + não-revogado):
- nome **completo** do servidor signatário;
- data/hora da assinatura;
- status da validação;
- hash SHA-256 + algoritmo;
- versão do documento;
- número do processo (se ostensivo);
- aviso "assinatura eletrônica interna com evidências — não é ICP-Brasil".

**Nunca exibir:** CPF, matrícula, e-mail, IP, user agent, método interno de
autenticação, evidências técnicas detalhadas, dados do cidadão/manifestante, dados
pessoais sensíveis, conteúdo do documento/anexo.

## 7. Matriz de respostas (endpoint JSON)

| Caso | Resposta |
|---|---|
| Ostensivo, válido, íntegro | `200 {valido:true, integro:true, signatario, assinado_em, hash, algoritmo, versao_documento, processo_numero?, nivel:"simples", aviso}` |
| Ostensivo, válido, **hash diverge** | `200 {valido:true, integro:false, detalhe:"documento alterado após a assinatura"}` *(sem metadados sensíveis)* |
| Inexistente | `404 {valido:false}` (neutro) |
| Revogado (manual ou lazy) | **mesma** resposta neutra que inexistente |
| Sigiloso / não-ostensivo | **mesma** resposta neutra que inexistente |

> *inexistente / revogado / sigiloso* são **indistinguíveis**. Apenas
> ostensivo-não-revogado confirma existência (válido íntegro **ou** hash-divergente).

## 8. Comprovante público × interno

- **Público** (este PR, por token, anônimo): só o mínimo probatório (signatário,
  data, hash, algoritmo, versão, resultado, processo se ostensivo, aviso) **+ QR/URL
  pública**. Oculta IP/UA/método/evidências.
- **Interno** (PR2b, autenticado, com guard de sigilo): mantém metadados completos.
- São **dois geradores distintos** (ou um gerador com modo `publico=True` que omite
  os blocos sensíveis). **QR via reportlab nativo**, apontando para
  `{PUBLIC_BASE_URL}/validar/{codigo}` — nova config `PUBLIC_BASE_URL`.

## 9. Rate-limit

- **nginx** `limit_req` no path `/publico/` (defesa dura, ex.: 20/min/IP).
- **App (Redis)** como defesa em profundidade, por IP (reusar o padrão fail-open de
  `assinatura_throttle.py` num novo `validacao_publica_throttle.py`). Bloqueio
  temporário após excesso.

## 10. Auditoria (controlada)

- Validação **válida**: 1 evento `acao="assinatura.validada_publica"`, payload
  `{resultado, integro, ip}` + referência ao `assinatura_anexo`.
- Token **inválido/neutro**: **agregado** (contador Redis), **não** 1 linha por
  tentativa — evita inundar o audit sob enumeração. Flush periódico/limiar.

## 11. Frontend (página pública)

- Rota **fora** do grupo autenticado `(app)`: `app/validar/[codigo]/page.tsx`
  (consome a API pública) + `app/validar/page.tsx` (form de entrada manual do código).
- **Não** importar layout/nav autenticado. Estados: válido-íntegro, válido-hash-
  divergente, neutro (não encontrado/indisponível). Sem dados sensíveis.
- Código + QR impressos no comprovante (interno e público).

## 12. Arquivos a criar / alterar

**Backend**
- `alembic/versions/0021_validacao_publica_assinatura.py` (NOVO) — colunas + índice
  único + backfill.
- `services/assinaturas.py` — gerar `codigo_validacao` no `assinar`;
  `validar_publico(codigo)` (lazy re-check + minimização); `revogar_validacao_publica(...)`.
- `services/validacao_publica_throttle.py` (NOVO) — rate-limit por IP (Redis fail-open).
- `routers/validacao_publica.py` (NOVO) — router público sem auth (`/publico/...`),
  com lookup sem RLS.
- `services/pdf_comprovante_assinatura.py` — modo público (omite IP/UA/método/
  evidências) + QR (reportlab nativo).
- `schemas/` — schema da resposta pública (campos minimizados).
- `core/config` — `PUBLIC_BASE_URL`.
- registro do router no app + verificação de que middleware de tenant/RLS libera
  `/publico/`.

**Infra**
- `nginx` conf — `limit_req` no path `/publico/`.

**Frontend**
- `app/validar/[codigo]/page.tsx`, `app/validar/page.tsx` (NOVOS) — públicas.
- `lib/api.ts` — client da validação pública (sem token de auth).

**Docs**
- atualizar `docs/assinatura-v2-operacao.md` (seção validação pública).

## 13. Sequência de implementação

1. Migration 0021 (+ backfill) + colunas no modelo.
2. `assinar` gera `codigo_validacao`; serviço `validar_publico` (lazy re-check + minimização) com testes unitários.
3. `validacao_publica_throttle` + auditoria agregada.
4. Router público `/publico/...` (lookup sem RLS) + matriz de respostas; verificar middleware.
5. Comprovante público + QR + `PUBLIC_BASE_URL`.
6. nginx `limit_req`.
7. Frontend páginas públicas + código/QR no comprovante.
8. Testes (§15) + atualizar operação.

## 14. Critérios de aceite

- Endpoint público valida por código **sem autenticação**.
- Token opaco, ≥128 bits, não enumerável; respostas **neutras** para
  inexistente/sigiloso/revogado (não vazam existência).
- **Processo sigiloso nunca é validável publicamente**; ostensivo→sigiloso deixa de validar.
- Resposta/comprovante público **não** expõem CPF, matrícula, e-mail, IP, UA, método,
  evidências nem dados do cidadão.
- Revogação funciona (manual + lazy por mudança de estado).
- Rate-limit ativo no path público; auditoria pública controlada (não inunda).
- Comprovante público distinto do interno; QR aponta para a URL pública.
- Sem regressão; testes verdes (backend + frontend + e2e).

## 15. Testes obrigatórios

1. token válido (ostensivo, íntegro) → `valido:true, integro:true`.
2. token inexistente → resposta neutra (404).
3. token revogado (manual) → resposta neutra.
4. processo sigiloso → resposta neutra.
5. processo era ostensivo e virou sigiloso → deixa de validar (lazy).
6. hash divergente → `integro:false` **sem** metadados sensíveis.
7. resposta pública **não contém** IP/UA/e-mail/CPF/matrícula/dados do cidadão.
8. rate-limit dispara após o limite.
9. auditoria pública não inunda sob abuso (agregação de inválidos).
10. comprovante público gerado **sem** evidências internas.
11. QR aponta para `{PUBLIC_BASE_URL}/validar/{codigo}`.

## 16. Riscos / decisões técnicas a confirmar na implementação

- **RLS no lookup público:** confirmar se a role de runtime sofre RLS; se sim,
  implementar bypass **restrito** só ao lookup por token (jamais ampliar acesso).
- **Backfill:** gerar token para linhas já assinadas na migration (idempotente).
- **`PUBLIC_BASE_URL`:** definir default seguro (dev) e documentar para produção.
- **nginx no CI:** o e2e leve do PR2d **não** sobe nginx; o teste de rate-limit do
  app (Redis) é coberto no pytest; o `limit_req` do nginx fica validado no compose
  local (não no CI leve).

## 17. Fora de escopo

gov.br, ICP-Brasil, carimbo de tempo externo, assinatura qualificada, hash chain de
audit_log, versionamento completo de GED, **download público do conteúdo do
documento**, exibição pública de evidências internas, **busca pública por número de
processo**, validação pública de processo sigiloso, validação pública com autenticação
gov.br.

---

> **Parar aqui.** Escopo fechado, nada implementado. Aguardando autorização explícita
> para iniciar a implementação na ordem do §13.
