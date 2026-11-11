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
  ModoUnidadeRelatorio,
  RelatorioFiltroInput,
  SituacaoRelatorio,
  StatusPrazoRelatorio,
} from "@/lib/api";

export const ROTA_RELATORIOS = "/m/protocolo/relatorios";
export const ROTA_LISTA_PROCESSOS = "/m/protocolo/relatorios/processos";
export const ROTA_LISTA_TRAMITACAO = "/m/protocolo/relatorios/tramitacao";
export const ROTA_LISTA_ASSINATURAS = "/m/protocolo/relatorios/assinaturas";

export const ROTULO_MODO_UNIDADE: Record<ModoUnidadeRelatorio, string> = {
  envolvida: "dona ou onde está agora",
  dona: "só a dona do processo",
  atual: "só onde está agora",
  passou: "por onde o processo passou",
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
  return {
    id_unidade: inteiro(sp.get("id_unidade")),
    modo_unidade: modo && MODOS.includes(modo) ? modo : undefined,
    id_assunto: inteiro(sp.get("id_assunto")),
    id_tipo_processo: inteiro(sp.get("id_tipo_processo")),
    desde: desde && DIA.test(desde) ? desde : undefined,
    ate: ate && DIA.test(ate) ? ate : undefined,
    data_base: (DATAS_BASE as string[]).includes(dataBase ?? "")
      ? (dataBase as DataBaseRelatorio)
      : undefined,
    situacao: situacao && SITUACOES.includes(situacao) ? situacao : undefined,
    parado_ha_dias: inteiro(sp.get("parado_ha_dias")),
    prazo: prazo && PRAZOS.includes(prazo) ? prazo : undefined,
    dias_parado: inteiro(sp.get("dias_parado")),
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
    ["desde", f.desde],
    ["ate", f.ate],
    ["data_base", f.data_base],
    ["situacao", f.situacao],
    ["parado_ha_dias", f.parado_ha_dias],
    ["prazo", f.prazo],
    ["dias_parado", f.dias_parado],
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
    desde: f.desde,
    ate: f.ate,
  };
}

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
