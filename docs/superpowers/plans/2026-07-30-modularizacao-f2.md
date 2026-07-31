# Modularização F2 — launcher, menus por módulo e switcher

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recomendado) ou superpowers:executing-plans para implementar task por task. Os passos usam
> checkbox (`- [ ]`).

**Goal:** Dar ao usuário a tela de seleção de módulos e um menu que mostra só o módulo em que ele
está, sem mudar nenhuma URL do sistema.

**Architecture:** O catálogo e o enforcement já existem (F1, em `main` desde `c4dcb53`).
`GET /api/v2/modulos/me` já devolve os módulos contratados ∩ permitidos com slug, nome, ícone e
ordem. Esta fatia é **só frontend**: o `NAV` monolítico da `Sidebar` vira seis arquivos de menu, a
`Sidebar` passa a receber qual módulo renderizar, nasce a tela `/modulos` e um switcher no Header. O
módulo ativo é derivado do **pathname atual** — ver a resolução abaixo.

**Tech Stack:** Next.js 15 App Router, React 19, Tailwind, vitest, lucide-react.

---

## Resolução de uma tensão do spec (2026-07-30)

O spec §9 diz que a F2 entrega "shell `m/[modulo]`" **e** que as URLs continuam as antigas. O §6
fundamenta esse shell em "o módulo ativo está na URL — `params.modulo` chega no `layout.tsx`". As
duas coisas não podem valer na mesma fatia: `params.modulo` só existe depois que a F3 move as rotas
para `/m/<slug>/…`.

**Decisão:** nesta fatia o módulo ativo é derivado do **pathname atual**, por um mapa
`prefixo → slug` (`lib/modulos.ts`), construído a partir do apêndice §12 do spec. O segmento
`app/(app)/m/[modulo]/` **não** é criado aqui — nasce na F3, junto com as rotas e os redirects 308.
O mapa não é trabalho jogado fora: a F3 precisa dele para gerar os redirects e para o guard.

Consequência: `<Sidebar modulo={slug} />` recebe o slug derivado, e a F3 troca a origem do slug de
"derivado do pathname" para "lido de `params`" sem tocar no resto.

**Também deliberadamente fora desta fatia:** o cookie de "último módulo" que o §6 menciona como
conveniência para pular o launcher no próximo login. Ele briga com o launcher ser "porta de entrada"
e só faz sentido depois de o Jorge ver a tela em uso e decidir se pular é desejável. Não implementar
sem pedir.

---

## Global Constraints

- **pt-BR** em tudo: código, comentários, textos de interface, mensagens de commit.
- **Nenhuma URL muda nesta fatia.** Não mover arquivo de rota, não criar redirect, não tocar
  `frontend/middleware.ts`. Isso é F3. Um diff que mexa nesse arquivo está fora de escopo por
  construção.
  - **Correção (2026-07-30, pós-revisão da Task 4):** a restrição acima NÃO cobre
    `nginx/default.conf`. O proibido é o roteamento `/m/<slug>` e os redirects 308 (isso sim é F3).
    Registrar rota de topo nova na regex de páginas migradas (`location ~ ^/(...)`) é obrigação de
    qualquer fatia que crie rota nova — está no `CLAUDE.md`, "Adicionando um módulo", item 3. A
    Task 4 foi instruída a não tocar o nginx e isso quase deixou `/modulos` invisível atrás do
    `:8090`; corrigido acrescentando `modulos` à regex na mesma leva. Fatias futuras que criem rota
    de topo devem editar essa regex como parte normal do trabalho, não como exceção.
- `cd frontend && npx tsc --noEmit` → **0 erros**, obrigatório antes de cada commit.
- Testes: `cd frontend && npx vitest run <arquivo>` (vitest roda no host; a imagem `runner` é
  standalone e não tem devDeps).
- **NÃO rodar `npm run lint`** — o projeto não tem ESLint configurado e `next lint` trava.
- **NÃO rodar `docker compose build` nem `up --build`.** O antivírus desta máquina intercepta HTTPS
  e o build de imagem morre em `npm install`. Para ver a tela no navegador, o caminho é: build no
  host **pelo PowerShell** (`$env:NEXT_PUBLIC_API_URL = "/api/v2"; npm run build`) e `docker cp`
  para dentro do container. Pelo Bash a variável é convertida em
  `C:/Program Files/Git/api/v2` e o bundle sai quebrado — já aconteceu.
- A **poda por permissão** da Sidebar (`perm` / `anyOf`) permanece intacta. O menu esconde o que o
  usuário não pode; o módulo escolhe *qual conjunto* de itens é candidato.
- **O guard de módulo no frontend é UX, não segurança.** A barreira real é o gate de contratação no
  backend (F1). Nenhum teste desta fatia deve afirmar que o frontend protege dado.
- Ao enviar formulário, normalizar `""` → `null` em campos opcionais.

---

## File Structure

**Criar:**

| Arquivo | Responsabilidade |
|---|---|
| `frontend/lib/menus/tipos.ts` | `NavItem`, `NavGroup`, `MenuModulo` — hoje inline na Sidebar |
| `frontend/lib/menus/protocolo.ts` | menu do protocolo (grupos Processos, Protocolo, Cadastros) |
| `frontend/lib/menus/pagamentos.ts` | menu de pagamentos |
| `frontend/lib/menus/frota.ts` | menu de frota |
| `frontend/lib/menus/transporte.ts` | menu de transporte regulado |
| `frontend/lib/menus/administracao.ts` | menu de administração (+ Organograma, que sai de "Geral") |
| `frontend/lib/menus/comum.ts` | itens transversais (Início, Dashboard) — sem módulo |
| `frontend/lib/menus/index.ts` | `MENUS: Record<string, MenuModulo>` e `menuDoModulo(slug)` |
| `frontend/lib/modulos.ts` | `moduloDoPathname(path)`, `ROTA_MODULO`, `ICONES_MODULO` |
| `frontend/app/(launcher)/layout.tsx` | layout do launcher — autenticado, **sem** Sidebar |
| `frontend/app/(launcher)/modulos/page.tsx` | a tela de seleção |
| `frontend/components/ModuloSwitcher.tsx` | dropdown de troca de módulo no Header |
| `frontend/__tests__/menus.test.tsx` | guarda estrutural: nada se perdeu no split |
| `frontend/__tests__/modulos-pathname.test.tsx` | o mapa pathname → módulo |
| `frontend/__tests__/Launcher.test.tsx` | a tela |

**Modificar:** `frontend/components/Sidebar.tsx` (vira renderizador), `frontend/app/(app)/layout.tsx`
(deriva o módulo e repassa), `frontend/components/Header.tsx` (recebe o switcher),
`frontend/app/login/page.tsx` (passa a mandar para `/modulos`),
`frontend/app/(plataforma)/admin/tenants/[id]/page.tsx` (aba Módulos).

---

### Task 1: `lib/menus/` — o `NAV` monolítico vira seis arquivos

**Files:**
- Create: `frontend/lib/menus/tipos.ts`, `.../protocolo.ts`, `.../pagamentos.ts`, `.../frota.ts`,
  `.../transporte.ts`, `.../administracao.ts`, `.../comum.ts`, `.../index.ts`
- Modify: `frontend/components/Sidebar.tsx:52-213` (remove `interface NavItem`, `interface NavGroup`
  e a constante `NAV`; passa a importar)
- Test: `frontend/__tests__/menus.test.tsx`

**Interfaces:**
- Produces: `MenuModulo { slug, raiz, grupos }`, `MENUS`, `menuDoModulo(slug): MenuModulo | null`
- Consumes: nada de tasks anteriores — é a primeira

**O split é um MOVE, não uma reescrita.** Copie os objetos de grupo **verbatim** de
`Sidebar.tsx`, incluindo `perm`, `anyOf`, `children`, `defaultOpen` e os imports de ícone que cada
um usa. Mapa exato de origem → destino:

| Origem em `Sidebar.tsx` | Destino |
|---|---|
| linha 71 grupo `"Geral"` → itens `Início` (`/home`) e `Dashboard` (`/dashboard`) | `comum.ts` |
| linha 71 grupo `"Geral"` → item `Organograma` (`/organograma`) | `administracao.ts` (§12: estrutura organizacional é matéria de administração) |
| linha 80 grupo `"Processos"` | `protocolo.ts` |
| linha 90 grupo `"Protocolo"` | `protocolo.ts` |
| linha 115 grupo `"Cadastros"` | `protocolo.ts` (§12: os catálogos de localização vão para protocolo — quem os consome é o endereço do manifestante) |
| linha 131 grupo `"Frota"` | `frota.ts` |
| linha 141 grupo `"Transporte Regulado"` | `transporte.ts` |
| linha 166 grupo `"Pagamentos"` | `pagamentos.ts` |
| linha 202 grupo `"Administração"` | `administracao.ts` |

- [ ] **Passo 1: Escrever a guarda estrutural (falha primeiro)**

`frontend/__tests__/menus.test.tsx`:

```tsx
/**
 * Guarda do split do menu. O NAV tinha 637 linhas num arquivo; o risco do split
 * não é escrever errado, é PERDER item no caminho — e item perdido não quebra
 * teste nenhum, só desaparece da tela de alguém.
 */
import { describe, expect, it } from "vitest";

import { MENUS, menuDoModulo } from "@/lib/menus";
import type { NavItem } from "@/lib/menus/tipos";
import { moduloDoPathname } from "@/lib/modulos";

/** Todos os hrefs de um menu, incluindo os de subitens. */
function hrefs(items: NavItem[]): string[] {
  return items.flatMap((i) => [i.href, ...(i.children ? hrefs(i.children) : [])]);
}

const TODOS = Object.values(MENUS).flatMap((m) => hrefs(m.grupos.flatMap((g) => g.items)));

describe("split dos menus", () => {
  it("não está vazio", () => {
    // Sem isto, todas as asserções abaixo passam vacuamente.
    expect(TODOS.length).toBeGreaterThan(40);
    expect(Object.keys(MENUS).sort()).toEqual([
      "administracao", "comum", "frota", "pagamentos", "protocolo", "transporte",
    ]);
  });

  it("nenhum href aparece em dois módulos", () => {
    const vistos = new Map<string, string>();
    const duplicados: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const antes = vistos.get(href);
        if (antes && antes !== slug) duplicados.push(`${href}: ${antes} e ${slug}`);
        vistos.set(href, slug);
      }
    }
    expect(duplicados).toEqual([]);
  });

  it("cada item está no módulo que o mapa de pathname aponta", () => {
    // Se um item foi para o arquivo errado, o menu do módulo A mostra tela do
    // módulo B — e na F3 o redirect vai jogar o usuário para fora do menu em
    // que ele acabou de clicar.
    const divergentes: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      if (slug === "comum") continue; // transversais não têm módulo
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const derivado = moduloDoPathname(href);
        if (derivado !== slug) divergentes.push(`${href}: arquivo=${slug} mapa=${derivado}`);
      }
    }
    expect(divergentes).toEqual([]);
  });

  it("todo módulo tem raiz navegável e ela pertence ao próprio módulo", () => {
    for (const [slug, menu] of Object.entries(MENUS)) {
      expect(menu.raiz, `${slug} sem raiz`).toMatch(/^\//);
      if (slug !== "comum") expect(moduloDoPathname(menu.raiz)).toBe(slug);
    }
  });

  it("menuDoModulo devolve null para slug desconhecido", () => {
    expect(menuDoModulo("nao-existe")).toBeNull();
  });
});
```

- [ ] **Passo 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run __tests__/menus.test.tsx
```

Esperado: FALHA ao resolver `@/lib/menus`.

- [ ] **Passo 3: `lib/menus/tipos.ts`**

```ts
/** Tipos do menu. Vieram de components/Sidebar.tsx, sem alteração de forma. */
import type React from "react";

export interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  perm?: string;
  anyOf?: string[];
  /** Subitens — vira um subgrupo colapsável (chevron) dentro do grupo pai. */
  children?: NavItem[];
}

export interface NavGroup {
  title: string;
  items: NavItem[];
  /** Estado inicial do grupo (antes da hidratação do localStorage). */
  defaultOpen?: boolean;
}

export interface MenuModulo {
  slug: string;
  /** Onde o launcher e o switcher entram. Nesta fatia é a URL ANTIGA. */
  raiz: string;
  grupos: NavGroup[];
}
```

- [ ] **Passo 4: Os seis arquivos de menu**

Cada um segue esta forma (exemplo real, `frota.ts` — copie o grupo da linha 131 da Sidebar
verbatim, com os ícones que ele usa):

```ts
import { Car, ClipboardList, IdCard, Truck } from "lucide-react";

import type { MenuModulo } from "./tipos";

export const menuFrota: MenuModulo = {
  slug: "frota",
  raiz: "/frotas",
  grupos: [
    {
      title: "Frota",
      defaultOpen: true,
      items: [
        { label: "Frota Pública", href: "/frotas", icon: Truck, perm: "frota" },
        { label: "Veículos", href: "/frotas/veiculos", icon: Car, perm: "frota" },
        { label: "Motoristas", href: "/frotas/motoristas", icon: IdCard, perm: "frota" },
        { label: "Solicitações", href: "/frotas/solicitacoes", icon: ClipboardList, perm: "frota" },
        // … o resto do grupo da linha 131, verbatim
      ],
    },
  ],
};
```

Raízes de cada módulo (é o destino do card no launcher):

| slug | `raiz` |
|---|---|
| `protocolo` | `/processos` |
| `pagamentos` | `/pagamentos` |
| `frota` | `/frotas` |
| `transporte` | `/transporte-regulado` |
| `administracao` | `/usuarios` |
| `comum` | `/home` |

- [ ] **Passo 5: `lib/menus/index.ts`**

```ts
import { menuAdministracao } from "./administracao";
import { menuComum } from "./comum";
import { menuFrota } from "./frota";
import { menuPagamentos } from "./pagamentos";
import { menuProtocolo } from "./protocolo";
import { menuTransporte } from "./transporte";
import type { MenuModulo } from "./tipos";

export type { MenuModulo, NavGroup, NavItem } from "./tipos";

/** slug do catálogo (aprimora_py.modulo.slug) → menu. */
export const MENUS: Record<string, MenuModulo> = {
  protocolo: menuProtocolo,
  pagamentos: menuPagamentos,
  frota: menuFrota,
  transporte: menuTransporte,
  administracao: menuAdministracao,
  comum: menuComum,
};

export function menuDoModulo(slug: string | null): MenuModulo | null {
  if (!slug) return null;
  return MENUS[slug] ?? null;
}
```

- [ ] **Passo 6: Tirar `NAV` da Sidebar**

Remover de `Sidebar.tsx` as linhas 52-213 (`interface NavItem`, `interface NavGroup`, `const NAV`) e
os imports de ícone que ficaram órfãos. Trocar por
`import { menuDoModulo, type NavGroup, type NavItem } from "@/lib/menus";`. **Não** mudar o
comportamento de renderização ainda — isso é a Task 3. Por ora, para o arquivo compilar, use
`const NAV: NavGroup[] = Object.values(MENUS).flatMap((m) => m.grupos);` com um comentário dizendo
que é ponte temporária da Task 1 e sai na Task 3.

- [ ] **Passo 7: Verificar**

```bash
cd frontend && npx tsc --noEmit && npx vitest run __tests__/menus.test.tsx
```

Esperado: 0 erros de tipo; 5 testes passando. O terceiro teste depende de `lib/modulos.ts`
(Task 2) — se ele ainda não existir, implemente a Task 2 antes de fechar esta.

- [ ] **Passo 8: Commit**

```bash
git add frontend/lib/menus frontend/components/Sidebar.tsx frontend/__tests__/menus.test.tsx
git commit -m "refactor(menus): o NAV monolitico vira seis arquivos por modulo"
```

---

### Task 2: `lib/modulos.ts` — pathname → módulo

**Files:**
- Create: `frontend/lib/modulos.ts`
- Test: `frontend/__tests__/modulos-pathname.test.tsx`

**Interfaces:**
- Produces: `moduloDoPathname(path: string): string | null`, `ROTA_MODULO`, `ICONES_MODULO`
- Consumes: nada

- [ ] **Passo 1: Escrever o teste**

`frontend/__tests__/modulos-pathname.test.tsx`:

```tsx
/**
 * O mapa pathname → módulo é o que sustenta a Sidebar nesta fatia e os
 * redirects na F3. Os casos abaixo vêm do apêndice §12 do spec, incluindo as
 * ambiguidades que ele resolveu de propósito.
 */
import { describe, expect, it } from "vitest";

import { moduloDoPathname } from "@/lib/modulos";

describe("moduloDoPathname", () => {
  it.each([
    ["/processos", "protocolo"],
    ["/processos/123", "protocolo"],
    ["/protocolo/balcao", "protocolo"],
    ["/workflow/7/editar", "protocolo"],
    ["/relatorios/tramitacao", "protocolo"],
    ["/servicos", "protocolo"],
    ["/manifestantes", "protocolo"],
    ["/tipos-manifestante", "protocolo"],
    ["/tipos-processo", "protocolo"],
    ["/tipos-anexo", "protocolo"],
    ["/assuntos", "protocolo"],
    ["/templates-documento", "protocolo"],
    ["/cidades", "protocolo"],
    ["/bairros", "protocolo"],
    ["/enderecos", "protocolo"],
    ["/pagamentos", "pagamentos"],
    ["/pagamentos/dashboard", "pagamentos"],
    ["/pagamentos/cadastros/fornecedores", "pagamentos"],
    ["/frotas", "frota"],
    ["/frotas/veiculos/9", "frota"],
    ["/transporte-regulado", "transporte"],
    ["/transporte-regulado/alvaras/3", "transporte"],
    ["/usuarios", "administracao"],
    ["/grupos", "administracao"],
    ["/unidades-trabalho", "administracao"],
    ["/organograma", "administracao"],
    ["/auditoria", "administracao"],
    ["/configuracoes", "administracao"],
    ["/jobs", "administracao"],
  ])("%s → %s", (path, esperado) => {
    expect(moduloDoPathname(path)).toBe(esperado);
  });

  it.each(["/home", "/dashboard", "/perfil", "/perfil/notificacoes", "/para-assinar", "/busca", "/modulos"])(
    "%s é transversal (null)",
    (path) => {
      // §12/D5: transversais não pertencem a módulo — agregam ATRAVÉS deles.
      expect(moduloDoPathname(path)).toBeNull();
    },
  );

  it("não confunde prefixo com palavra maior", () => {
    // "/processos" não pode capturar "/processos-antigos" de um módulo futuro,
    // e "/pagamentos" não pode capturar um "/pagamentosx" qualquer.
    expect(moduloDoPathname("/processosx")).toBeNull();
    expect(moduloDoPathname("/pagamentosx")).toBeNull();
  });

  it("tolera querystring e barra final", () => {
    expect(moduloDoPathname("/frotas/")).toBe("frota");
    expect(moduloDoPathname("/frotas?tab=ativos")).toBe("frota");
  });
});
```

- [ ] **Passo 2: Rodar e ver falhar**

```bash
cd frontend && npx vitest run __tests__/modulos-pathname.test.tsx
```

Esperado: FALHA ao resolver `@/lib/modulos`.

- [ ] **Passo 3: Implementar**

```ts
/**
 * Mapa rota → módulo, derivado do apêndice §12 do spec de modularização.
 *
 * Nesta fatia (F2) é o que diz à Sidebar qual menu renderizar, porque as URLs
 * ainda são as antigas. Na F3, quando as rotas virarem `/m/<slug>/…`, o slug
 * passa a vir de `params` — mas este mapa continua sendo a fonte dos redirects
 * 308 e do guard. Ou seja: não é ponte descartável.
 */
export const ROTA_MODULO: ReadonlyArray<readonly [string, string]> = [
  // A ordem importa: o primeiro prefixo que casar ganha. `/protocolo` antes de
  // nada mais que comece com "protocolo" seria ambíguo — hoje não é o caso.
  ["/processos", "protocolo"],
  ["/protocolo", "protocolo"],
  ["/workflow", "protocolo"],
  ["/relatorios", "protocolo"],
  ["/servicos", "protocolo"],
  ["/manifestantes", "protocolo"],
  ["/tipos-manifestante", "protocolo"],
  ["/tipos-processo", "protocolo"],
  ["/tipos-anexo", "protocolo"],
  ["/assuntos", "protocolo"],
  ["/templates-documento", "protocolo"],
  ["/cidades", "protocolo"],
  ["/bairros", "protocolo"],
  ["/enderecos", "protocolo"],
  ["/pagamentos", "pagamentos"],
  ["/frotas", "frota"],
  ["/transporte-regulado", "transporte"],
  ["/usuarios", "administracao"],
  ["/grupos", "administracao"],
  ["/unidades-trabalho", "administracao"],
  ["/organograma", "administracao"],
  ["/auditoria", "administracao"],
  ["/configuracoes", "administracao"],
  ["/jobs", "administracao"],
];

/**
 * Slug do módulo dono da rota, ou `null` se a rota é transversal.
 *
 * Casa por SEGMENTO, não por substring: `/processosx` não é `/processos`.
 */
export function moduloDoPathname(path: string): string | null {
  const limpo = path.split("?")[0].split("#")[0].replace(/\/+$/, "") || "/";
  for (const [prefixo, slug] of ROTA_MODULO) {
    if (limpo === prefixo || limpo.startsWith(`${prefixo}/`)) return slug;
  }
  return null;
}
```

- [ ] **Passo 4: Verificar**

```bash
cd frontend && npx tsc --noEmit && npx vitest run __tests__/modulos-pathname.test.tsx __tests__/menus.test.tsx
```

Esperado: tudo passando (inclusive o terceiro teste da Task 1, que depende deste mapa).

- [ ] **Passo 5: Commit**

```bash
git add frontend/lib/modulos.ts frontend/__tests__/modulos-pathname.test.tsx
git commit -m "feat(modulos): mapa pathname -> modulo, derivado do apendice do spec"
```

---

### Task 3: A Sidebar vira renderizador

**Files:**
- Modify: `frontend/components/Sidebar.tsx`, `frontend/app/(app)/layout.tsx`
- Test: `frontend/__tests__/Sidebar.modulo.test.tsx` (criar)

**Interfaces:**
- Consumes: `menuDoModulo` (Task 1), `moduloDoPathname` (Task 2)
- Produces: `<Sidebar modulo={slug|null} open onClose />`

- [ ] **Passo 1: Escrever o teste**

```tsx
/**
 * A Sidebar passa a renderizar SÓ o módulo ativo, mais os transversais.
 * O que este teste protege: estar em /frotas não pode mostrar menu de
 * pagamentos — era exatamente o que a Sidebar de 637 linhas fazia.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/frotas/veiculos",
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: true },
    permissoes: [],
    temPermissao: () => true,
    logout: vi.fn(),
  }),
}));

import { Sidebar } from "@/components/Sidebar";

describe("Sidebar por módulo", () => {
  it("mostra o menu do módulo ativo e não o dos outros", () => {
    render(<Sidebar modulo="frota" open onClose={() => {}} />);
    expect(screen.getByText("Veículos")).toBeTruthy();
    expect(screen.queryByText("Contas a pagar")).toBeNull();
    expect(screen.queryByText("Permissionários")).toBeNull();
  });

  it("em rota transversal mostra os itens comuns e nenhum menu de módulo", () => {
    render(<Sidebar modulo={null} open onClose={() => {}} />);
    expect(screen.getByText("Início")).toBeTruthy();
    expect(screen.queryByText("Veículos")).toBeNull();
  });
});
```

> Ajuste os `getByText` aos labels reais dos arquivos de menu se algum diferir — o que este teste
> afirma é o **isolamento**, não os rótulos.

- [ ] **Passo 2: Rodar e ver falhar** — `npx vitest run __tests__/Sidebar.modulo.test.tsx`.
  Esperado: falha porque `Sidebar` ainda não aceita `modulo`.

- [ ] **Passo 3: Implementar**

Na `Sidebar.tsx`: acrescentar `modulo: string | null` às props e trocar a ponte temporária da Task 1
por:

```tsx
  const menu = menuDoModulo(modulo);
  const NAV: NavGroup[] = [
    ...MENUS.comum.grupos,
    ...(menu && menu.slug !== "comum" ? menu.grupos : []),
  ];
```

> **Correção de 2026-07-30 (decisão do Jorge).** A primeira redação deste passo prescrevia os
> transversais **no fim** (`[...modulo, ...comum]`). Estava errada — quem escreveu foi o autor deste
> plano, não uma leitura equivocada de quem implementou. No `NAV` original o grupo "Geral"
> (Início/Dashboard/Para assinar) vinha **primeiro**; pôr os transversais no fim reordenava o menu
> sem que ninguém tivesse pedido — o mesmo tipo de regressão que a rodada de revisão da Task 1 já
> tinha corrigido uma vez (ver `ORDEM_GRUPOS_ORIGINAL` e o histórico de `menus.test.tsx`), agora
> reintroduzida por outro caminho. A ordem certa, corrigida em revisão da Task 3, é **comum primeiro,
> módulo depois** — o snippet acima já reflete a versão corrigida.

Os transversais entram **sempre**, agora **primeiro** — são o caminho de volta para `/home` e
`/dashboard`. Todo o resto do componente (poda por `perm`/`anyOf`, `localStorage` de grupos abertos,
auto-expand, colapso) fica **inalterado**: ele já opera sobre `NAV`.

Em `app/(app)/layout.tsx`, dentro de `Shell`, derivar e repassar:

```tsx
  const modulo = moduloDoPathname(pathname);
  …
  <Sidebar modulo={modulo} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
```

`pathname` já existe no componente (`const pathname = usePathname()`).

- [ ] **Passo 4: Verificar** — `npx tsc --noEmit` e a suíte de frontend inteira
  (`npx vitest run`), porque a Sidebar é usada por outros testes.

- [ ] **Passo 5: Commit**

```bash
git add frontend/components/Sidebar.tsx "frontend/app/(app)/layout.tsx" frontend/__tests__/Sidebar.modulo.test.tsx
git commit -m "feat(menus): Sidebar renderiza o modulo ativo mais os transversais"
```

---

### Task 4: O launcher `/modulos`

**Files:**
- Create: `frontend/app/(launcher)/layout.tsx`, `frontend/app/(launcher)/modulos/page.tsx`
- Modify: `frontend/lib/modulos.ts` (acrescenta `ICONES_MODULO`)
- Test: `frontend/__tests__/Launcher.test.tsx`

**Interfaces:**
- Consumes: `api.modulos()` → `{ itens: ModuloOut[] }` com `slug, nome, icone, ordem` (já existe em
  `lib/api.ts:2127`); `MENUS[slug].raiz` (Task 1)
- Produces: a rota `/modulos`

**Ícone vem como string do banco** (`"FileText"`, `"Wallet"`, `"Truck"`, `"Bus"`, `"Settings"`).
Precisa de mapa explícito — import dinâmico de nome arbitrário não sobrevive ao bundler e abriria
porta para nome inválido virar erro de runtime:

```ts
// em lib/modulos.ts
import { Bus, FileText, LayoutGrid, Settings, Truck, Wallet } from "lucide-react";
import type React from "react";

/** Ícones que o catálogo pode nomear. Nome desconhecido cai no genérico. */
export const ICONES_MODULO: Record<string, React.ComponentType<{ className?: string }>> = {
  FileText, Wallet, Truck, Bus, Settings,
};

export function iconeDoModulo(nome: string | null) {
  return (nome && ICONES_MODULO[nome]) || LayoutGrid;
}
```

- [ ] **Passo 1: Escrever o teste**

```tsx
/**
 * O launcher. O modo de falha que importa é a TELA EM BRANCO: já custou um PR
 * neste projeto, e o F1 teve um Critical exatamente porque o teste do endpoint
 * passava com lista vazia. Aqui, lista vazia tem de aparecer como mensagem
 * explícita, não como página muda.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push }) }));

const modulos = vi.fn();
vi.mock("@/lib/api", () => ({ api: { modulos: () => modulos() } }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { nome: "Teste" }, loading: false }) }));

import Launcher from "@/app/(launcher)/modulos/page";

const TRES = {
  itens: [
    { slug: "protocolo", nome: "Protocolo", icone: "FileText", ordem: 1 },
    { slug: "frota", nome: "Frota", icone: "Truck", ordem: 3 },
    { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
  ],
};

describe("launcher", () => {
  it("mostra um card por módulo, na ordem do catálogo", async () => {
    modulos.mockResolvedValue(TRES);
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText("Protocolo")).toBeTruthy());
    const nomes = screen.getAllByRole("link").map((a) => a.textContent);
    expect(nomes[0]).toContain("Protocolo");
    expect(nomes[1]).toContain("Pagamentos"); // ordem 2 antes de ordem 3
    expect(nomes[2]).toContain("Frota");
  });

  it("cada card aponta para a raiz do módulo", async () => {
    modulos.mockResolvedValue(TRES);
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText("Frota")).toBeTruthy());
    const frota = screen.getAllByRole("link").find((a) => a.textContent?.includes("Frota"));
    expect(frota?.getAttribute("href")).toBe("/frotas");
  });

  it("com um módulo só, entra direto — o launcher é porta, não pedágio", async () => {
    modulos.mockResolvedValue({ itens: [TRES.itens[1]] });
    render(<Launcher />);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/frotas"));
  });

  it("lista vazia mostra mensagem explícita, não tela muda", async () => {
    modulos.mockResolvedValue({ itens: [] });
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText(/nenhum módulo/i)).toBeTruthy());
  });

  it("erro de API mostra mensagem, não tela muda", async () => {
    modulos.mockRejectedValue(new Error("falhou"));
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText(/não foi possível/i)).toBeTruthy());
  });
});
```

- [ ] **Passo 2: Rodar e ver falhar.**

- [ ] **Passo 3: Implementar o layout** (`app/(launcher)/layout.tsx`)

Autenticado como `(app)`, mas **sem** Sidebar nem Header de módulo — o launcher é tela cheia. Copie
a estrutura de providers de `app/(app)/layout.tsx` (`Providers` → `AuthProvider`), com o mesmo
tratamento de `loading` e `!user`, e um `<main>` centralizado.

- [ ] **Passo 4: Implementar a página**

Client component. Usa `useQuery` do react-query como o resto do app (`queryKey: ["modulos-me"]`,
`queryFn: api.modulos`). Renderiza `<Link href={MENUS[slug]?.raiz ?? "/home"}>` por módulo,
ordenando por `ordem`, com `iconeDoModulo(m.icone)`. Módulo cujo slug não esteja em `MENUS` **não
some**: cai em `/home` com o ícone genérico — é o comportamento fail-open desta camada, coerente com
D8, e evita que um módulo novo no catálogo desapareça da tela antes de a UI existir.

Um módulo só → `router.replace(raiz)` num `useEffect`. Lista vazia → mensagem
"Nenhum módulo disponível para o seu usuário" + o que fazer (falar com o administrador do tenant).
Erro → "Não foi possível carregar os módulos" + botão de tentar de novo.

- [ ] **Passo 5: Verificar** — `npx tsc --noEmit` e `npx vitest run __tests__/Launcher.test.tsx`.

- [ ] **Passo 6: Commit**

```bash
git add "frontend/app/(launcher)" frontend/lib/modulos.ts frontend/__tests__/Launcher.test.tsx
git commit -m "feat(launcher): tela de selecao de modulos em /modulos"
```

---

### Task 5: O login passa a aterrissar no launcher

**Files:**
- Modify: `frontend/app/login/page.tsx:34-36`
- Test: `frontend/__tests__/LoginRedirect.test.tsx` (criar)

**Interfaces:** consome a rota `/modulos` (Task 4).

- [ ] **Passo 1: Escrever o teste**

`frontend/__tests__/LoginRedirect.test.tsx`:

```tsx
/**
 * Sem esta mudança o launcher existe e ninguém chega nele. Com ela, a troca de
 * senha obrigatória continua tendo precedência — é requisito de segurança
 * (SEC-1) e não pode ser atropelada pela porta de entrada nova.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  useSearchParams: () => new URLSearchParams(),
}));

const login = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ login: (...a: unknown[]) => login(...a), user: null, loading: false }),
}));

import LoginPage from "@/app/login/page";

async function submeter() {
  render(<LoginPage />);
  fireEvent.change(screen.getByLabelText(/e-?mail/i), { target: { value: "a@b.test" } });
  fireEvent.change(screen.getByLabelText(/senha/i), { target: { value: "x" } });
  fireEvent.click(screen.getByRole("button", { name: /entrar/i }));
}

describe("destino após o login", () => {
  it("vai para o launcher", async () => {
    login.mockResolvedValue({ must_change_password: false });
    await submeter();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/modulos"));
  });

  it("troca de senha obrigatória tem precedência sobre o launcher", async () => {
    login.mockResolvedValue({ must_change_password: true });
    await submeter();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/alterar-senha-obrigatoria"));
    expect(push).not.toHaveBeenCalledWith("/modulos");
  });
});
```

> Se os seletores não casarem com o formulário real (`getByLabelText`, nome do botão), ajuste-os ao
> que `app/login/page.tsx` renderiza — o que o teste afirma é o **destino**, não a marcação.

- [ ] **Passo 2: Rodar e ver falhar.**

- [ ] **Passo 3: Trocar `"/home"` por `"/modulos"`** na linha 35. O comentário existente sobre
  "evita o salto extra por /home" precisa ser reescrito, não apagado: a razão dele muda.

- [ ] **Passo 4: Verificar** — `npx tsc --noEmit` + a suíte de frontend inteira. Atenção: teste e2e
  do Playwright que assume aterrissagem em `/home` passa a falhar. Rodar
  `docker compose --profile test run --rm e2e` **não** é possível aqui (o build de imagem está
  quebrado) — então **procure em `tests-e2e/specs/` por `'/home'` e reporte o que achar** em vez de
  consertar às cegas. É informação que o controller precisa antes do merge.

- [ ] **Passo 5: Commit.**

---

### Task 6: Switcher de módulo no Header

**Files:**
- Create: `frontend/components/ModuloSwitcher.tsx`
- Modify: `frontend/components/Header.tsx:56` (a `div` de ações, ao lado de `NotificacoesBell`)
- Test: `frontend/__tests__/ModuloSwitcher.test.tsx`

**Interfaces:** consome `api.modulos()`, `MENUS[slug].raiz`, `moduloDoPathname`.

- [ ] **Passo 1: Escrever o teste**

`frontend/__tests__/ModuloSwitcher.test.tsx`:

```tsx
/**
 * O switcher. A propriedade de desenho que ele carrega (§6): trocar de módulo
 * NÃO passa pelo launcher — "o launcher é porta de entrada, não pedágio".
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  usePathname: () => "/frotas/veiculos",
}));

vi.mock("@/lib/api", () => ({
  api: {
    modulos: () =>
      Promise.resolve({
        itens: [
          { slug: "frota", nome: "Frota", icone: "Truck", ordem: 3 },
          { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
        ],
      }),
  },
}));

import { ModuloSwitcher } from "@/components/ModuloSwitcher";

describe("switcher de módulo", () => {
  it("mostra o módulo ativo, derivado do pathname", async () => {
    render(<ModuloSwitcher />);
    await waitFor(() => expect(screen.getByRole("button", { name: /frota/i })).toBeTruthy());
  });

  it("trocar de módulo vai direto para a raiz, sem passar pelo launcher", async () => {
    render(<ModuloSwitcher />);
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /frota/i })));
    fireEvent.click(screen.getByText("Pagamentos"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/pagamentos"));
    expect(push).not.toHaveBeenCalledWith("/modulos");
  });

  it("oferece um caminho explícito de volta ao launcher", async () => {
    render(<ModuloSwitcher />);
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /frota/i })));
    fireEvent.click(screen.getByText(/todos os módulos/i));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/modulos"));
  });
});
```

- [ ] **Passo 2: Rodar e ver falhar.**

- [ ] **Passo 3: Implementar.** Reaproveite o padrão de dropdown que já existe no projeto
  (`NotificacoesBell` ou o menu de usuário do Header) em vez de inventar um novo: mesmo
  comportamento de fechar ao clicar fora e de acessibilidade.

- [ ] **Passo 4: Verificar** — `npx tsc --noEmit` + vitest.

- [ ] **Passo 5: Commit.**

---

### Task 7: Aba Módulos no admin de plataforma

**Files:**
- Modify: `frontend/app/(plataforma)/admin/tenants/[id]/page.tsx`, `frontend/lib/api.ts`
- Test: `frontend/__tests__/AdminTenantModulos.test.tsx`

**Interfaces:**
- Consumes: `GET`/`PUT /api/v2/admin/tenants/{id}/modulos`, entregues pela F1 (Task 7 daquela
  fatia, `backend/app/routers/admin_tenants.py`). O `GET` devolve o catálogo contratável com
  `contratado` e `ativo` por módulo; o `PUT` recebe `{ "modulos": ["slug", …] }` e **reconcilia** —
  o que não vier na lista é descontratado.
- Produces: métodos em `lib/api.ts` (`adminTenantModulos(id)`, `adminTenantContratarModulos(id, slugs)`)
  com as interfaces TypeScript correspondentes.

- [ ] **Passo 1: Escrever o teste**

`frontend/__tests__/AdminTenantModulos.test.tsx`:

```tsx
/**
 * A aba de contratação. Duas propriedades do backend que a interface tem de
 * respeitar, senão ela produz 400 ou engana o administrador:
 *  1. o PUT RECONCILIA — manda a lista completa do estado final, não um delta;
 *  2. módulo inativo não pode ser CONTRATADO, mas pode ser DESCONTRATADO
 *     (services/modulos.py::contratar recusa o primeiro e permite o segundo).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const salvar = vi.fn(() => Promise.resolve());
vi.mock("@/lib/api", () => ({
  api: {
    adminTenantModulos: () =>
      Promise.resolve([
        { slug: "protocolo", nome: "Protocolo", contratado: true, ativo: true, ordem: 1 },
        { slug: "frota", nome: "Frota", contratado: false, ativo: true, ordem: 3 },
        { slug: "transporte", nome: "Transporte Regulado", contratado: true, ativo: false, ordem: 4 },
      ]),
    adminTenantContratarModulos: (id: number, slugs: string[]) => salvar(id, slugs),
  },
}));

import { TenantModulosTab } from "@/app/(plataforma)/admin/tenants/[id]/page";

describe("aba Módulos do tenant", () => {
  it("contratar um módulo manda a lista completa, não o delta", async () => {
    render(<TenantModulosTab tenantId={7} />);
    fireEvent.click(await waitFor(() => screen.getByLabelText("Frota")));
    fireEvent.click(screen.getByRole("button", { name: /salvar/i }));
    await waitFor(() =>
      expect(salvar).toHaveBeenCalledWith(7, ["protocolo", "frota", "transporte"]),
    );
  });

  it("módulo inativo não pode ser contratado", async () => {
    render(<TenantModulosTab tenantId={7} />);
    // transporte está contratado E inativo: pode soltar, não pode marcar de novo.
    const inativo = await waitFor(() => screen.getByLabelText("Transporte Regulado"));
    fireEvent.click(inativo); // descontrata — permitido
    fireEvent.click(inativo); // tentaria recontratar — a interface tem de barrar
    expect((inativo as HTMLInputElement).checked).toBe(false);
  });

  it("diz que descontratar não apaga dado", async () => {
    render(<TenantModulosTab tenantId={7} />);
    // Garantia do spec §8. Sem isso na tela, o administrador hesita em usá-la.
    await waitFor(() => expect(screen.getByText(/não apaga|dados permanecem/i)).toBeTruthy());
  });
});
```

> `TenantModulosTab` precisa ser exportado do arquivo da página para ser testável isoladamente. Se a
> página já for grande, extraia o componente para
> `frontend/components/plataforma/TenantModulosTab.tsx` e importe de lá — decisão sua, mas o teste
> tem de poder montar a aba sem montar a página inteira.

- [ ] **Passo 2: Rodar e ver falhar.**

- [ ] **Passo 3: Implementar.** Siga o padrão das abas já existentes na página de detalhe do tenant.
  Deixe explícito na interface que **descontratar não apaga dado** — é a garantia registrada no spec
  §8, e um administrador que não sabe disso hesita em usar a tela.

- [ ] **Passo 4: Verificar** — `npx tsc --noEmit` + vitest.

- [ ] **Passo 5: Commit.**

---

> **Não há Task 8.** O guard de módulo no frontend (entrar em rota de módulo não contratado e ser
> devolvido ao launcher) está na linha da **F3** na tabela do §9, e é lá que ele fica. Ele não
> conserta nada que esta fatia quebre: navegar para `/pagamentos` num tenant sem pagamentos já era
> possível antes da F2 — o menu não oferece o caminho, e o backend nega o dado desde a F1.
> Antecipá-lo seria escopo a mais sem risco a menos.

---

## Critério de aceite da fatia F2

- `cd frontend && npx tsc --noEmit` → 0 erros
- `cd frontend && npx vitest run` → verde, e as guardas do split passando com conjunto **não vazio**
- **Nenhuma URL mudou:** `git diff --stat` não toca `nginx/default.conf`, `frontend/middleware.ts`
  nem move arquivo de rota sob `app/(app)/`
- Login aterrissa em `/modulos`; usuário com um módulo entra direto nele
- Estar em `/frotas` mostra menu de frota + transversais, e **nenhum** item de pagamentos
- O switcher troca de módulo sem passar pelo launcher
- A aba Módulos do admin de plataforma contrata e descontrata, e a mudança aparece no launcher do
  tenant afetado
- **Verificação visual pendente de decisão:** confirmar a tela no navegador exige build no host +
  `docker cp` (o build de imagem está quebrado por interceptação de TLS do antivírus). O plano não
  presume que isso esteja resolvido; se estiver, `docker compose up -d --build frontend` é o
  caminho normal.

## Fora do escopo desta fatia

Rotas `/m/<slug>/…`, redirects 308, token `m` na regex do nginx, `?next=` no middleware (tudo F3);
remoção do ORM legado `public.modulos`/`configuracoes_modulos` e geração prefixada de
`notificacao.link_url` (F4); cookie de "último módulo"; menu servido pelo backend (D6 decidiu o
contrário).
