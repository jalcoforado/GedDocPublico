"use client";

import {
  CheckCircle2,
  Clock,
  FileText,
  MessageCircle,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type {
  ChecklistDocumentosResponse,
  CidadaoProcessoDetail,
  ComplementacaoOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  processo: { ativo: boolean };
  checklist?: ChecklistDocumentosResponse;
  complementacaoAberta?: ComplementacaoOut | null;
}

interface Mensagem {
  intent: "default" | "success" | "warning" | "info";
  title: string;
  description: string;
  icon: LucideIcon;
}

const INTENT_CLASSES: Record<Mensagem["intent"], { bg: string; ring: string; iconBg: string; iconColor: string }> = {
  default: {
    bg: "bg-surface-1",
    ring: "ring-border",
    iconBg: "bg-brand/10",
    iconColor: "text-brand dark:text-brand-light",
  },
  success: {
    bg: "bg-success-soft/40",
    ring: "ring-success-soft-foreground/20",
    iconBg: "bg-success/15",
    iconColor: "text-success-soft-foreground",
  },
  warning: {
    bg: "bg-warning-soft/50",
    ring: "ring-warning-soft-foreground/20",
    iconBg: "bg-warning/20",
    iconColor: "text-warning-soft-foreground",
  },
  info: {
    bg: "bg-info-soft/40",
    ring: "ring-info-soft-foreground/20",
    iconBg: "bg-info-soft",
    iconColor: "text-info-soft-foreground",
  },
};

/**
 * Calcula a mensagem em ordem estrita de prioridade. Pura, sem I/O.
 *
 * Prioridade (Fase C, decisao D-PROXIMOS-PASSOS):
 *   1. Processo encerrado (!ativo)
 *   2. Complementacao aberta esperando o cidadao
 *   3. Checklist obrigatorio incompleto (pendente | parcial)
 *   4. Em ordem — fallback "Acompanhe o andamento"
 *
 * Linguagem cidada deliberada: sem "garantia", "SLA", "prazo legal",
 * "deferido", "indeferido". Sem promessa de prazo.
 */
export function calcularProximoPasso(
  processo: { ativo: boolean },
  checklist?: ChecklistDocumentosResponse,
  complementacaoAberta?: ComplementacaoOut | null,
): Mensagem {
  if (!processo.ativo) {
    return {
      intent: "success",
      icon: CheckCircle2,
      title: "Sua solicitação foi concluída.",
      description:
        "Você pode rever os detalhes e o histórico nesta página a qualquer momento.",
    };
  }

  if (complementacaoAberta && complementacaoAberta.status === "aberta") {
    return {
      intent: "warning",
      icon: MessageCircle,
      title: "Responda à solicitação de complementação documental.",
      description:
        "O servidor pediu documentos adicionais para continuar a análise. Envie o que estiver pendente e confirme o envio.",
    };
  }

  if (
    checklist &&
    (checklist.status_documental === "pendente" ||
      checklist.status_documental === "parcial")
  ) {
    return {
      intent: "info",
      icon: FileText,
      title: "Envie os documentos pendentes para que a análise possa continuar.",
      description:
        checklist.obrigatorios_total > 0
          ? `${checklist.obrigatorios_enviados} de ${checklist.obrigatorios_total} documentos obrigatórios enviados. Anexe os que faltam abaixo.`
          : "Anexe os documentos solicitados abaixo.",
    };
  }

  return {
    intent: "default",
    icon: Clock,
    title: "Acompanhe o andamento da solicitação.",
    description:
      "Não há ação pendente sua no momento. Você verá aqui novas instruções, se forem necessárias.",
  };
}

export function ProximosPassosCard({
  processo,
  checklist,
  complementacaoAberta,
}: Props) {
  const msg = calcularProximoPasso(processo, checklist, complementacaoAberta);
  const Icon = msg.icon;
  const tint = INTENT_CLASSES[msg.intent];

  return (
    <Card
      data-testid="proximos-passos"
      className={cn("ring-1", tint.bg, tint.ring)}
    >
      <CardContent className="flex items-start gap-3 py-4">
        <div
          aria-hidden="true"
          className={cn(
            "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            tint.iconBg,
          )}
        >
          <Icon className={cn("h-5 w-5", tint.iconColor)} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-medium uppercase tracking-wider text-foreground-muted">
            Próximos passos
          </p>
          <p className="mt-0.5 text-sm font-semibold text-foreground">
            {msg.title}
          </p>
          <p className="mt-1 text-xs text-foreground-muted">{msg.description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
