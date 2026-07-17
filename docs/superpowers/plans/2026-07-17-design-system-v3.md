# Design System v3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Elevar o app ao DS v3 "Institucional Refinado": tokens em 3 camadas (verde-petróleo como marca, âmbar assinatura, Inter), 22 componentes ui/ com specs de estado completas, e sweep tela a tela nas 62 páginas.

**Architecture:** Spec: `docs/superpowers/specs/2026-07-17-design-system-v3-design.md` (fonte da verdade — ramps, escalas, checklist de tela, ordem dos módulos). Reescrita do `globals.css` preservando os NOMES semânticos públicos (zero quebra imediata); componentes consomem tokens de componente; sweep por módulo com o checklist §5.

## Global Constraints
- NENHUM valor cru (hex/px mágico) em componente ou página — sempre token/escala Tailwind mapeada. Exceção: cores de DADO dos charts (allowlist).
- Nomes semânticos existentes não podem sumir (aliases legados mantidos).
- Cada task: tsc limpo + vitest dos componentes (`docker exec aprimora-py-frontend npx vitest run` — conferir comando real no package.json) + screenshot sanity da tela-âncora do lote (controller confere).
- Dark mode e densidade compact verificados em toda task de componente/tela.
- Commits pequenos por task; mensagens `feat(ds)`/`refactor(ds)`.

## File Structure
- `frontend/app/globals.css` — camadas primitiva+semântica (reescrita §1-2 da spec).
- `frontend/tailwind.config.ts` — mapear novas escalas (spacing/radius/shadow/text) e cores.
- `frontend/app/layout.tsx` — Inter via next/font.
- `frontend/components/ui/*` — component tokens + estados (§3).
- `docs/design-system.md` — documentação viva.
- `frontend/package.json` — script `design:check` (validate-tokens com allowlist).
- 62 páginas em `frontend/app/(app)/**` — sweep §5 por módulo.

---

### Task DS-1: Fundação — primitivos, semânticos, Inter, escalas
- [ ] Reescrever `globals.css`: camada primitiva (§1 da spec: ramps green/amber/neutral/status, space, radius, shadow, text, motion, z) + camada semântica re-apontada (§2) nos DOIS temas + densidade compact re-expressa nas novas escalas. Manter aliases legados.
- [ ] `tailwind.config.ts`: expor escalas novas (fontSize com line-heights pareados, borderRadius, boxShadow, spacing continua default do Tailwind — só garantir consistência) e cores novas (green/amber ramps como `brand-*`/`accent-*` se útil) sem remover mapeamentos existentes.
- [ ] Inter: `next/font/google` no `layout.tsx` raiz (`variable: "--font-sans"`), `--font-sans` no tailwind fontFamily. Confirmar que o build do container baixa a fonte (next/font faz no build; se o ambiente bloquear rede no build, fallback: importar de `next/font/local` com os woff2 baixados no repo — decidir pelo que funcionar e reportar).
- [ ] Sanity visual: app sobe, telas-âncora legíveis nos 2 temas (screenshot pelo controller depois). tsc + vitest verdes.
- [ ] Commit: `feat(ds): fundação v3 — camadas primitiva/semântica, marca verde-petróleo, Inter e escalas`

### Task DS-2: Componentes ui/ — tokens de componente + estados + docs
- [ ] Para cada um dos 22 componentes de `frontend/components/ui/`: consumir tokens (nada cru), estados completos (default/hover/active/focus-visible/disabled(/loading em Button)), focus ring padronizado, tipografia da escala. Ajustes visuais finos permitidos (sombra/borda/radius conforme spec §3), sem mudar APIs públicas (props) — os testes em `__tests__` devem continuar passando.
- [ ] Criar `docs/design-system.md`: paleta+escalas (tabela), spec de estados por componente (tabela do padrão da skill), checklist de tela (§5 da spec).
- [ ] `package.json`: script `design:check` rodando `node .claude/skills/design-system/scripts/validate-tokens.cjs --dir frontend/components frontend/app` (ver flags reais do script; allowlist p/ hex de charts — se o script não suportar allowlist, wrapper grep que exclui os arquivos de chart).
- [ ] tsc + vitest verdes; `design:check` limpo em components/ui.
- [ ] Commit: `feat(ds): componentes base com tokens de componente, estados completos e docs`

### Tasks DS-3..DS-9: Sweep por módulo (uma task por lote, checklist §5 da spec em cada tela)
- DS-3 **Geral**: home, dashboard, perfil, perfil/notificacoes, configuracoes, para-assinar.
- DS-4 **Processos+Protocolo**: processos, processos/[id], processos/novo, protocolo/balcao, protocolo/ccd, protocolo/ttd, protocolo/vencendo-prazo, relatorios, relatorios/assinaturas, relatorios/tramitacao.
- DS-5 **Cadastros GED/Admin**: assuntos, manifestantes, tipos-manifestante*, cidades, bairros, enderecos, servicos, tipos-anexo, tipos-processo*, templates-documento, organograma, grupos, usuarios*, unidades*, jobs, auditoria (*conferir nomes reais das rotas no filesystem).
- DS-6 **Frota**: frotas + 7 subtelas.
- DS-7 **Transporte regulado**: 3-4 telas.
- DS-8 **Pagamentos (passada fina)**: 12 telas — já modernas; aqui é só conformidade (tokens/escala/headers) sem redesenho.
- DS-9 **Workflows/restantes**: workflows e qualquer page.tsx não coberto (diff da lista de 62).
- Cada task: aplicar o checklist §5, rodar tsc, `design:check` no diretório do lote, commit `refactor(ds): sweep <módulo>`.

### Task DS-10: Validação final (controller)
- [ ] Regressão frontend completa (vitest) + tsc + design:check global.
- [ ] Screenshots claro/escuro das telas-âncora (home, processos/[id], frotas, pagamentos/dashboard, tesouraria) e revisão visual.
- [ ] Spot-check de contraste AA (pares de status) com o validador dataviz.
- [ ] Ledger + apresentação ao Jorge.

## Self-review
- Spec §1-2↔DS-1, §3+§6-docs↔DS-2, §5 módulos A-G↔DS-3..9, §Verificação↔DS-10. Zero quebra de API de componentes garante que o sweep é independente da fundação. Ordem dos lotes = valor pro usuário (Geral primeiro).
