/**
 * Formatação e regras de arquivo do portal do cidadão. Ficam juntas porque
 * só o portal as usa e porque as telas de abrir pedido e de responder
 * complementação precisam anunciar o MESMO limite.
 */

/** Data `dd/mm/aaaa`. Data pura (`2026-05-01`) é lida no fuso local — lida
 *  como UTC, à noite em UTC-3 ela virava o dia anterior. */
export function fmtDia(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("pt-BR");
}

/** Data e hora `dd/mm/aaaa às 14:30`, sem segundos. */
export function fmtDiaHora(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${d.toLocaleDateString("pt-BR")} às ${hora}`;
}

// Tem de espelhar `max_upload_size_mb` do backend (app/config.py, hoje 20 e
// também no MAX_UPLOAD_SIZE_MB do compose). Anunciava 25: o portal aceitava um
// arquivo de 22 MB, subia tudo e só então o servidor recusava com "Arquivo
// excede 20 MB". Ao mudar o limite no backend, mudar aqui junto.
export const MAX_UPLOAD_MB = 20;
export const EXTENSOES_PERMITIDAS = [
  "pdf", "png", "jpg", "jpeg", "gif", "webp",
  "doc", "docx", "xls", "xlsx", "odt", "ods",
];
/** O mesmo, em palavras de quem não sabe o que é extensão. */
export const FORMATOS_EM_PALAVRAS = "PDF, foto (JPG ou PNG) ou documento do Word/Excel";

export function extensaoDe(nome: string): string {
  const i = nome.lastIndexOf(".");
  return i >= 0 ? nome.slice(i + 1).toLowerCase() : "";
}

/** Motivo pelo qual o arquivo não pode subir, ou `null` se pode. */
export function problemaDoArquivo(f: File): string | null {
  const ext = extensaoDe(f.name);
  if (!EXTENSOES_PERMITIDAS.includes(ext)) {
    return `Arquivos .${ext || "sem extensão"} não são aceitos. Envie ${FORMATOS_EM_PALAVRAS}.`;
  }
  if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `O arquivo excede ${MAX_UPLOAD_MB} MB, o limite. Escolha um arquivo menor ou tire a foto com menos qualidade.`;
  }
  return null;
}

export function tamanhoLegivel(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}
