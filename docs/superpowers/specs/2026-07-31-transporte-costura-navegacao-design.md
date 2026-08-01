# Transporte Regulado — costura da navegação

**Data:** 2026-07-31 · **Base:** `main` @ `bead6ee` · **Escopo fechado, aguardando implementação.**

## O problema

As fases P1 a P4 do transporte regulado estão entregues no backend, têm tela pronta e ~113 testes
verdes — e **o usuário não chega nelas**. A navegação nunca foi costurada.

Evidência levantada em 2026-07-31, no código:

- O hub (`frontend/app/(app)/transporte-regulado/page.tsx`, linhas 51–57) mostra **Documentos,
  Vistorias, Alvarás e Relatórios** como cards tracejados "em estruturação", sem `href`.
- O menu (`frontend/lib/menus/transporte.ts`) tem quatro itens: hub, Permissionários, Empresas,
  Veículos. Nada de alvarás nem relatórios.
- As páginas existem e são completas: `alvaras/page.tsx`, `alvaras/[id]/page.tsx`,
  `relatorio/page.tsx`. Vistorias, documentos e avaliações vivem dentro de `veiculos/[id]/page.tsx`.
- Busca por `transporte-regulado/(alvaras|relatorio|vistorias)` em todo o `frontend/` só encontra
  chamadas de API em `lib/api.ts` — **nenhum `href`**. Hoje só se chega digitando a URL.

É a mesma classe de problema que a F2 resolveu para a modularização: trabalho entregue que o usuário
não vê. A diferença é que aqui não há decisão de produto envolvida — é costura.

## O que muda

### 1. Menu — `frontend/lib/menus/transporte.ts`

Dois itens novos no grupo "Transporte Regulado", ambos com `perm: "transporte_regulado"` — a mesma
dos itens existentes. **Nenhuma permissão nova, nenhuma transação nova.**

| Label | href | Ícone |
|---|---|---|
| Alvarás | `/transporte-regulado/alvaras` | `ScrollText` |
| Relatórios | `/transporte-regulado/relatorio` | `BarChart3` |

Ordem final do grupo: hub → Permissionários → Empresas → Veículos → Alvarás → Relatórios. Segue o
rito do domínio: cadastro, depois operação, depois análise.

Atenção ao caminho: a rota é `/transporte-regulado/relatorio`, **singular**. O `/relatorios` plural
pertence ao protocolo e está antes na tabela `ROTA_MODULO`; como o casamento é por prefixo de
segmento e a nossa rota começa com `/transporte-regulado`, não há ambiguidade — mas trocar para o
plural criaria uma.

Consequência que não custa nada: o **Ctrl+K passa a encontrar as duas telas**. O `CommandPalette`
consome de `lib/menus`, que a F2 estabeleceu como fonte única de navegação.

Nada muda em `lib/modulos.ts`: o prefixo `/transporte-regulado` já resolve para o módulo
`transporte`, inclusive nas sub-rotas.

### 2. Hub — `frontend/app/(app)/transporte-regulado/page.tsx`

- **Alvarás** e **Relatórios** ganham `href` e `ready: true`.
- **Documentos** e **Vistorias**: cards **removidos**. Decisão tomada em 2026-07-31. Não são
  destinos — no backend existem apenas aninhados sob um veículo
  (`/transporte-regulado/veiculos/{veiculo_id}/vistorias`, idem documentos e avaliações), sem
  nenhuma listagem transversal, e no frontend são seções do detalhe do veículo. Card que não leva a
  lugar nenhum é ruído, e card que leva ao mesmo lugar que outro é pior.
- Continuam tracejados os três que de fato não existem: **Recadastramento**, **Rotas e Linhas**,
  **Ocorrências** — que são, na ordem, P5, P6 e P7.

Resultado: cinco cards navegáveis e três em estruturação, e o hub passa a descrever o módulo
honestamente.

Dois detalhes que o `tsc` cobra: o card de Relatórios hoje usa o ícone `Map`, e deve passar a usar
`BarChart3` — o mesmo do `PageHeader` da própria página de destino, senão o usuário vê um ícone no
hub e outro ao chegar. E remover os cards de Documentos e Vistorias deixa `FileText` e
`ClipboardCheck` órfãos no `import` do topo do arquivo.

### 3. Bug — `backend/app/routers/transporte_regulado.py`

`GET /transporte-regulado/veiculos/{id}/vistorias/vencidas` **está morto**. `/{vistoria_id}` é
declarada na linha 643 e `/vencidas` só na 681; como o FastAPI casa as rotas na ordem de declaração,
`vencidas` bate primeiro em `/{vistoria_id}: int` e a requisição morre em 422 sem nunca alcançar o
handler. Verificado na aplicação real:

```
>>> primeiro match para /api/v2/transporte-regulado/veiculos/1/vistorias/vencidas
/api/v2/transporte-regulado/veiculos/{veiculo_id}/vistorias/{vistoria_id}
```

O conserto é mover a declaração de `/vencidas` para antes de `/{vistoria_id}`. Handler e service
estão corretos e não mudam.

**Por que passou despercebido:** os testes de vencidas
(`test_vistoria_listar_vencidas_basico`, `test_vistoria_listar_vencidas_ordem_descendente`) chamam
`tr_svc.listar_vistorias_vencidas` **direto no service**. Nenhum exercita o HTTP. Um endpoint pode
estar inalcançável com o service inteiramente verde — e foi o que aconteceu.

## Testes

| Teste | Onde | Por quê |
|---|---|---|
| Duas entradas em `PERMISSOES_ESPERADAS` | `frontend/__tests__/menus.test.tsx` | **Obrigatório.** O teste reprova href sem entrada na tabela. É ele que impede um `perm` perdido de virar item visível para quem não deveria vê-lo. |
| Teste **HTTP** de `/vencidas` | `backend/tests/test_transporte_regulado_vistoria.py` | Sem ele o conserto não fica travado, e a ordem das rotas volta a quebrar na primeira edição do router. Teste de service não cobre roteamento. |
| Todo card `ready` tem `href` | novo, junto dos testes de frontend | Trava a classe de erro que criou esta fatia: card marcado como pronto que não leva a lugar nenhum, ou o inverso. |
| `npx tsc --noEmit` | host | Obrigatório antes de commitar mexida no frontend. |

Regressão esperada no backend: as duas falhas pré-existentes já registradas
(`test_jwt_compat::test_emitted_token_has_required_claims` e
`test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`) e nada além disso.

## Fora de escopo

- **Telas transversais** de vistorias e documentos (listagem de todos os veículos). Exigiriam
  endpoints novos no backend; deixa de ser costura e vira fase.
- **P5 (Recadastramento), P6 (Rotas e Linhas), P7 (Ocorrências)** — os três cards que continuam
  tracejados.
- **F3 da modularização** (prefixo `/m/<slug>` e redirects 308).

## Riscos

Baixos. Sem migration, sem permissão nova, sem tabela nova, sem rota de topo nova — a armadilha da
regex do `nginx/default.conf` não se aplica, porque `transporte-regulado` já está lá.

O risco operacional é de validação, não de produto: o contorno que faz o frontend rodar na máquina
do Jorge (build no host, `docker cp` para dentro do container) não sobrevive à recriação do
container, e o container do frontend foi recriado em 2026-07-31. Ver o resultado **na tela** vai
exigir refazer o contorno. `tsc` e o vitest rodam no host e não dependem disso.

## Divergência de numeração das fases — resolvida

Duas fontes discordavam sobre o que são P5–P8. A canônica é o `docs/BACKLOG-PENDENCIAS.md`
(seção 2.2, de 2026-07-28), que é também a mais recente:

- **P5** — Recadastramento
- **P6** — Rotas / linhas
- **P7** — Ocorrências regulatórias
- **P8** — Workflows avançados

A numeração antiga que circulava em anotações de sessão (P4 = CRUD frontend, P5 = histórico,
P6 = relatórios, P7 = documentos genéricos, P8 = workflows) descreve trabalho **já entregue** em
P1–P4 e não deve ser usada.

---

# Adendo de 2026-08-01 — dois defeitos achados durante a execução

Jorge reportou `TypeError: D.map is not a function` no navegador. A investigação levou a dois
defeitos **pré-existentes em `main`**, nenhum causado por esta fatia. Ambos autorizados a entrar
nela em 2026-08-01, porque a fatia acabou de dar visibilidade a telas que estão quebradas — costurar
o menu para uma tela que estoura é pior que deixá-la escondida.

## Defeito 1 — o contrato de paginação quebrou e o TypeScript não viu

O commit `628ca34` (2026-07-20, "P3 — Paginação — 13 endpoints") passou 13 endpoints do transporte
a devolver `Paginated` — `{items, total, page, page_size}`. O `frontend/lib/api.ts` nunca foi
atualizado: **12 métodos continuam declarando array**.

O `tsc` não pega porque `request<T>()` faz cast do JSON sem validar — o tipo é uma afirmação sobre a
resposta, não uma verificação dela. Verde no type-check, `TypeError` no navegador.

Confirmado na aplicação real, contra o banco real:

```
/api/v2/transporte-regulado/veiculos -> 200 | dict chaves=['items','total','page','page_size']
```

Dois sintomas, e o silencioso é o pior:

- **Estoura:** `veiculos/page.tsx:499` faz `permsQ.data?.map(...)`. O `?.` protege contra `null`, não
  contra objeto. Roda mesmo com o diálogo fechado, porque os `children` são construídos pelo
  componente pai a cada render — o `Dialog` só decide depois se mostra.
- **Mente:** `veiculos/page.tsx:351` faz `(listaQ.data?.length ?? 0) === 0`. Objeto não tem
  `.length` → `undefined` → `0` → a tela anuncia "Nenhum veículo regulado" com veículos cadastrados.

**Conserto:** seguir o precedente que já existe no próprio `api.ts` — `Paginated<T>` (usado
corretamente em `/usuarios`, `/unidades-trabalho` e `/processos`) e telas consumindo `data?.items`.

**Por que essa forma e não desembrulhar dentro do `api.ts`:** desembrulhar (`.then(r => r.items)`)
seria uma linha por método e não mudaria tela nenhuma — mas manteria o tipo mentindo sobre a
resposta, que é exatamente a causa raiz. Com `Paginated<T>` o `tsc` passa a ser a guarda: qualquer
tela futura que faça `.map` direto no retorno **não compila**. A proteção é estrutural, não um teste
que alguém pode esquecer de escrever.

**Consequência assumida, e não silenciada:** as telas do transporte não têm UI de paginação e o
backend usa `page_size` padrão de 50. Depois do conserto elas exibem **até 50 registros**. Isso não
é regressão — hoje exibem zero ou estouram —, mas é um teto real. Fica registrado como pendência de
follow-up no backlog; resolver exige decidir UI de paginação, que é decisão de produto.

## Defeito 2 — mais duas rotas engolidas, a mesma classe da Task 1

```
ENGOLIDA -> /alvaras/vencidos  => /alvaras/{alvara_id}
ENGOLIDA -> /alvaras/relatorio => /alvaras/{alvara_id}
OK          /alvaras/relatorio/kpis
OK          /alvaras/relatorio/export/csv
```

Verificado na aplicação real; `/alvaras/relatorio` responde **422**. As duas de `/relatorio/...`
sobrevivem só porque têm dois segmentos, e `{alvara_id}` casa um segmento só.

Efeito visível: na tela de Relatórios os KPIs carregam e a lista não.

**Conserto:** mover as duas declarações para antes de `/{alvara_id}`, com teste HTTP — igual à
Task 1. Que o mesmo defeito tenha aparecido duas vezes no mesmo arquivo diz que a ordem das rotas
precisa de guarda, não de vigilância.
