"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  FlaskConical,
  Mail,
  MessageCircle,
  Phone,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { Checkbox } from "@/components/ui/checkbox";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  notificacoesApi,
  type NotificacaoPreferenciaEvento,
} from "@/lib/api";
import { aplicarMascara } from "@/lib/mascaras";

const CANAL_ICON: Record<"in_app" | "email" | "whatsapp", React.ComponentType<{ className?: string }>> = {
  in_app: Bell,
  email: Mail,
  whatsapp: MessageCircle,
};

const ERRO_TELEFONE =
  "Use só números, com o código do país e o DDD. Ex.: +5588999998888.";

/**
 * "+5588999998888" → "+55 (88) 99999-8888", só para mostrar: o que se grava
 * continua sendo o número cru. Número de fora do Brasil volta como veio.
 */
function telefoneLegivel(t: string): string {
  const m = /^\+?55(\d{10,11})$/.exec(t);
  return m ? `+55 ${aplicarMascara("telefone", m[1]).valor}` : t;
}

const CANAL_LABEL: Record<"in_app" | "email" | "whatsapp", string> = {
  in_app: "No app",
  email: "E-mail",
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
  evento,
  valor,
  disabled,
  onChange,
}: {
  canal: "in_app" | "email" | "whatsapp";
  /** Nome do evento, para o nome acessível da caixa ("E-mail — Processo recebido"). */
  evento: string;
  valor: boolean | null;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  const Icon = CANAL_ICON[canal];
  if (valor === null) {
    return (
      <div
        className="flex flex-col items-center gap-1 px-3 py-2 text-foreground-subtle"
        title={`${CANAL_LABEL[canal]}: não se aplica a este evento`}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs">—</span>
      </div>
    );
  }
  return (
    <label
      className="flex cursor-pointer flex-col items-center gap-1 rounded-md px-3 py-2 hover:bg-muted"
      title={CANAL_LABEL[canal]}
    >
      <Icon className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
      <Checkbox
        checked={valor}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        aria-label={`${CANAL_LABEL[canal]} — ${evento}`}
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
  const [telTocado, setTelTocado] = useState(false);
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
    return <Carregando className="text-foreground-muted" />;
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

  function salvarTelefone() {
    // Erro só depois da tentativa: ao sair do campo ou ao salvar.
    if (!telValido) {
      setTelTocado(true);
      document.getElementById("tel")?.focus();
      return;
    }
    saveTel.mutate(telLimpo || null);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Bell}
        title="Preferências de notificações"
        description="Por onde você quer ser avisado de cada tipo de evento."
        breadcrumbs={[
          { label: "Meu perfil", href: "/perfil" },
          { label: "Notificações" },
        ]}
      />

      {/* Mesma largura de leitura dos cartões de Meu perfil, alinhada à
          esquerda como o resto das telas. */}
      <div className="max-w-3xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Por evento</CardTitle>
            <CardDescription>
              Escolha por quais canais você quer receber cada tipo de aviso. Uma
              célula marcada com <strong>—</strong> significa que este evento não
              usa aquele canal — não é um toggle desligado, é uma combinação que
              não existe no sistema.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Table>
              <THead>
                <TR>
                  <TH>Evento</TH>
                  {(["in_app", "email", "whatsapp"] as const).map((canal) => (
                    <TH key={canal} className="text-center">
                      {CANAL_LABEL[canal]}
                    </TH>
                  ))}
                </TR>
              </THead>
              <TBody>
                {p.map((linha) => (
                  <TR key={linha.evento}>
                    <TD className="font-medium">{linha.label}</TD>
                    {(["in_app", "email", "whatsapp"] as const).map((canal) => (
                      <TD key={canal} className="p-0 text-center">
                        <CelulaCanal
                          canal={canal}
                          evento={linha.label}
                          valor={linha[canal]}
                          disabled={canal === "whatsapp" && !telSalvo}
                          onChange={(v) =>
                            updatePref.mutate({
                              evento: linha.evento,
                              patch: { [canal]: v },
                            })
                          }
                        />
                      </TD>
                    ))}
                  </TR>
                ))}
              </TBody>
            </Table>
            {p.some((l) => l.whatsapp !== null) && !telSalvo && (
              <p className="text-xs text-foreground-muted">
                Adicione seu telefone abaixo para poder ligar o canal WhatsApp.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Telefone para WhatsApp</CardTitle>
            <CardDescription>
              Usado só nos avisos que você ligar no canal WhatsApp.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <form
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                salvarTelefone();
              }}
              className="flex flex-wrap items-start gap-2"
            >
              <FormField
                label="Celular com WhatsApp"
                className="min-w-0 flex-1 basis-60"
                error={telTocado && !telValido ? ERRO_TELEFONE : undefined}
                hint={
                  telLimpo && telValido
                    ? `Os avisos vão para ${telefoneLegivel(telLimpo)}.`
                    : "Com o código do país e o DDD. Pode digitar com espaços ou traços."
                }
              >
                <Input
                  id="tel"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  value={telefone}
                  // Espaço, parêntese, ponto e traço saem na hora: o envio
                  // espera só "+" e dígitos (E.164), e assim quem digita
                  // "(88) 99999-8888" não leva um erro por isso.
                  onChange={(e) => setTelefone(e.target.value.replace(/[\s().-]/g, ""))}
                  onBlur={() => setTelTocado(true)}
                  placeholder="Ex.: +55 88 99999-8888"
                />
              </FormField>
              {/* Primário só quando há o que salvar: desligado, o laranja
                  pálido parecia um botão quebrado, não um "nada mudou". */}
              <Button
                type="submit"
                size="md"
                className="mt-6"
                variant={telMudou ? "primary" : "secondary"}
                disabled={!telMudou}
                loading={saveTel.isPending}
              >
                {!saveTel.isPending && <Phone className="h-4 w-4" aria-hidden="true" />}
                {saveTel.isPending ? "Salvando…" : "Salvar telefone"}
              </Button>
            </form>

            {telSalvo && (
              <div className="flex items-center justify-between gap-3 rounded-md border border-dashed border-border bg-surface-2 p-3">
                <div className="text-xs text-foreground-muted">
                  Testar envio agora pelo provedor configurado no servidor.
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={test.isPending}
                  onClick={() => test.mutate()}
                >
                  <FlaskConical className="h-3.5 w-3.5" aria-hidden="true" />
                  {test.isPending ? "Enviando…" : "Enviar teste"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
