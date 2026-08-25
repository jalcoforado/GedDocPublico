# PR 2a — Escopo Definitivo (Assinatura v2: núcleo probatório)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** escopo fechado (não implementado)

> Consolida a [proposta técnica](assinatura-v2-proposta-tecnica.md) com as
> decisões do Jorge. PR 2a = **núcleo de valor probatório** (integridade +
> evidências + autenticação forte + recusa + validação + proteção do conteúdo
> assinado + throttle + auditoria). **Comprovante PDF, UI rica e validação
> pública ficam para o PR 2b.** gov.br/ICP-Brasil/qualificada/carimbo externo
> permanecem fora.

## Decisões aplicadas (do Jorge)
1. **Sem fallback MD5 para assinar.** Usuário só-MD5 pode logar (regra atual),
   mas **não assina**; ao tentar, bloqueio + mensagem orientando atualizar a senha.
2. **Documento assinado é imutável (versionamento).** Versão assinada não pode
   ser sobrescrita; alteração gera nova versão (novo hash) que **não herda** a
   assinatura. No PR 2a: **proteção mínima** (bloquear sobrescrita de conteúdo
   assinado); versionamento completo de GED fica registrado como limitação.
3. **`documento_versao = 1`** fixo enquanto não há GED de versão, mas o campo e a
   lógica já existem no schema desde agora.
4. **Throttle:** 5 tentativas falhas / janela 15 min / escopo `(tenant_id,
   user_id, anexo)`; ao exceder, bloqueia novas tentativas por 15 min. Registro
   controlado (sem poluir o audit_log). **Redis** (já é dependência do projeto).
5. **Auditoria de validação só on-demand** (clique em "validar", download de
   comprovante de validação, endpoint formal). Visualização não é auditada.

---

## 1. Objetivo do PR 2a
Toda **assinatura nova** passa a:
- ser autenticada por **bcrypt** (MD5 bloqueado para o ato de assinar);
- gravar **hash SHA-256** dos bytes do documento + algoritmo + `documento_versao`;
- coletar **evidências** (IP, user agent, dt servidor, método, nível, status);
- ter **status** (`pendente/assinada/recusada/cancelada`) e fluxo de **recusa**;
- ser **validável** (recomputa hash atual vs. gravado);
- proteger o conteúdo assinado contra **sobrescrita**;
- registrar **auditoria** controlada (incl. tentativa falha em commit próprio).

## 2. Alterações de banco (migration `0020`)

`protocolos.assinatura_anexo` (+colunas):
```
documento_hash      VARCHAR(64)  NULL
hash_algoritmo      VARCHAR(20)  NULL DEFAULT 'sha256'
documento_versao    INTEGER      NULL DEFAULT 1
ip                  VARCHAR(64)  NULL
user_agent          VARCHAR(512) NULL
metodo_autenticacao VARCHAR(30)  NULL
nivel_assinatura    VARCHAR(20)  NOT NULL DEFAULT 'simples'
                      CHECK IN ('legado','simples','avancada')
status              VARCHAR(20)  NOT NULL DEFAULT 'pendente'
                      CHECK IN ('pendente','assinada','recusada','cancelada')
motivo              VARCHAR(1000) NULL
evidencias          JSONB        NULL
id_audit_log        BIGINT       NULL FK aprimora_py.audit_log(id)
```
`protocolos.usuario_assinatura` (+colunas):
```
status        VARCHAR(20) NOT NULL DEFAULT 'pendente'
                CHECK IN ('pendente','realizada','recusada')
motivo_recusa VARCHAR(1000) NULL
dt_recusa     TIMESTAMP     NULL
```
**Backfill (não-disruptivo):** `assinatura_anexo` → `nivel='legado'`,
`metodo='senha_md5_legado'`, `status = assinado ? 'assinada' : 'pendente'`.
`usuario_assinatura` → `status = realizada ? 'realizada' : 'pendente'`.
Índice `(tenant_id, status)` em `assinatura_anexo`. RLS já coberto (0006).
Após aplicar no dev: **regenerar `ci/legacy-schema.sql`** (CI usa stamp).

## 3. Alterações de backend
- `alembic/versions/0020_assinatura_v2.py` (novo) — §2.
- `models/assinatura.py` — novos campos em `AssinaturaAnexo` e `UsuarioAssinatura`.
- `schemas/assinatura.py` — `SolicitacaoOut`/`AssinaturaAnexoStatus` ganham
  `status`, `nivel`, `tem_hash`; novos `RecusarRequest`, `ValidacaoOut`,
  `EvidenciasOut`.
- `services/assinaturas.py`:
  - `assinar`: trocar `verify_md5` por `verify_password(...)`. **Se só bater em
    MD5 (`needs_rehash`) → NÃO assina**: levanta erro "atualize sua senha antes
    de assinar". Calcular SHA-256 do arquivo (via helper §abaixo), gravar
    hash/algoritmo/versao=1/ip/ua/metodo='senha_bcrypt'/nivel='simples'/
    status='assinada'/evidencias; vincular `id_audit_log`.
  - `recusar_assinatura(solicitacao_id, usuario_id, motivo)` (novo) — marca a
    `UsuarioAssinatura` do signatário como `recusada` + motivo + dt; reflete
    `status='recusada'` nas `assinatura_anexo` dele; audita.
  - `validar_assinatura(aa_id)` (novo) — legado/sem hash → `{integro:null,
    legado:true}`; senão recomputa hash atual e compara.
  - `consultar_evidencias(aa_id)` (novo).
  - `cancelar_solicitacao` — refletir `status='cancelada'`.
- `services/anexos.py` — helper `hash_anexo(tenant_slug, e_doc) -> (sha256, 'sha256')`
  lendo bytes via `resolve_anexo_path`; **guard de imutabilidade**: bloquear
  substituição/desentranhamento de anexo com assinatura `assinada`.
- `services/desentranhamento.py` — aplicar o mesmo guard.
- `services/audit.py` — `log()` passa a **retornar o id** criado (para
  `id_audit_log`). Mudança aditiva; callers atuais ignoram o retorno.
- `services/assinatura_throttle.py` (novo) — Redis (`redis.asyncio` sobre
  `settings.celery_broker_url`): chave `assinatura:falha:{tenant}:{user}:{anexo}`,
  `INCR`+`EXPIRE 900`; bloqueia quando `> 5`. **Fail-open** se o Redis estiver
  indisponível (não bloqueia assinatura legítima; loga aviso) — complementado
  pelo rate-limit do nginx.
- `routers/assinaturas.py` — `assinar` recebe `Request` (IP via x-forwarded-for,
  user agent via header) e repassa ao serviço; novos endpoints `recusar`,
  `validar`, `evidencias`. Leitura de validação/evidências **respeita o sigilo**
  (reusar o guard de acesso por nível).

## 4. Alterações de frontend (mínimas no 2a)
- `lib/api.ts` — novos métodos `recusar`, `validar`, `evidencias`; campos
  `status`/`nivel` nos tipos de saída.
- `app/(app)/para-assinar/page.tsx` — ação **Recusar** (com motivo) ao lado de
  Assinar; tratar mensagem de bloqueio MD5; mostrar erro de throttle.
- `components/AssinaturasProcesso.tsx` — exibir `status`/`nivel`; botão **Validar**
  por anexo assinado (mostra íntegro / alterado / legado).
> Comprovante PDF, tela dedicada de evidências e validação pública → **PR 2b**.

## 5. Regras de compatibilidade com o legado
- Tabelas reaproveitadas (sem tabela nova de evidências): `solicitacao_assinatura`,
  `usuario_assinatura`, `assinatura_anexo`, `tipo_assinatura`.
- Assinaturas antigas: `nivel='legado'`, sem hash; `validar` retorna "sem prova
  de integridade"; **não** são re-assinadas nem apagadas.
- `assinado`/`realizada` (bools) mantidos; `status` é a fonte nova.
- Frontend: mudanças **aditivas**; tipos TS atuais seguem válidos.
- Usuário só-MD5: continua logando pela regra atual; **bloqueado de assinar** até
  atualizar a senha (depende do fluxo de troca de senha em `/perfil`, já existente).

## 6. Endpoints impactados
| Método | Rota | Estado |
|---|---|---|
| POST | `/assinaturas/{aa_id}/assinar` | **ajustar** (bcrypt-only, hash, evidências, IP/UA, status) |
| POST | `/solicitacoes-assinatura/{id}/recusar` | **novo** (pelo signatário) |
| GET | `/assinaturas/{aa_id}/validar` | **novo** |
| GET | `/assinaturas/{aa_id}/evidencias` | **novo** |
| POST | `/processos/{id}/solicitacoes-assinatura` | inalterado |
| POST | `/solicitacoes-assinatura/{id}/cancelar` | inalterado (reflete status) |
| GET | `/assinaturas/{aa_id}/comprovante.pdf` | **PR 2b** |

## 7. Testes obrigatórios
1. assinar grava `documento_hash` (sha256) + evidências + `status='assinada'`.
2. alteração posterior do arquivo → `validar` retorna `integro=false`.
3. assinar gera `audit_log` (`assinatura.assinada`) com hash no payload.
4. recusar gera `audit_log` (`assinatura.recusada`) + `usuario_assinatura.status='recusada'`.
5. cancelar gera `audit_log` (`assinatura.cancelada`).
6. **MD5-only:** usuário sem `senha_bcrypt` é **bloqueado** de assinar (mensagem clara), sem gravar assinatura.
7. **throttle:** 5 falhas em 15 min por `(tenant,user,anexo)` → 6ª bloqueada; auditoria de falha em **commit próprio** e **limitada**.
8. usuário que não é o `id_assinante` designado não assina.
9. assinatura/validação de **outro tenant** bloqueada (RLS).
10. **imutabilidade:** anexo com assinatura `assinada` não pode ser sobrescrito/desentranhado.
11. legado (`nivel='legado'`, sem hash) não quebra listagem nem `validar`.
12. `validar` audita **só on-demand** (não em cada leitura).

## 8. Riscos
- **Redis no caminho de request:** novo uso de Redis pela API. Mitigação:
  fail-open + log; brute-force também coberto pelo rate-limit do nginx.
- **I/O do hash:** ler bytes do arquivo no assinar/validar; aceitável p/ tamanhos
  típicos; arquivo ausente = erro de assinatura.
- **Proteção mínima vs. versionamento completo:** sem GED de versão, a garantia é
  "bloquear sobrescrita". Se houver caminho de alteração de arquivo não coberto
  pelo guard, a premissa de integridade falha — mapear todos os pontos de escrita.
- **MD5-only bloqueado de assinar:** fricção operacional; depende do fluxo de
  troca de senha existir e estar acessível.
- **`audit.log` retornando id:** mudança em função compartilhada; verificar que
  nenhum caller quebra (retorno ignorado pelos atuais).

## 9. Fora de escopo (PR 2a)
- Comprovante PDF, tela de evidências/validação dedicada, **validação pública por
  código** → PR 2b.
- Versionamento completo de documento por anexo (GED) → futuro.
- Assinatura **avançada plena** (par de chaves do usuário), gov.br, ICP-Brasil,
  **qualificada**, **carimbo de tempo externo**, **hash chain** do audit_log.

## 10. Critérios de aceite
- Migration 0020 aplica no dev + `ci/legacy-schema.sql` regenerado.
- Assinatura nova grava hash + evidências + status; **nunca** via MD5 (bloqueio
  com mensagem clara).
- `recusar` e `validar` funcionam; `validar` detecta alteração e identifica legado.
- Conteúdo assinado **não** pode ser sobrescrito (guard testado).
- Throttle 5/15min por `(tenant,user,anexo)` + bloqueio 15min; tentativa falha
  auditada de forma controlada (commit próprio).
- Validação auditada **só on-demand**.
- Legado não quebra. Todos os testes do §7 verdes + suíte total verde.
- Frontend mínimo (recusar/validar/status) sem **novo** erro de typecheck.
- Entrega com resumo de diff, arquivos alterados, testes executados e riscos.

---

> **Parar aqui.** Nenhum código de produção alterado. Aguardando autorização para
> implementar o PR 2a (sugiro: confirmar fail-open do throttle e que o fluxo de
> troca de senha em `/perfil` cobre o caso MD5-only).
