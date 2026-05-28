# Assinatura v2 — Proposta Técnica (PR 2)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** proposta (nenhum código de produção alterado)

> Evoluir a assinatura interna de "senha-MD5 sem prova de integridade" para uma
> **assinatura eletrônica interna com valor probatório**: baseada em evidências,
> integridade documental (hash) e trilha de auditoria. **Fora do PR 2:** gov.br,
> ICP-Brasil, assinatura qualificada e carimbo de tempo externo. A arquitetura é
> desenhada para evoluir até lá sem reescrita.

Base legal de referência: **Lei 14.063/2020** (assinaturas eletrônicas no setor
público — define simples/avançada/qualificada) e **Lei 11.419/2006** (valor
probatório do documento eletrônico, exige integridade/autenticidade).

---

## 0. Ponto de partida (estado atual, pós-PR1)

Tabelas (schema `protocolos`, todas com RLS via migration 0006):
- `solicitacao_assinatura` — cabeçalho (processo + solicitante).
- `usuario_assinatura` — cada signatário da solicitação (`ordem`, `realizada`).
- `assinatura_anexo` — par (signatário × anexo); onde `assinado` é registrado.
  Colunas hoje: `id, tenant_id, id_usuario_assinatura, id_anexo, assinado,
  dt_assinatura, id_usuario, id_processo, ativo, excluido`.
- `tipo_assinatura` — catálogo genérico.

Serviço (`services/assinaturas.py`): `solicitar_assinatura`, `assinar(senha)`
(usa `verify_md5(senha, usuario.senha)`), `cancelar_solicitacao`, queries.
Auditoria (PR1): `assinatura.solicitada/assinada/cancelada`.

Autenticação disponível (`auth/password.py`):
`verify_password(plain, *, bcrypt_hash, md5_hash) -> (ok, needs_rehash)` —
**bcrypt primeiro, MD5 como fallback** sinalizando rehash. É a peça que permite
tirar o MD5 do fluxo novo.

Armazenamento: arquivo em disco por tenant; `config.resolve_anexo_path(slug, e_doc)`
resolve o caminho. **Nenhum hash de documento é guardado hoje.**

---

## 1. Modelo conceitual da Assinatura v2

### Assinatura **simples** (entregue no PR 2)
Ato de assinar **autenticado** (re-autenticação por senha **bcrypt**), que:
- identifica o signatário (user_id + tenant_id + unidade);
- vincula a vontade ao **conteúdo exato** do documento via **hash SHA-256** dos
  bytes do anexo no instante da assinatura;
- coleta **evidências** (IP, user agent, data/hora do servidor, método de
  autenticação, nível);
- gera **trilha de auditoria** imutável (append-only) ligada ao ato.

Atende ao conceito de assinatura eletrônica **simples** da Lei 14.063/2020
(identifica o signatário e associa dados ao documento).

### Evolução para **avançada** (gancho no PR 2, plena no PR 3)
Avançada (art. 4º, II) exige: associação unívoca ao signatário, **dados de
criação sob controle exclusivo** do signatário, e detecção de alteração
posterior. O PR 2 já entrega **detecção de alteração** (hash) e **associação ao
signatário** (evidências + autenticação). O "controle exclusivo" pleno exige
**par de chaves por usuário** (assinatura criptográfica do hash com chave
privada do usuário) — fica como **PR 3**. O schema reserva `nivel_assinatura`
e `evidencias` (JSONB) para plugar isso sem migração disruptiva.

### Fora de escopo (exige gov.br/ICP-Brasil)
- Assinatura **qualificada** (certificado ICP-Brasil / e-CPF).
- Integração **gov.br** (SSO / assinatura na nuvem).
- **Carimbo de tempo** de Autoridade de Carimbo de Tempo (ACT) credenciada — o
  PR 2 usa apenas o **timestamp do servidor** (não-credenciado), explicitamente.

### Evidências coletadas (por ato de assinatura)
hash do documento + algoritmo; versão do documento; dt_assinatura (servidor);
IP; user agent; tenant_id; user_id; processo + anexo; método de autenticação;
nível; status; e um `evidencias` JSONB para extensões (ex.: fuso, request_id).

### Como provar integridade
No ato: `documento_hash = SHA-256(bytes do arquivo resolvido)`. Na **validação**:
recomputa o hash do arquivo atual e compara com o gravado. Igual → íntegro para
aquela versão; diferente → **documento alterado após a assinatura** (assinatura
inválida para o conteúdo atual).

### Compatibilidade com o legado
Assinaturas antigas (`assinado=true`, sem hash) **coexistem**, marcadas como
`nivel_assinatura='legado'` e `metodo_autenticacao='senha_md5_legado'`. **Não há
hash retroativo** (não dá pra provar o conteúdo do passado). A validação dessas
retorna explicitamente "legado — sem prova de integridade". Nada é apagado nem
re-assinado automaticamente.

---

## 2. Alterações de banco de dados (proposta — migration `0020`)

**Decisão:** estender `assinatura_anexo` (1 linha por ato; relação 1:1 com a
evidência) + `evidencias` JSONB para extensibilidade. **Não criar tabela
separada de evidências** (seria 1:1, overhead sem ganho). A *trilha* de eventos
fica no `audit_log` (já existe), não numa tabela nova.

### `protocolos.assinatura_anexo` — colunas novas
```text
documento_hash         VARCHAR(64)  NULL      -- SHA-256 hex no ato
hash_algoritmo         VARCHAR(20)  NULL DEFAULT 'sha256'
documento_versao       INTEGER      NULL      -- ver §9 (decisão: sem GED de versão)
ip                     VARCHAR(64)  NULL
user_agent             VARCHAR(512) NULL
metodo_autenticacao    VARCHAR(30)  NULL      -- 'senha_bcrypt'|'senha_md5_legado'
nivel_assinatura       VARCHAR(20)  NOT NULL DEFAULT 'simples'
                         CHECK IN ('legado','simples','avancada')
status                 VARCHAR(20)  NOT NULL DEFAULT 'pendente'
                         CHECK IN ('pendente','assinada','recusada','cancelada')
motivo                 VARCHAR(1000) NULL     -- recusa/cancelamento
evidencias             JSONB        NULL
id_audit_log           BIGINT       NULL FK aprimora_py.audit_log(id)
```
`dt_assinatura`, `tenant_id`, `id_usuario`, `id_processo`, `id_anexo` já existem.
`assinado` (bool) é **mantido** por compatibilidade e tratado como legado/derivado
de `status='assinada'`.

**Backfill (não-disruptivo):**
```text
nivel_assinatura     = 'legado'
metodo_autenticacao  = 'senha_md5_legado'
status               = CASE WHEN assinado THEN 'assinada' ELSE 'pendente' END
```

### `protocolos.usuario_assinatura` — colunas novas (recusa por signatário)
```text
status        VARCHAR(20) NOT NULL DEFAULT 'pendente'
                CHECK IN ('pendente','realizada','recusada')
motivo_recusa VARCHAR(1000) NULL
dt_recusa     TIMESTAMP     NULL
```
`realizada` (bool) mantido; backfill `status = CASE WHEN realizada THEN
'realizada' ELSE 'pendente'`.

### RLS / grants
As 3 tabelas já têm policies tenant-scoped (0006). Colunas novas não exigem
policy nova. `id_audit_log` aponta para `aprimora_py.audit_log` (mesma tenant).
Índice sugerido: `(tenant_id, status)` em `assinatura_anexo` para filtros.

---

## 3. Compatibilidade com o modelo atual

| Item | Decisão |
|---|---|
| Tabelas reaproveitadas | `solicitacao_assinatura`, `usuario_assinatura`, `assinatura_anexo`, `tipo_assinatura` — **todas**. |
| Campos adicionados | §2 (em `assinatura_anexo` e `usuario_assinatura`). |
| Nova tabela de evidências | **Não.** JSONB `evidencias` + `audit_log` cobrem. |
| Assinaturas antigas | Coexistência. `nivel='legado'`, sem hash. Validação informa "sem prova de integridade". |
| Migração de dados | Apenas **backfill de defaults** (status/nivel/metodo). Sem reprocessamento. |
| Não quebrar o frontend | Mudanças **aditivas** nos schemas de saída (`SolicitacaoOut`/`AssinaturaAnexoStatus` ganham `status`, `nivel`, `tem_hash`). Tipos TS atuais continuam válidos; UI exibe os novos campos quando presentes. |

---

## 4. Fluxos funcionais

1. **Solicitar assinatura** — inalterado no essencial; cria solicitação +
   `usuario_assinatura` + `assinatura_anexo` (status `pendente`).
2. **Visualizar antes de assinar** — já existe (`anexoInlineUrl`); a tela de
   assinatura mostra o hash que **será** calculado (preview) e os anexos.
3. **Assinar** — re-autentica com **bcrypt** (`verify_password`); calcula
   `SHA-256` dos bytes do anexo; grava hash + evidências + `status='assinada'`;
   audita; vincula `id_audit_log`. Idempotente (não re-assina `assinada`).
4. **Recusar** (novo) — signatário recusa sua `usuario_assinatura` com motivo;
   propaga `status='recusada'` nas `assinatura_anexo` dele; audita.
5. **Cancelar** — solicitante cancela a solicitação inteira (já existe); reflete
   `status='cancelada'`; audita.
6. **Validar** (novo) — recomputa hash do arquivo atual e compara; retorna
   `{integro: bool, motivo, nivel, legado: bool}`.
7. **Consultar evidências** (novo) — retorna o pacote de evidências de uma
   assinatura (hash, algoritmo, dt, ip, ua, metodo, nivel, status, audit ref).
8. **Comprovante** (novo) — PDF com: identificação do processo/anexo, lista de
   signatários + dt + hash + nível + status, resultado da validação, aviso de
   "assinatura eletrônica simples interna (não ICP-Brasil)".

---

## 5. Auditoria

| Evento | acao | Quando | Commit |
|---|---|---|---|
| Solicitação criada | `assinatura.solicitada` | já no PR1 | transação principal |
| Assinatura concluída | `assinatura.assinada` | já no PR1 (enriquecer payload c/ hash) | transação principal |
| Recusa | `assinatura.recusada` | novo | transação principal |
| Cancelamento | `assinatura.cancelada` | já no PR1 | transação principal |
| **Tentativa malsucedida** | `assinatura.tentativa_falha` | novo | **commit próprio** |
| Validação | `assinatura.validada` | novo (opcional) | transação própria |
| Alteração de status | coberto pelos eventos acima | — | — |

**Tentativa malsucedida — commit próprio:** o `assinar` levanta erro **antes**
do commit, então o `audit_log` da falha seria revertido junto. Proposta: capturar
a falha de autenticação, gravar a auditoria numa **sessão/transação separada**,
e re-levantar o erro.

**Evitar poluição por força bruta:** *throttle* da auditoria de falha — registrar
no máximo 1 evento por `(tenant_id, id_usuario, id_assinatura_anexo)` a cada N
segundos (contador em Redis, que já temos), e mandar as demais só para o log
estruturado/Sentry. Complementa o rate-limit do nginx no login. **Decisão humana:**
janela do throttle e se bloqueia a assinatura após X tentativas.

---

## 6. Segurança

- **MD5 fora do fluxo novo:** `assinar` passa a usar `verify_password(senha,
  bcrypt_hash=u.senha_bcrypt, md5_hash=u.senha)`. Se bater em bcrypt →
  `metodo='senha_bcrypt'`. Se só houver MD5 (`needs_rehash`) → autentica, **grava
  `senha_bcrypt` na hora** (rehash transparente) e registra
  `metodo='senha_md5_legado'` naquele ato. Assinaturas novas deixam de **depender**
  de MD5. **Decisão humana:** permitir assinar via MD5-fallback (com rehash) ou
  exigir troca de senha antes da 1ª assinatura v2.
- **Hash sobre o conteúdo correto:** ler os **bytes do arquivo resolvido**
  (`resolve_anexo_path`) no ato; nunca confiar em metadado. Tratar arquivo ausente
  como erro de assinatura.
- **Documento mudar após assinatura:** a validação detecta (hash diverge). Além
  disso, **bloquear substituição de anexo assinado**: anexo com assinatura
  `assinada` não pode ser desentranhado/substituído sem fluxo explícito.
  **Decisão humana:** bloquear de vez vs. versionar (depende de GED de versão — §9).
- **Replay:** assinatura é **one-shot** por `assinatura_anexo` (`status` impede
  re-assinar); ação autenticada + CSRF/JWT já existentes; sem novo token de uso
  único no PR 2 (avaliar no PR 3 se necessário).
- **Permissão:** só o `id_assinante` designado assina (já enforce). Endpoints sob
  `require_permission("processo","atualizar")`. Leitura de evidências/validação
  **respeita sigilo** (reusar o guard de acesso por nível já criado).
- **Isolamento multi-tenant:** todas as queries por `tenant_id` + RLS.

---

## 7. API e frontend

### Endpoints
| Método | Rota | Estado |
|---|---|---|
| POST | `/processos/{id}/solicitacoes-assinatura` | existe |
| POST | `/assinaturas/{aa_id}/assinar` | **ajustar** — receber `Request` (IP/UA) + evidências |
| POST | `/assinaturas/{aa_id}/recusar` | **novo** |
| POST | `/solicitacoes-assinatura/{id}/cancelar` | existe |
| GET | `/assinaturas/{aa_id}/validar` | **novo** |
| GET | `/assinaturas/{aa_id}/evidencias` | **novo** |
| GET | `/assinaturas/{aa_id}/comprovante.pdf` | **novo** |

### Arquivos provavelmente alterados
- Backend: `alembic/versions/0020_*.py` (novo), `models/assinatura.py`,
  `schemas/assinatura.py`, `services/assinaturas.py`, `routers/assinaturas.py`,
  novo helper de hash (em `services/anexos.py` ou `services/assinatura_hash.py`),
  novo `services/pdf_comprovante_assinatura.py`, `services/audit.py` (sem mudança;
  só uso). Possível: guard em `services/anexos.py`/`desentranhamento.py` para
  bloquear anexo assinado.
- Frontend: `lib/api.ts` (novos métodos/tipos), `components/AssinaturasProcesso.tsx`
  (status/nível/validar/comprovante), `app/(app)/para-assinar/page.tsx` (recusar),
  possível nova tela de evidências/validação.

---

## 8. Testes obrigatórios

1. hash do documento é registrado no ato (`documento_hash` populado, `sha256`).
2. alteração posterior do arquivo → `validar` retorna `integro=false`.
3. assinar gera `audit_log` (`assinatura.assinada`) com hash no payload.
4. recusar gera `audit_log` (`assinatura.recusada`) + `usuario_assinatura.status='recusada'`.
5. cancelar gera `audit_log` (`assinatura.cancelada`).
6. tentativa malsucedida: erro retornado, **audit em commit próprio**, throttle respeitado.
7. usuário sem ser o `id_assinante` designado não assina (403/erro).
8. assinatura de **outro tenant** é bloqueada (RLS) — reusar padrão de `test_rls_isolation`.
9. compatibilidade: assinatura legado (`nivel='legado'`, sem hash) não quebra
   listagem nem `validar` (retorna "sem prova de integridade").
10. MD5-fallback faz **rehash** para bcrypt e marca `metodo='senha_md5_legado'`.

---

## 9. Escopo do PR 2

### Obrigatório
- Migration 0020 (campos de hash/evidência/status/nível + recusa) + backfill.
- `assinar` v2: bcrypt (`verify_password` + rehash), hash SHA-256 do conteúdo,
  evidências (IP/UA/metodo/nível), `status`, vínculo `id_audit_log`.
- Fluxo **recusar** + **validar** + **consultar evidências**.
- Auditoria de recusa + **tentativa malsucedida (commit próprio + throttle)**.
- Comprovante PDF de assinatura.
- Compatibilidade legado (coexistência, sem hash retroativo).
- Testes do §8.

### Desejável (pode ir para PR 3)
- **Bloqueio robusto** de edição de anexo assinado / versionamento real (depende de GED).
- Endpoint **público** de validação por código (terceiros validarem).
- Comprovante avançado (QR + link de validação).
- Tela dedicada de evidências/validação no frontend.

### Fora de escopo
- gov.br, ICP-Brasil, assinatura **qualificada**, **carimbo de tempo externo**,
  **assinatura criptográfica com par de chaves do usuário** (avançada plena),
  **hash chain** do audit_log.

### Riscos que exigem decisão humana
1. **Usuários só-MD5:** permitir assinar via fallback (com rehash) ou exigir troca de senha antes?
2. **Anexo assinado:** bloquear edição de vez **ou** versionar (precisa GED de versão)?
3. **`documento_versao`:** sem GED de versionamento, definir como `1` fixo, ou
   derivar de um marcador? (proposta: `1` até existir versionamento real).
4. **Throttle de tentativa falha:** janela/limite e se bloqueia após X falhas.
5. **Auditar validação** (`assinatura.validada`) sempre, ou só on-demand (custo/volume)?

---

## 10. Recomendação de execução

Quebrar o PR 2 em **dois sub-PRs** para revisão segura:
- **PR 2a — Integridade + evidências + auditoria:** migration, `assinar` v2 (hash,
  bcrypt, evidências, status), recusar, validar, auditoria (incl. falha), testes.
  É o núcleo de valor probatório.
- **PR 2b — Comprovante + UI:** PDF de comprovante, ajustes de frontend
  (status/nível/recusar/validar), tela de evidências.

> **Parar aqui.** Nenhum código de produção foi alterado. Aguardando sua
> autorização (e as decisões dos itens 1–5 do §9) antes de implementar.
