"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  FlaskConical,
  Mail,
  MessageCircle,
  Phone,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import {
  notificacoesApi,
  type NotificacaoPreferenciaEvento,
} from "@/lib/api";

const CANAL_ICON: Record<"in_app" | "email" | "whatsapp", React.ComponentType<{ className?: string }>> = {
  in_app: Bell,
  email: Mail,
  whatsapp: MessageCircle,
};

const CANAL_LABEL: Record<"in_app" | "email" | "whatsapp", string> = {
  in_app: "No app",
  email: "Email",
  whatsapp: "WhatsApp",
};

/**
 * F9 — uma célula da matriz evento × canal. `valor === null` é "não se
 * aplica" (o evento nunca usa este canal): mostra travessão em vez de
 * checkbox, porque oferecer um toggle que não muda nada é pior que não
 * oferecer nada — a pessoa clicaria e nada aconteceria, sem explicação.
 */
function CelulaCanal({
  canal,
  valor,
  disabled,
  onChange,
}: {
  canal: "in_app" | "email" | "whatsapp";
  valor: boolean | null;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  const Icon = CANAL_ICON[canal];
  if (valor === null) {
    return (
      <div
        className="flex flex-col items-center gap-1 px-3 py-2 text-muted-foreground/50"
        title={`${CANAL_LABEL[canal]}: não se aplica a este evento`}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs">—</span>
      </div>
    );
  }
  return (
    <label
      className="flex cursor-pointer flex-col items-center gap-1 rounded-md px-3 py-2 hover:bg-muted/40"
      title={CANAL_LABEL[canal]}
    >
      <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      <Checkbox
        checked={valor}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

export default function PreferenciasNotificacoesPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const prefsQ = useQuery({
    queryKey: ["notificacoes", "preferencias"],
    queryFn: () => notificacoesApi.getPreferencias(),
  });

  const telQ = useQuery({
    queryKey: ["notificacoes", "telefone"],
    queryFn: () => notificacoesApi.getTelefone(),
  });

  const [telefone, setTelefone] = useState<string>("");
  useEffect(() => {
    if (telQ.data) setTelefone(telQ.data.telefone ?? "");
  }, [telQ.data]);

  const updatePref = useMutation({
    mutationFn: ({
      evento,
      patch,
    }: {
      evento: string;
      patch: { in_app?: boolean; email?: boolean; whatsapp?: boolean };
    }) => notificacoesApi.setPreferenciaEvento(evento, patch),
    onSuccess: (linha) => {
      qc.setQueryData<NotificacaoPreferenciaEvento[]>(
        ["notificacoes", "preferencias"],
        (atual) =>
          atual?.map((l) => (l.evento === linha.evento ? linha : l)) ?? [linha],
      );
      toast.success("Preferência salva.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveTel = useMutation({
    mutationFn: (t: string | null) => notificacoesApi.setTelefone(t),
    onSuccess: (data) => {
      qc.setQueryData(["notificacoes", "telefone"], data);
      toast.success("Telefone salvo.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Sem destino: o servidor manda para o telefone salvo no perfil (1.0.6).
  // O bloco do botão só aparece com `telSalvo`, então o 400 de "salve o
  // telefone antes" não deve acontecer por aqui — mas o toast de erro cobre.
  const test = useMutation({
    mutationFn: () => notificacoesApi.whatsappTest("Teste de WhatsApp do Aprimora"),
    onSuccess: (data) => {
      if (data.erro) {
        toast.error(`Falhou: ${data.erro}`);
      } else {
        toast.success(`Enviado via ${data.provider}.`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (prefsQ.isLoading) {
    return <div className="text-muted-foreground">Carregando…</div>;
  }
  if (prefsQ.error || !prefsQ.data) {
    return (
      <div className="text-danger-soft-foreground">
        Erro: {(prefsQ.error as Error)?.message ?? "sem dados"}
      </div>
    );
  }

  const p = prefsQ.data;
  const telSalvo = telQ.data?.telefone ?? "";
  const telLimpo = telefone.trim();
  const telMudou = telLimpo !== (telSalvo ?? "");
  const telValido = telLimpo === "" || /^\+?[1-9]\d{7,14}$/.test(telLimpo);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">Preferências de notificações</h1>
        <Link href="/perfil" className="text-sm text-primary hover:underline">
          ← Voltar
        </Link>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Por evento
        </h2>
        <p className="text-sm text-muted-foreground">
          Escolha por quais canais você quer receber cada tipo de aviso. Uma
          célula marcada com <strong>—</strong> significa que este evento não
          usa aquele canal — não é um toggle desligado, é uma combinação que
          não existe no sistema.
        </p>

        <div className="overflow-hidden rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                  Evento
                </th>
                {(["in_app", "email", "whatsapp"] as const).map((canal) => (
                  <th key={canal} className="px-3 py-2 text-center font-medium text-muted-foreground">
                    {CANAL_LABEL[canal]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.map((linha) => (
                <tr key={linha.evento} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 font-medium">{linha.label}</td>
                  {(["in_app", "email", "whatsapp"] as const).map((canal) => (
                    <td key={canal} className="text-center">
                      <CelulaCanal
                        canal={canal}
                        valor={linha[canal]}
                        disabled={canal === "whatsapp" && !telSalvo}
                        onChange={(v) =>
                          updatePref.mutate({
                            evento: linha.evento,
                            patch: { [canal]: v },
                          })
                        }
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {p.some((l) => l.whatsapp !== null) && !telSalvo && (
          <p className="text-xs text-muted-foreground">
            Adicione seu telefone abaixo para poder ligar o canal WhatsApp.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Telefone (para WhatsApp)
        </h2>
        <div className="space-y-1">
          <Label htmlFor="tel">Número com DDD (E.164 sugerido)</Label>
          <div className="flex gap-2">
            <Input
              id="tel"
              value={telefone}
              onChange={(e) => setTelefone(e.target.value)}
              placeholder="+5588999998888"
              aria-invalid={!telValido}
            />
            <Button
              size="md"
              disabled={!telMudou || !telValido || saveTel.isPending}
              onClick={() => saveTel.mutate(telLimpo || null)}
            >
              <Phone className="mr-1 h-4 w-4" aria-hidden="true" />
              {saveTel.isPending ? "Salvando…" : "Salvar"}
            </Button>
          </div>
          {!telValido && (
            <p className="text-xs text-danger-soft-foreground">
              Use só dígitos e opcionalmente prefixo +. Ex: +5588999998888.
            </p>
          )}
        </div>

        {telSalvo && (
          <div className="flex items-center justify-between rounded-md border border-dashed border-border bg-muted/30 p-3">
            <div className="text-xs text-muted-foreground">
              Testar envio agora pelo provider configurado no servidor.
            </div>
            <Button
              size="sm"
              variant="secondary"
              disabled={test.isPending}
              onClick={() => test.mutate()}
            >
              <FlaskConical className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              {test.isPending ? "Enviando…" : "Enviar teste"}
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
