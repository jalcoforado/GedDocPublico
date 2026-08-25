# PR-E — Minuta/Documento: Hardening

**Autorizado:** 2026-07-18 (Jorge)  
**Branch:** feat/minuta-documento  
**Base:** 7465a44 (PR-A/B/C)

## Escopo

Endereça segurança, auditoria e UX de histórico da feature "redigir documento na hora de anexar" (PR-A/B/C).

### 1. Sanitização HTML com Bleach

**Por quê:** Templates admins podem conter HTML legítimo; usuários digitam no TipTap (WYSIWYG) que gera HTML. Bleach remove tags/attrs perigosas antes de gerar PDF (prevenção XSS/SSRF em PDF).

**O quê:**
- Instalar `bleach` em `pyproject.toml`
- Criar `backend/app/services/html_sanitizer.py` com:
  - Whitelist de tags: `p, br, b, i, u, strong, em, h1, h2, h3, ul, ol, li, blockquote, a, span, div`
  - Whitelist de attrs: `href` (a), `class` (span/div — para estilos Tiptap)
  - Strip scripts, events, styles perigosos
  - Função `sanitizar_html(html: str) -> str`
- Aplicar em:
  - `POST /minutas/{id}/salvar` (entrada do TipTap no frontend)
  - `POST /minutas/{id}/finalizar` (antes de WeasyPrint)
  - Templates admin já salvos: migração 0045 limpa `template_documento.conteudo` existente

**Testes:** 
- Unit: conteúdo legítimo passa, tags perigosas removidas
- Integration: HTML→PDF válido com bleach aplicado

### 2. Audit Log do Ciclo de Minuta

**Por quê:** Conformidade + rastreabilidade de quem criou/editou/finalizou documento (importante se houver contestação).

**O quê:**
- Disparar `audit_log` (padrão aprimora) em:
  - `POST /minutas` → `minuta.criada` (ator = usuário, processo_id)
  - `PATCH /minutas/{id}` → `minuta.editada` (ator = usuário, processo_id)
  - `POST /minutas/{id}/finalizar` → `minuta.finalizada` (ator = usuário, anexo_id)
  - `DELETE /minutas/{id}` → `minuta.excluida` (ator = usuário, processo_id)
- Evento também dispara quando `DELETE /anexos/{id}` revert minuta a rascunho (novo evento: `minuta.revertida_a_rascunho`)
- Payload compacto: só id, ator, timestamp, status

**Testes:**
- Unit: eventos corretos por ação
- Integration: `audit_log` consulta ✓, RLS respeita tenant_id

### 3. Fix Page-Count WeasyPrint

**Por quê:** WeasyPrint tem bug com `{{PAGE_NUMBER}}` em footers; páginas podem contar errado ou mostrar NaN.

**O quê:**
- Opção A (simples): remover suporte a `{{PAGE_COUNT}}`/`{{PAGE_NUMBER}}` de templates por enquanto (documentado em RUNBOOK)
- Opção B (futuro): implementar footer customizado em PDF antes de salvar (requer pré-processamento)
- Para PR-E: ir com **Opção A** — adicionar nota em `PLACEHOLDERS_DISPONIVEIS` que page-count será suportado em PR-F

**Testes:**
- Validação: templates com `{{PAGE_COUNT}}` devem ser rejeitados no save (mensagem: "Page count não suportado ainda")

### 4. Viewer de Histórico

**Por quê:** Usuários precisam revisar versões anteriores da minuta (rastreabilidade de mudanças).

**O quê:**

**Backend:**
- Endpoint `GET /minutas/{id}/historico` retorna lista de `minuta_historico` DESC (mais recente primeiro):
  ```json
  {
    "versoes": [
      {"versao": 1, "criado_em": "2026-07-18T10:00Z", "conteudo_html": "..."},
      {"versao": 0, "criado_em": "2026-07-18T09:00Z", "conteudo_html": "..."}
    ]
  }
  ```
- Gate: `require_permission("processo", "ler")`

**Frontend:**
- Componente `MinutaHistoricoViewer` em `frontend/components/MinutaHistoricoViewer.tsx`:
  - Expandable section no card `MinutasProcesso` com label "Ver histórico"
  - Lista versões com timestamp e botão "Restaurar versão" (cria nova edição com conteúdo antigo)
  - HTML renderizado em iframe sandbox (read-only, sem interação)

**Testes:**
- Unit: endpoint retorna versões corretas
- Integration: histórico renderiza, restore cria nova versão com versao_anterior referenciado

## Implementação

### Ordem

1. Migration 0045 (sanitização de templates existentes)
2. `html_sanitizer.py` service
3. Aplicar bleach em endpoints POST/PATCH/finalizar
4. Audit log eventos (backend)
5. Histórico endpoint (GET)
6. Histórico UI (frontend)
7. Testes (547 → ~570 backend, vitest +10-15)

### Commits

- `feat(minuta): PR-E hardening — sanitização HTML, audit, histórico`
- Tests: pytest 547 → ~570, vitest 79 → 90

## Ganchos Abertos

- **PR-F (page-count WeasyPrint):** quando WeasyPrint tiver fix ou alternativa
- **PR-D (Google Docs):** independente, bloqueado por OAuth
- **Notificações:** quando motor de notificação para `UsuarioInterno` existir

## Verificação Pré-Commit

- [ ] Bleach remove XSS/SSRF payload (unit test)
- [ ] Templates antigos sanitizados via migration
- [ ] Audit log registra corretamente
- [ ] Histórico endpoint completo + RLS
- [ ] Viewer renderiza versões anteriores
- [ ] Testes passam (pytest + vitest + tsc)
- [ ] Fluxo de-ponta-a-ponta: criar minuta → editar → ver histórico → restore → finalizar

## Referências

- Migration 0044: `backend/alembic/versions/0044_minuta_documento.py`
- Service minuta: `backend/app/services/minutas.py`
- Placeholders: `backend/app/services/placeholders.py`
- Anexos hook: `backend/app/services/anexos.py` (delete_anexo)
