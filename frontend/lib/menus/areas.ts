import { Bus, Truck, type LucideIcon } from "lucide-react";

import { ROTA_PROCESSOS } from "@/lib/caixas-processos";

import { MENUS } from "./index";
import type { NavGroup, NavItem } from "./tipos";

/**
 * MENU POR ÁREA (2026-11-14, no modelo do IAnalisys: Comercial, Financeiro,
 * Clientes…). A barra deixa de ter uma seção por MÓDULO — em que cada uma
 * repetia a sua "Visão geral", "Painel", "Dashboard", "Relatórios" e
 * "Cadastros" — e passa a ter uma seção por ÁREA de trabalho da prefeitura.
 * Cadastros e configuração de todos os módulos viram uma tela só
 * (`/cadastros`), fora das áreas.
 *
 * As áreas só ORGANIZAM a barra: cada item continua declarado no menu do seu
 * módulo (`lib/menus/<módulo>.ts`) e é buscado de lá pelo `href`. Permissão,
 * Ctrl+K, guardas de rota e a tela de permissões seguem lendo os menus dos
 * módulos — nada disso muda. Módulo não contratado não aparece; item sem
 * permissão é podado na barra pela mesma `canSeeItem`.
 *
 * Duas redes de segurança, para nada sumir em silêncio:
 * - tela "barra" de um módulo que nenhuma área cita entra no FIM da área do
 *   módulo (o teste `menus-por-area.test.ts` cobra que hoje não haja nenhuma);
 * - módulo contratado que nenhuma área cita (um módulo novo) ganha seção
 *   própria, como antes.
 */

/** Referência a um item do menu de um módulo. `label` troca só o rótulo na barra. */
export interface RefItem {
  modulo: string;
  href: string;
  label?: string;
}

/** Subgrupo colapsável dentro da área (ex.: Frota pública dentro de Mobilidade). */
export interface RefSubgrupo {
  subgrupo: string;
  icon: LucideIcon;
  itens: RefItem[];
}

export interface Area {
  titulo: string;
  itens: (RefItem | RefSubgrupo)[];
}

export const AREAS: Area[] = [
  {
    titulo: "Atendimento",
    itens: [
      // "Painel de controle" é o nome que a prefeitura pediu (reunião de
      // 2026-10-20, referência: Painel de Controle do SEI) — fica.
      { modulo: "protocolo", href: "/m/protocolo/painel" },
      { modulo: "protocolo", href: ROTA_PROCESSOS },
      { modulo: "protocolo", href: "/m/protocolo/protocolo/balcao" },
      { modulo: "protocolo", href: "/m/protocolo/relatorios" },
    ],
  },
  {
    titulo: "Financeiro",
    itens: [
      // "Indicadores" (o antigo Dashboard) é aba da Visão geral, não item.
      { modulo: "pagamentos", href: "/m/pagamentos" },
      { modulo: "pagamentos", href: "/m/pagamentos/solicitacoes" },
      { modulo: "pagamentos", href: "/m/pagamentos/autorizacao" },
      { modulo: "pagamentos", href: "/m/pagamentos/tesouraria" },
      { modulo: "pagamentos", href: "/m/pagamentos/conciliacao" },
    ],
  },
  {
    titulo: "Mobilidade",
    itens: [
      {
        subgrupo: "Frota pública",
        icon: Truck,
        itens: [
          { modulo: "frota", href: "/m/frota" },
          { modulo: "frota", href: "/m/frota/veiculos" },
          { modulo: "frota", href: "/m/frota/solicitacoes" },
        ],
      },
      {
        subgrupo: "Transporte regulado",
        icon: Bus,
        itens: [
          { modulo: "transporte", href: "/m/transporte" },
          { modulo: "transporte", href: "/m/transporte/permissionarios" },
          { modulo: "transporte", href: "/m/transporte/alvaras" },
          { modulo: "transporte", href: "/m/transporte/ocorrencias" },
          { modulo: "transporte", href: "/m/transporte/recadastramento" },
        ],
      },
    ],
  },
];

/** A tela-índice que reúne cadastros e configuração de todos os módulos (declarada em `comum.ts`). */
export const ROTA_CADASTROS = "/cadastros";
function itemCadastros(): NavItem | null {
  const i = acharItem("comum", ROTA_CADASTROS);
  return i ? { ...i, lugar: "barra" } : null;
}

function ehSubgrupo(r: RefItem | RefSubgrupo): r is RefSubgrupo {
  return "subgrupo" in r;
}

/** Todos os itens de um módulo, inclusive filhos, achatados. */
function itensDoModulo(slug: string): NavItem[] {
  const achata = (xs: NavItem[]): NavItem[] => xs.flatMap((i) => [i, ...achata(i.children ?? [])]);
  return achata((MENUS[slug]?.grupos ?? []).flatMap((g) => g.items));
}

export function acharItem(modulo: string, href: string): NavItem | undefined {
  return itensDoModulo(modulo).find((i) => i.href === href);
}

/** Módulos que alguma área cita. */
export function modulosDasAreas(): Set<string> {
  const s = new Set<string>();
  for (const a of AREAS)
    for (const r of a.itens) for (const x of ehSubgrupo(r) ? r.itens : [r]) s.add(x.modulo);
  return s;
}

/** hrefs que alguma área cita, por módulo. */
function hrefsCitados(): Set<string> {
  const s = new Set<string>();
  for (const a of AREAS)
    for (const r of a.itens) for (const x of ehSubgrupo(r) ? r.itens : [r]) s.add(`${x.modulo} ${x.href}`);
  return s;
}

/**
 * Telas "barra" do módulo que nenhuma área cita. Os índices de cadastro dos
 * módulos não entram: `/cadastros` os substitui na barra.
 */
export function orfasDaBarra(slug: string): NavItem[] {
  const citados = hrefsCitados();
  return (MENUS[slug]?.grupos ?? [])
    .flatMap((g) => g.items)
    .filter((i) => (i.lugar ?? "barra") === "barra" && !citados.has(`${slug} ${i.href}`));
}

function resolver(r: RefItem, contratados: Set<string>): NavItem | null {
  if (!contratados.has(r.modulo)) return null;
  const item = acharItem(r.modulo, r.href);
  if (!item) return null;
  // Filhos não viajam: na área o item é a tela, não o acordeão do módulo.
  const { children: _filhos, ...semFilhos } = item;
  return { ...semFilhos, label: r.label ?? item.label, lugar: "barra" };
}

/**
 * Seções da barra, por área. `contratados` em ordem do catálogo; `nomeDoModulo`
 * dá o título da seção de um módulo que nenhuma área cita.
 */
export function navPorArea(contratados: string[], nomeDoModulo: (slug: string) => string): NavGroup[] {
  const ativos = new Set(contratados);
  const grupos: NavGroup[] = [];

  for (const area of AREAS) {
    const itens: NavItem[] = [];
    const subgrupos: NavItem[] = [];
    for (const r of area.itens) {
      if (ehSubgrupo(r)) {
        const filhos = r.itens.map((x) => resolver(x, ativos)).filter((x): x is NavItem => !!x);
        if (filhos.length > 0) {
          subgrupos.push({ label: r.subgrupo, href: filhos[0].href, icon: r.icon, children: filhos });
        }
      } else {
        const it = resolver(r, ativos);
        if (it) itens.push(it);
      }
    }
    // Um subgrupo sozinho na área não precisa de acordeão: os filhos sobem.
    if (itens.length === 0 && subgrupos.length === 1) itens.push(...(subgrupos[0].children ?? []));
    else itens.push(...subgrupos);

    // Rede de segurança: tela de trabalho que a área esqueceu entra no fim.
    const modulosDaArea = new Set(
      area.itens.flatMap((r) => (ehSubgrupo(r) ? r.itens : [r]).map((x) => x.modulo)),
    );
    for (const m of modulosDaArea) {
      if (!ativos.has(m)) continue;
      for (const orfa of orfasDaBarra(m)) {
        if (!ehIndiceDeCadastro(orfa)) itens.push(orfa);
      }
    }

    if (itens.length > 0) grupos.push({ title: area.titulo, items: itens, defaultOpen: true });
  }

  // Módulos que nenhuma área cita: seção própria, como no menu por módulo.
  const citados = modulosDasAreas();
  const quieto = (s: string) => (MENUS[s]?.grupos ?? []).some((g) => g.quieto);
  const soltos = contratados.filter((s) => !citados.has(s) && !!MENUS[s]);
  for (const s of soltos.filter((x) => !quieto(x))) {
    grupos.push({
      title: nomeDoModulo(s),
      items: (MENUS[s].grupos.flatMap((g) => g.items)).filter((i) => (i.lugar ?? "barra") === "barra"),
      defaultOpen: true,
    });
  }

  // Cadastros e configuração de todos os módulos: uma entrada só, sem título.
  const cadastros = itemCadastros();
  if (cadastros && contratados.some((s) => citados.has(s))) {
    grupos.push({ title: "Cadastros e configuração", semTitulo: true, items: [cadastros], defaultOpen: true });
  }

  // Administração (e outro módulo "quieto") por último, como sempre.
  for (const s of soltos.filter(quieto)) {
    grupos.push({
      title: nomeDoModulo(s),
      items: (MENUS[s].grupos.flatMap((g) => g.items)).filter((i) => (i.lugar ?? "barra") === "barra"),
      defaultOpen: false,
      quieto: true,
    });
  }
  return grupos;
}

/** Índice de cadastro de um módulo (`/m/<módulo>/cadastros`): `/cadastros` o substitui na barra. */
export function ehIndiceDeCadastro(i: NavItem): boolean {
  return /^\/m\/[^/]+\/cadastros$/.test(i.href);
}
