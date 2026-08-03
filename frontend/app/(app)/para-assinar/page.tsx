"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
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
      <h1 className="text-2xl font-bold text-primary">Para assinar</h1>
      <p className="text-sm text-muted-foreground">
        {q.data?.length ?? 0} pendência(s) — cada linha é um anexo que precisa da sua
        assinatura.
      </p>

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
          {q.isLoading && (
            <TR>
              <TD colSpan={5} className="text-center text-muted-foreground">
                Carregando...
              </TD>
            </TR>
          )}
          {!q.isLoading && (q.data?.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={5} className="text-center text-muted-foreground">
                Você não tem pendências de assinatura.
              </TD>
            </TR>
          )}
          {q.data?.map((p) => (
            <TR key={p.id_assinatura_anexo}>
              <TD>
                <Link
                  href={`/m/protocolo/processos/${p.id_processo}`}
                  className="font-mono text-xs text-primary hover:underline"
                >
                  {p.numero_processo}
                </Link>
              </TD>
              <TD className="text-sm">{p.anexo_descricao ?? `Anexo #${p.id_anexo}`}</TD>
              <TD className="text-sm">{p.nome_solicitante ?? "—"}</TD>
              <TD className="text-xs tabular-nums">{fmt(p.dt_inicio)}</TD>
              <TD className="text-right">
                <div className="inline-flex flex-wrap items-center gap-2">
                  <a
                    href={anexoInlineUrl(p.id_anexo)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-9 items-center rounded-md px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Visualizar
                  </a>
                  <a
                    href={anexoDownloadUrl(p.id_anexo)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-9 items-center rounded-md px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Baixar
                  </a>
                  <Button
                    size="sm"
                    onClick={() => {
                      setAssinando(p);
                      setSenha("");
                      setErr(null);
                    }}
                  >
                    Assinar
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setRecusando(p);
                      setMotivo("");
                    }}
                  >
                    Recusar
                  </Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={!!assinando}
        onClose={() => {
          setAssinando(null);
          setSenha("");
          setErr(null);
        }}
        title={assinando ? `Assinar — ${assinando.anexo_descricao}` : ""}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setAssinando(null);
                setSenha("");
                setErr(null);
              }}
            >
              Cancelar
            </Button>
            <Button onClick={() => m.mutate()} disabled={m.isPending || !senha}>
              {m.isPending ? "Assinando..." : "Confirmar assinatura"}
            </Button>
          </>
        }
      >
        <p className="text-sm">
          Confirme sua senha para registrar a assinatura do anexo{" "}
          <b>{assinando?.anexo_descricao}</b> no processo{" "}
          <b className="font-mono">{assinando?.numero_processo}</b>.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            m.mutate();
          }}
          className="mt-3"
        >
          <Label htmlFor="senha-assinar" required>
            Senha
          </Label>
          <PasswordInput
            id="senha-assinar"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoFocus
            required
          />
        </form>
        {err && (
          <div
            role="alert"
            className="mt-3 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </div>
        )}
      </Dialog>

      <Dialog
        open={!!recusando}
        onClose={() => {
          setRecusando(null);
          setMotivo("");
        }}
        title={recusando ? `Recusar — ${recusando.anexo_descricao ?? "anexo"}` : ""}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setRecusando(null);
                setMotivo("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => recusaM.mutate()}
              disabled={recusaM.isPending || motivo.trim().length < 3}
            >
              {recusaM.isPending ? "Recusando..." : "Confirmar recusa"}
            </Button>
          </>
        }
      >
        <p className="text-sm">
          Informe o motivo da recusa. Ele fica registrado na trilha de auditoria.
        </p>
        <Label htmlFor="motivo-recusa" required>
          Motivo
        </Label>
        <textarea
          id="motivo-recusa"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          rows={3}
          autoFocus
          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </Dialog>
    </div>
  );
}
