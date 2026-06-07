# TECH-1 — Zerar baseline TypeScript

> Documento **somente de escopo**. Nada será implementado sem autorização.
> Estado base: `origin/main` em `2eab123` (SEC-1 follow-up publicado).
> Meta: `tsc --noEmit` ⇒ **0 erros**, sem refactor amplo e sem mudança
> funcional.

## 1. Resumo executivo

- **21 erros** no `tsc --noEmit`, distribuídos em **8 arquivos**.
- **5 famílias** de causa-raiz; nenhuma indica bug de runtime — todos são
  desvios de tipagem que o TypeScript já conseguiria validar com 1–2 ajustes
  centralizados por família.
- **12 dos 21 erros (~57%)** caem numa única família: query-string com
  `boolean` em `lib/api.ts`. Uma correção no helper `qs(...)` resolve tudo.
- Outros 7 são pattern-fix em React Flow (`@xyflow/react`); 1 é typo de
  modelo; 1 é signature do `Pie` (Recharts); 0 envolvem mudança de
  comportamento.
- **Backend, payloads, endpoints, contratos de rede, runtime e UX: tudo
  intocado.**

## 2. Saída do `tsc --noEmit` (resumida)

| # | Arquivo | Linha | Tipo |
|---|---|---|---|
| 1 | `app/(app)/dashboard/page.tsx` | 571 | TS2769 — overload do `Pie` (Recharts) |
| 2 | `components/AnexosProcesso.tsx` | 71 | TS2551 — typo `id_tipo_anexo` |
| 3 | `components/CommandPalette.tsx` | 317 | TS2339 — `_idx` fora do tipo |
| 4 | `components/CommandPalette.tsx` | 322 | TS2339 — `_idx` fora do tipo |
| 5 | `components/CommandPalette.tsx` | 325 | TS2339 — `_idx` fora do tipo |
| 6 | `components/UnidadePicker.tsx` | 94 | TS2322 — `sourcePosition: "bottom"` vs enum `Position` |
| 7 | `components/organograma/OrganogramaDiagramView.tsx` | 342 | TS2322 — idem |
| 8 | `components/workflow/WorkflowDiagram.tsx` | 95 | TS2322 — `sourcePosition: "right"` vs enum `Position` |
| 9 | `components/workflow/WorkflowEditor.tsx` | 80 | TS2322 — idem |
| 10 | `lib/api.ts` | 1046 | TS2345 — `boolean` em params `qs()` |
| 11 | `lib/api.ts` | 1182 | TS2345 — interface sem index signature em `qs()` |
| 12 | `lib/api.ts` | 1267 | TS2345 — `boolean` em params `qs()` |
| 13 | `lib/api.ts` | 1667 | TS2345 — interface sem index signature em `qs()` |
| 14 | `lib/api.ts` | 2005 | TS2322 — `boolean` em params `qs()` |
| 15 | `lib/api.ts` | 2253 | TS2322 — `boolean` em params `qs()` |
| 16 | `lib/api.ts` | 2378 | TS2322 — `boolean` em params `qs()` |
| 17 | `lib/api.ts` | 2420 | TS2345 — `boolean` em params `qs()` |
| 18 | `lib/api.ts` | 2450 | TS2345 — `boolean` em params `qs()` |
| 19 | `lib/api.ts` | 2530 | TS2322 — `boolean` em params `qs()` |
| 20 | `lib/api.ts` | 2557 | TS2345 — `boolean` em params `qs()` |
| 21 | `lib/api.ts` | 2611 | TS2345 — `boolean` em params `qs()` |

## 3. Famílias de erros

### Família A — `qs(...)` aceita só `string|number|null|undefined` (12 erros)

**Causa-raiz:** [lib/api.ts:906-913](frontend/lib/api.ts#L906-L913)

```typescript
function qs(params: Record<string, string | number | undefined | null>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  }
  ...
}
```

O runtime já faz `String(v)` — `String(true) === "true"` funciona. A
restrição é apenas de TIPO. Dois sub-padrões aparecem:

A1. **Boolean em params anônimo** (10 erros — linhas 1046, 1267, 2005, 2253,
2378, 2420, 2450, 2530, 2557, 2611): call sites passam um objeto inline com
`ativo?: boolean`, `apenas_nao_lidas?: boolean`, etc.

A2. **Interface tipada sem index signature** (2 erros — linhas 1182, 1667):
`ProcessoListFilters` e `AuditFilters` são `interface`s nomeadas. TS exige
que o tipo seja assinalável a `Record<string, ...>`, o que requer index
signature.

**Correção mínima e segura:** ampliar o tipo do helper para incluir
`boolean`. Já há outro helper interno (`crud<T>`) que usa
`Record<string, any>` — alargar o `qs` para
`Record<string, string | number | boolean | undefined | null>` resolve
todos os 12 erros sem nenhuma alteração no runtime nem nos call sites.

Para o sub-padrão A2 (interfaces nomeadas), a correção mais correta é
adicionar `[key: string]: string | number | boolean | undefined | null`
nas duas interfaces OU castar localmente nos 2 call sites. **Recomendo
ajuste apenas no `qs()`** — interfaces não-extensíveis ganham um cast
explícito tipo-só no único call site, mantendo a interface limpa.

**Risco:** baixíssimo. Mudança de tipagem; runtime já cobria.

### Família B — React Flow: `sourcePosition` como string em vez do enum (4 erros)

**Causa-raiz:** o `@xyflow/react` v12 endureceu o tipo de `Node` —
`sourcePosition` e `targetPosition` exigem o enum `Position`
(`Position.Bottom`, `Position.Right`, etc.), não a string literal.

Arquivos afetados:
- [components/UnidadePicker.tsx:94](frontend/components/UnidadePicker.tsx#L94)
- [components/organograma/OrganogramaDiagramView.tsx:342](frontend/components/organograma/OrganogramaDiagramView.tsx#L342)
- [components/workflow/WorkflowDiagram.tsx:95](frontend/components/workflow/WorkflowDiagram.tsx#L95)
- [components/workflow/WorkflowEditor.tsx:80](frontend/components/workflow/WorkflowEditor.tsx#L80)

**Correção:** importar `Position` de `@xyflow/react` e trocar
`sourcePosition: "bottom"` por `sourcePosition: Position.Bottom` (e idem
para `"top"`/`"right"`/`"left"`). Runtime equivalente — o enum resolve
para a mesma string em runtime.

**Risco:** baixo. Mudança de literal para constante do enum; testes e
visual idênticos.

### Família C — `CommandPalette._idx` fora do tipo `CommandAction` (3 erros)

**Causa-raiz:** [components/CommandPalette.tsx:317,322,325](frontend/components/CommandPalette.tsx#L317-L325)

`_idx` é um campo de uso interno, atribuído no momento da composição da
lista (provavelmente no `useMemo` que monta `groups`) mas não declarado
em `CommandAction`. TS reclama dos 3 acessos.

**Correção:** adicionar `_idx?: number` ao tipo `CommandAction` **ou**
extrair um tipo `CommandActionView extends CommandAction { _idx: number }`
para o que circula dentro do `groups.items`. A 2ª variante é mais
ergonômica e documenta a invariante. **Recomendo opção 2** (5–10 linhas).

**Risco:** baixo. Não muda runtime. Pequeno cuidado: garantir que `_idx`
é sempre atribuído antes do uso (já é, pelo que se vê no fluxo do
componente).

### Família D — `AnexosProcesso.id_tipo_anexo` — typo / campo inexistente (1 erro)

**Causa-raiz:** [components/AnexosProcesso.tsx:71](frontend/components/AnexosProcesso.tsx#L71)

```typescript
const tipo = tiposQ.data?.find((t) => t.id === a.id_tipo_anexo);
```

`AnexoNoProcesso` ([lib/api.ts:270-280](frontend/lib/api.ts#L270-L280)) só
tem `tipo_anexo: string | null`, **não tem** `id_tipo_anexo`. O backend
nunca devolve `id_tipo_anexo` neste endpoint.

A linha imediatamente acima já cobre o caso de existir nome de tipo:

```typescript
if (a.tipo_anexo) return a.tipo_anexo;  // ← este já trata o feliz
const tipo = tiposQ.data?.find((t) => t.id === a.id_tipo_anexo);  // ← unreachable em prática
```

**O fallback do find é código morto** — `a.id_tipo_anexo` é sempre
`undefined`, então `find((t) => t.id === undefined)` retorna `undefined` e
o `??` cai no `"—"`.

**Correção mínima:** simplificar para
`return a.tipo_anexo ?? "—";` — remove a linha morta sem mudar
comportamento observável (verificado pela lógica: se `tipo_anexo` for
falsy, hoje retorna `"—"` exatamente como retornaria após).

**Risco:** baixo, mas é o único erro que **toca código** em vez de só
tipagem. Aceite recomendado: confirmar visualmente em
`/processos/:id` que a coluna "Tipo" continua mostrando o nome quando
existe e `"—"` quando não.

### Família E — Recharts `Pie` label: signature do callback (1 erro)

**Causa-raiz:** [app/(app)/dashboard/page.tsx:571](frontend/app/(app)/dashboard/page.tsx#L571)

```typescript
label={(entry: { label: string }) => entry.label}
```

O `Pie` espera `PieLabel | undefined` cujo callback recebe
`PieLabelRenderProps` (não o item original). A versão atual cita `entry`
como `{ label: string }`, que é incompatível com a interface da lib.

**Correção:** usar a assinatura correta — `PieLabelRenderProps` traz
`name` que é o `nameKey` resolvido:

```typescript
label={(props) => String(props.name ?? "")}
```

(ou importar `PieLabelRenderProps` da `recharts` e tipar explicitamente).

**Risco:** baixo. Runtime equivalente — Recharts internamente passa o
`label` (via `nameKey="label"`) como `name` no `PieLabelRenderProps`.

## 4. Plano de execução

Ordem recomendada (do mais seguro/maior payoff para o mais focado):

1. **Família A — `qs()`** ⇒ −12 erros. Alterar uma linha do signature.
2. **Família B — React Flow `Position`** ⇒ −4 erros. Import + replace nos 4
   arquivos.
3. **Família C — CommandPalette `_idx`** ⇒ −3 erros. Tipo derivado local.
4. **Família E — Dashboard Pie** ⇒ −1 erro. Reescrita do callback.
5. **Família D — AnexosProcesso typo** ⇒ −1 erro. Remoção de linha morta
   + revalidação visual.

**Total esperado:** 21 → 0.

## 5. Estimativa de impacto

| Família | Arquivos | Linhas Δ | Runtime |
|---|---|---|---|
| A — `qs()` | 1 (`lib/api.ts`) | 1 linha (signature) + ~2 casts em interfaces | inalterado |
| B — React Flow | 4 | ~4 imports + ~8 substituições | inalterado (enum = mesma string) |
| C — CommandPalette | 1 | ~5–10 linhas (tipo + assert) | inalterado |
| D — AnexosProcesso | 1 | −3 / +1 | **possível** mudança de UX em edge case (ver §3.D) |
| E — Pie label | 1 | 2 linhas | inalterado |
| **TOTAL** | **6 arquivos** | **~30 linhas** | só Família D pede revalidação |

## 6. Testes a executar

- `tsc --noEmit` ⇒ deve passar a **0 erros**.
- `vitest run` ⇒ **243/243 verde** (nada deve regredir).
- Família D ⇒ smoke manual em `/processos/:id` com anexo que tem
  `tipo_anexo` definido e com anexo sem tipo, confirmando coluna "Tipo".
- Família B ⇒ smoke manual rápido em `/organograma`, em algum workflow do
  PR4d, e no `UnidadePicker` (modal de processo). Confirmar que o diagrama
  ainda desenha conexões nas direções corretas (`Bottom`/`Top` para árvore
  vertical; `Right`/`Left` para horizontal).
- Playwright ⇒ **N/A** salvo se algum smoke surgir regressão.

## 7. Fora de escopo (reafirmado)

- ❌ Backend.
- ❌ Migration.
- ❌ Endpoint novo.
- ❌ Payload novo.
- ❌ Mudança de regra de negócio (a única coisa próxima é a linha morta da
  Família D — mesmo assim, mantém o `"—"` no caminho final, então UX é
  equivalente).
- ❌ Refactor amplo do `lib/api.ts` (ex.: extrair query builder; consolidar
  interfaces de filtro num pacote `filters.ts`). Tudo isso pode vir depois,
  fora do TECH-1.
- ❌ Reescrita de componentes (CommandPalette, OrganogramaDiagramView,
  dashboard) — só ajustes localizados.
- ❌ Troca de biblioteca (Recharts, @xyflow/react, etc).
- ❌ Mudança visual ou de UX. As mudanças aqui não mexem em pixel.
- ❌ Mudança de rotas.

## 8. Critérios de aceite

1. `docker compose exec frontend npx tsc --noEmit` ⇒ **0 erros, 0 warnings**.
2. `docker compose exec frontend npx vitest run` ⇒ **243/243 verde**.
3. Backend: zero arquivos alterados (`git diff --name-only main` não inclui
   `backend/**`).
4. Payloads de rede: zero — nenhuma `string` substituída por outra coisa em
   chamadas `request<...>(...)`.
5. Família D: confirmar manualmente que a coluna "Tipo" continua coerente.
6. Famílias B (React Flow): confirmar manualmente que os diagramas ainda
   conectam nodes na direção correta.
7. Nenhuma nova diretiva `// @ts-ignore`, `// @ts-expect-error` ou cast
   `as any` introduzida (exceto, se necessário, no único cast localizado
   das interfaces sem index signature da Família A — documentado com
   comentário breve).

## 9. Decisão em aberto

**A1 vs A2 (Família A):** o `qs()` deve aceitar `boolean` no signature OU
os 12 call sites devem normalizar o boolean para string?

- **Opção 1 (recomendada):** alargar o `qs()` — fix único, 1 linha, todos
  os call sites continuam idênticos. Mantém o lugar onde se decide o
  serializer (um só ponto: `String(v)`).
- **Opção 2:** cada call site converte `ativo ? "true" : "false"` (ou só
  passa `undefined` quando falso). 12 mudanças, mais cerimônia, sem ganho
  de tipo (o `qs()` continua aceitando `string`).

Prefiro a Opção 1. Aguardo aval para escolher.

---

**Próximo passo após este doc**: aguardar autorização para implementar,
com a decisão de §9 confirmada.
