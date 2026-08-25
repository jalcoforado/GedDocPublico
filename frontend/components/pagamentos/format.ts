// Helpers de formatação compartilhados pelas telas de Pagamentos (BRL/pt-BR).

export function fmtMoeda(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** dd/mm/yyyy — usado em vencimentos e datas de referência. */
export function fmtData(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("pt-BR");
}

/** dd/mm/aa — usado em metadados discretos (ex.: "aprovado por X em dd/mm/aa"). */
export function fmtDataCurta(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

export function fmtDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} ${hora}`;
}

/** Meia-noite local de hoje — base para os agrupamentos de urgência da Tesouraria. */
export function hojeSemHora(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export function parseDataLocal(v: string): Date {
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v);
  return d;
}

/** Tamanho de arquivo legível (KB/MB) — usado na lista de documentos do débito (F2). */
export function fmtTamanho(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
