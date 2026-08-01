# Transporte — costura da navegação: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development`
> (recomendado) ou `superpowers:executing-plans` para executar tarefa a tarefa. Os passos usam
> checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** tornar alcançáveis pela navegação as telas de Alvarás e Relatórios que P1–P4 já
entregaram, e consertar o endpoint `/vistorias/vencidas`, hoje morto por ordem de rota.

**Arquitetura:** três mudanças independentes e pequenas. No backend, mover uma declaração de rota
para antes de outra e cobrir com o primeiro teste HTTP do módulo. No frontend, acrescentar dois
itens ao menu do módulo (que a F2 fez ser fonte única, então o Ctrl+K vem junto de graça) e corrigir
os cards do hub, extraindo-os para um módulo de dados próprio para que possam ser testados sem
renderizar a página.

**Stack:** FastAPI + pytest/httpx no backend; Next 15 + React 19 + vitest no frontend.

**Spec:** `docs/superpowers/specs/2026-07-31-transporte-costura-navegacao-design.md`

## Global Constraints

- Código, comentários, docs e mensagens de commit em **português (pt-BR)**.
- **Não rodar `npm run lint`** — o projeto não tem ESLint e `next lint` trava.
- `cd frontend && npx tsc --noEmit` é **obrigatório** antes de commitar mexida no frontend.
- Backend roda por bind-mount: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest ...`
  valida o código da branch sem rebuild. `PYTEST_DB_HOST=db` é obrigatório.
- Suíte de backend verde = **`2 failed, N passed`** com exatamente
  `test_jwt_compat.py::test_emitted_token_has_required_claims` e
  `test_pr5a_dashboard_servicos.py::test_http_dashboard_com_perm_acessa`. Qualquer outra falha é
  regressão.
- Branch: `feat/transporte-costura-navegacao`, já criada, com a spec commitada em `033b5ab`.
- **Nenhuma migration, nenhuma permissão nova, nenhuma transação nova.** Tudo reusa
  `transporte_regulado`. Se a tarefa parecer pedir uma dessas, pare — saiu do escopo.
- Nenhuma rota de topo nova: `transporte-regulado` já está na regex do `nginx/default.conf`.

## Estrutura de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `backend/app/routers/transporte_regulado.py` | ordem de declaração das rotas de vistoria | 1 |
| `backend/tests/test_transporte_regulado_vistoria.py` | ganha o primeiro teste **HTTP** do módulo | 1 |
| `frontend/lib/menus/transporte.ts` | itens de menu do módulo | 2 |
| `frontend/__tests__/menus.test.tsx` | tabela `PERMISSOES_ESPERADAS` + alcance do menu | 2 |
| `frontend/lib/transporte-hub.ts` | **novo** — os cards do hub, como dado | 3 |
| `frontend/app/(app)/transporte-regulado/page.tsx` | só renderiza; consome os cards de `lib/` | 3 |
| `frontend/__tests__/transporte-hub.test.tsx` | **novo** — invariantes dos cards | 3 |

Por que `lib/transporte-hub.ts` existe: os cards precisam ser testados como dado, e importar um
`page.tsx` com `"use client"` e `next/link` dentro do vitest é frágil sem ganho nenhum. Separar dado
de renderização também deixa o `page.tsx` com uma responsabilidade só. Fica ao lado de `lib/menus/`
e `lib/modulos.ts`, que é onde a F2 pôs a navegação como dado.

---

## Task 1: Backend — `/vistorias/vencidas` alcançável

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py:643-699`
- Test: `backend/tests/test_transporte_regulado_vistoria.py`

**Interfaces:**
- Consumes: nada de tarefas anteriores.
- Produces: nada que tarefas posteriores usem. Tarefa independente das outras duas.

**Contexto que o implementador não tem:** o FastAPI casa rotas na **ordem de declaração**. Hoje
`@vistorias_router.get("/{vistoria_id}")` está na linha 643 e `@vistorias_router.get("/vencidas")` na
681. A requisição para `.../vistorias/vencidas` casa primeiro com `/{vistoria_id}`, falha ao validar
`vistoria_id: int` e devolve **422** — nunca alcança o handler de vencidas. Os dois testes de
vencidas que já existem no arquivo chamam `tr_svc.listar_vistorias_vencidas` **direto no service**, e
por isso ficam verdes com o endpoint morto.

O teste precisa contratar o módulo `transporte` para o tenant: `provisionar_tenant` não contrata
nada, e a transação `transporte_regulado` pertence ao módulo `transporte`
(`app/cli/seed_bootstrap.py::MODULO_TRANSACOES`). Sem contratar, o gate devolve 403 — inclusive para
super-usuário, que é deliberado.

- [ ] **Step 1: Acrescentar os imports que o teste HTTP precisa**

No topo de `backend/tests/test_transporte_regulado_vistoria.py`, o bloco de imports hoje traz
`from sqlalchemy import text`. Deixe-o assim:

```python
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from app.main import app
from app.models import Usuario
from app.models import usuario as user_models
from app.schemas.transporte_regulado import (
    PermissionarioCreate,
    VeiculoReguladoCreate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaRenovarInput,
    VeiculoVistoriaUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
```

`user_models` já era importado e continua em uso pelo resto do arquivo — não remova.

- [ ] **Step 2: Acrescentar o helper de autenticação, ao lado dos outros helpers do arquivo**

Logo depois de `_usuario(...)`, no bloco de helpers do topo:

```python
def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Emula usuário autenticado por dependency_overrides.

    Mesmo padrão de test_permissoes_modulo.py::_as_user. Existe porque este
    arquivo era inteiramente de service e não tinha harness de HTTP.
    """

    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup
```

- [ ] **Step 3: Escrever o teste que falha**

No fim de `backend/tests/test_transporte_regulado_vistoria.py`:

```python
@pytest.mark.asyncio
async def test_http_vencidas_nao_e_engolida_por_vistoria_id(admin_engine):
    """A rota /vencidas tem de ser alcançável por HTTP, não só pelo service.

    O FastAPI casa rotas na ordem de declaração. Com `/{vistoria_id}: int`
    declarada antes, esta requisição batia nela, falhava a validação do int e
    voltava 422 sem nunca chegar no handler. Os dois testes de vencidas acima
    chamam o service direto — endpoint morto, service verde.
    """
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        veiculo = await _veiculo(admin_engine, tenant.id)
        auditor_id = await _usuario(admin_engine, tenant.id)

        ontem = datetime.utcnow().date() - timedelta(days=1)
        async with _sm(admin_engine)() as s:
            vencida = await tr_svc.criar_vistoria(
                s, tenant_id=tenant.id, veiculo_id=veiculo.id, auditor_id=auditor_id,
                payload=VeiculoVistoriaCreate(
                    resultado="aprovado",
                    parecer="Vistoria que venceu ontem.",
                    data_vistoria=datetime.combine(ontem, datetime.min.time()),
                    data_validade=ontem,
                ),
            )

        async with _sm(admin_engine)() as s:
            su_id = int((await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                {"t": tenant.id},
            )).scalar_one())

        _as_user(admin_engine, su_id, tenant.id, tenant.slug)()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                f"/api/v2/transporte-regulado/veiculos/{veiculo.id}/vistorias/vencidas"
            )

        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()["items"]] == [vencida.id]
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
```

- [ ] **Step 4: Rodar e confirmar que falha pelo motivo certo**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend \
  pytest tests/test_transporte_regulado_vistoria.py::test_http_vencidas_nao_e_engolida_por_vistoria_id -v
```

Esperado: **FAIL** com `assert 422 == 200`. Se falhar com 403, o `contratar` não pegou. Se falhar
com 404, o veículo ou a vistoria não foram criados. Só 422 confirma o bug que estamos consertando —
qualquer outro código significa que o teste está errado, não o router.

- [ ] **Step 5: Mover a declaração de `/vencidas` para antes de `/{vistoria_id}`**

Em `backend/app/routers/transporte_regulado.py`, recorte o bloco inteiro que hoje começa na linha
681 (`@vistorias_router.get("/vencidas", ...)` até o `)` que fecha o `return Paginated(...)`) e cole-o
**imediatamente antes** de `@vistorias_router.get("/{vistoria_id}", ...)`, hoje na linha 643. O corpo
não muda em nada — só a posição.

Acrescente, logo acima do decorador movido, o comentário que impede a regressão:

```python
# ORDEM IMPORTA: precisa vir antes de `/{vistoria_id}`. O FastAPI casa rotas na
# ordem de declaração, e `/{vistoria_id}: int` engole "vencidas" e devolve 422.
# Travado por test_http_vencidas_nao_e_engolida_por_vistoria_id.
@vistorias_router.get("/vencidas", response_model=Paginated[VeiculoVistoriaOut])
```

- [ ] **Step 6: Rodar o teste e confirmar que passa**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend \
  pytest tests/test_transporte_regulado_vistoria.py::test_http_vencidas_nao_e_engolida_por_vistoria_id -v
```

Esperado: **PASS**.

- [ ] **Step 7: Rodar o arquivo inteiro, para garantir que mover a rota não quebrou vizinha**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend \
  pytest tests/test_transporte_regulado_vistoria.py -q
```

Esperado: todos verdes.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/transporte_regulado.py backend/tests/test_transporte_regulado_vistoria.py
git commit -m "fix(transporte): /vistorias/vencidas deixa de ser engolida por /{vistoria_id}"
```

---

## Task 2: Menu do módulo alcança Alvarás e Relatórios

**Files:**
- Modify: `frontend/lib/menus/transporte.ts`
- Test: `frontend/__tests__/menus.test.tsx:32-60` (tabela) e um `it` novo

**Interfaces:**
- Consumes: nada da Task 1.
- Produces: os dois hrefs `/transporte-regulado/alvaras` e `/transporte-regulado/relatorio` passam a
  existir no menu do módulo `transporte`. A Task 3 depende disso — um dos testes do hub exige que
  todo card pronto esteja no menu.

**Contexto:** o `CommandPalette` (Ctrl+K) e a Sidebar consomem os dois de `lib/menus`. Acrescentar
aqui resolve os dois lugares; era esse o ponto da F2. A rota de relatório é **singular**
(`/transporte-regulado/relatorio`) — o plural `/relatorios` pertence ao protocolo.

- [ ] **Step 1: Escrever o teste que falha**

No fim do `describe("split dos menus", ...)` em `frontend/__tests__/menus.test.tsx`, antes do `});`
que fecha o describe:

```tsx
  it("o menu do transporte alcança alvarás e relatórios", () => {
    // P1–P4 entregaram estas duas telas e ninguém as ligou à navegação: por
    // meses só se chegava nelas digitando a URL. Este teste é o que impede
    // que uma tela entregue volte a ficar invisível.
    const menu = menuDoModulo("transporte");
    expect(menu).not.toBeNull();
    const doTransporte = hrefs(menu!.grupos.flatMap((g) => g.items));
    expect(doTransporte).toContain("/transporte-regulado/alvaras");
    expect(doTransporte).toContain("/transporte-regulado/relatorio");
  });
```

`menuDoModulo` e `hrefs` já estão importados/definidos no arquivo — não redeclare.

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
cd frontend && npx vitest run __tests__/menus.test.tsx
```

Esperado: **FAIL** no teste novo, `expected [...] to contain '/transporte-regulado/alvaras'`.

- [ ] **Step 3: Acrescentar os dois itens ao menu**

`frontend/lib/menus/transporte.ts` — troque a linha de import e acrescente os dois itens no fim do
array `items`, depois de Veículos:

```ts
import { BarChart3, Building2, Bus, Car, IdCard, ScrollText } from "lucide-react";
```

```ts
        {
          label: "Alvarás",
          href: "/transporte-regulado/alvaras",
          icon: ScrollText,
          perm: "transporte_regulado",
        },
        {
          label: "Relatórios",
          href: "/transporte-regulado/relatorio",
          icon: BarChart3,
          perm: "transporte_regulado",
        },
```

A ordem final do grupo fica: hub, Permissionários, Empresas, Veículos, Alvarás, Relatórios — cadastro,
depois operação, depois análise.

- [ ] **Step 4: Rodar e ver o teste novo passar e outro quebrar**

```bash
cd frontend && npx vitest run __tests__/menus.test.tsx
```

Esperado: o teste novo **PASSA**, e agora falha
`perm/anyOf de cada item bate com a tabela original` com duas divergências
`sem entrada na tabela PERMISSOES_ESPERADAS`. Isso é o comportamento correto da guarda: ela exige
que toda entrada de menu tenha `perm` declarado explicitamente numa tabela independente.

- [ ] **Step 5: Declarar as permissões esperadas**

Em `frontend/__tests__/menus.test.tsx`, na tabela `PERMISSOES_ESPERADAS`, logo depois da linha de
`"/transporte-regulado/veiculos"`:

```tsx
  "/transporte-regulado/alvaras": { perm: "transporte_regulado" },
  "/transporte-regulado/relatorio": { perm: "transporte_regulado" },
```

- [ ] **Step 6: Rodar o arquivo inteiro**

```bash
cd frontend && npx vitest run __tests__/menus.test.tsx
```

Esperado: **todos PASS**.

- [ ] **Step 7: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sem saída (sucesso).

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/menus/transporte.ts frontend/__tests__/menus.test.tsx
git commit -m "feat(transporte): menu do modulo alcanca alvaras e relatorios"
```

---

## Task 3: Hub do módulo diz a verdade

**Files:**
- Create: `frontend/lib/transporte-hub.ts`
- Create: `frontend/__tests__/transporte-hub.test.tsx`
- Modify: `frontend/app/(app)/transporte-regulado/page.tsx:21-58`

**Interfaces:**
- Consumes: da Task 2, os hrefs `/transporte-regulado/alvaras` e `/transporte-regulado/relatorio` já
  presentes no menu do módulo `transporte`. **A Task 3 não passa sem a Task 2** — o teste
  "todo card pronto está no menu" falha.
- Produces: `frontend/lib/transporte-hub.ts` exportando
  `export interface HubCard { href?: string; icon: React.ComponentType<{ className?: string }>; title: string; desc: string; ready?: boolean }`
  e `export const CARDS: HubCard[]`.

**Contexto:** hoje o hub marca Documentos, Vistorias, Alvarás e Relatórios como "em estruturação"
sem `href`. Alvarás e Relatórios têm tela pronta; Documentos e Vistorias **não são destinos** — no
backend só existem aninhados sob um veículo, sem listagem transversal, e no frontend são seções de
`veiculos/[id]/page.tsx`. Por isso os dois cards saem em vez de ganharem link.

- [ ] **Step 1: Escrever os testes primeiro — eles devem falhar por módulo inexistente**

Crie `frontend/__tests__/transporte-hub.test.tsx`:

```tsx
/**
 * O hub é a porta do módulo. Card entregue e não ligado — ou ligado e marcado
 * como não-pronto — é exatamente como Alvarás e Relatórios ficaram invisíveis
 * por quatro fases, com backend, tela e testes todos verdes.
 */
import { describe, expect, it } from "vitest";

import { menuDoModulo } from "@/lib/menus";
import type { NavItem } from "@/lib/menus/tipos";
import { moduloDoPathname } from "@/lib/modulos";
import { CARDS } from "@/lib/transporte-hub";

function hrefs(items: NavItem[]): string[] {
  return items.flatMap((i) => [i.href, ...(i.children ? hrefs(i.children) : [])]);
}

describe("hub do transporte regulado", () => {
  it("todo card pronto tem href", () => {
    expect(CARDS.filter((c) => c.ready && !c.href).map((c) => c.title)).toEqual([]);
  });

  it("nenhum card com href fica escondido como não-pronto", () => {
    expect(CARDS.filter((c) => c.href && !c.ready).map((c) => c.title)).toEqual([]);
  });

  it("todo card pronto aponta para rota do próprio módulo", () => {
    const fora = CARDS.filter((c) => c.ready && c.href)
      .filter((c) => moduloDoPathname(c.href!) !== "transporte")
      .map((c) => c.title);
    expect(fora).toEqual([]);
  });

  it("todo card pronto está no menu do módulo", () => {
    // Hub e menu são duas listas da mesma navegação. Divergir significa que a
    // tela existe num lugar e some no outro — o sintoma é o usuário achar por
    // um caminho e não achar pelo outro.
    const menu = menuDoModulo("transporte");
    expect(menu).not.toBeNull();
    const doMenu = new Set(hrefs(menu!.grupos.flatMap((g) => g.items)));
    const foraDoMenu = CARDS.filter((c) => c.ready && c.href)
      .filter((c) => !doMenu.has(c.href!))
      .map((c) => c.title);
    expect(foraDoMenu).toEqual([]);
  });

  it("os três cards não entregues seguem sem href", () => {
    // Recadastramento (P5), Rotas e Linhas (P6) e Ocorrências (P7) ainda não
    // existem. Card tracejado é honesto; card tracejado sobre tela pronta, não.
    const semHref = CARDS.filter((c) => !c.ready).map((c) => c.title);
    expect(semHref).toEqual(["Recadastramento", "Rotas e Linhas", "Ocorrências"]);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falham pelo motivo certo**

```bash
cd frontend && npx vitest run __tests__/transporte-hub.test.tsx
```

Esperado: **FAIL** na resolução do import — `Failed to resolve import "@/lib/transporte-hub"` ou
equivalente. O módulo ainda não existe; é essa a falha que se espera. Se falhar por outro motivo,
pare e investigue antes de criar o módulo.

- [ ] **Step 3: Criar o módulo de dados dos cards**

Crie `frontend/lib/transporte-hub.ts` com exatamente:

```ts
import {
  AlertOctagon,
  BarChart3,
  Building2,
  Car,
  IdCard,
  RefreshCw,
  Route,
  ScrollText,
} from "lucide-react";
import type React from "react";

export interface HubCard {
  href?: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  ready?: boolean;
}

/**
 * Cards do hub do transporte regulado — dado, não JSX, para que as invariantes
 * possam ser testadas sem renderizar a página.
 *
 * Card `ready` sem `href` é o defeito que deixou P1–P4 invisíveis: tela
 * entregue, sem caminho até ela. `__tests__/transporte-hub.test.tsx` trava isso.
 *
 * Documentos, vistorias e avaliações NÃO aparecem aqui de propósito: no backend
 * só existem aninhados sob um veículo (`/veiculos/{id}/vistorias`), sem listagem
 * transversal, e no frontend são seções do detalhe do veículo. Não são destinos.
 */
export const CARDS: HubCard[] = [
  {
    href: "/transporte-regulado/permissionarios",
    icon: IdCard,
    title: "Permissionários",
    desc: "Cadastro de permissionários: dados pessoais, CNH, tipo de serviço, permissão e situação.",
    ready: true,
  },
  {
    href: "/transporte-regulado/empresas",
    icon: Building2,
    title: "Empresas",
    desc: "Empresas e operadoras reguladas: dados cadastrais, endereço, autorização e situação.",
    ready: true,
  },
  {
    href: "/transporte-regulado/veiculos",
    icon: Car,
    title: "Veículos",
    desc: "Veículos regulados, com documentos, avaliações e vistorias no detalhe de cada um.",
    ready: true,
  },
  {
    href: "/transporte-regulado/alvaras",
    icon: ScrollText,
    title: "Alvarás",
    desc: "Alvarás e autorizações de operação, com documentos, responsáveis e renovação.",
    ready: true,
  },
  {
    href: "/transporte-regulado/relatorio",
    icon: BarChart3,
    title: "Relatórios",
    desc: "KPIs e análise de alvarás regulados, com exportação.",
    ready: true,
  },
  { icon: RefreshCw, title: "Recadastramento", desc: "Campanhas e ciclos de recadastramento." },
  { icon: Route, title: "Rotas e Linhas", desc: "Rotas, linhas e localidades atendidas." },
  { icon: AlertOctagon, title: "Ocorrências", desc: "Ocorrências regulatórias e fiscalização." },
];
```

A descrição de Veículos muda de propósito: agora que os cards de Documentos e Vistorias saíram, é
esse card que precisa dizer onde eles foram parar.

- [ ] **Step 4: Rodar e confirmar que agora passam**

```bash
cd frontend && npx vitest run __tests__/transporte-hub.test.tsx
```

Esperado: **todos PASS**. Se `todo card pronto esta no menu` falhar, a Task 2 nao foi feita.

- [ ] **Step 5: Fazer a página consumir os cards de `lib/`**

Em `frontend/app/(app)/transporte-regulado/page.tsx`, remova a `interface HubCard` (linhas 21–27) e a
const `CARDS` (linhas 29–58), e ajuste os imports do topo. O arquivo passa a começar assim:

```tsx
"use client";

import { Bus } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";
import { CARDS } from "@/lib/transporte-hub";
```

`Bus` continua sendo usado no `PageHeader`; todos os outros ícones saem do import da página porque
agora vivem em `lib/transporte-hub.ts`. O corpo do componente (`export default function
TransporteReguladoHubPage`) **não muda em nada** — continua mapeando `CARDS`.

- [ ] **Step 6: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sem saída. **Não conte com o `tsc` para pegar ícone órfão** — `frontend/tsconfig.json`
não tem `noUnusedLocals`/`noUnusedParameters`, então import não usado não é erro de type-check.
Revise o import da página manualmente e remova o que sobrou.

- [ ] **Step 7: Rodar a suíte de frontend inteira**

```bash
cd frontend && npm test
```

Esperado: todos verdes, incluindo `menus.test.tsx` da Task 2.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/transporte-hub.ts frontend/__tests__/transporte-hub.test.tsx frontend/app/\(app\)/transporte-regulado/page.tsx
git commit -m "feat(transporte): hub liga alvaras e relatorios e para de anunciar o que nao e destino"
```

---

## Verificação final, antes de abrir o PR

- [ ] **Suíte de backend completa** (~10 min):

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q
```

Esperado: `2 failed, N passed`, e as duas são exatamente `test_jwt_compat` e
`test_pr5a_dashboard_servicos`. Qualquer terceira falha é regressão desta branch.

- [ ] **Frontend:**

```bash
cd frontend && npm test && npx tsc --noEmit
```

- [ ] **Conferir que a numeração das fases não foi contrariada:** os três cards tracejados devem ser
  Recadastramento (P5), Rotas e Linhas (P6) e Ocorrências (P7), nessa ordem.

- [ ] **Atualizar `docs/BACKLOG-PENDENCIAS.md`:** a seção 2.2 diz que P0–P4 estão "entregues e no
  ar". Acrescentar que a navegação até Alvarás e Relatórios só passou a existir nesta fatia, e que o
  endpoint `/vistorias/vencidas` estava morto até aqui — é o tipo de coisa que a próxima sessão não
  deve redescobrir.

## Fora de escopo — não faça, mesmo se parecer óbvio

- Telas transversais de vistorias/documentos (exigiriam endpoints novos).
- P5 (Recadastramento), P6 (Rotas e Linhas), P7 (Ocorrências).
- Prefixo `/m/<slug>` e redirects 308 — é a F3 da modularização.
- Trocar o `datetime.utcnow()` que o `DeprecationWarning` acusa no módulo. É real, é ruído em ~6 mil
  warnings da suíte, e não é desta fatia.

## Nota operacional sobre validar na tela

O contorno que faz o frontend rodar na máquina do Jorge — build no host pelo **PowerShell**
(`$env:NEXT_PUBLIC_API_URL = "/api/v2"; npm run build`) seguido de `docker cp` para dentro do
container — não sobrevive à recriação do container, e o container do frontend foi recriado em
2026-07-31. Ver o resultado no `:8090` vai exigir refazê-lo. Pelo Bash o MSYS converte a variável em
`C:/Program Files/Git/api/v2` e o bundle sai quebrado — tem de ser PowerShell. `tsc` e o vitest rodam
no host e não dependem de nada disso.

---

# Adendo de 2026-08-01 — Tasks 4 e 5

Dois defeitos pré-existentes em `main`, achados durante a execução e autorizados a entrar nesta
fatia. Ver o adendo do spec para a investigação completa. **Nenhum dos dois foi causado pelas
Tasks 1–3.**

---

## Task 4: Backend — as duas rotas de alvará engolidas, e uma guarda contra a terceira vez

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py` (ordem de declaração, rotas de alvará)
- Create: `backend/tests/test_guarda_ordem_rotas.py`

**Interfaces:**
- Consumes: nada das Tasks 1–3. A Task 1 consertou a mesma classe de defeito em outro sub-router; o
  padrão do comentário de guarda que ela deixou deve ser repetido aqui.
- Produces: nada que a Task 5 use. As duas tarefas são independentes.

**Contexto.** O FastAPI casa rotas na **ordem de declaração**. Em `alvaras_router`, `/{alvara_id}` é
declarada na linha 763, e depois dela vêm `/vencidos` (809) e `/relatorio` (842). Ambas têm um
segmento só, então `/{alvara_id}` as engole e a requisição morre em 422. Verificado na aplicação
real:

```
ENGOLIDA -> /alvaras/vencidos  => /alvaras/{alvara_id}
ENGOLIDA -> /alvaras/relatorio => /alvaras/{alvara_id}
OK          /alvaras/relatorio/kpis
OK          /alvaras/relatorio/export/csv
```

As duas de `/relatorio/...` sobrevivem porque têm dois segmentos e `{alvara_id}` casa um só.

- [ ] **Step 1: Escrever a guarda estrutural — ela deve falhar acusando as duas rotas**

Crie `backend/tests/test_guarda_ordem_rotas.py`:

```python
"""Guarda de ordem de declaração de rotas.

O FastAPI casa rotas na ordem em que foram declaradas. Uma rota de segmento
literal (`/vencidos`) declarada DEPOIS de uma paramétrica irmã (`/{alvara_id}`)
fica inalcançável: a paramétrica casa primeiro, a validação do tipo falha e a
resposta é 422 — sem nunca chegar no handler.

Esse defeito não aparece em teste de service, não aparece no type-check e não
aparece na leitura do arquivo: só aparece se alguém pedir a URL. Ele já ocorreu
TRÊS vezes neste repositório (vistorias/vencidas, alvaras/vencidos,
alvaras/relatorio). Esta guarda é a resposta a isso.
"""
from __future__ import annotations

import re

from app.main import app

# Rotas que sabidamente ficam à sombra de outra e cuja correção NÃO pertence a
# esta fatia. Entrada aqui é dívida registrada, não permissão: cada uma precisa
# de uma razão escrita ao lado. Lista vazia é o estado desejado.
SOMBREADAS_CONHECIDAS: set[tuple[str, str]] = set()


def _concretiza(caminho: str) -> str:
    """Troca cada `{param}` por `1` para obter uma URL concreta que a rota atende."""
    return re.sub(r"\{[^}]+\}", "1", caminho)


def rotas_sombreadas() -> set[tuple[str, str]]:
    """(método, caminho) de toda rota que outra, declarada antes, engole."""
    rotas = [
        r for r in app.routes
        if getattr(r, "path_regex", None) is not None
        and getattr(r, "path", "").startswith("/api/v2")
    ]
    sombreadas: set[tuple[str, str]] = set()
    for rota in rotas:
        alvo = _concretiza(rota.path)
        for metodo in getattr(rota, "methods", set()):
            primeira = next(
                (
                    outra for outra in rotas
                    if metodo in getattr(outra, "methods", set())
                    and outra.path_regex.match(alvo)
                ),
                None,
            )
            if primeira is not None and primeira.path != rota.path:
                sombreadas.add((metodo, rota.path))
    return sombreadas


def test_nenhuma_rota_fica_a_sombra_de_outra():
    """Rota inalcançável é código morto que o CI reprova, não que produção descobre."""
    novas = rotas_sombreadas() - SOMBREADAS_CONHECIDAS
    assert not novas, (
        "Rotas inalcançáveis — outra declarada ANTES casa a mesma URL: "
        f"{sorted(novas)}. Mova a declaração de segmento literal para antes da "
        "paramétrica irmã, ou registre em SOMBREADAS_CONHECIDAS com a razão."
    )


def test_allowlist_nao_tem_entrada_obsoleta():
    """Allowlist que apodrece deixa de ser dívida registrada e vira ruído."""
    obsoletas = SOMBREADAS_CONHECIDAS - rotas_sombreadas()
    assert not obsoletas, (
        f"Entradas obsoletas em SOMBREADAS_CONHECIDAS: {sorted(obsoletas)}. "
        "A rota foi consertada ou removida — tire-a da lista."
    )
```

- [ ] **Step 2: Rodar e ler o que ela acusa — este passo é de investigação, não de conserto**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_ordem_rotas.py -q
```

Esperado: **FAIL**, listando pelo menos
`('GET', '/api/v2/transporte-regulado/alvaras/vencidos')` e
`('GET', '/api/v2/transporte-regulado/alvaras/relatorio')`.

**Anote a lista completa que ela imprimir.** Se aparecerem rotas de **outros** módulos (pagamentos,
protocolo, frota…), elas são dívida pré-existente e **não** são desta fatia: não as conserte.
Registre cada uma em `SOMBREADAS_CONHECIDAS` com um comentário de uma linha dizendo qual é e que a
correção está fora do escopo desta fatia, e **reporte a lista** no seu relatório — ela precisa ir
para o backlog.

- [ ] **Step 3: Mover as duas declarações de alvará**

Em `backend/app/routers/transporte_regulado.py`, recorte os blocos inteiros de
`@alvaras_router.get("/vencidos", ...)` (hoje na linha 809) e de
`@alvaras_router.get("/relatorio", ...)` (hoje na 842) — cada um do decorador até o fim do corpo da
função — e cole-os **imediatamente antes** de `@alvaras_router.get("/{alvara_id}", ...)`, hoje na
linha 763. Os corpos não mudam em nada.

Acrescente, acima do primeiro dos dois blocos movidos, o comentário de guarda:

```python
# ORDEM IMPORTA: estas rotas de segmento literal precisam vir antes de
# `/{alvara_id}`. O FastAPI casa na ordem de declaração, e a paramétrica engole
# "vencidos" e "relatorio", devolvendo 422 sem chegar no handler.
# Travado por tests/test_guarda_ordem_rotas.py.
```

Não mexa em `/relatorio/kpis` nem em `/relatorio/export/csv`: têm dois segmentos, nunca foram
engolidas, e movê-las é risco sem ganho.

- [ ] **Step 4: Rodar a guarda de novo**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_ordem_rotas.py -q
```

Esperado: **2 passed**.

- [ ] **Step 5: Confirmar as quatro rotas na aplicação real**

```
docker exec aprimora-py-backend python -c "
from app.main import app
for p in ['/api/v2/transporte-regulado/alvaras/vencidos',
          '/api/v2/transporte-regulado/alvaras/relatorio',
          '/api/v2/transporte-regulado/alvaras/relatorio/kpis',
          '/api/v2/transporte-regulado/alvaras/relatorio/export/csv']:
    for r in app.routes:
        if getattr(r,'path_regex',None) and r.path_regex.match(p) and 'GET' in getattr(r,'methods',set()):
            print(p, '=>', r.path); break
"
```

Esperado: cada caminho casando com **ele mesmo**, nenhum com `{alvara_id}`.

- [ ] **Step 6: Rodar os testes de alvará que já existem, para garantir que mover não quebrou vizinha**

```
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_regulado_alvara.py tests/test_transporte_p4_relatorio.py -q
```

Esperado: todos verdes.

- [ ] **Step 7: Commit**

```
git add backend/app/routers/transporte_regulado.py backend/tests/test_guarda_ordem_rotas.py
git commit -m "fix(transporte): alvaras/vencidos e alvaras/relatorio saem da sombra de /{alvara_id}"
```

---

## Task 5: Frontend — o contrato de paginação para de mentir

**Files:**
- Modify: `frontend/lib/api.ts` (12 métodos)
- Modify: as telas que consomem esses métodos (o `tsc` dirá exatamente quais)

**Interfaces:**
- Consumes: nada das Tasks 1–4.
- Produces: os 12 métodos passam a devolver `Paginated<T>` em vez de `T[]`.

**Contexto.** O commit `628ca34` passou 13 endpoints do transporte a devolver `Paginated`
(`{items, total, page, page_size}`), e o `api.ts` continuou declarando array. Como `request<T>()`
faz cast sem validar, o `tsc` fica verde e o navegador estoura com
`TypeError: ….map is not a function`. Já está em `main` desde 2026-07-20.

O tipo `Paginated<T>` **já existe** em `frontend/lib/api.ts` e já é usado corretamente por
`/usuarios`, `/unidades-trabalho` e `/processos`; as telas desses módulos consomem `data?.items.map`.
Siga esse precedente — não invente forma nova, e **não** desembrulhe dentro do `api.ts`: manter o
tipo honesto é o que faz o `tsc` virar a guarda contra a próxima ocorrência.

**Teto assumido, e que você deve deixar escrito no relatório:** estas telas não têm UI de paginação
e o backend usa `page_size` padrão 50. Depois do conserto elas exibem **até 50 registros**. Não é
regressão — hoje exibem zero ou estouram — mas é teto real. Não construa paginação: está fora do
escopo.

- [ ] **Step 1: Trocar os 12 tipos em `frontend/lib/api.ts`**

Em cada método, troque `request<X[]>` por `request<Paginated<X>>`, sem mudar caminho nem parâmetros:

| Linha | Método | De | Para |
|---|---|---|---|
| 2538 | `permissionarios.list` | `Permissionario[]` | `Paginated<Permissionario>` |
| 2570 | `empresas.list` | `Empresa[]` | `Paginated<Empresa>` |
| 2606 | `veiculosRegulados.list` | `VeiculoRegulado[]` | `Paginated<VeiculoRegulado>` |
| 2636 | `veiculosRegulados.documentos.list` | `VeiculoDocumentoTR[]` | `Paginated<VeiculoDocumentoTR>` |
| 2656 | `veiculosRegulados.avaliacoes.list` | `VeiculoAvaliacao[]` | `Paginated<VeiculoAvaliacao>` |
| 2676 | `veiculosRegulados.vistorias.list` | `VeiculoVistoriaTR[]` | `Paginated<VeiculoVistoriaTR>` |
| 2694 | `veiculosRegulados.vistorias.listarVencidas` | `VeiculoVistoriaTR[]` | `Paginated<VeiculoVistoriaTR>` |
| 2704 | `alvaras.list` | `Alvara[]` | `Paginated<Alvara>` |
| 2720 | `alvaras.listVencidos` | `Alvara[]` | `Paginated<Alvara>` |
| 2728 | `alvaras.documentos.list` | `AlvaraDocumento[]` | `Paginated<AlvaraDocumento>` |
| 2748 | `alvaras.responsaveis.list` | `AlvaraResponsavel[]` | `Paginated<AlvaraResponsavel>` |
| 2801 | `alvaras.veiculos.list` | `AlvaraVeiculo[]` | `Paginated<AlvaraVeiculo>` |

**Confira contra o backend antes de aceitar a tabela como completa.** O router declara
`response_model=Paginated[...]` em **13** endpoints:

```
grep -n "response_model=Paginated\[" backend/app/routers/transporte_regulado.py
```

Se sobrar endpoint `Paginated` do backend cujo método no `api.ts` ainda declare array, conserte-o
também e diga no relatório. Se algum dos 13 não tiver método no `api.ts`, também diga — não crie
método novo.

- [ ] **Step 2: Rodar o type-check e deixar que ele liste os consumidores quebrados**

```
cd frontend && npx tsc --noEmit
```

Esperado: **muitos erros**, do tipo "Property 'map' does not exist on type 'Paginated<X>'" ou
"Property 'length' does not exist…". **Essa lista é a sua lista de trabalho** — é exatamente o
conjunto de lugares onde o código estava errado em silêncio. Copie-a para o relatório antes de
consertar: é a evidência do alcance do defeito.

- [ ] **Step 3: Consertar cada consumidor que o `tsc` apontou**

A transformação é mecânica e segue o precedente de `app/(app)/usuarios/page.tsx:196`:

- `q.data?.map(...)` → `q.data?.items.map(...)`
- `q.data?.find(...)` → `q.data?.items.find(...)`
- `(q.data?.length ?? 0)` → `(q.data?.items.length ?? 0)`
- `q.data?.filter(...)` → `q.data?.items.filter(...)`

Os arquivos que a investigação já identificou como consumidores — a lista do `tsc` é que manda, esta
serve só para você conferir se não sobrou nada:

- `frontend/app/(app)/transporte-regulado/veiculos/page.tsx`
- `frontend/app/(app)/transporte-regulado/veiculos/[id]/page.tsx`
- `frontend/app/(app)/transporte-regulado/permissionarios/page.tsx`
- `frontend/app/(app)/transporte-regulado/empresas/page.tsx`
- `frontend/app/(app)/transporte-regulado/alvaras/page.tsx`
- `frontend/app/(app)/transporte-regulado/alvaras/[id]/page.tsx`
- `frontend/components/transporte-regulado/alvara-veiculos-modal.tsx`

**Não** aproveite a passagem para refatorar, renomear ou "melhorar" essas telas. A mudança é só
`data` → `data.items`.

**Atenção ao sintoma silencioso:** onde havia `(q.data?.length ?? 0) === 0` decidindo mostrar estado
vazio, o `?.` mascarava o defeito — a tela dizia "nenhum registro" com registros no banco. Depois da
troca para `.items.length` isso passa a funcionar. Confira que cada estado vazio que você tocar
continua fazendo sentido.

- [ ] **Step 4: Type-check limpo**

```
cd frontend && npx tsc --noEmit
```

Esperado: **sem saída nenhuma**.

- [ ] **Step 5: Suíte de frontend inteira**

```
cd frontend && npm test
```

Esperado: todos verdes, incluindo os testes das Tasks 2 e 3.

- [ ] **Step 6: Commit**

```
git add frontend/lib/api.ts frontend/app frontend/components
git commit -m "fix(transporte): api.ts para de declarar array onde o backend devolve Paginated"
```

---

## Verificação final revisada (substitui a seção anterior)

- [ ] Suíte de backend completa: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q`
      → `2 failed, N passed`, e as duas são as pré-existentes conhecidas.
- [ ] `cd frontend && npm test && npx tsc --noEmit`
- [ ] `docs/BACKLOG-PENDENCIAS.md`: registrar na seção 2.2 (a) que a navegação até Alvarás e
      Relatórios só passou a existir nesta fatia; (b) o teto de 50 registros das telas do transporte,
      que segue aberto e depende de decisão de UI de paginação; (c) as rotas sombreadas de outros
      módulos que a guarda da Task 4 tiver encontrado, se houver.
