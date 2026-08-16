# UX-HOTFIX-02 — Foco inicial do Dialog compartilhado (escopo)

## Evidência

`components/ui/dialog.tsx:48-49` fazia `items?.[0]?.focus()` sobre o mesmo seletor
`FOCUSABLE` do trap. Como o botão "Fechar" (X) mora no `<header>`, antes do conteúdo no DOM,
ele era o primeiro focável de **todo** dialog: modais de formulário abriam com o foco no X, e
até o `autoFocus` do prompt (`ui/confirm.tsx:143`) era sobrescrito — o `autoFocus` do React
foca durante o commit, e o efeito do Dialog rodava depois e roubava o foco.

Varredura: **72 ocorrências de `<Dialog`** em ~45 arquivos (fora o teste). Categorias:
maioria **A formulário** (CRUDs de frota/transporte/pagamentos/administração/protocolo,
CrudPage); **B confirmação** e **C prompt** via `ConfirmProvider` (`ui/confirm.tsx:90`);
**D informativos/visualizadores** (PdfViewerDialog, GoogleConnectDialog,
ValidacaoPublicaCard, alvara-veiculos-modal); **E outros** (UnidadePicker). `autoFocus`
dentro de Dialog compartilhado: `confirm.tsx:143`, `UnidadeEditDrawer.tsx:264`,
`para-assinar/page.tsx:211,264`. Modais artesanais confirmados (fora de escopo, fatia
própria): `AnexoDesentranhar.tsx:100`, `ProcessoApensados.tsx:397`, `ProcessoVolumes.tsx:260`.

## Causa raiz

Foco inicial = primeiro elemento do seletor do trap, e o X é o primeiro no DOM.

## Comportamento alvo e decisão

Prioridade no efeito de abertura (`dialog.tsx`):
1. algo dentro do dialog **já tem foco** (ex.: `autoFocus` de um filho, que roda no commit,
   antes do efeito) → preservar (`root.contains(document.activeElement)`);
2. senão → primeiro focável **que não seja o botão Fechar** (`closeRef`): campo do conteúdo
   ou, sem campo, a 1ª ação do footer (no ConfirmProvider isso é "Cancelar" — confirmação
   destrutiva não nasce com foco no botão danger, sem lógica especial de intent);
3. só o Fechar existe → Fechar (fallback).

Uma mudança de ~10 linhas no primitivo; **nenhum call-site alterado** (o genérico resolve
todas as categorias). O X continua na ordem normal de tabulação — trap intacto (o seletor do
trap não mudou). Escape, scroll lock e restauração de foco intactos.

## Arquivos afetados

- `frontend/components/ui/dialog.tsx` — `closeRef` + regra de foco inicial.
- `frontend/components/ui/__tests__/dialog.test.tsx` — 7 testes novos, regressão mantida.

## Critérios de aceite

Dialog com campo abre focado no campo; `autoFocus` explícito vence; confirmação foca
"Cancelar"; dialog só-com-X foca o X; Escape fecha; Tab/Shift+Tab ciclam incluindo o X; foco
volta ao gatilho ao fechar; digitação com `onClose` inline não perde foco (regressão de
2026-08 preservada).

## Testes

TDD: os 4 testes de foco foram vistos **falhar** contra a implementação antiga (prova por
inversão: com `items[0].focus()`, o X recebia o foco e "Dentro"/"Nome"/"Cancelar"/"Segundo"
não) e passar após a mudança. Suíte do arquivo: 8/8.

## Adendo 02B/02C — restauração de foco com filho `autoFocus` (2026-08-16)

**Causa original**: a captura do "elemento anterior" vivia no efeito do Dialog. O
`autoFocus` de filho dispara no **commit**, antes de qualquer efeito do pai (efeitos,
inclusive de layout, rodam filho-primeiro) — então o efeito guardava o próprio filho do
dialog como "anterior", e no fechamento o foco não voltava ao trigger.

**Tentativa rejeitada (02B)**: detectar a transição `open: false→true` durante o render,
lendo/escrevendo refs (`wasOpen`/`previouslyFocused`) no corpo do componente. Funcionava,
mas viola a regra de pureza do render do React (refs não devem registrar lifecycle
durante render) — descartada por decisão arquitetural, com os testes preservados.

**Solução final (02C)**: o destino de retorno vem de **evento sobre árvore commitada** —
o primeiro evento de foco que cruza a fronteira "fora → dentro" do dialog
(`onFocus` no container) carrega em `relatedTarget` o elemento que perdeu o foco: o
trigger. Cobre o `autoFocus` (o evento dispara no commit e é a única testemunha do
trigger naquele instante) e o foco programático do próprio Dialog. Fallback defensivo no
efeito para ambiente sem `relatedTarget`: se nada dentro do dialog tem foco ainda,
`document.activeElement` (≠ body) é o anterior. Invariantes: primeiro ingresso vence o
ciclo (movimentação interna não sobrescreve); o ciclo zera no cleanup (reabrir captura o
novo trigger); só elemento conectado é restaurado (trigger desmontado → fechar sem erro);
zero mudança de API; nenhuma lógica por call-site.

**Regressões cobertas** (13 testes em `dialog.test.tsx`): foco inicial (input / autoFocus
/ footer / só-X), Escape, trap nos dois sentidos, restauração normal, restauração com
autoFocus, restauração com autoFocus sob StrictMode, reabertura por outro trigger,
movimentação interna sem sobrescrita, trigger removido sem exceção, digitação com
`onClose` inline. Prova por inversão do 02C: removendo só o handler de evento, os 2
testes de autoFocus falham (o evento é o sustentáculo); com ele, 13/13.

## Fora de escopo

Migração dos 3 modais artesanais; política de clique no backdrop; `aria-describedby`;
Radix/Floating UI; qualquer mudança visual.

## Rollback

Revert do commit desta fatia (mudança isolada em 2 arquivos + esta spec).
