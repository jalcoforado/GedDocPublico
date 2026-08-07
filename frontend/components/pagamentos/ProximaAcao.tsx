"use client";

import type { SituacaoTramitacao } from "@/lib/api";
import {
  AJUSTE_AUTORIDADE,
  AJUSTE_GESTOR,
  AJUSTE_VALIDACAO,
  AUTORIZADA,
  AGUARDANDO_AUTORIDADE,
  AGUARDANDO_GESTOR,
  AGUARDANDO_VALIDACAO,
  CANCELADA,
  INDEFERIDA_AUTORIDADE,
  REJEITADA_GESTOR,
  RASCUNHO,
} from "@/components/pagamentos/situacoes";

interface ProximaAcaoProps {
  tramitacao: SituacaoTramitacao;
  /** Transações que o usuário possui (ex: ['pagamento_solicitar', 'pagamento_gerir']) */
  perfis: string[];
  onAction?: (acao: string, etapa?: string) => void;
}

interface AcaoItem {
  chave: string;
  label: string;
  primaria?: boolean;
  destrutiva?: boolean;
  etapa?: string;
}

const ACOES_POR_ETAPA: Record<
  SituacaoTramitacao,
  {
    transacao: string | null;
    fraseResponsavel: string;
    fraseTerceiro: string;
    acoes: AcaoItem[];
  }
> = {
  RASCUNHO: {
    transacao: "pagamento_solicitar",
    fraseResponsavel:
      "Rascunho. Complete os dados e envie para o gestor da pasta.",
    fraseTerceiro:
      "Esta solicitação ainda é um rascunho da unidade setorial.",
    acoes: [
      {
        chave: "enviar",
        label: "Enviar para o gestor",
        primaria: true,
        etapa: "UNIDADE",
      },
      {
        chave: "cancelar",
        label: "Cancelar solicitação",
        destrutiva: true,
        etapa: "UNIDADE",
      },
    ],
  },
  AGUARDANDO_GESTOR: {
    transacao: "pagamento_gerir",
    fraseResponsavel:
      "Esta solicitação aguarda sua análise como gestor da pasta.",
    fraseTerceiro:
      "Esta solicitação aguarda a análise do gestor da pasta.",
    acoes: [
      {
        chave: "gestor/autorizar",
        label: "Autorizar solicitação",
        primaria: true,
        etapa: "GESTOR",
      },
      {
        chave: "ajuste/solicitar",
        label: "Solicitar ajustes",
        etapa: "GESTOR",
      },
      {
        chave: "gestor/rejeitar",
        label: "Rejeitar solicitação",
        destrutiva: true,
        etapa: "GESTOR",
      },
    ],
  },
  AJUSTE_GESTOR: {
    transacao: "pagamento_solicitar",
    fraseResponsavel:
      "O gestor da pasta pediu correções. Veja o motivo no histórico, corrija e reenvie.",
    fraseTerceiro:
      "Aguardando a unidade setorial responder ao ajuste pedido pelo gestor.",
    acoes: [
      {
        chave: "ajuste/responder",
        label: "Reenviar ao gestor",
        primaria: true,
        etapa: "UNIDADE",
      },
      {
        chave: "cancelar",
        label: "Cancelar solicitação",
        destrutiva: true,
        etapa: "UNIDADE",
      },
    ],
  },
  AGUARDANDO_VALIDACAO: {
    transacao: "pagamento_validar",
    fraseResponsavel:
      "Esta solicitação aguarda sua conferência de conformidade.",
    fraseTerceiro:
      "Esta solicitação aguarda a validação da unidade financeira.",
    acoes: [
      {
        chave: "validar",
        label: "Validar conformidade",
        primaria: true,
        etapa: "VALIDACAO",
      },
      {
        chave: "ajuste/solicitar",
        label: "Solicitar ajustes",
        etapa: "VALIDACAO",
      },
    ],
  },
  AJUSTE_VALIDACAO: {
    transacao: "pagamento_solicitar",
    fraseResponsavel:
      "A unidade financeira apontou inconformidade. Corrija e reenvie para nova validação.",
    fraseTerceiro:
      "Aguardando a unidade setorial responder ao ajuste pedido pela validação financeira.",
    acoes: [
      {
        chave: "ajuste/responder",
        label: "Reenviar para validação",
        primaria: true,
        etapa: "UNIDADE",
      },
      {
        chave: "cancelar",
        label: "Cancelar solicitação",
        destrutiva: true,
        etapa: "UNIDADE",
      },
    ],
  },
  AGUARDANDO_AUTORIDADE: {
    transacao: "pagamento_autorizar",
    fraseResponsavel:
      "Esta solicitação aguarda sua aprovação e ordenação de pagamento.",
    fraseTerceiro:
      "Esta solicitação aguarda a autoridade competente.",
    acoes: [
      {
        chave: "autoridade/aprovar",
        label: "Aprovar e ordenar pagamento",
        primaria: true,
        etapa: "AUTORIDADE",
      },
      {
        chave: "ajuste/solicitar",
        label: "Solicitar ajustes",
        etapa: "AUTORIDADE",
      },
      {
        chave: "autoridade/indeferir",
        label: "Não aprovar",
        destrutiva: true,
        etapa: "AUTORIDADE",
      },
    ],
  },
  AJUSTE_AUTORIDADE: {
    transacao: "pagamento_solicitar",
    fraseResponsavel:
      "A autoridade pediu correções. Corrija e reenvie para nova apreciação.",
    fraseTerceiro:
      "Aguardando a unidade setorial responder ao ajuste pedido pela autoridade.",
    acoes: [
      {
        chave: "ajuste/responder",
        label: "Reenviar à autoridade",
        primaria: true,
        etapa: "UNIDADE",
      },
      {
        chave: "cancelar",
        label: "Cancelar solicitação",
        destrutiva: true,
        etapa: "UNIDADE",
      },
    ],
  },
  AUTORIZADA: {
    transacao: null,
    fraseResponsavel:
      "Autorizada. O pagamento segue para a tesouraria conforme a ordem cronológica.",
    fraseTerceiro:
      "Autorizada. O pagamento segue para a tesouraria conforme a ordem cronológica.",
    acoes: [],
  },
  REJEITADA_GESTOR: {
    transacao: null,
    fraseResponsavel:
      "Rejeitada pelo gestor da pasta. O motivo está no histórico.",
    fraseTerceiro:
      "Rejeitada pelo gestor da pasta. O motivo está no histórico.",
    acoes: [],
  },
  INDEFERIDA_AUTORIDADE: {
    transacao: null,
    fraseResponsavel:
      "Indeferida pela autoridade competente. O motivo está no histórico.",
    fraseTerceiro:
      "Indeferida pela autoridade competente. O motivo está no histórico.",
    acoes: [],
  },
  CANCELADA: {
    transacao: null,
    fraseResponsavel:
      "Cancelada pela unidade solicitante. O motivo está no histórico.",
    fraseTerceiro:
      "Cancelada pela unidade solicitante. O motivo está no histórico.",
    acoes: [],
  },
};

/**
 * Bloco "próxima ação": frase contextualizada e botões de ação permitidos.
 * Ação que o perfil não pode executar é OCULTADA — botão cinza sem motivo é pior.
 */
export function ProximaAcao({
  tramitacao,
  perfis,
  onAction,
}: ProximaAcaoProps) {
  const config = ACOES_POR_ETAPA[tramitacao];
  const temTransacao = config.transacao && perfis.includes(config.transacao);
  const frase = temTransacao ? config.fraseResponsavel : config.fraseTerceiro;

  // Filtra ações que o usuário pode executar
  const acoesPossiveis = config.acoes.filter((acao) => {
    if (!acao.etapa) return true;

    // Se a ação é um solicitar_ajuste, precisa de qualquer uma das 3 transações
    if (acao.chave === "ajuste/solicitar") {
      return perfis.some((p) =>
        [
          "pagamento_gerir",
          "pagamento_validar",
          "pagamento_autorizar",
        ].includes(p)
      );
    }

    // Mapa de etapa para transação necessária
    const transacaoPorEtapa: Record<string, string> = {
      UNIDADE: "pagamento_solicitar",
      GESTOR: "pagamento_gerir",
      VALIDACAO: "pagamento_validar",
      AUTORIDADE: "pagamento_autorizar",
    };

    const transacao = transacaoPorEtapa[acao.etapa];
    return transacao && perfis.includes(transacao);
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">
        Próxima ação
      </h3>
      <p className="mb-4 text-sm text-gray-700 dark:text-gray-300">{frase}</p>

      {acoesPossiveis.length > 0 && (
        <div className="space-y-2">
          {acoesPossiveis.map((acao) => (
            <button
              key={acao.chave}
              onClick={() => onAction?.(acao.chave, acao.etapa)}
              className={`w-full rounded px-3 py-2 text-sm font-medium transition-colors ${
                acao.primaria
                  ? "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-600"
                  : acao.destrutiva
                    ? "border border-red-300 bg-white text-red-600 hover:bg-red-50 dark:border-red-700 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40"
                    : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              {acao.label}
            </button>
          ))}
        </div>
      )}

      {acoesPossiveis.length === 0 && config.acoes.length > 0 && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Você não tem permissão para executar ações nesta etapa.
        </p>
      )}
    </div>
  );
}
