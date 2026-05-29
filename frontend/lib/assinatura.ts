// Helpers puros da UI de assinatura — extraídos para serem testáveis sem
// renderizar componentes/providers (PR2c).
import type {
  AssinanteStatus,
  SolicitacaoAssinatura,
  ValidacaoAssinatura,
  ValidacaoPublicaStatus,
} from "./api";

export type BadgeIntent = "success" | "warning" | "danger";

// PR2f — apresentação do status da validação pública (calculado no backend; a
// UI só reflete). `exibeCodigo` controla se código/URL podem aparecer.
export function statusValidacaoPublica(status: ValidacaoPublicaStatus | undefined): {
  label: string;
  intent: BadgeIntent;
  exibeCodigo: boolean;
} {
  switch (status) {
    case "ativa":
      return { label: "Validação pública ativa", intent: "success", exibeCodigo: true };
    case "revogada":
      return { label: "Validação pública revogada", intent: "danger", exibeCodigo: true };
    case "bloqueada_sigilo":
      return { label: "Bloqueada por sigilo", intent: "warning", exibeCodigo: false };
    case "indisponivel":
      return { label: "Validação pública indisponível", intent: "warning", exibeCodigo: false };
    default:
      return { label: "Sem validação pública", intent: "warning", exibeCodigo: false };
  }
}

export function statusSolicitacao(
  s: Pick<SolicitacaoAssinatura, "cancelada" | "realizada">,
): { label: string; intent: BadgeIntent } {
  if (s.cancelada) return { label: "Cancelada", intent: "danger" };
  if (s.realizada) return { label: "Concluída", intent: "success" };
  return { label: "Em andamento", intent: "warning" };
}

export function statusAssinante(
  a: Pick<AssinanteStatus, "status" | "realizada">,
): { label: string; intent: BadgeIntent } {
  if (a.status === "recusada") return { label: "Recusou", intent: "danger" };
  if (a.realizada) return { label: "Assinou tudo", intent: "success" };
  return { label: "Pendente", intent: "warning" };
}

export function validacaoMensagem(
  v: Pick<ValidacaoAssinatura, "legado" | "integro">,
): { texto: string; ok: boolean | null } {
  if (v.legado)
    return {
      texto: "Assinatura legada — sem verificação de integridade.",
      ok: null,
    };
  if (v.integro) return { texto: "Assinatura íntegra.", ok: true };
  return { texto: "Documento alterado após a assinatura.", ok: false };
}
