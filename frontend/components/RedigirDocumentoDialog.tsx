"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";
import { api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  processoId: number;
  /** Minuta existente para retomar edição; ausente = criar nova. */
  minutaId?: number;
  onSaved?: () => void;
}

/**
 * Redige um documento na plataforma (trilha interna). Fluxo:
 *  - sem minutaId: escolhe título + template (ou em branco) → cria rascunho → editor.
 *  - com minutaId: carrega o rascunho e abre direto no editor.
 * A FINALIZAÇÃO (gerar PDF/anexo) é adicionada no PR-C.
 */
export function RedigirDocumentoDialog({
  open,
  onClose,
  processoId,
  minutaId,
  onSaved,
}: Props) {
  const qc = useQueryClient();
  const toast = useToast();

  const [minutaAtualId, setMinutaAtualId] = useState<number | undefined>(minutaId);
  const [titulo, setTitulo] = useState("");
  const [origem, setOrigem] = useState<"interno" | "google">("interno");
  const [templateId, setTemplateId] = useState<string>("");
  const [corpo, setCorpo] = useState("");
  const [versao, setVersao] = useState<number | undefined>(undefined);
  const [showGoogleConnect, setShowGoogleConnect] = useState(false);

  const credentialQ = useQuery({
    queryKey: ["user", "google-credential"],
    queryFn: () => api.users.getGoogleCredential(),
    enabled: open,
    throwOnError: false,
  });
  const hasGoogleCredentials = credentialQ.data?.connected === true;

  useEffect(() => {
    if (open) {
      setMinutaAtualId(minutaId);
      setTitulo("");
      setOrigem("interno");
      setTemplateId("");
      setCorpo("");
      setVersao(undefined);
    }
  }, [open, minutaId]);

  const templatesQ = useQuery({
    queryKey: ["templates-documento", "ativos"],
    queryFn: () => api.templatesDocumento.list({ apenas_ativos: true }),
    enabled: open && minutaAtualId === undefined,
  });

  const minutaQ = useQuery({
    queryKey: ["minuta", minutaAtualId],
    queryFn: () => api.minutas.get(minutaAtualId as number),
    enabled: open && minutaAtualId !== undefined,
  });

  useEffect(() => {
    if (minutaQ.data) {
      setTitulo(minutaQ.data.titulo);
      setCorpo(minutaQ.data.corpo_html ?? "");
      setVersao(minutaQ.data.versao);
    }
  }, [minutaQ.data]);

  const criarM = useMutation({
    mutationFn: () =>
      api.minutas.create(processoId, {
        titulo: titulo.trim(),
        origem: origem,
        id_template_origem: origem === "interno" ? (templateId ? Number(templateId) : null) : null,
      }),
    onSuccess: (m) => {
      if (origem === "google") {
        // Criar Google Doc para a minuta
        criarGoogleM.mutate(m.id);
      } else {
        setMinutaAtualId(m.id);
        setCorpo(m.corpo_html ?? "");
        setVersao(m.versao);
        qc.invalidateQueries({ queryKey: ["minutas", processoId] });
        onSaved?.();
        toast.success("Rascunho criado.");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const criarGoogleM = useMutation({
    mutationFn: (minutaId: number) =>
      api.minutas.criarEmGoogle(minutaId),
    onSuccess: (m) => {
      setMinutaAtualId(m.id);
      qc.invalidateQueries({ queryKey: ["minutas", processoId] });
      onSaved?.();
      toast.success("Documento criado em Google Docs. Redirecionando…");
      // Redirect to Google Docs editor
      setTimeout(() => {
        window.location.href = m.google_doc_url || "";
      }, 1000);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const salvarM = useMutation({
    mutationFn: () =>
      api.minutas.update(minutaAtualId as number, {
        titulo: titulo.trim(),
        corpo_html: corpo,
        versao,
      }),
    onSuccess: (m) => {
      setVersao(m.versao);
      qc.invalidateQueries({ queryKey: ["minutas", processoId] });
      qc.invalidateQueries({ queryKey: ["minuta", m.id] });
      onSaved?.();
      toast.success(`Rascunho salvo (v${m.versao}).`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const emEdicao = minutaAtualId !== undefined;
  const carregando = emEdicao && minutaQ.isLoading;

  const footer = emEdicao ? (
    <div className="flex justify-end gap-2">
      <Button variant="secondary" onClick={onClose}>
        Fechar
      </Button>
      <Button onClick={() => salvarM.mutate()} disabled={salvarM.isPending || carregando}>
        {salvarM.isPending ? "Salvando…" : "Salvar rascunho"}
      </Button>
    </div>
  ) : (
    <div className="flex justify-end gap-2">
      <Button variant="secondary" onClick={onClose}>
        Cancelar
      </Button>
      <Button
        onClick={() => criarM.mutate()}
        disabled={criarM.isPending || criarGoogleM.isPending || titulo.trim().length === 0}
      >
        {criarM.isPending || criarGoogleM.isPending
          ? "Criando…"
          : origem === "google"
            ? "Criar em Google Docs"
            : "Criar rascunho"}
      </Button>
    </div>
  );

  return (
    <>
    <Dialog
      open={open}
      onClose={onClose}
      title={emEdicao ? "Editar documento" : "Redigir documento"}
      size="xl"
      footer={footer}
    >
      {!emEdicao ? (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="minuta-titulo">Título do documento</Label>
            <Input
              id="minuta-titulo"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Despacho de encaminhamento"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Plataforma de redação</Label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value="interno"
                  checked={origem === "interno"}
                  onChange={(e) => setOrigem(e.target.value as "interno" | "google")}
                  className="w-4 h-4"
                />
                <span className="text-sm">Plataforma (editor interno com templates)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value="google"
                  checked={origem === "google"}
                  onChange={(e) => setOrigem(e.target.value as "interno" | "google")}
                  disabled={!hasGoogleCredentials}
                  className="w-4 h-4"
                />
                <span className="text-sm">Google Docs (editor externo)</span>
              </label>

              {!hasGoogleCredentials && (
                <div className="ml-6 text-xs text-amber-600 space-y-1">
                  <p>⚠️ Você precisa conectar sua conta Google Docs primeiro.</p>
                  <button
                    type="button"
                    onClick={() => setShowGoogleConnect(true)}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    Conectar agora →
                  </button>
                </div>
              )}
            </div>
          </div>
          {origem === "interno" && (
            <div className="space-y-1.5">
              <Label htmlFor="minuta-template">Modelo (template)</Label>
              <Select
                id="minuta-template"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Documento em branco</option>
                {(templatesQ.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.categoria ? `[${t.categoria}] ` : ""}
                    {t.nome}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Ao usar um modelo, os campos do processo (número, requerente, data…) são
                preenchidos automaticamente.
              </p>
            </div>
          )}
        </div>
      ) : carregando ? (
        <p className="text-sm text-muted-foreground">Carregando rascunho…</p>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="minuta-titulo-edit">Título</Label>
            <Input
              id="minuta-titulo-edit"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Conteúdo</Label>
            <RichTextEditor
              value={corpo}
              onChange={setCorpo}
              minHeight={320}
              ariaLabel="Editor do documento"
              onUploadImage={async (file) => {
                const { url } = await api.editorImagens.upload(file);
                return url;
              }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Versão atual: v{versao}. Cada "Salvar rascunho" registra uma nova versão.
          </p>
        </div>
      )}
    </Dialog>

    {/* Google Connect Dialog */}
    <GoogleConnectDialog
      open={showGoogleConnect}
      onClose={() => setShowGoogleConnect(false)}
      minutaId={minutaAtualId || 0}
      processoId={processoId}
      onSuccess={() => {
        setShowGoogleConnect(false);
        credentialQ.refetch();
      }}
    />
    </>
  );
}
