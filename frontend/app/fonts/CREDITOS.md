# Fontes de `frontend/app/fonts/`

Fontes hospedadas no próprio frontend (woff2 variáveis, subconjunto latino),
declaradas em `app/layout.tsx` por `next/font/local` — sem dependência de rede
no build.

| Arquivo | Fonte | Papel | Licença |
|---|---|---|---|
| `inter.woff2` | Inter | Texto corrido e tabelas | SIL Open Font License 1.1 |
| `montserrat.woff2` | Montserrat | Títulos (padrão) | SIL Open Font License 1.1 |
| `jetbrains-mono.woff2` | JetBrains Mono | Código e números de processo | SIL Open Font License 1.1 |
| `roboto-slab.woff2` | Roboto Slab | Títulos (opção do tema por município) | Apache License 2.0 |
| `nunito.woff2` | Nunito | Títulos (opção do tema por município) | SIL Open Font License 1.1 |

`roboto-slab.woff2` e `nunito.woff2` vieram dos pacotes
`@fontsource-variable/roboto-slab` e `@fontsource-variable/nunito` (5.1.0),
arquivo `*-latin-wght-normal.woff2`, sem alteração.

Fonte nova na lista de títulos pede quatro coisas, no mesmo PR: o arquivo aqui,
a declaração em `app/layout.tsx`, a entrada em `FONTES`
(`lib/tema-cores.ts`) e uma migration que a acrescente ao CHECK de
`aprimora_py.tenant.fonte_titulos`.
