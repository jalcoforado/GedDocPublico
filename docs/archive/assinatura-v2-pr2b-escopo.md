# PR 2b — Escopo Definitivo (Assinatura v2: guard de sigilo + UI mínima + comprovante)

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** escopo fechado (não implementado)

> Continuação do [PR 2a](assinatura-v2-pr2a-escopo.md) (núcleo backend já entregue
> em `097903d`). O PR 2b **começa pelo backend de autorização**, não pela UI.
> Primeiro item obrigatório: **guard de sigilo/permissão** nos endpoints
> `validar` e `evidencias`, que hoje expõem metadados (hash, status, nome do
> assinante, IP, user agent, método, nível) protegidos apenas por auth + tenant/RLS.

## Ordem de execução (obrigatória)
1. **Guard de sigilo/permissão** em `validar`/`evidencias` (backend) — primeiro.
2. Comprovante PDF de assinatura (backend).
3. Frontend mínimo (recusar/validar/status/nível + mensagens 409/429).
4. Troca de senha em `/perfil` — avaliar (provável PR 2c).
5. Testes.

---

## 1. Guard de sigilo/permissão em `validar`/`evidencias` (PRIMEIRO)

**Problema:** `GET /assinaturas/{aa_id}/validar` e `GET /assinaturas/{aa_id}/evidencias`
hoje exigem só `get_current_user` + tenant (RLS). Um servidor de baixa credencial
poderia ver metadados de assinatura de um anexo de processo **reservado/secreto/
ultrassecreto**. Precisa respeitar: tenant, usuário autenticado, **acesso ao
processo/anexo** e as **regras de sigilo por nível** já existentes.

**Onde a lógica vive hoje:**
- `services/sigilo.py`: `NIVEIS`, `niveis_permitidos(credencial)`, `pode_acessar(...)`.
- `routers/processos.py`: `_niveis_acesso(db, user, tenant_id)` (super-usuário via
  `load_permissions` → `None`, senão `niveis_permitidos(user.nivel_acesso_sigilo)`)
  e `require_acesso_processo` (carrega `processo.nivel_sigilo` e 404 se fora dos
  níveis). Essa lógica está **acoplada ao router de processos**.

**Proposta (reaproveitar, não duplicar):** extrair um helper reutilizável em
`services/sigilo.py`:
```python
class SigiloAcessoError(SigiloError): ...   # mapeado para 404 (não vaza existência)

async def assert_acesso_processo(
    db, *, tenant_id: int, processo_id: int | None, usuario
) -> None:
    # super-usuário (load_permissions) → ok
    # niveis = niveis_permitidos(usuario.nivel_acesso_sigilo)
    # carrega processo.nivel_sigilo (tenant-scoped); se fora dos níveis → raise
```
- `validar_assinatura`/`consultar_evidencias` passam a **receber o `usuario`** e,
  após carregar o `aa`, chamam `assert_acesso_processo(..., processo_id=aa.id_processo, usuario=usuario)`.
- Mapear `SigiloAcessoError` → **404** nos endpoints (consistente com o guard de
  processo, que usa 404 para não revelar a existência de sigiloso).
- **Desejável (DRY):** `routers/processos.py::require_acesso_processo` passa a
  delegar para o novo helper. Marcado como desejável para não inflar o PR; se
  ficar trivial, fazer junto.

**Aplicar o guard também ao comprovante** (`GET /assinaturas/{aa_id}/comprovante.pdf`,
item 3) — mesma checagem.

---

## 2. Comprovante PDF de assinatura

`services/pdf_comprovante_assinatura.py` (novo), no padrão reportlab dos PDFs
existentes (`pdf_comprovante.py`: `canvas` + `BytesIO` → `bytes`). Conteúdo:
- identificação do processo (número/NUP) + anexo (descrição/id);
- status da assinatura + nível + método;
- nome/id do assinante; data/hora;
- **hash SHA-256** + algoritmo + `documento_versao`;
- **resultado da validação** (recomputa no momento da geração);
- aviso claro: *"Assinatura eletrônica interna com evidências — não é assinatura
  qualificada ICP-Brasil"*;
- referência ao `id_audit_log` (identificador de validação).

Endpoint: `GET /assinaturas/{aa_id}/comprovante.pdf` (router `assinaturas.py`),
**guardado por sigilo** (item 1) e por `require_permission`/auth. Retorna
`Response(media_type="application/pdf")` como os outros PDFs.

> **Validação pública anônima fica fora** (PR 2c), salvo se trivial — não é.

---

## 3. Frontend mínimo

Apenas o necessário para usar o backend v2 (evitar UI rica):
- `lib/api.ts`: métodos `recusar(solicitacaoId, motivo)`, `validar(aaId)`,
  `evidencias(aaId)`, e URL do comprovante; tipos `ValidacaoOut`/`EvidenciasOut`.
- `app/(app)/para-assinar/page.tsx`: ação **Recusar** (com motivo) ao lado de Assinar.
- `components/AssinaturasProcesso.tsx`: ação **Validar** por anexo assinado;
  exibir **status** e **nível/método** da assinatura; link/baixar comprovante.
- **Mensagens claras** (usar toast/erro já existentes):
  - **409** → "Atualize sua senha antes de assinar (faça login novamente)."
  - **429** → "Muitas tentativas. Aguarde alguns minutos."
  - validação **inválida** → "Documento alterado após a assinatura."
  - validação **ok** → "Assinatura íntegra."

Os campos `status`/`nivel`/`tem_hash` já vêm de `SolicitacaoOut` (PR 2a).

---

## 4. Troca de senha em `/perfil` (avaliação)

**Achado:** não há endpoint self-service de troca de senha para usuário interno.
Existe: `PUT /usuarios/{id}` (admin, grava bcrypt) e **rehash automático no login**
(`auth.py` — MD5→bcrypt na autenticação bem-sucedida). `/perfil` não tem form de
senha.

**Decisão proposta para o 2b:** **mensagem apenas** — o 409 orienta "faça login
novamente" (o relogin já rehasha e desbloqueia a assinatura). Um **form dedicado
de troca de senha em `/perfil`** (endpoint self-service + UI) é **PR 2c**
(é form + endpoint novos, não trivial). *Decisão humana:* aceitar o desbloqueio
via relogin no 2b, ou exigir o form de senha já no 2b?

---

## 5. Testes obrigatórios
1. **Usuário sem credencial não acessa evidências** de anexo de processo sigiloso (404).
2. **Usuário sem credencial não valida** assinatura de anexo sigiloso (404).
3. **Usuário autorizado valida** corretamente (íntegro / alterado).
4. **Super-usuário** acessa evidências/validação de qualquer nível.
5. **Comprovante PDF** é gerado (bytes com header `%PDF`).
6. Frontend trata **409 (MD5)** — e2e ou verificação de UI.
7. Frontend trata **429 (throttle)** — e2e ou verificação de UI.
8. **Recusa** funciona no frontend (e2e/manual).
9. **status/nível** aparecem corretamente na tela.
> Backend (1–5) é determinístico e entra no pytest. Itens de UI (6–9) via e2e
> Playwright e/ou verificação manual no navegador — declarar qual no PR.
> Reusar o setup de `test_sigilo_enforcement.py` + `test_assinatura_v2.py` para o
> processo sigiloso + usuário de baixa credencial.

---

## 6. Fora de escopo (PR 2b)
- Validação **pública anônima** (PR 2c).
- Form dedicado de troca de senha em `/perfil` (PR 2c, salvo decisão contrária).
- gov.br, ICP-Brasil, **assinatura qualificada**, **carimbo de tempo externo**,
  **hash chain** do audit_log, **versionamento completo de GED**, IA,
  reformulação grande de UX.

---

## 7. Arquivos prováveis
- Backend: `services/sigilo.py` (helper `assert_acesso_processo` + `SigiloAcessoError`),
  `services/assinaturas.py` (validar/evidencias recebem `usuario` + guard),
  `routers/assinaturas.py` (guard + endpoint comprovante; mapear 404),
  `services/pdf_comprovante_assinatura.py` (novo), (desejável) `routers/processos.py`
  delegando ao helper.
- Frontend: `lib/api.ts`, `app/(app)/para-assinar/page.tsx`,
  `components/AssinaturasProcesso.tsx`.
- Testes: `backend/tests/test_assinatura_v2.py` (ou novo `test_assinatura_guard.py`),
  e e2e em `tests-e2e/` para a UI.

## 8. Riscos / decisões humanas
1. **Desbloqueio MD5 via relogin** (sem form em /perfil no 2b) — aceitável?
2. **Testes de UI (409/429/recusa)**: e2e Playwright vs verificação manual — definir.
3. **Refator do `require_acesso_processo`** para delegar ao helper: fazer no 2b (DRY) ou deixar quieto?
4. Comprovante recomputa o hash na geração (I/O) — ok para tamanhos típicos.

## 9. Critérios de aceite
- `validar`/`evidencias`/`comprovante` **negam acesso** (404) a quem não pode ver o processo; **permitem** a quem pode e ao super-usuário — com testes.
- Comprovante PDF gerado com hash + evidências + resultado da validação + aviso de "não ICP-Brasil".
- Frontend: recusar/validar/status/nível funcionando; mensagens 409/429/validação claras.
- Sem regressão (suíte verde); diff mínimo; relatório final (arquivos, testes, riscos, proposta do PR 2c).

---

> **Parar aqui.** Nenhum código alterado. Aguardando autorização para implementar
> o PR 2b (e a decisão do §4/§8 sobre a troca de senha e os testes de UI).
