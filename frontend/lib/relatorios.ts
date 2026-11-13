/**
 * Apoio da página gerencial de relatórios e das listas de cada seção (SI-34).
 *
 * O recorte mora na URL: a página gerencial e as listas leem e escrevem os
 * mesmos parâmetros, então o "ver lista" de uma seção abre com o filtro que
 * produziu o número, e o link pode ser copiado para outra pessoa.
 *
 * Datas: o backend manda hora de Brasília SEM fuso (`2026-10-10T23:30:00`).
 * Formatamos o texto em vez de passar por `new Date`, que trataria a string
 * como hora do navegador — certo por acaso aqui, errado no primeiro servidor
 * ou navegador fora do fuso.
 */
import type {
  DocumentacaoFiltroInput,
  FiltroOrigemRelatorio,
  FiltroSigiloRelatorio,
  ModoUnidadeRelatorio,
  RelatorioFiltroInput,
  SituacaoRelatorio,
  StatusPrazoRelatorio,
  VisaoDocumentacao,
} from "@/lib/api";

export const ROTA_RELATORIOS = "/m/protocolo/relatorios";
export const ROTA_LISTA_PROCESSOS = "/m/protocolo/relatorios/processos";
export const ROTA_LISTA_TRAMITACAO = "/m/protocolo/relatorios/tramitacao";
export const ROTA_LISTA_ASSINATURAS = "/m/protocolo/relatorios/assinaturas";
export const ROTA_LISTA_DOCUMENTACAO = "/m/protocolo/relatorios/documentacao";

export const ROTULO_MODO_UNIDADE: Record<ModoUnidadeRelatorio, string> = {
  envolvida: "dona ou onde está agora",
  dona: "só a dona do processo",
  atual: "só onde está agora",
};

export const ROTULO_SITUACAO: Record<SituacaoRelatorio, string> = {
  em_andamento: "Em andamento",
  em_transito: "Em trânsito",
  arquivado: "Arquivado",
};

export const ROTULO_PRAZO: Record<StatusPrazoRelatorio, string> = {
  sem_prazo: "Sem prazo de serviço",
  dentro_do_prazo: "Dentro do prazo",
  vencendo: "Vencendo",
  atrasado: "Prazo vencido",
  concluido_no_prazo: "Arquivado no prazo",
  concluido_atrasado: "Arquivado com atraso",
};

const MODOS = Object.keys(ROTULO_MODO_UNIDADE) as ModoUnidadeRelatorio[];
const SITUACOES = Object.keys(ROTULO_SITUACAO) as SituacaoRelatorio[];
const PRAZOS = Object.keys(ROTULO_PRAZO) as StatusPrazoRelatorio[];
const DATAS_BASE: DataBaseRelatorio[] = ["abertura", "arquivamento", "chegada", "pedido", "conclusao"];
const DIA = /^\d{4}-\d{2}-\d{2}$/;

/** O recorte comum + os campos das listas, lidos da URL. Valor estranho
 * (link editado à mão) é ignorado em vez de virar erro do servidor. */
export type DataBaseRelatorio = "abertura" | "arquivamento" | "chegada" | "pedido" | "conclusao";

export interface FiltroDaUrl extends Omit<RelatorioFiltroInput, "data_base"> {
  /** Abertura/arquivamento (processos), chegada (tramitação), pedido/conclusão
   * (assinaturas). */
  data_base?: DataBaseRelatorio;
  dias_parado?: number;
  /** Lista de documentação: qual número dela está aberto. */
  visao?: VisaoDocumentacao;
}

function inteiro(v: string | null): number | undefined {
  if (!v || !/^\d+$/.test(v)) return undefined;
  const n = Number(v);
  return n > 0 ? n : undefined;
}

export function filtroDaUrl(sp: URLSearchParams): FiltroDaUrl {
  const modo = sp.get("modo_unidade") as ModoUnidadeRelatorio | null;
  const situacao = sp.get("situacao") as SituacaoRelatorio | null;
  const prazo = sp.get("prazo") as StatusPrazoRelatorio | null;
  const desde = sp.get("desde");
  const ate = sp.get("ate");
  const dataBase = sp.get("data_base");
  const sigilo = sp.get("sigilo");
  const origem = sp.get("origem");
  const visao = sp.get("visao");
  return {
    id_unidade: inteiro(sp.get("id_unidade")),
    modo_unidade: modo && MODOS.includes(modo) ? modo : undefined,
    id_assunto: inteiro(sp.get("id_assunto")),
    id_tipo_processo: inteiro(sp.get("id_tipo_processo")),
    id_servico: inteiro(sp.get("id_servico")),
    desde: desde && DIA.test(desde) ? desde : undefined,
    ate: ate && DIA.test(ate) ? ate : undefined,
    data_base: (DATAS_BASE as string[]).includes(dataBase ?? "")
      ? (dataBase as DataBaseRelatorio)
      : undefined,
    situacao: situacao && SITUACOES.includes(situacao) ? situacao : undefined,
    parado_ha_dias: inteiro(sp.get("parado_ha_dias")),
    prazo: prazo && PRAZOS.includes(prazo) ? prazo : undefined,
    dias_parado: inteiro(sp.get("dias_parado")),
    sigilo: sigilo === "ostensivo" || sigilo === "sigiloso" ? sigilo : undefined,
    origem: origem === "interna" || origem === "externa" ? origem : undefined,
    com_atraso: sp.get("com_atraso") === "true" || undefined,
    visao: VISOES_DOCUMENTACAO.some((v) => v.id === visao) ? (visao as VisaoDocumentacao) : undefined,
  };
}

/** `?a=1&b=2` sem os campos vazios; `""` quando não sobra nenhum. */
export function filtroParaUrl(f: FiltroDaUrl): string {
  const sp = new URLSearchParams();
  const campos: [string, string | number | undefined][] = [
    ["id_unidade", f.id_unidade],
    ["modo_unidade", f.id_unidade ? f.modo_unidade : undefined],
    ["id_assunto", f.id_assunto],
    ["id_tipo_processo", f.id_tipo_processo],
    ["id_servico", f.id_servico],
    ["desde", f.desde],
    ["ate", f.ate],
    ["data_base", f.data_base],
    ["situacao", f.situacao],
    ["parado_ha_dias", f.parado_ha_dias],
    ["prazo", f.prazo],
    ["dias_parado", f.dias_parado],
    ["sigilo", f.sigilo],
    ["origem", f.origem],
    ["com_atraso", f.com_atraso ? "true" : undefined],
    ["visao", f.visao],
  ];
  for (const [k, v] of campos) if (v !== undefined && v !== "") sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/** Só o recorte comum (o que a barra de filtros controla). */
export function recorteComum(f: FiltroDaUrl): FiltroDaUrl {
  return {
    id_unidade: f.id_unidade,
    modo_unidade: f.modo_unidade,
    id_assunto: f.id_assunto,
    id_tipo_processo: f.id_tipo_processo,
    id_servico: f.id_servico,
    desde: f.desde,
    ate: f.ate,
  };
}

export const ROTULO_SIGILO: Record<FiltroSigiloRelatorio, string> = {
  ostensivo: "Só ostensivos (públicos)",
  sigiloso: "Só sigilosos",
};
export const ROTULO_ORIGEM: Record<FiltroOrigemRelatorio, string> = {
  interna: "Só internos",
  externa: "Só externos",
};

/** `2026-10-10T23:30:00` → `10/10/2026 23:30`. */
export function fmtDataHora(s: string | null | undefined): string {
  if (!s) return "—";
  const [d, h = ""] = s.split("T");
  const [a, m, dia] = d.split("-");
  return `${dia}/${m}/${a}${h ? ` ${h.slice(0, 5)}` : ""}`;
}

/** `2026-10-10…` → `10/10/2026`. */
export function fmtData(s: string | null | undefined): string {
  if (!s) return "—";
  const [a, m, dia] = s.slice(0, 10).split("-");
  return `${dia}/${m}/${a}`;
}

/** Dias com uma casa e vírgula: `19,1 dias`; `1,0 dia`. */
export function fmtDias(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const n = v.toFixed(1).replace(".", ",");
  return `${n} ${v === 1 ? "dia" : "dias"}`;
}

/** Minutos em texto curto: `45 min`, `3h 05min`, `2d 4h`. */
export function fmtMinutos(m: number | null | undefined): string {
  if (m === null || m === undefined) return "—";
  const v = Math.round(m);
  if (v < 60) return `${v} min`;
  const h = Math.floor(v / 60);
  if (h < 24) return `${h}h ${String(v % 60).padStart(2, "0")}min`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

/**
 * As "visões" da lista de processos — o seletor "Mostrar" (SI-34).
 *
 * A página gerencial tem um único "Ver lista de processos"; cada número dos
 * subgrupos (Entrada, Andamento, Saída, Prazos) é uma destas visões, e a lista
 * deixa escolher qual. Cada visão é EXATAMENTE a consulta que produziu o
 * número na página — é o que mantém "número da página = total da lista"
 * (garantido pelo backend em `test_relatorios_protocolo_medidas.py`).
 *
 * `hoje`: a visão é a situação de hoje e ignora o período. O período continua
 * na URL, para voltar a uma visão "no período" sem perder o filtro.
 */
export type VisaoProcessos =
  | "abertos"
  | "arquivados"
  | "em_andamento"
  | "em_transito"
  | "parados"
  | "no_prazo"
  | "com_atraso"
  | "dentro_do_prazo"
  | "vencendo"
  | "vencidos";

interface DefVisao {
  id: VisaoProcessos;
  rotulo: string;
  grupo: string;
  hoje: boolean;
  campos: (diasParado: number) => Pick<FiltroDaUrl, "data_base" | "situacao" | "parado_ha_dias" | "prazo">;
}

export const VISOES_PROCESSOS: DefVisao[] = [
  { id: "abertos", rotulo: "Abertos no período", grupo: "Entrada e saída (no período)", hoje: false,
    campos: () => ({ data_base: "abertura" }) },
  { id: "arquivados", rotulo: "Arquivados no período", grupo: "Entrada e saída (no período)", hoje: false,
    campos: () => ({ data_base: "arquivamento" }) },
  { id: "em_andamento", rotulo: "Em andamento", grupo: "Andamento (hoje)", hoje: true,
    campos: () => ({ situacao: "em_andamento" }) },
  { id: "em_transito", rotulo: "Em trânsito", grupo: "Andamento (hoje)", hoje: true,
    campos: () => ({ situacao: "em_transito" }) },
  { id: "parados", rotulo: "Parados", grupo: "Andamento (hoje)", hoje: true,
    campos: (d) => ({ parado_ha_dias: d }) },
  { id: "no_prazo", rotulo: "Arquivados no prazo", grupo: "Prazos — arquivados no período", hoje: false,
    campos: () => ({ data_base: "arquivamento", prazo: "concluido_no_prazo" }) },
  { id: "com_atraso", rotulo: "Arquivados com atraso", grupo: "Prazos — arquivados no período", hoje: false,
    campos: () => ({ data_base: "arquivamento", prazo: "concluido_atrasado" }) },
  { id: "dentro_do_prazo", rotulo: "Dentro do prazo", grupo: "Prazos — em aberto hoje", hoje: true,
    campos: () => ({ prazo: "dentro_do_prazo" }) },
  { id: "vencendo", rotulo: "Vencendo", grupo: "Prazos — em aberto hoje", hoje: true,
    campos: () => ({ prazo: "vencendo" }) },
  { id: "vencidos", rotulo: "Vencidos", grupo: "Prazos — em aberto hoje", hoje: true,
    campos: () => ({ prazo: "atrasado" }) },
];

const DIAS_PARADO_PADRAO = 15;

/** Qual visão a URL descreve. Sem nada específico, "abertos no período". */
export function visaoDe(f: FiltroDaUrl): DefVisao {
  const dias = f.dias_parado ?? DIAS_PARADO_PADRAO;
  const igual = (v: DefVisao) => {
    const c = v.campos(dias);
    return (
      (c.data_base ?? "abertura") === (f.data_base ?? "abertura") &&
      c.situacao === f.situacao &&
      (c.parado_ha_dias !== undefined) === (f.parado_ha_dias !== undefined) &&
      c.prazo === f.prazo
    );
  };
  return VISOES_PROCESSOS.find(igual) ?? VISOES_PROCESSOS[0];
}

/** A URL com a visão trocada — o recorte comum e o período ficam. */
export function comVisao(f: FiltroDaUrl, id: VisaoProcessos): FiltroDaUrl {
  const v = VISOES_PROCESSOS.find((x) => x.id === id) ?? VISOES_PROCESSOS[0];
  const dias = f.dias_parado ?? DIAS_PARADO_PADRAO;
  return {
    ...recorteComum(f),
    dias_parado: f.dias_parado,
    // os filtros próprios da lista ficam ao trocar de visão
    sigilo: f.sigilo,
    origem: f.origem,
    ...v.campos(dias),
    ...(id === "parados" ? { parado_ha_dias: f.parado_ha_dias ?? dias } : {}),
  };
}

/** O que a lista pede ao servidor para a visão da URL: visão "de hoje" não
 * leva período. */
export function consultaDaLista(f: FiltroDaUrl): RelatorioFiltroInput {
  const v = visaoDe(f);
  const c = v.campos(f.dias_parado ?? DIAS_PARADO_PADRAO);
  return {
    ...recorteComum(f),
    ...(v.hoje ? { desde: undefined, ate: undefined } : {}),
    data_base: c.data_base === "arquivamento" ? "arquivamento" : "abertura",
    situacao: c.situacao,
    parado_ha_dias: v.id === "parados" ? (f.parado_ha_dias ?? c.parado_ha_dias) : undefined,
    prazo: c.prazo,
    sigilo: f.sigilo,
    origem: f.origem,
  };
}

/**
 * As visões da lista de documentação — o "Mostrar" dela. Cada uma é a lista
 * de um número do grupo Documentação da página gerencial; o backend conta a
 * mesma consulta (`relatorios_documentacao`). `hoje`: sem período.
 */
interface DefVisaoDoc {
  id: VisaoDocumentacao;
  rotulo: string;
  grupo: string;
  hoje: boolean;
  /** Por qual data o período conta. */
  data: string;
}

export const VISOES_DOCUMENTACAO: DefVisaoDoc[] = [
  { id: "documentos", rotulo: "Todos que exigem documentos", grupo: "Documentos exigidos (abertos no período)",
    hoje: false, data: "abertura" },
  { id: "doc_pendente", rotulo: "Pendentes", grupo: "Documentos exigidos (abertos no período)",
    hoje: false, data: "abertura" },
  { id: "doc_parcial", rotulo: "Parciais", grupo: "Documentos exigidos (abertos no período)",
    hoje: false, data: "abertura" },
  { id: "doc_completo", rotulo: "Completos", grupo: "Documentos exigidos (abertos no período)",
    hoje: false, data: "abertura" },
  { id: "compl_pedida", rotulo: "Complementação pedida no período", grupo: "Complementação",
    hoje: false, data: "pedido" },
  { id: "compl_aberta", rotulo: "Aguardando o cidadão (hoje)", grupo: "Complementação",
    hoje: true, data: "" },
  { id: "compl_respondida", rotulo: "Respondida no período", grupo: "Complementação",
    hoje: false, data: "resposta do cidadão" },
];

export function visaoDocDe(f: FiltroDaUrl): DefVisaoDoc {
  return VISOES_DOCUMENTACAO.find((v) => v.id === f.visao) ?? VISOES_DOCUMENTACAO[0];
}

/** O que a lista de documentação pede ao servidor: visão "de hoje" sem período. */
export function consultaDaDocumentacao(f: FiltroDaUrl): DocumentacaoFiltroInput {
  const v = visaoDocDe(f);
  return {
    ...recorteComum(f),
    data_base: undefined,
    ...(v.hoje ? { desde: undefined, ate: undefined } : {}),
    visao: v.id,
  };
}
