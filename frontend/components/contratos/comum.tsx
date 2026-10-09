import { Badge } from "@/components/ui/badge";
import {
  SITUACAO_CONTRATO_LABEL,
  type SituacaoAditivo,
  type SituacaoContrato,
} from "@/lib/api";

/** Transação que gateia o módulo inteiro na G1. */
export const TRANSACAO_CONTRATO = "contrato";

export const ROTA_CONTRATOS = "/m/contratos/contratos";

/** `""` → `null`: campo opcional vazio não vai como string vazia para a API. */
export function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

/** aaaa-mm-dd de hoje + `dias`, no fuso LOCAL (toISOString daria o dia em UTC). */
export function isoEmDias(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** "12,50%" a partir do Decimal em string que o backend devolve. */
export function fmtPercentual(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return `${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

const INTENT_SITUACAO: Record<SituacaoContrato, "neutral" | "success" | "info" | "danger"> = {
  RASCUNHO: "neutral",
  VIGENTE: "success",
  ENCERRADO: "info",
  RESCINDIDO: "danger",
};

export function SituacaoContratoBadge({ situacao }: { situacao: SituacaoContrato }) {
  return <Badge intent={INTENT_SITUACAO[situacao]}>{SITUACAO_CONTRATO_LABEL[situacao]}</Badge>;
}

const INTENT_ADITIVO: Record<SituacaoAditivo, "neutral" | "success" | "danger"> = {
  RASCUNHO: "neutral",
  VIGENTE: "success",
  ANULADO: "danger",
};

const LABEL_ADITIVO: Record<SituacaoAditivo, string> = {
  RASCUNHO: "Rascunho",
  VIGENTE: "Vigente",
  ANULADO: "Anulado",
};

export function SituacaoAditivoBadge({ situacao }: { situacao: SituacaoAditivo }) {
  return <Badge intent={INTENT_ADITIVO[situacao]}>{LABEL_ADITIVO[situacao]}</Badge>;
}

/**
 * Quanto falta para vencer. `null` = contrato fora de vigência (rascunho,
 * encerrado, rescindido): não há prazo a mostrar.
 *
 * As faixas são as do painel: até 30 dias é urgente porque uma nova licitação
 * não cabe mais; até 120 é o horizonte em que ainda dá para decidir.
 */
export function VencimentoBadge({ dias }: { dias: number | null }) {
  if (dias === null) return null;
  if (dias < 0) {
    return <Badge intent="danger">Vencido há {Math.abs(dias)} dia(s)</Badge>;
  }
  if (dias === 0) return <Badge intent="danger">Vence hoje</Badge>;
  if (dias <= 30) return <Badge intent="danger">Vence em {dias} dia(s)</Badge>;
  if (dias <= 120) return <Badge intent="warning">Vence em {dias} dias</Badge>;
  return null;
}

/** Caixa de erro dos formulários — mesmo padrão das demais telas de módulo. */
export function ErroFormulario({ mensagem }: { mensagem: string | null }) {
  if (!mensagem) return null;
  return (
    <div
      role="alert"
      className="rounded border border-danger/40 bg-danger-soft p-3 text-sm text-danger-soft-foreground"
    >
      {mensagem}
    </div>
  );
}
