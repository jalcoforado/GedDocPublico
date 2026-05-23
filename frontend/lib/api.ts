const BROWSER_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8090/api/v2";
const SERVER_API_URL = process.env.INTERNAL_API_URL ?? BROWSER_API_URL;

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_API_URL : BROWSER_API_URL;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  usuario_id: number;
  usuario_email: string;
  nome: string;
}

export interface MeResponse {
  id: number;
  nome: string;
  email: string;
  cargo: string | null;
  id_unidade_trabalho: number | null;
}

export interface PermissaoItem {
  codigo: string;
  transacao: string;
  inserir: boolean;
  atualizar: boolean;
  excluir: boolean;
}
export interface PermissaoMeResponse {
  usuario_id: number;
  is_super_usuario: boolean;
  nivel_valor: number | null;
  permissoes: PermissaoItem[];
}

export interface ModuloItem {
  id: number;
  modulo: string;
  icone: string | null;
  url: string | null;
}
export interface ModulosMeResponse {
  items: ModuloItem[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// Fase 1
export interface Usuario {
  id: number;
  nome: string;
  email: string;
  cpf: string;
  id_unidade_trabalho: number | null;
  cargo: string | null;
  ativo: boolean;
}
export interface UsuarioDetail extends Usuario {
  grupos: number[];
  unidades_extras: number[];
}
export interface UsuarioInput {
  nome: string;
  email: string;
  cpf: string;
  id_unidade_trabalho?: number | null;
  cargo?: string | null;
  ativo?: boolean;
  senha?: string;
  grupos?: number[];
}

export interface UnidadeTrabalho {
  id: number;
  unidade_trabalho: string;
  sigla: string | null;
  id_unidade_pai: number | null;
  id_tipo_unidade_trabalho: number | null;
}

export interface Grupo {
  id: number;
  grupo: string;
  id_nivel: number;
  id_sistema: number;
}

export interface Transacao {
  id: number;
  transacao: string;
  codigo: string;
}

export interface GrupoTransacao {
  id_transacao: number;
  inserir: boolean;
  atualizar: boolean;
  excluir: boolean;
}

export interface Nivel {
  id: number;
  nivel: string;
  valor: number;
}

export interface Sistema {
  id: number;
  sistema: string;
  app: string | null;
}

export interface TipoUnidade {
  id: number;
  tipo_unidade_trabalho: string;
  codigo: string | null;
}

// Fase 2
export interface Estado {
  id: number;
  estado: string;
  uf: string;
}
export interface Cidade {
  id: number;
  cidade: string;
  id_estado: number | null;
}
export interface Bairro {
  id: number;
  bairro: string;
  id_cidade: number | null;
  ativo: boolean;
}
export interface Endereco {
  id: number;
  id_cidade: number | null;
  id_bairro: number | null;
  id_estado: number | null;
  rua: string | null;
  numero: string | null;
  complemento: string | null;
  latitude: number | null;
  longitude: number | null;
}
export interface TipoManifestante {
  id: number;
  tipo_manifestante: string;
  id_categoria: number;
  ativo: boolean;
}
export interface Manifestante {
  id: number;
  id_tipo_manifestante: number;
  cpf_cnpj: string | null;
  nome: string | null;
  responsavel: string | null;
  organizacao: string | null;
  telefone_celular: string | null;
  telefone_residencial: string | null;
  telefone_comercial: string | null;
  email: string | null;
  observacao: string | null;
  ativo: boolean;
}
export interface TipoProcesso {
  id: number;
  tipo_processo: string;
  exige_processo_pai: boolean;
  ativo: boolean;
}
export interface Assunto {
  id: number;
  assunto: string;
  id_tipo_processo: number;
  exige_processo_pai: boolean;
  ativo: boolean;
}
export interface TipoAnexo {
  id: number;
  tipo_anexo: string;
}
export interface AssuntoTipoAnexo {
  id: number;
  id_assunto: number | null;
  id_tipo_processo: number | null;
  id_tipo_anexo: number;
  obrigatorio: boolean;
  opcional: boolean;
}

// Fase 3
export interface ProcessoListItem {
  id: number;
  numero_processo: string;
  numero_origem: string | null;
  data_hora_abertura: string;
  ativo: boolean;
  publico: boolean;
  externo: boolean;
  assunto: string | null;
  tipo_processo: string | null;
  manifestante: string | null;
  manifestante_cpf_cnpj: string | null;
  unidade_proprietaria: string | null;
  local_atual: string | null;
}

export interface AnexoNoProcesso {
  id: number;
  descricao: string | null;
  publico: boolean;
  qtd_paginas: number | null;
  e_doc: string | null;
  tipo_anexo: string | null;
  ordem: number | null;
}

export interface EncaminhamentoOut {
  id: number;
  unidade_origem: string | null;
  unidade_destino: string;
  prioridade: string | null;
  quantidade_folhas: number;
  data_prazo: string | null;
  recebido: boolean;
  data_hora_recebimento: string | null;
  cancelado: boolean;
}

export interface DespachoOut {
  id: number;
  despacho: string;
  usuario: string | null;
}

export interface MovimentacaoItem {
  id: number;
  data_hora_movimentacao: string;
  acao_flag: string;
  acao: string;
  status_acao: string;
  status_movimentacao: string;
  unidade_responsavel: string | null;
  usuario: string | null;
  despacho: DespachoOut | null;
  encaminhamento: EncaminhamentoOut | null;
}

export interface ProcessoDetail extends ProcessoListItem {
  observacao: string | null;
  corpo: string | null;
  virtual: boolean;
  migrado: boolean;
  id_processo_pai: number | null;
  movimentacoes: MovimentacaoItem[];
  anexos: AnexoNoProcesso[];
}

export interface ProcessoListFilters {
  page?: number;
  page_size?: number;
  q?: string;
  id_assunto?: number;
  id_manifestante?: number;
  id_unidade?: number;
  apenas_ativos?: boolean;
  desde?: string;
  ate?: string;
}

export interface ProcessoCreateInput {
  id_assunto: number;
  id_manifestante: number;
  id_unidade_proprietaria: number;
  observacao?: string | null;
  corpo?: string | null;
  numero_origem?: string | null;
  publico?: boolean;
  externo?: boolean;
  virtual?: boolean;
}

export interface EncaminharInput {
  id_unidade_destino: number;
  id_prioridade: number;
  quantidade_folhas?: number;
  data_prazo?: string | null;
  despacho?: string | null;
}

export interface CancelarEncaminhamentoInput {
  despacho?: string | null;
}

export interface Prioridade {
  id: number;
  prioridade: string;
  fator: number;
  cor: string;
}

// Fase 6 — Relatórios
export interface RelatorioFiltroInput {
  id_unidade?: number;
  id_assunto?: number;
  id_tipo_processo?: number;
  desde?: string;
  ate?: string;
  apenas_ativos?: boolean;
  max_rows?: number;
}

export interface RelatorioTotais {
  total: number;
  ativos: number;
  inativos: number;
  sigilosos: number;
  externos: number;
}

export interface RelatorioBreakdownItem {
  label: string;
  count: number;
  pct: number;
}

export interface RelatorioProcessoRow {
  id: number;
  numero_processo: string;
  data_hora_abertura: string;
  manifestante: string | null;
  tipo_processo: string | null;
  assunto: string | null;
  unidade_proprietaria: string | null;
  local_atual: string | null;
  ativo: boolean;
  publico: boolean;
  externo: boolean;
}

export interface RelatorioResposta {
  filtros_aplicados: RelatorioFiltroInput;
  nome_unidade: string | null;
  totais: RelatorioTotais;
  por_tipo_processo: RelatorioBreakdownItem[];
  por_unidade_proprietaria: RelatorioBreakdownItem[];
  processos: RelatorioProcessoRow[];
}

// Fase 6.2 — Relatório de tramitação
export interface TramitacaoEtapa {
  id_unidade: number | null;
  unidade: string | null;
  chegou_em: string | null;
  saiu_em: string | null;
  minutos_no_local: number | null;
  prazo_estipulado: string | null;
  atrasou: boolean;
}

export interface TramitacaoProcesso {
  id: number;
  numero_processo: string;
  data_hora_abertura: string;
  ativo: boolean;
  manifestante: string | null;
  assunto: string | null;
  qtd_encaminhamentos: number;
  qtd_unidades_visitadas: number;
  minutos_total: number;
  minutos_em_andamento: number;
  teve_atraso: boolean;
  qtd_atrasos: number;
  local_atual: string | null;
  etapas: TramitacaoEtapa[];
}

export interface TramitacaoPorUnidade {
  id_unidade: number | null;
  unidade: string | null;
  qtd_passagens: number;
  qtd_atrasos: number;
  minutos_total: number;
  minutos_medio: number;
}

export interface RelatorioTramitacaoResposta {
  filtros_aplicados: RelatorioFiltroInput;
  nome_unidade: string | null;
  qtd_processos: number;
  qtd_processos_com_atraso: number;
  minutos_medio_por_processo: number;
  por_unidade: TramitacaoPorUnidade[];
  processos: TramitacaoProcesso[];
}

// Fase 6.3 — Relatório de assinaturas
export type StatusSolicitacaoAssin = "pendente" | "concluida" | "cancelada";

export interface AssinaturasFiltroInput {
  desde?: string;
  ate?: string;
  id_solicitante?: number;
  id_assinante?: number;
  status?: StatusSolicitacaoAssin;
  max_rows?: number;
}

export interface AssinaturasTotais {
  total: number;
  pendentes: number;
  concluidas: number;
  canceladas: number;
  minutos_medio_conclusao: number;
}

export interface AssinanteAgregado {
  id_assinante: number;
  nome: string | null;
  pendentes: number;
  concluidas: number;
  minutos_medio: number;
}

export interface SolicitanteAgregado {
  id_solicitante: number;
  nome: string | null;
  total: number;
  pendentes: number;
  concluidas: number;
  canceladas: number;
}

export interface SolicitacaoRow {
  id: number;
  id_processo: number;
  numero_processo: string | null;
  id_solicitante: number;
  nome_solicitante: string | null;
  status: StatusSolicitacaoAssin;
  dt_inicio: string;
  dt_fim: string | null;
  minutos_decorridos: number | null;
  qtd_assinantes: number;
  qtd_assinantes_concluidos: number;
  qtd_anexos: number;
  qtd_anexos_assinados: number;
  assinantes_resumo: string[];
}

export interface RelatorioAssinaturasResposta {
  filtros_aplicados: AssinaturasFiltroInput;
  totais: AssinaturasTotais;
  por_assinante: AssinanteAgregado[];
  por_solicitante: SolicitanteAgregado[];
  solicitacoes: SolicitacaoRow[];
}

// Fase 7 — Jobs assíncronos
export type JobStatus = "pendente" | "em_andamento" | "concluido" | "falhou";

export interface JobOut {
  id: number;
  tipo: string;
  descricao: string | null;
  status: JobStatus;
  parametros: Record<string, unknown> | null;
  resultado_path: string | null;
  erro: string | null;
  id_usuario: number;
  nome_usuario: string | null;
  celery_task_id: string | null;
  criado_em: string;
  iniciado_em: string | null;
  concluido_em: string | null;
}

export interface AgendaItem {
  nome: string;
  task: string;
  schedule: string;
  kwargs: Record<string, unknown> | null;
}

// Fase 8 — Cidadão
export interface CidadaoMe {
  id: number;
  nome: string | null;
  cpf_cnpj: string | null;
  email: string | null;
  telefone: string | null;
  telefone_whatsapp: boolean;
  ativo: boolean;
}

export interface CidadaoLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  cidadao: CidadaoMe;
}

export interface CidadaoCadastroInput {
  cpf_cnpj: string;
  nome: string;
  email: string;
  senha: string;
  telefone?: string;
  telefone_whatsapp?: boolean;
}

export interface CidadaoAssunto {
  id: number;
  assunto: string;
  tipo_processo: string | null;
}

export interface CidadaoProcessoListItem {
  id: number;
  numero_processo: string;
  data_hora_abertura: string;
  assunto: string | null;
  tipo_processo: string | null;
  local_atual: string | null;
  ativo: boolean;
  publico: boolean;
}

export interface CidadaoMovimentacao {
  id: number;
  data_hora_movimentacao: string;
  acao: string;
  unidade_responsavel: string | null;
  despacho_publico: string | null;
}

export interface CidadaoProcessoDetail extends CidadaoProcessoListItem {
  observacao: string | null;
  corpo: string | null;
  movimentacoes: CidadaoMovimentacao[];
}

export interface AbrirProcessoCidadaoInput {
  id_assunto: number;
  corpo: string;
  observacao?: string;
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(init.headers);
  // Não setar Content-Type para FormData — fetch monta o boundary sozinho.
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  // Cookie HttpOnly: JS não pode ler (`readCookie` retorna null). O navegador
  // envia o cookie automaticamente em requests same-origin, e o backend tem
  // fallback em `get_current_user`. Só usamos Bearer se houver token explícito
  // (testes, scripts curl).
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "include",  // garante envio de cookies cross-origin (dev: 8090 → 3000)
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((d: any) => d.msg).join("; ")
          : `Erro ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return data as T;
}

// Versão da função `request` que usa o cookie `aprimora_cidadao_token` em vez
// do cookie de admin. Necessária pra coexistência (mesmo navegador pode estar
// logado como admin E como cidadão sem que um sobrescreva o outro).
async function requestCidadao<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  // Cookie HttpOnly (aprimora_cidadao_token) enviado automaticamente same-origin.
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "include",
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((d: any) => d.msg).join("; ")
          : `Erro ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return data as T;
}

export function anexoDownloadUrl(anexoId: number): string {
  // Auth via cookie `aprimora_token` (servida no fallback do backend).
  return `${BROWSER_API_URL}/anexos/${anexoId}/download`;
}

export function anexoInlineUrl(anexoId: number): string {
  return `${BROWSER_API_URL}/anexos/${anexoId}/download?inline=1`;
}

export function anexoCarimbadoUrl(anexoId: number, inline = true): string {
  return `${BROWSER_API_URL}/anexos/${anexoId}/carimbado.pdf${inline ? "" : "?inline=false"}`;
}

export function processoCapaUrl(processoId: number, inline = true): string {
  return `${BROWSER_API_URL}/processos/${processoId}/capa.pdf${inline ? "" : "?inline=false"}`;
}

export function processoCompletoUrl(processoId: number, inline = true): string {
  return `${BROWSER_API_URL}/processos/${processoId}/completo.pdf${inline ? "" : "?inline=false"}`;
}

export function etiquetaUnicaUrl(processoId: number, inline = true): string {
  return `${BROWSER_API_URL}/processos/${processoId}/etiqueta-unica.pdf${inline ? "" : "?inline=false"}`;
}

export function etiquetaDuplaUrl(processoId: number, inline = true): string {
  return `${BROWSER_API_URL}/processos/${processoId}/etiqueta-dupla.pdf${inline ? "" : "?inline=false"}`;
}

export function comprovanteUrl(
  encaminhamentoId: number,
  tipo: "envio" | "recebimento",
  inline = true,
): string {
  const qs = inline ? `tipo=${tipo}` : `tipo=${tipo}&inline=false`;
  return `${BROWSER_API_URL}/processos/encaminhamentos/${encaminhamentoId}/comprovante.pdf?${qs}`;
}

function relatorioQs(f: RelatorioFiltroInput): string {
  return qs({
    id_unidade: f.id_unidade,
    id_assunto: f.id_assunto,
    id_tipo_processo: f.id_tipo_processo,
    desde: f.desde,
    ate: f.ate,
    apenas_ativos: f.apenas_ativos ? "true" : undefined,
    max_rows: f.max_rows,
  });
}

export function relatorioCsvUrl(f: RelatorioFiltroInput): string {
  return `${BROWSER_API_URL}/relatorios/processos.csv${relatorioQs(f)}`;
}

export function relatorioPdfUrl(f: RelatorioFiltroInput, inline = true): string {
  const baseQs = relatorioQs(f);
  if (inline) return `${BROWSER_API_URL}/relatorios/processos.pdf${baseQs}`;
  const sep = baseQs ? "&" : "?";
  return `${BROWSER_API_URL}/relatorios/processos.pdf${baseQs}${sep}inline=false`;
}

export function tramitacaoCsvUrl(f: RelatorioFiltroInput): string {
  return `${BROWSER_API_URL}/relatorios/tramitacao.csv${relatorioQs(f)}`;
}

export function tramitacaoPdfUrl(f: RelatorioFiltroInput, inline = true): string {
  const baseQs = relatorioQs(f);
  if (inline) return `${BROWSER_API_URL}/relatorios/tramitacao.pdf${baseQs}`;
  const sep = baseQs ? "&" : "?";
  return `${BROWSER_API_URL}/relatorios/tramitacao.pdf${baseQs}${sep}inline=false`;
}

function assinaturasQs(f: AssinaturasFiltroInput): string {
  return qs({
    desde: f.desde,
    ate: f.ate,
    id_solicitante: f.id_solicitante,
    id_assinante: f.id_assinante,
    status: f.status,
    max_rows: f.max_rows,
  });
}

export function assinaturasCsvUrl(f: AssinaturasFiltroInput): string {
  return `${BROWSER_API_URL}/relatorios/assinaturas.csv${assinaturasQs(f)}`;
}

export function assinaturasPdfUrl(f: AssinaturasFiltroInput, inline = true): string {
  const baseQs = assinaturasQs(f);
  if (inline) return `${BROWSER_API_URL}/relatorios/assinaturas.pdf${baseQs}`;
  const sep = baseQs ? "&" : "?";
  return `${BROWSER_API_URL}/relatorios/assinaturas.pdf${baseQs}${sep}inline=false`;
}

export function jobResultadoUrl(jobId: number): string {
  return `${BROWSER_API_URL}/jobs/${jobId}/resultado`;
}

export interface AnexoUploadInput {
  file: File;
  descricao?: string;
  id_tipo_anexo?: number;
  publico?: boolean;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  }
  const q = s.toString();
  return q ? `?${q}` : "";
}

function crud<T, C = Partial<T>, U = Partial<T>>(path: string) {
  return {
    list: (params?: Record<string, any>) =>
      request<Paginated<T>>(`${path}${qs(params ?? {})}`),
    listAll: (params?: Record<string, any>) => request<T[]>(`${path}${qs(params ?? {})}`),
    get: (id: number) => request<T>(`${path}/${id}`),
    create: (data: C) =>
      request<T>(path, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: U) =>
      request<T>(`${path}/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    remove: (id: number) => request<void>(`${path}/${id}`, { method: "DELETE" }),
  };
}

export const api = {
  login: (email: string, senha: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, senha }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: (token?: string) => request<MeResponse>("/auth/me", {}, token),
  permissoes: () => request<PermissaoMeResponse>("/permissoes/me"),
  modulos: () => request<ModulosMeResponse>("/modulos/me"),

  niveis: () => request<Nivel[]>("/catalogo/niveis"),
  sistemas: () => request<Sistema[]>("/catalogo/sistemas"),
  transacoes: () => request<Transacao[]>("/catalogo/transacoes"),
  tiposUnidade: () => request<TipoUnidade[]>("/catalogo/tipos-unidade"),
  prioridades: () => request<Prioridade[]>("/catalogo/prioridades"),

  usuarios: {
    list: (params?: { page?: number; page_size?: number; q?: string }) =>
      request<Paginated<Usuario>>(`/usuarios${qs(params ?? {})}`),
    get: (id: number) => request<UsuarioDetail>(`/usuarios/${id}`),
    create: (data: UsuarioInput) =>
      request<UsuarioDetail>("/usuarios", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<UsuarioInput>) =>
      request<UsuarioDetail>(`/usuarios/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) => request<void>(`/usuarios/${id}`, { method: "DELETE" }),
    setGrupos: (id: number, grupos: number[]) =>
      request<UsuarioDetail>(`/usuarios/${id}/grupos`, {
        method: "PUT",
        body: JSON.stringify(grupos),
      }),
    setUnidades: (id: number, unidades: number[]) =>
      request<UsuarioDetail>(`/usuarios/${id}/unidades`, {
        method: "PUT",
        body: JSON.stringify(unidades),
      }),
  },

  unidades: {
    list: (params?: { page?: number; page_size?: number; q?: string }) =>
      request<Paginated<UnidadeTrabalho>>(`/unidades-trabalho${qs(params ?? {})}`),
    get: (id: number) => request<UnidadeTrabalho>(`/unidades-trabalho/${id}`),
    create: (data: Omit<UnidadeTrabalho, "id">) =>
      request<UnidadeTrabalho>("/unidades-trabalho", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Omit<UnidadeTrabalho, "id">>) =>
      request<UnidadeTrabalho>(`/unidades-trabalho/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) =>
      request<void>(`/unidades-trabalho/${id}`, { method: "DELETE" }),
  },

  grupos: {
    list: () => request<Grupo[]>("/grupos"),
    get: (id: number) => request<Grupo>(`/grupos/${id}`),
    create: (data: Omit<Grupo, "id">) =>
      request<Grupo>("/grupos", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Omit<Grupo, "id">>) =>
      request<Grupo>(`/grupos/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    transacoes: (id: number) => request<GrupoTransacao[]>(`/grupos/${id}/transacoes`),
    setTransacoes: (id: number, transacoes: Omit<GrupoTransacao, never>[]) =>
      request<GrupoTransacao[]>(`/grupos/${id}/transacoes`, {
        method: "PUT",
        body: JSON.stringify({ transacoes }),
      }),
  },

  // Fase 2
  estados: () => request<Estado[]>("/estados"),
  cidades: crud<Cidade>("/cidades"),
  bairros: crud<Bairro>("/bairros"),
  enderecos: crud<Endereco>("/enderecos"),
  tiposManifestante: {
    list: () => request<TipoManifestante[]>("/tipos-manifestante"),
    create: (data: Omit<TipoManifestante, "id">) =>
      request<TipoManifestante>("/tipos-manifestante", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Omit<TipoManifestante, "id">>) =>
      request<TipoManifestante>(`/tipos-manifestante/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) =>
      request<void>(`/tipos-manifestante/${id}`, { method: "DELETE" }),
  },
  manifestantes: crud<Manifestante>("/manifestantes"),
  tiposProcesso: {
    list: () => request<TipoProcesso[]>("/tipos-processo"),
    create: (data: Omit<TipoProcesso, "id">) =>
      request<TipoProcesso>("/tipos-processo", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Omit<TipoProcesso, "id">>) =>
      request<TipoProcesso>(`/tipos-processo/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) =>
      request<void>(`/tipos-processo/${id}`, { method: "DELETE" }),
  },
  assuntos: crud<Assunto>("/assuntos"),
  tiposAnexo: {
    list: () => request<TipoAnexo[]>("/tipos-anexo"),
    create: (data: Omit<TipoAnexo, "id">) =>
      request<TipoAnexo>("/tipos-anexo", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Omit<TipoAnexo, "id">>) =>
      request<TipoAnexo>(`/tipos-anexo/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) => request<void>(`/tipos-anexo/${id}`, { method: "DELETE" }),
  },

  // Fase 3
  processos: {
    list: (params?: ProcessoListFilters) =>
      request<Paginated<ProcessoListItem>>(`/processos${qs(params ?? {})}`),
    get: (id: number) => request<ProcessoDetail>(`/processos/${id}`),
    create: (data: ProcessoCreateInput) =>
      request<ProcessoDetail>("/processos", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    encaminhar: (id: number, data: EncaminharInput) =>
      request<ProcessoDetail>(`/processos/${id}/encaminhamentos`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    receber: (id: number) =>
      request<ProcessoDetail>(`/processos/${id}/receber`, { method: "POST" }),
    cancelarEncaminhamento: (encaminhamentoId: number, data: CancelarEncaminhamentoInput) =>
      request<ProcessoDetail>(`/processos/encaminhamentos/${encaminhamentoId}/cancelar`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    uploadAnexo: (processoId: number, input: AnexoUploadInput) => {
      const fd = new FormData();
      fd.append("file", input.file);
      if (input.descricao) fd.append("descricao", input.descricao);
      if (input.id_tipo_anexo) fd.append("id_tipo_anexo", String(input.id_tipo_anexo));
      fd.append("publico", String(input.publico ?? true));
      return request<AnexoNoProcesso>(`/processos/${processoId}/anexos`, {
        method: "POST",
        body: fd,
      });
    },
    deleteAnexo: (processoId: number, anexoId: number) =>
      request<void>(`/processos/${processoId}/anexos/${anexoId}`, {
        method: "DELETE",
      }),
  },

  // Fase 6 — Relatórios
  relatorios: {
    processos: (f: RelatorioFiltroInput) =>
      request<RelatorioResposta>(`/relatorios/processos.json${relatorioQs(f)}`),
    tramitacao: (f: RelatorioFiltroInput) =>
      request<RelatorioTramitacaoResposta>(
        `/relatorios/tramitacao.json${relatorioQs(f)}`,
      ),
    assinaturas: (f: AssinaturasFiltroInput) =>
      request<RelatorioAssinaturasResposta>(
        `/relatorios/assinaturas.json${assinaturasQs(f)}`,
      ),
  },

  // Fase 7 — Jobs assíncronos
  jobs: {
    list: (params?: { todos?: boolean; limit?: number }) =>
      request<JobOut[]>(`/jobs${qs(params ?? {})}`),
    get: (id: number) => request<JobOut>(`/jobs/${id}`),
    processoCompleto: (idProcesso: number) =>
      request<JobOut>("/jobs/processo-completo", {
        method: "POST",
        body: JSON.stringify({ id_processo: idProcesso }),
      }),
    carimbarAnexos: (idProcesso: number) =>
      request<JobOut>("/jobs/carimbar-anexos", {
        method: "POST",
        body: JSON.stringify({ id_processo: idProcesso }),
      }),
    relatorioTramitacao: (f: RelatorioFiltroInput) =>
      request<JobOut>("/jobs/relatorio-tramitacao", {
        method: "POST",
        body: JSON.stringify({
          id_unidade: f.id_unidade,
          id_assunto: f.id_assunto,
          id_tipo_processo: f.id_tipo_processo,
          desde: f.desde,
          ate: f.ate,
          apenas_ativos: f.apenas_ativos ?? false,
          max_processos: f.max_rows ?? 200,
        }),
      }),
    limparAntigos: (dias: number) =>
      request<JobOut>("/jobs/limpar-antigos", {
        method: "POST",
        body: JSON.stringify({ dias }),
      }),
    agenda: () => request<AgendaItem[]>("/jobs/agenda"),
  },

  // Fase 8 — Cidadão (usa cookie aprimora_cidadao_token)
  cidadao: {
    cadastrar: (data: CidadaoCadastroInput) =>
      requestCidadao<CidadaoMe>("/cidadao/cadastrar", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    login: (cpf_cnpj: string, senha: string) =>
      requestCidadao<CidadaoLoginResponse>("/cidadao/login", {
        method: "POST",
        body: JSON.stringify({ cpf_cnpj, senha }),
      }),
    logout: () => requestCidadao<void>("/cidadao/logout", { method: "POST" }),
    me: (token?: string) => requestCidadao<CidadaoMe>("/cidadao/me", {}, token),
    assuntos: () => requestCidadao<CidadaoAssunto[]>("/cidadao/assuntos"),
    listarProcessos: () =>
      requestCidadao<CidadaoProcessoListItem[]>("/cidadao/processos"),
    getProcesso: (id: number) =>
      requestCidadao<CidadaoProcessoDetail>(`/cidadao/processos/${id}`),
    abrirProcesso: (data: AbrirProcessoCidadaoInput) =>
      requestCidadao<CidadaoProcessoDetail>("/cidadao/processos", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
};

// Backward-compat exports
export const apiLogin = api.login;
export const apiMe = api.me;
