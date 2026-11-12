"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Download, Eye, PenLine } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { PasswordInput } from "@/components/ui/password-input";
import { SkeletonRow } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR, TRLink } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  anexoDownloadUrl,
  anexoInlineUrl,
  api,
  type PendenciaAssinatura,
} from "@/lib/api";

function fmt(s: string) {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function ParaAssinarPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [assinando, setAssinando] = useState<PendenciaAssinatura | null>(null);
  const [senha, setSenha] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [recusando, setRecusando] = useState<PendenciaAssinatura | null>(null);
  const [motivo, setMotivo] = useState("");
  // Erro sob o campo só depois de tentar confirmar; os botões não ficam
  // cinza esperando a senha ou o motivo.
  const [tentouAssinar, setTentouAssinar] = useState(false);
  const [tentouRecusar, setTentouRecusar] = useState(false);

  function fecharAssinatura() {
    setAssinando(null);
    setSenha("");
    setErr(null);
    setTentouAssinar(false);
  }
  function fecharRecusa() {
    setRecusando(null);
    setMotivo("");
    setTentouRecusar(false);
  }
  function assinar() {
    setTentouAssinar(true);
    if (!senha) {
      document.getElementById("senha-assinar")?.focus();
      return;
    }
    m.mutate();
  }
  function recusar() {
    setTentouRecusar(true);
    if (motivo.trim().length < 3) {
      document.getElementById("motivo-recusa")?.focus();
      return;
    }
    recusaM.mutate();
  }

  const q = useQuery({
    queryKey: ["minhas-pendencias-assinatura"],
    queryFn: () => api.assinaturas.minhasPendentes(),
  });

  const m = useMutation({
    mutationFn: () => {
      if (!assinando) throw new Error("Nenhuma pendência selecionada");
      return api.assinaturas.assinar(assinando.id_assinatura_anexo, senha);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["minhas-pendencias-assinatura"] });
      toast.success("Assinatura registrada.");
      setAssinando(null);
      setSenha("");
      setErr(null);
    },
    // A mensagem (incl. 409 "atualize a senha" e 429 "muitas tentativas") vem
    // pronta do backend em e.message.
    onError: (e: Error) => setErr(e.message),
  });

  const recusaM = useMutation({
    mutationFn: () => {
      if (!recusando) throw new Error("Nada para recusar");
      return api.assinaturas.recusar(recusando.id_solicitacao, motivo);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["minhas-pendencias-assinatura"] });
      toast.success("Assinatura recusada.");
      setRecusando(null);
      setMotivo("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={PenLine}
        title="Para assinar"
        description={
          q.data
            ? `${q.data.length} pendência(s) — cada linha é um anexo que precisa da sua assinatura.`
            : "Cada linha é um anexo que precisa da sua assinatura."
        }
      />

      {!q.isLoading && (q.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={PenLine}
          title="Você não tem pendências de assinatura"
          description="Quando alguém pedir a sua assinatura num documento, ele aparece aqui."
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Processo</TH>
              <TH>Anexo</TH>
              <TH>Solicitante</TH>
              <TH>Solicitada em</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {q.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={5} />)}
            {q.data?.map((p) => (
              <TRLink key={p.id_assinatura_anexo} href={`/m/protocolo/processos/${p.id_processo}`}>
                <TD>
                  <Link
                    href={`/m/protocolo/processos/${p.id_processo}`}
                    className="font-mono text-xs text-primary hover:underline"
                  >
                    {p.numero_processo ?? "Rascunho"}
                  </Link>
                </TD>
                <TD className="text-sm">{p.anexo_descricao ?? `Anexo #${p.id_anexo}`}</TD>
                <TD className="text-sm">{p.nome_solicitante ?? "—"}</TD>
                <TD className="text-xs tabular-nums">{fmt(p.dt_inicio)}</TD>
                <TD className="text-right">
                  {/* Eram quatro botões que quebravam em duas linhas. À vista o
                      que a tela existe para fazer (assinar) e o ver; baixar e
                      recusar no ⋯. Os anexos continuam abrindo em outra aba. */}
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Assinar",
                        icon: PenLine,
                        onClick: () => {
                          setAssinando(p);
                          setSenha("");
                          setErr(null);
                        },
                      },
                      {
                        label: "Visualizar",
                        icon: Eye,
                        onClick: () =>
                          window.open(anexoInlineUrl(p.id_anexo), "_blank", "noopener,noreferrer"),
                      },
                      {
                        label: "Baixar",
                        icon: Download,
                        onClick: () =>
                          window.open(anexoDownloadUrl(p.id_anexo), "_blank", "noopener,noreferrer"),
                      },
                      {
                        label: "Recusar",
                        icon: Ban,
                        perigo: true,
                        onClick: () => {
                          setRecusando(p);
                          setMotivo("");
                        },
                      },
                    ]}
                  />
                </TD>
              </TRLink>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={!!assinando}
        onClose={fecharAssinatura}
        title={assinando ? `Assinar — ${assinando.anexo_descricao}` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={fecharAssinatura}>
              Cancelar
            </Button>
            <Button onClick={assinar} loading={m.isPending}>
              {m.isPending ? "Assinando…" : "Confirmar assinatura"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm">
            Confirme sua senha para registrar a assinatura do anexo{" "}
            <b>{assinando?.anexo_descricao}</b> no processo{" "}
            <b className="font-mono">{assinando?.numero_processo ?? "Rascunho"}</b>.
          </p>
          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              assinar();
            }}
          >
            <FormField
              label="Senha"
              required
              hint="A mesma do login. Ela confirma que é você quem assina."
              error={tentouAssinar && !senha ? "Digite sua senha para assinar." : undefined}
            >
              <PasswordInput
                id="senha-assinar"
                autoComplete="current-password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                autoFocus
              />
            </FormField>
          </form>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={!!recusando}
        onClose={fecharRecusa}
        title={recusando ? `Recusar — ${recusando.anexo_descricao ?? "anexo"}` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={fecharRecusa}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={recusar} loading={recusaM.isPending}>
              {recusaM.isPending ? "Recusando…" : "Confirmar recusa"}
            </Button>
          </>
        }
      >
        <FormField
          label="Motivo"
          required
          hint="Fica registrado na trilha de auditoria."
          error={
            tentouRecusar && motivo.trim().length < 3
              ? "Escreva o motivo da recusa, com pelo menos 3 letras."
              : undefined
          }
        >
          <Textarea
            id="motivo-recusa"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={3}
            autoFocus
            placeholder="Ex.: O documento está com o valor errado na cláusula 2."
          />
        </FormField>
      </Dialog>
    </div>
  );
}
