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
import { notificacoesApi, type NotificacaoPreferencias } from "@/lib/api";

interface ToggleRowProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint: string;
  disabled?: boolean;
  checked: boolean;
  onChange: (v: boolean) => void;
}

function ToggleRow({ icon: Icon, label, hint, disabled, checked, onChange }: ToggleRowProps) {
  return (
    <label className="flex items-start gap-3 rounded-md border border-border bg-card p-4 cursor-pointer hover:bg-muted/40">
      <Checkbox
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1"
      />
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="flex-1">
        <div className="font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{hint}</div>
      </div>
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
    mutationFn: (p: Partial<NotificacaoPreferencias>) =>
      notificacoesApi.setPreferencias(p),
    onSuccess: (data) => {
      qc.setQueryData(["notificacoes", "preferencias"], data);
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

  const test = useMutation({
    mutationFn: (t: string) =>
      notificacoesApi.whatsappTest(t, "Teste de WhatsApp do Aprimora"),
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
          Canais
        </h2>
        <p className="text-sm text-muted-foreground">
          Escolha por quais canais você quer receber notificações. Você sempre
          verá os alertas no app — outros canais são complementares.
        </p>

        <div className="space-y-2">
          <ToggleRow
            icon={Bell}
            label="No app (Bell icon)"
            hint="Notificações no sininho do topo da tela."
            checked={p.in_app}
            onChange={(v) => updatePref.mutate({ in_app: v })}
          />
          <ToggleRow
            icon={Mail}
            label="Email"
            hint="Mandamos um email com link pro processo. Precisa de SMTP configurado no servidor."
            checked={p.email}
            onChange={(v) => updatePref.mutate({ email: v })}
          />
          <ToggleRow
            icon={MessageCircle}
            label="WhatsApp"
            hint={
              telSalvo
                ? `Será enviado para ${telSalvo}.`
                : "Adicione seu telefone abaixo para receber via WhatsApp."
            }
            disabled={!telSalvo}
            checked={p.whatsapp}
            onChange={(v) => updatePref.mutate({ whatsapp: v })}
          />
        </div>
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
              onClick={() => test.mutate(telSalvo)}
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
