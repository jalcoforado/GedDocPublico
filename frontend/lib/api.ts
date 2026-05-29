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

// Fase 15 — branding/white-label do tenant atual (resolvido pelo Host header).
export interface BrandingResponse {
  slug: string;
  nome: string;
  cor_primaria: string | null;
  logo_url: string | null;
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
  /** Sigilo gradual — credencial de acesso (só super-usuário altera) */
  nivel_acesso_sigilo: NivelSigilo;
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
  /** Só aplicado em update e apenas por super-usuário */
  nivel_acesso_sigilo?: NivelSigilo;
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
  /** Fase P2 — NUP federal, só preenchido quando tenant tem usar_nup_federal=true */
  nup?: string | null;
  numero_origem: string | null;
  data_hora_abertura: string;
  ativo: boolean;
  publico: boolean;
  /** Sigilo gradual (LAI): ostensivo|interno|reservado|secreto|ultrassecreto */
  nivel_sigilo: NivelSigilo;
  externo: boolean;
  assunto: string | null;
  tipo_processo: string | null;
  manifestante: string | null;
  manifestante_cpf_cnpj: string | null;
  unidade_proprietaria: string | null;
  local_atual: string | null;
}

export type NivelSigilo =
  | "ostensivo"
  | "interno"
  | "reservado"
  | "secreto"
  | "ultrassecreto";

export const NIVEL_SIGILO_LABEL: Record<NivelSigilo, string> = {
  ostensivo: "Ostensivo",
  interno: "Interno",
  reservado: "Reservado",
  secreto: "Secreto",
  ultrassecreto: "Ultrassecreto",
};

/** Graus de sigilo legal (LAI) que exigem TCI: fundamento + autoridade + prazo. */
export const GRAUS_SIGILO_LEGAL: NivelSigilo[] = [
  "reservado",
  "secreto",
  "ultrassecreto",
];

/** Prazo máximo de restrição por grau (LAI art. 24 §1º). */
export const NIVEL_PRAZO_MAX: Partial<Record<NivelSigilo, number>> = {
  reservado: 5,
  secreto: 15,
  ultrassecreto: 25,
};

export interface AnexoNoProcesso {
  id: number;
  /** Fase P6 — id do JOIN (necessário pra desentranhar) */
  id_anexo_processo?: number | null;
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
  /** TCI — preenchido só para graus de sigilo legal */
  sigilo_fundamento_legal: string | null;
  sigilo_autoridade: string | null;
  sigilo_prazo_anos: number | null;
  sigilo_data_classificacao: string | null;
  sigilo_data_desclassificacao: string | null;
  movimentacoes: MovimentacaoItem[];
  anexos: AnexoNoProcesso[];
}

export interface ClassificarSigiloInput {
  nivel: NivelSigilo;
  fundamento_legal?: string | null;
  autoridade?: string | null;
  prazo_anos?: number | null;
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
  /** ostensivo|interno na abertura; sigilo legal exige classificação posterior */
  nivel_sigilo?: NivelSigilo;
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
  nivel_sigilo: NivelSigilo;
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

export interface CidadaoEspecie {
  id: number;
  codigo: string;
  nome: string;
}

export interface CidadaoAnexo {
  id: number;
  descricao: string | null;
  e_doc: string | null;
  qtd_paginas: number | null;
  publico: boolean;
}

export interface CidadaoProcessoListItem {
  id: number;
  numero_processo: string;
  nup: string | null;
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
  especie_nome: string | null;
  ccd_codigo: string | null;
  ccd_nome: string | null;
  movimentacoes: CidadaoMovimentacao[];
  anexos: CidadaoAnexo[];
}

export interface AbrirProcessoCidadaoInput {
  id_assunto: number;
  corpo: string;
  observacao?: string;
  id_especie_documental?: number;
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
  alterarSenha: (senha_atual: string, nova_senha: string) =>
    request<void>("/auth/alterar-senha", {
      method: "POST",
      body: JSON.stringify({ senha_atual, nova_senha }),
    }),
  // Fase 15 — branding público (não exige login)
  branding: () => request<BrandingResponse>("/branding/me"),
  permissoes: () => request<PermissaoMeResponse>("/permissoes/me"),
  modulos: () => request<ModulosMeResponse>("/modulos/me"),

  niveis: () => request<Nivel[]>("/catalogo/niveis"),
  sistemas: () => request<Sistema[]>("/catalogo/sistemas"),
  transacoes: () => request<Transacao[]>("/catalogo/transacoes"),
  tiposUnidade: () => request<TipoUnidade[]>("/catalogo/tipos-unidade"),
  prioridades: () => request<Prioridade[]>("/catalogo/prioridades"),

  assinaturas: {
    minhasPendentes: () =>
      request<PendenciaAssinatura[]>("/solicitacoes-assinatura/me/pendentes"),
    listarDoProcesso: (processoId: number) =>
      request<SolicitacaoAssinatura[]>(
        `/processos/${processoId}/solicitacoes-assinatura`,
      ),
    solicitar: (processoId: number, body: SolicitarAssinaturaInput) =>
      request<SolicitacaoAssinatura>(
        `/processos/${processoId}/solicitacoes-assinatura`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    cancelar: (solicitacaoId: number) =>
      request<SolicitacaoAssinatura>(
        `/solicitacoes-assinatura/${solicitacaoId}/cancelar`,
        { method: "POST" },
      ),
    assinar: (assinaturaAnexoId: number, senha: string) =>
      request<SolicitacaoAssinatura>(
        `/assinaturas/${assinaturaAnexoId}/assinar`,
        { method: "POST", body: JSON.stringify({ senha }) },
      ),
    recusar: (solicitacaoId: number, motivo: string) =>
      request<SolicitacaoAssinatura>(
        `/solicitacoes-assinatura/${solicitacaoId}/recusar`,
        { method: "POST", body: JSON.stringify({ motivo }) },
      ),
    validar: (assinaturaAnexoId: number) =>
      request<ValidacaoAssinatura>(`/assinaturas/${assinaturaAnexoId}/validar`),
    evidencias: (assinaturaAnexoId: number) =>
      request<EvidenciasAssinatura>(`/assinaturas/${assinaturaAnexoId}/evidencias`),
  },

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
    classificarSigilo: (id: number, data: ClassificarSigiloInput) =>
      request<ProcessoDetail>(`/processos/${id}/classificar-sigilo`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
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
    especies: () => requestCidadao<CidadaoEspecie[]>("/cidadao/especies"),
    listarProcessos: () =>
      requestCidadao<CidadaoProcessoListItem[]>("/cidadao/processos"),
    getProcesso: (id: number) =>
      requestCidadao<CidadaoProcessoDetail>(`/cidadao/processos/${id}`),
    abrirProcesso: (data: AbrirProcessoCidadaoInput) =>
      requestCidadao<CidadaoProcessoDetail>("/cidadao/processos", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    uploadAnexo: (processoId: number, file: File, descricao?: string) => {
      const fd = new FormData();
      fd.append("file", file);
      if (descricao) fd.append("descricao", descricao);
      return requestCidadao<CidadaoAnexo>(
        `/cidadao/processos/${processoId}/anexos`,
        { method: "POST", body: fd },
      );
    },
  },
};

// ===== Fase 19-21: Workflow =====

export interface PosicaoXY {
  x: number;
  y: number;
}

export interface WorkflowEstado {
  slug: string;
  nome: string;
  descricao: string | null;
  final: boolean;
  sla_dias: number | null;
  posicao?: PosicaoXY | null;
  /** Unidade responsável (UX fix workflow↔org).
   * - Auto-encaminhamento na transição quando setado e diferente do local atual.
   * - Transição só visível para usuários lotados nessa unidade (admins ven todas).
   */
  id_unidade_responsavel?: number | null;
}

export interface WorkflowTransicao {
  de: string;
  para: string;
  label: string;
  descricao: string | null;
  condicao: string | null;
  grupos_permitidos: string[];
  evento: "manual" | "abertura" | "encaminhamento" | "recebimento";
}

export interface WorkflowDSL {
  version: string;
  estado_inicial: string;
  estados: WorkflowEstado[];
  transicoes: WorkflowTransicao[];
  /** Strict mode: backend bloqueia encaminhamentos/recebimentos fora do trilho. */
  strict?: boolean;
}

export interface WorkflowDefinitionListItem {
  id: number;
  slug: string;
  nome: string;
  versao: number;
  ativo: boolean;
  criado_em: string;
}

export interface WorkflowDefinition {
  id: number;
  slug: string;
  nome: string;
  descricao: string | null;
  versao: number;
  ativo: boolean;
  dsl: WorkflowDSL;
  criado_em: string;
  atualizado_em: string | null;
  id_usuario_criador: number | null;
}

export interface WorkflowTransicaoLog {
  id: number;
  estado_de: string;
  estado_para: string;
  transicao_label: string;
  id_usuario: number | null;
  executada_em: string;
  contexto_snapshot: Record<string, unknown> | null;
}

export interface TransicaoDisponivel {
  de: string;
  para: string;
  label: string;
  descricao: string | null;
  grupos_permitidos: string[];
}

export interface WorkflowInstance {
  id: number;
  id_workflow_definition: number;
  id_processo: number;
  estado_atual: string;
  ativa: boolean;
  iniciada_em: string;
  finalizada_em: string | null;
  id_usuario_inicio: number | null;
}

export interface WorkflowInstanceDetail extends WorkflowInstance {
  transicoes_disponiveis: TransicaoDisponivel[];
  log: WorkflowTransicaoLog[];
  contexto_atual: Record<string, unknown>;
}

// ===== Fase 17: Notificações =====

export interface Notificacao {
  id: number;
  canal: "in_app" | "email" | "whatsapp";
  tipo: string;
  titulo: string;
  mensagem: string;
  link_url: string | null;
  payload: Record<string, unknown> | null;
  prioridade: "baixa" | "normal" | "alta";
  criado_em: string;
  lido_em: string | null;
  enviado_em: string | null;
  erro: string | null;
}

export interface NotificacaoListResponse {
  items: Notificacao[];
  nao_lidas: number;
}

// ===== Fase 18a: Dashboard =====

export interface DashboardBreakdownItem {
  label: string;
  count: number;
}

export interface DashboardKpis {
  periodo_dias: number;
  id_unidade: number | null;
  volume: {
    abertos_periodo: number;
    ativos_hoje: number;
    externos_periodo: number;
    sigilosos_periodo: number;
  };
  conclusao: {
    arquivados_periodo: number;
    taxa_conclusao_pct: number | null;
    tempo_medio_dias: number | null;
  };
  sla: {
    pendentes: number;
    resolvidos_periodo: number;
  };
  /** Fase 18b — contadores do período anterior (mesma duração). UI calcula delta. */
  comparativo: {
    abertos_anterior: number;
    externos_anterior: number;
    sigilosos_anterior: number;
    arquivados_anterior: number;
    tempo_medio_dias_anterior: number | null;
    taxa_conclusao_pct_anterior: number | null;
    sla_resolvidos_anterior: number;
  };
  por_tipo: DashboardBreakdownItem[];
  por_assunto: DashboardBreakdownItem[];
  por_unidade: DashboardBreakdownItem[];
  serie_temporal: { dia: string; count: number }[];
}

export const dashboardApi = {
  kpis: (params?: { periodo?: number; id_unidade?: number }) =>
    request<DashboardKpis>(`/dashboard/kpis${qs(params ?? {})}`),
};

export function dashboardExportCsvUrl(params?: {
  periodo?: number;
  id_unidade?: number;
}): string {
  return `${BROWSER_API_URL}/dashboard/export.csv${qs(params ?? {})}`;
}

export function dashboardExportPdfUrl(
  params?: { periodo?: number; id_unidade?: number },
  inline = true,
): string {
  const baseQs = qs(params ?? {});
  if (inline) return `${BROWSER_API_URL}/dashboard/export.pdf${baseQs}`;
  const sep = baseQs ? "&" : "?";
  return `${BROWSER_API_URL}/dashboard/export.pdf${baseQs}${sep}inline=false`;
}

// ===== Organograma =====

export interface OrganogramaNo {
  id: number;
  id_unidade_pai: number | null;
  unidade_trabalho: string;
  sigla: string | null;
  processos_ativos: number;
  usuarios: number;
  sla_pendentes: number;
  tempo_medio_dias: number | null;
}

export const organogramaApi = {
  tree: () => request<OrganogramaNo[]>(`/organograma`),
};

// ===== Auditoria (Fase 24) =====

export interface AuditLogItem {
  id: number;
  id_usuario: number | null;
  nome_usuario: string | null;
  acao: string;
  entidade: string;
  id_entidade: number | null;
  payload: Record<string, unknown> | null;
  request_id: string | null;
  ip: string | null;
  criado_em: string;
}

export interface AuditLogPage {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilters {
  acao?: string;
  entidade?: string;
  id_entidade?: number;
  id_usuario?: number;
  desde?: string;
  ate?: string;
  page?: number;
  page_size?: number;
}

export const auditApi = {
  list: (filters?: AuditFilters) =>
    request<AuditLogPage>(`/audit${qs(filters ?? {})}`),
};

// ===== Busca global (Fase 24) =====

export interface BuscaResultado {
  q: string;
  processos: { id: number; numero: string; data_abertura: string | null }[];
  manifestantes: { id: number; nome: string; cpf_cnpj: string | null }[];
  usuarios: { id: number; nome: string; email: string }[];
}

export const buscaApi = {
  global: (q: string) => request<BuscaResultado>(`/busca${qs({ q })}`),
};

// ===== Protocolo (Fase P1) =====

export interface EspecieDocumental {
  id: number;
  flag: string;
  nome: string;
  descricao: string | null;
  ativo: boolean;
}

export interface ProtocoloBalcaoPayload {
  id_manifestante: number;
  id_assunto: number;
  id_especie_documental: number;
  id_unidade_proprietaria: number;
  observacao?: string | null;
  numero_origem?: string | null;
  publico?: boolean;
  data_recepcao?: string | null;
  id_ccd_classe?: number | null;
}

export interface ProtocoloBalcaoResult {
  id: number;
  numero_processo: string;
  nup?: string | null;
  data_hora_abertura: string;
  data_recepcao: string | null;
  canal_entrada: "balcao" | "portal" | "email" | "api" | "interno";
  id_especie_documental: number | null;
  especie_documental: string | null;
  manifestante: string;
  assunto: string;
  unidade_proprietaria: string;
}

// ===== Tenant / Configurações =================================================

export interface TenantMe {
  id: number;
  slug: string;
  nome: string;
  plano: string;
  cor_primaria: string | null;
  logo_url: string | null;
  /** Fase P2 — código do órgão (5 dígitos) atribuído pelo SIORG/MP */
  codigo_orgao_nup: string | null;
  /** Fase P2 — se true, processos novos recebem NUP federal além do número legado */
  usar_nup_federal: boolean;
}

export interface NupConfigUpdate {
  codigo_orgao_nup?: string | null;
  usar_nup_federal?: boolean;
}

// ===== Assinaturas pendentes do usuário ======================================

export interface PendenciaAssinatura {
  id_assinatura_anexo: number;
  id_anexo: number;
  anexo_descricao: string | null;
  id_solicitacao: number;
  id_processo: number;
  numero_processo: string;
  nome_solicitante: string;
  dt_inicio: string;
}

// Solicitação de assinatura (espelha SolicitacaoOut do backend)
export interface AssinaturaAnexoStatus {
  id: number;
  id_anexo: number;
  anexo_descricao: string | null;
  assinado: boolean;
  dt_assinatura: string | null;
  status: string;
  nivel: string;
  tem_hash: boolean;
}

export interface AssinanteStatus {
  id_usuario_assinatura: number;
  id_assinante: number;
  nome_assinante: string | null;
  realizada: boolean;
  ordem: number;
  status: string;
  motivo_recusa: string | null;
  anexos: AssinaturaAnexoStatus[];
}

export interface SolicitacaoAssinatura {
  id: number;
  id_processo: number;
  numero_processo: string | null;
  id_solicitante: number;
  nome_solicitante: string | null;
  realizada: boolean;
  cancelada: boolean;
  dt_inicio: string;
  dt_fim: string | null;
  assinantes: AssinanteStatus[];
}

export interface SolicitarAssinaturaInput {
  id_assinantes: number[];
  id_anexos: number[];
  id_tipo_assinatura?: number | null;
}

export interface ValidacaoAssinatura {
  id_assinatura_anexo: number;
  legado: boolean;
  integro: boolean | null;
  nivel: string;
  status: string;
  documento_hash: string | null;
  hash_atual: string | null;
  dt_assinatura: string | null;
  detalhe: string;
}

export interface EvidenciasAssinatura {
  id_assinatura_anexo: number;
  id_anexo: number;
  id_processo: number | null;
  numero_processo: string | null;
  anexo_descricao: string | null;
  nome_assinante: string | null;
  nivel: string;
  status: string;
  metodo_autenticacao: string | null;
  documento_hash: string | null;
  hash_algoritmo: string | null;
  documento_versao: number | null;
  ip_assinatura: string | null;
  user_agent_assinatura: string | null;
  dt_assinatura: string | null;
  id_audit_log: number | null;
  evidencias: Record<string, unknown> | null;
  codigo_validacao?: string | null;
}

export function assinaturaComprovanteUrl(assinaturaAnexoId: number): string {
  return `${BROWSER_API_URL}/assinaturas/${assinaturaAnexoId}/comprovante.pdf`;
}

// PR2e — validação PÚBLICA por código/token. Sem autenticação (anônima):
// não envia cookies. Resposta neutra (404 {valido:false}) NÃO é erro — é o
// caso "não encontrado/indisponível", indistinguível de revogado/sigiloso.
export interface ValidacaoPublica {
  valido: boolean;
  integro: boolean | null;
  signatario: string | null;
  processo_numero: string | null;
  assinado_em: string | null;
  hash: string | null;
  algoritmo: string | null;
  versao_documento: number | null;
  status: string | null;
  detalhe: string | null;
  aviso: string | null;
}

const VALIDACAO_NEUTRA: ValidacaoPublica = {
  valido: false,
  integro: null,
  signatario: null,
  processo_numero: null,
  assinado_em: null,
  hash: null,
  algoritmo: null,
  versao_documento: null,
  status: null,
  detalhe: null,
  aviso: null,
};

export async function validarAssinaturaPublica(
  codigo: string
): Promise<ValidacaoPublica> {
  const res = await fetch(
    `${baseUrl()}/publico/validacao/${encodeURIComponent(codigo)}`,
    { cache: "no-store" } // sem credentials: requisição anônima
  );
  if (res.status === 429) {
    throw new ApiError("Muitas consultas. Tente novamente em instantes.", 429);
  }
  const data = await res.json().catch(() => ({}));
  // 200 (positivo) e 404 (neutro {valido:false}) são ambos resultados válidos.
  return { ...VALIDACAO_NEUTRA, ...(data as Partial<ValidacaoPublica>) };
}

export function validacaoPublicaComprovanteUrl(codigo: string): string {
  return `${BROWSER_API_URL}/publico/validacao/${encodeURIComponent(codigo)}/comprovante.pdf`;
}

export const assinaturasApi = {
  minhasPendentes: () =>
    request<PendenciaAssinatura[]>(`/solicitacoes-assinatura/me/pendentes`),
};

// ===== P6 — Apensamento + Desentranhamento + Volumes ========================

export interface ApensamentoDetail {
  id: number;
  id_processo_apensado: number;
  id_processo_principal: number;
  id_usuario: number;
  motivo: string;
  criado_em: string;
  desapensado_em: string | null;
  id_usuario_desapensamento: number | null;
  motivo_desapensamento: string | null;
  numero_processo_apensado: string | null;
  numero_processo_principal: string | null;
  usuario_nome: string | null;
  usuario_desapensamento_nome: string | null;
  ativo: boolean;
}

export interface ProcessoApensadoListItem {
  id_apensamento: number;
  id_processo: number;
  numero_processo: string;
  nup: string | null;
  manifestante: string | null;
  apensado_em: string;
  motivo: string;
}

export interface DesentranhamentoResult {
  id_anexo_processo: number;
  id_anexo: number;
  descricao_anexo: string | null;
  desentranhado_em: string;
  motivo: string;
  autoridade: string;
  usuario_nome: string | null;
}

export interface VolumeDetail {
  id: number;
  id_processo: number;
  numero: number;
  pagina_inicial: number | null;
  pagina_final: number | null;
  observacao: string | null;
  id_usuario: number;
  criado_em: string;
  usuario_nome: string | null;
}

export const apensamentoApi = {
  apensar: (processoId: number, payload: { id_processo_principal: number; motivo: string }) =>
    request<ApensamentoDetail>(`/processos/${processoId}/apensar`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  desapensar: (processoId: number, motivo: string) =>
    request<ApensamentoDetail>(`/processos/${processoId}/desapensar`, {
      method: "POST",
      body: JSON.stringify({ motivo }),
    }),
  listarHistorico: (processoId: number, apenasAtivos = false) =>
    request<ApensamentoDetail[]>(
      `/processos/${processoId}/apensamentos${qs({ apenas_ativos: apenasAtivos })}`,
    ),
  listarApensados: (processoId: number) =>
    request<ProcessoApensadoListItem[]>(`/processos/${processoId}/apensados`),
};

export function termoApensamentoPdfUrl(apensamentoId: number): string {
  return `${BROWSER_API_URL}/processos/apensamentos/${apensamentoId}/termo.pdf`;
}

export const desentranhamentoApi = {
  desentranhar: (
    processoId: number,
    anexoProcessoId: number,
    payload: { motivo: string; autoridade: string },
  ) =>
    request<DesentranhamentoResult>(
      `/processos/${processoId}/anexos/${anexoProcessoId}/desentranhar`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
};

export function termoDesentranhamentoPdfUrl(
  processoId: number,
  anexoProcessoId: number,
): string {
  return `${BROWSER_API_URL}/processos/${processoId}/anexos/${anexoProcessoId}/termo-desentranhamento.pdf`;
}

export const volumesApi = {
  list: (processoId: number) =>
    request<VolumeDetail[]>(`/processos/${processoId}/volumes`),
  create: (
    processoId: number,
    payload: {
      numero: number;
      pagina_inicial?: number | null;
      pagina_final?: number | null;
      observacao?: string | null;
    },
  ) =>
    request<VolumeDetail>(`/processos/${processoId}/volumes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (
    volumeId: number,
    payload: {
      pagina_inicial?: number | null;
      pagina_final?: number | null;
      observacao?: string | null;
    },
  ) =>
    request<VolumeDetail>(`/processos/volumes/${volumeId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (volumeId: number) =>
    request<void>(`/processos/volumes/${volumeId}`, { method: "DELETE" }),
};

export const tenantsApi = {
  me: () => request<TenantMe>(`/tenants/me`),
  updateNupConfig: (payload: NupConfigUpdate) =>
    request<TenantMe>(`/tenants/me/nup-config`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};

export const protocoloApi = {
  listEspecies: (incluirInativas = false) =>
    request<EspecieDocumental[]>(
      `/protocolo/especies-documentais${qs({ incluir_inativas: incluirInativas })}`,
    ),
  createEspecie: (payload: { flag: string; nome: string; descricao?: string }) =>
    request<EspecieDocumental>(`/protocolo/especies-documentais`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  protocolarBalcao: (payload: ProtocoloBalcaoPayload) =>
    request<ProtocoloBalcaoResult>(`/protocolo/balcao`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export function protocoloEtiquetaPdfUrl(processoId: number): string {
  return `${BROWSER_API_URL}/protocolo/${processoId}/etiqueta.pdf`;
}

export function protocoloComprovantePdfUrl(processoId: number): string {
  return `${BROWSER_API_URL}/protocolo/${processoId}/comprovante.pdf`;
}

// ===== P4 — CCD + TTD + Temporalidade ========================================

export interface CcdClasse {
  id: number;
  codigo: string;
  nome: string;
  descricao: string | null;
  id_classe_pai: number | null;
  palavras_chave: string | null;
  ativo: boolean;
}

export interface CcdClasseTreeNode {
  id: number;
  codigo: string;
  nome: string;
  descricao: string | null;
  palavras_chave: string | null;
  ativo: boolean;
  filhos: CcdClasseTreeNode[];
}

export interface CcdClasseCreatePayload {
  codigo: string;
  nome: string;
  descricao?: string | null;
  id_classe_pai?: number | null;
  palavras_chave?: string | null;
}

export interface CcdClasseUpdatePayload {
  codigo?: string;
  nome?: string;
  descricao?: string | null;
  id_classe_pai?: number | null;
  palavras_chave?: string | null;
  ativo?: boolean;
}

export type DestinoFinal = "ELIMINACAO" | "GUARDA_PERMANENTE";

export interface TtdRegra {
  id: number;
  id_ccd_classe: number;
  id_especie_documental: number | null;
  anos_corrente: number;
  anos_intermediario: number;
  destino_final: DestinoFinal;
  observacao: string | null;
  ativo: boolean;
}

export interface TtdRegraDetail extends TtdRegra {
  classe_codigo: string;
  classe_nome: string;
  especie_nome: string | null;
}

export interface TtdRegraCreatePayload {
  id_ccd_classe: number;
  id_especie_documental?: number | null;
  anos_corrente: number;
  anos_intermediario: number;
  destino_final: DestinoFinal;
  observacao?: string | null;
}

export interface TtdRegraUpdatePayload {
  id_especie_documental?: number | null;
  anos_corrente?: number;
  anos_intermediario?: number;
  destino_final?: DestinoFinal;
  observacao?: string | null;
  ativo?: boolean;
}

export interface SugestaoCcd {
  id_ccd_classe: number;
  codigo: string;
  nome: string;
  score: number;
  matched_keywords: string[];
}

export interface Temporalidade {
  id_processo: number;
  numero_processo: string;
  id_ccd_classe: number | null;
  classe_codigo: string | null;
  classe_nome: string | null;
  id_especie_documental: number | null;
  especie_nome: string | null;
  regra_aplicada: TtdRegra | null;
  data_referencia: string | null;
  fim_fase_corrente: string | null;
  fim_fase_intermediaria: string | null;
  destino_final: DestinoFinal | null;
  motivo_sem_regra: string | null;
}

export const ccdApi = {
  list: (incluirInativas = false) =>
    request<CcdClasse[]>(
      `/protocolo/ccd-classes${qs({ incluir_inativas: incluirInativas })}`,
    ),
  tree: () => request<CcdClasseTreeNode[]>(`/protocolo/ccd-classes/tree`),
  create: (payload: CcdClasseCreatePayload) =>
    request<CcdClasse>(`/protocolo/ccd-classes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: number, payload: CcdClasseUpdatePayload) =>
    request<CcdClasse>(`/protocolo/ccd-classes/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: number) =>
    request<void>(`/protocolo/ccd-classes/${id}`, { method: "DELETE" }),
  sugerir: (params: { id_assunto?: number; texto?: string; limit?: number }) =>
    request<SugestaoCcd[]>(`/protocolo/sugerir-ccd${qs(params)}`),
};

export const ttdApi = {
  list: (id_ccd_classe?: number) =>
    request<TtdRegraDetail[]>(
      `/protocolo/ttd-regras${qs({ id_ccd_classe })}`,
    ),
  create: (payload: TtdRegraCreatePayload) =>
    request<TtdRegra>(`/protocolo/ttd-regras`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: number, payload: TtdRegraUpdatePayload) =>
    request<TtdRegra>(`/protocolo/ttd-regras/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: number) =>
    request<void>(`/protocolo/ttd-regras/${id}`, { method: "DELETE" }),
};

export const temporalidadeApi = {
  doProcesso: (processoId: number) =>
    request<Temporalidade>(`/processos/${processoId}/temporalidade`),
  vencendoPrazo: (params?: { dias?: number; incluir_permanentes?: boolean }) =>
    request<Temporalidade[]>(`/protocolo/vencendo-prazo${qs(params ?? {})}`),
};

// ===== Trail do processo (caminho percorrido) =====

export interface TrailStep {
  ordem: number;
  id_unidade: number;
  unidade_nome: string;
  unidade_sigla: string | null;
  tipo: "abertura" | "encaminhamento";
  data: string | null;
  recebido_em: string | null;
  cancelado: boolean;
  atual: boolean;
}

export const processosApi = {
  trail: (processoId: number) =>
    request<TrailStep[]>(`/processos/${processoId}/trail`),
};

export interface NotificacaoPreferencias {
  in_app: boolean;
  email: boolean;
  whatsapp: boolean;
}

export const notificacoesApi = {
  listarMinhas: (params?: { apenas_nao_lidas?: boolean; limit?: number }) =>
    request<NotificacaoListResponse>(`/notificacoes/me${qs(params ?? {})}`),
  marcarLida: (id: number) =>
    request<Notificacao>(`/notificacoes/${id}/marcar-lida`, { method: "POST" }),
  marcarTodasLidas: () =>
    request<{ atualizadas: number }>(`/notificacoes/marcar-todas-lidas`, {
      method: "POST",
    }),
  getPreferencias: () =>
    request<NotificacaoPreferencias>(`/notificacoes/preferencias`),
  setPreferencias: (p: Partial<NotificacaoPreferencias>) =>
    request<NotificacaoPreferencias>(`/notificacoes/preferencias`, {
      method: "PUT",
      body: JSON.stringify(p),
    }),
  // Fase 16 — telefone do usuário corrente
  getTelefone: () => request<{ telefone: string | null }>(`/notificacoes/telefone`),
  setTelefone: (telefone: string | null) =>
    request<{ telefone: string | null }>(`/notificacoes/telefone`, {
      method: "PUT",
      body: JSON.stringify({ telefone }),
    }),
  whatsappTest: (telefone: string, mensagem: string) =>
    request<{
      id_notificacao: number;
      enviado_em: string | null;
      erro: string | null;
      provider: string;
    }>(`/notificacoes/whatsapp-test`, {
      method: "POST",
      body: JSON.stringify({ telefone, mensagem }),
    }),
};

export interface WorkflowSlaAlerta {
  id: number;
  id_workflow_instance: number;
  estado: string;
  sla_dias: number;
  dias_no_estado: number;
  criado_em: string;
  resolvido_em: string | null;
  resolucao: string | null;
  notificado_em: string | null;
  id_processo: number;
  numero_processo: string | null;
  estado_atual: string;
  instance_ativa: boolean;
}

export interface WorkflowDefinitionCreateInput {
  slug: string;
  nome: string;
  descricao?: string | null;
  dsl: WorkflowDSL;
}

export interface WorkflowDefinitionUpdateInput {
  nome?: string;
  descricao?: string | null;
  dsl?: WorkflowDSL;
  ativo?: boolean;
}

export interface TestExprResult {
  resultado: boolean | number | string | null;
  truthy: boolean;
  erro: string | null;
}

export interface TipoProcessoWorkflow {
  id: number;
  id_tipo_processo: number;
  slug_workflow: string;
  criado_em: string;
  atualizado_em: string | null;
}

export const workflowApi = {
  listDefinitions: (apenasAtivos = true) =>
    request<WorkflowDefinitionListItem[]>(
      `/workflow-definitions${qs({ apenas_ativos: apenasAtivos })}`,
    ),
  getDefinition: (id: number) =>
    request<WorkflowDefinition>(`/workflow-definitions/${id}`),
  createDefinition: (data: WorkflowDefinitionCreateInput) =>
    request<WorkflowDefinition>("/workflow-definitions", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateDefinition: (id: number, data: WorkflowDefinitionUpdateInput) =>
    request<WorkflowDefinition>(`/workflow-definitions/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  testExpr: (expressao: string, contexto: Record<string, unknown>) =>
    request<TestExprResult>("/workflow-definitions/test-expr", {
      method: "POST",
      body: JSON.stringify({ expressao, contexto }),
    }),
  getProcessoWorkflow: (processoId: number) =>
    request<WorkflowInstanceDetail | null>(`/processos/${processoId}/workflow`),
  transicionar: (instanceId: number, para: string) =>
    request<WorkflowInstanceDetail>(
      `/workflow-instances/${instanceId}/transicao`,
      { method: "POST", body: JSON.stringify({ para, contexto_extra: {} }) },
    ),
  listAlertas: (params?: { apenas_pendentes?: boolean; id_processo?: number }) =>
    request<WorkflowSlaAlerta[]>(`/workflow-alertas${qs(params ?? {})}`),
  resolverAlerta: (alertaId: number, resolucao: string) =>
    request<WorkflowSlaAlerta>(`/workflow-alertas/${alertaId}/resolver`, {
      method: "POST",
      body: JSON.stringify({ resolucao }),
    }),
  verificarAgora: () =>
    request<{ task_id: string; tenant_id: number }>(
      `/workflow-alertas/verificar-agora`,
      { method: "POST" },
    ),
  // Mapeamento tipo_processo → workflow (Fase 20b + UX fix)
  listMapeamentos: () =>
    request<TipoProcessoWorkflow[]>(`/tipo-processo-workflow`),
  setMapeamento: (idTipoProcesso: number, slugWorkflow: string | null) =>
    request<TipoProcessoWorkflow | null>(
      `/tipo-processo-workflow/${idTipoProcesso}`,
      { method: "PUT", body: JSON.stringify({ slug_workflow: slugWorkflow }) },
    ),
  // Instância manual (sem mapeamento)
  iniciarInstance: (idWorkflowDefinition: number, idProcesso: number) =>
    request<WorkflowInstance>(`/workflow-instances`, {
      method: "POST",
      body: JSON.stringify({
        id_workflow_definition: idWorkflowDefinition,
        id_processo: idProcesso,
      }),
    }),
  // Fase 22c — versões + migração
  listVersoes: (wfId: number) =>
    request<
      {
        id: number;
        slug: string;
        nome: string;
        versao: number;
        ativo: boolean;
        criado_em: string;
        instances_ativas: number;
      }[]
    >(`/workflow-definitions/${wfId}/versoes`),
  migrarInstance: (
    instanceId: number,
    idDestino: number,
    mapaEstados?: Record<string, string>,
  ) =>
    request<WorkflowInstance>(`/workflow-instances/${instanceId}/migrar`, {
      method: "POST",
      body: JSON.stringify({
        id_workflow_definition_destino: idDestino,
        mapa_estados: mapaEstados ?? null,
      }),
    }),
  listInstances: (params?: { id_workflow_definition?: number; apenas_ativas?: boolean }) =>
    request<WorkflowInstance[]>(`/workflow-instances${qs(params ?? {})}`),
};

// Backward-compat exports
export const apiLogin = api.login;
export const apiMe = api.me;
