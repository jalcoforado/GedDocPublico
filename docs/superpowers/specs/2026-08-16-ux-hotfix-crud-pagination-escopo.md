# UX-HOTFIX-01 — Paginação real no CrudPage (escopo)

## Bug observado

`components/CrudPage.tsx` aceita, pelo próprio tipo (`fetchList`, linha 45-46), resposta
paginada `{items, total, ...}` — mas extrai só `items` (linha 150-152), descarta `total` e não
tem estado de página. Toda tela baseada nele mostra **apenas a primeira página** retornada pela
API, sem indicar que há mais registros.

## Call-sites (12) e contratos reais

**Afetados de verdade (5)** — usam `crud<T>().list()` de `lib/api.ts:1519-1531`, que retorna
`Paginated<T> = {items, total, page, page_size}` (`api.ts:66-71`); backend aceita
`page`/`page_size`/`q` (`Query(1, ge=1)` / `Query(20, ge=1, le=200)`; ex.
`routers/assuntos.py:98-99`, `localizacao.py`, `manifestantes.py:99-100`). Todos passam
`page_size: 50` e `q`, nenhum passa `page`:

| Tela | queryKey | fetchList |
|---|---|---|
| `m/protocolo/assuntos` | `["assuntos", q]` | `api.assuntos.list({q, page_size: 50})` |
| `m/protocolo/bairros` | `["bairros", q]` | `api.bairros.list({q, page_size: 50})` |
| `m/protocolo/cidades` | `["cidades", q]` | `api.cidades.list({q, page_size: 50})` |
| `m/protocolo/enderecos` | `["enderecos", q]` | `api.enderecos.list({q, page_size: 50})` |
| `m/protocolo/manifestantes` | `["manifestantes", q]` | `api.manifestantes.list({q, page_size: 50})` |

**Não afetados (7)** — contrato real é `T[]` sem paginação (cliente `request<T[]>`, backend
`response_model=list[...]`, ex. `pagamentos_cadastros.py:93-97`): tipos-anexo,
tipos-manifestante, tipos-processo, pag-naturezas, pag-contratos, pag-checklist, pag-alcadas.
Esses devolvem o conjunto completo; nada a corrigir e nenhum controle falso deve aparecer.

*(Correção sobre a auditoria UX-00, que dizia "12 telas truncando": são 5.)*

## Decisão implementada (menor evolução coerente)

- `CrudPage` ganha estado `page` (inicia em 1).
- `fetchList` passa a receber `{ page }` — retrocompatível: os call-sites `T[]` com lambda
  sem parâmetro continuam válidos em TS e em runtime.
- QueryKey da listagem vira `[...queryKey, { page }]` — páginas não colidem no cache, e
  `invalidateQueries({ queryKey })` das mutations segue casando por prefixo (invalida a
  família inteira, comportamento preservado sem tocar nas mutations).
- Resposta paginada (detectada por `total`/`page_size` numéricos, metadata real da API — sem
  hardcode de 20/50) exibe rodapé no padrão já existente do produto
  (`m/administracao/unidades-trabalho/page.tsx:182-197`): `"{total} registros — página {page}"`
  + Anterior/Próxima (`Button` secondary sm). Anterior desabilitado na página 1; Próxima
  desabilitada quando `page * page_size >= total`.
- Resposta `T[]`: nenhum controle de paginação (caminho legítimo preservado).
- Mudar o termo de busca volta para a página 1 (mesmo padrão da tela de referência). **Sem
  debounce** — fora do escopo desta fatia, por decisão.
- Clamp de página órfã: se a resposta disser que a página atual passou do fim (ex.: exclusão
  do último item da última página), volta para a última página válida — efeito de 4 linhas.
- Call-sites: só os 5 afetados mudam, e só na lambda de `fetchList` (repassam `page` à API,
  mantendo `q` e `page_size: 50`). Zero mudança de layout, permissão ou mutation.

## Critérios de aceite

1. Nas 5 telas, registros além da primeira página são alcançáveis por Anterior/Próxima.
2. Total real exibido; página atual exibida.
3. Anterior/Próxima desabilitados nos limites.
4. Buscar reinicia na página 1.
5. Telas `T[]` continuam idênticas (sem controles).
6. Criar/editar/excluir seguem invalidando a listagem (todas as páginas da família).
7. `tsc`, vitest e `next build` verdes.

## Testes

`components/__tests__/CrudPage.test.tsx` (TDD — escritos antes da implementação, vistos
falhar): página 1 renderiza + total visível; Próxima busca/renderiza página 2 (prova por
inversão: se `page` for ignorado ou a queryKey não diferenciar páginas, o item da página 2
nunca aparece e o teste falha); Próxima desabilitada na última; Anterior volta e desabilita
na 1; busca reseta página; array `T[]` sem controles; criação refaz a listagem (invalidação
por prefixo com a key estendida); clamp de página órfã.

## Limites desta fatia

Não inclui: debounce da busca, PageHeader, ordenação, seletor de page-size, redesign do
CrudPage, extração de ListPage/Pagination universal (fases UX-04/05 do master), mudanças de
backend (não são necessárias — os endpoints já paginam).
