"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";
import { PreVisualizacaoDocumento } from "@/components/PreVisualizacaoDocumento";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Modo = "editar" | "lado" | "previa";

const MODOS: { valor: Modo; rotulo: string }[] = [
  { valor: "editar", rotulo: "Editar" },
  { valor: "lado", rotulo: "Lado a lado" },
  { valor: "previa", rotulo: "Pré-visualizar" },
];

/** Escolha entre só o editor, editor + documento, ou só o documento (SI-30). */
function ModoDeVisualizacao({ modo, onChange }: { modo: Modo; onChange: (m: Modo) => void }) {
  return (
    <div role="group" aria-label="Visualização" className="inline-flex rounded-md border border-border p-0.5">
      {MODOS.map((m) => (
        <button
          key={m.valor}
          type="button"
          aria-pressed={modo === m.valor}
          onClick={() => onChange(m.valor)}
          className={cn(
            "rounded px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            modo === m.valor
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {m.rotulo}
        </button>
      ))}
    </div>
  );
}

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
  const [destinatario, setDestinatario] = useState("");
  const [origem, setOrigem] = useState<"interno" | "google">("interno");
  const [templateId, setTemplateId] = useState<string>("");
  const [corpo, setCorpo] = useState("");
  const [versao, setVersao] = useState<number | undefined>(undefined);
  const [showGoogleConnect, setShowGoogleConnect] = useState(false);
  // Abre lado a lado: ver o documento enquanto escreve é o ponto (SI-30).
  const [modo, setModo] = useState<Modo>("lado");

  const credentialQ = useQuery({
    queryKey: ["user", "google-credential"],
    queryFn: () => api.users.getGoogleCredential(),
    enabled: open,
    throwOnError: false,
  });
  const hasGoogleCredentials = credentialQ.data?.connected === true;
  // SI-32: sem client ID/secret no servidor não há o que conectar.
  const googleConfigurado = credentialQ.data?.configurado !== false;

  useEffect(() => {
    if (open) {
      setMinutaAtualId(minutaId);
      setTitulo("");
      setDestinatario("");
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

  // Preenche com a minuta carregada. Depende também de `open`: o diálogo fica
  // montado e o efeito acima zera os campos a cada abertura — com a minuta já
  // no cache, `minutaQ.data` é o MESMO objeto (o React Query reaproveita a
  // referência quando nada mudou), e um efeito só em `[minutaQ.data]` não
  // rodava de novo: "Editar" abria o documento em branco.
  // O id confere com o pedido: na abertura, `minutaAtualId` ainda é o da vez
  // anterior por um render — sem isso, o texto de outro documento piscava.
  useEffect(() => {
    const m = minutaQ.data;
    if (!open || !m || m.id !== minutaAtualId) return;
    if (minutaId !== undefined && m.id !== minutaId) return;
    setTitulo(m.titulo);
    setDestinatario(m.destinatario ?? "");
    setCorpo(m.corpo_html ?? "");
    setVersao(m.versao);
  }, [open, minutaQ.data, minutaAtualId, minutaId]);

  const criarM = useMutation({
    mutationFn: () =>
      api.minutas.create(processoId, {
        titulo: titulo.trim(),
        destinatario: destinatario.trim() || null,
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
      // Abre numa aba nova — trocar a própria aba (window.location.href) tirava
      // o usuário do processo sem volta fácil; assim o app continua aberto e o
      // Google Docs some sozinho quando a aba é fechada ao terminar de editar.
      if (m.google_doc_url) {
        window.open(m.google_doc_url, "_blank", "noopener,noreferrer");
      }
      toast.success("Documento criado em Google Docs numa nova aba.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Traz de volta o que foi editado no Google Docs (backend: PR #70). O
  // backend só sobe a versão se o conteúdo mudou — por isso comparar com a
  // versão de antes, para não anunciar "versão nova" quando nada mudou.
  const sincronizarM = useMutation({
    mutationFn: (id: number) => api.minutas.sincronizarGoogle(id),
    onSuccess: (m) => {
      const antes = minutaQ.data?.versao;
      qc.setQueryData(["minuta", m.id], m);
      qc.invalidateQueries({ queryKey: ["minutas", processoId] });
      if (antes !== undefined && m.versao > antes) {
        onSaved?.();
        toast.success(`Conteúdo trazido do Google Docs (v${m.versao}).`);
      } else {
        toast.info("Nada mudou no Google Docs desde a última sincronização.");
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const salvarM = useMutation({
    mutationFn: () =>
      api.minutas.update(minutaAtualId as number, {
        titulo: titulo.trim(),
        destinatario: destinatario.trim() || null,
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
  // Minuta de origem Google não tem conteúdo pra editar aqui — o texto vive
  // no Google Docs, não em corpo_html. Mostrar o RichTextEditor pra ela dava
  // uma tela de edição "normal" só que sempre vazia (nada foi sincronizado
  // de volta), e "Salvar rascunho" sobrescreveria corpo_html com esse vazio.
  const ehGoogle = emEdicao ? minutaQ.data?.origem === "google" : origem === "google";

  // Título é o único obrigatório. O botão não fica cinza esperando por ele:
  // clicar sem título mostra o erro sob o campo.
  const [tentouCriar, setTentouCriar] = useState(false);
  const faltaTitulo = titulo.trim().length === 0;
  function criar() {
    setTentouCriar(true);
    if (faltaTitulo) {
      document.getElementById("minuta-titulo")?.focus();
      return;
    }
    criarM.mutate();
  }

  const footer = emEdicao && ehGoogle ? (
    <div className="flex justify-end gap-2">
      <Button variant="ghost" onClick={onClose}>
        Fechar
      </Button>
      <Button
        variant="secondary"
        onClick={() => minutaAtualId !== undefined && sincronizarM.mutate(minutaAtualId)}
        disabled={sincronizarM.isPending || !minutaQ.data?.google_doc_id}
      >
        {sincronizarM.isPending ? "Sincronizando…" : "Sincronizar do Google Docs"}
      </Button>
      <Button
        onClick={() => {
          if (minutaQ.data?.google_doc_url) {
            window.open(minutaQ.data.google_doc_url, "_blank", "noopener,noreferrer");
          }
        }}
        disabled={!minutaQ.data?.google_doc_url}
      >
        Abrir no Google Docs
      </Button>
    </div>
  ) : emEdicao ? (
    <div className="flex justify-end gap-2">
      <Button variant="ghost" onClick={onClose}>
        Fechar
      </Button>
      <Button onClick={() => salvarM.mutate()} disabled={salvarM.isPending || carregando}>
        {salvarM.isPending ? "Salvando…" : "Salvar rascunho"}
      </Button>
    </div>
  ) : (
    <div className="flex justify-end gap-2">
      <Button variant="ghost" onClick={onClose}>
        Cancelar
      </Button>
      <Button onClick={criar} loading={criarM.isPending || criarGoogleM.isPending}>
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
      size={emEdicao && !ehGoogle && modo === "lado" ? "2xl" : "xl"}
      footer={footer}
    >
      {!emEdicao ? (
        <div className="space-y-4">
          <FormField
            label="Título do documento"
            required
            error={
              tentouCriar && faltaTitulo
                ? "Dê um título ao documento, ex.: Despacho de encaminhamento."
                : undefined
            }
          >
            <Input
              id="minuta-titulo"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Despacho de encaminhamento"
            />
          </FormField>
          <FormField
            label="Destinatário"
            opcional
            hint={
              <>
                Preenche o campo automático {"{{"}destinatario.nome{"}}"} do modelo, se houver.
              </>
            }
          >
            <Input
              id="minuta-destinatario"
              value={destinatario}
              onChange={(e) => setDestinatario(e.target.value)}
              placeholder="Ex.: Secretaria de Obras"
            />
          </FormField>
          <div>
            {/* Google Docs sem conta conectada: escolher a opção abre a
                conexão (se o servidor tiver a integração configurada), em vez
                de deixar seguir para um "criar" que falharia. */}
            <EscolhaSegmentada
              nome="minuta-origem"
              titulo="Onde redigir"
              moldura={false}
              valor={origem}
              onChange={(v) => {
                if (v === "google" && !hasGoogleCredentials) {
                  if (googleConfigurado) setShowGoogleConnect(true);
                  return;
                }
                setOrigem(v);
              }}
              opcoes={[
                {
                  valor: "interno",
                  rotulo: "Editor da plataforma",
                  icon: FileText,
                  descricao: "Edita aqui mesmo, com os modelos de documento.",
                },
                {
                  valor: "google",
                  rotulo: "Google Docs",
                  icon: ExternalLink,
                  descricao: "Abre o documento no Google Docs, numa nova aba.",
                  // Sem a integração no servidor não há o que conectar (SI-32).
                  disabled: !googleConfigurado,
                },
              ]}
            />
            {!hasGoogleCredentials && !googleConfigurado && (
              <p className="mt-1.5 text-xs text-foreground-muted">
                A integração com o Google Docs ainda não foi configurada neste servidor. Fale
                com o administrador do sistema.
              </p>
            )}
            {!hasGoogleCredentials && googleConfigurado && (
              <p className="mt-1.5 text-xs text-foreground-muted">
                Para usar o Google Docs, conecte sua conta primeiro.{" "}
                <button
                  type="button"
                  onClick={() => setShowGoogleConnect(true)}
                  className="font-medium text-primary hover:underline"
                >
                  Conectar agora
                </button>
              </p>
            )}
          </div>
          {origem === "interno" && (
            <FormField
              label="Modelo"
              opcional
              hint="Com um modelo, os dados do processo (número, requerente, data…) já entram preenchidos."
            >
              <Select
                id="minuta-template"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Documento em branco</option>
                {(templatesQ.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nome}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
        </div>
      ) : carregando ? (
        <p className="text-sm text-muted-foreground">Carregando rascunho…</p>
      ) : ehGoogle ? (
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            <span className="font-medium">{titulo}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            Este documento é editado no Google Docs, não aqui. Use "Abrir no
            Google Docs" para continuar editando numa aba nova e "Sincronizar do
            Google Docs" para trazer o texto de volta à plataforma.
          </p>
          {minutaQ.data?.corpo_html ? (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-foreground-muted">
                Conteúdo trazido do Google Docs (v{minutaQ.data.versao})
              </p>
              {/* Como o PDF vai sair (SI-30), não o texto cru da tela. */}
              <PreVisualizacaoDocumento
                titulo={minutaQ.data.titulo}
                corpoHtml={minutaQ.data.corpo_html}
                className="h-96"
              />
              <p className="text-xs text-foreground-subtle">
                Vêm negrito, itálico, títulos, listas, alinhamento e tabelas.
                Imagens, links, cores e fontes continuam só no Google Docs.
              </p>
            </div>
          ) : (
            <p className="text-xs text-foreground-subtle">
              O conteúdo ainda não foi trazido para a plataforma.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <GradeCampos>
            <FormField label="Título" required>
              <Input
                id="minuta-titulo-edit"
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
              />
            </FormField>
            <FormField label="Destinatário" opcional>
              <Input
                id="minuta-destinatario-edit"
                value={destinatario}
                onChange={(e) => setDestinatario(e.target.value)}
                placeholder="Ex.: Secretaria de Obras"
              />
            </FormField>
          </GradeCampos>
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <Label>Conteúdo</Label>
              <ModoDeVisualizacao modo={modo} onChange={setModo} />
            </div>
            <div className={cn("grid gap-4", modo === "lado" && "lg:grid-cols-2")}>
              {modo !== "previa" && (
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
              )}
              {modo !== "editar" && (
                <PreVisualizacaoDocumento
                  titulo={titulo}
                  corpoHtml={corpo}
                  className={modo === "previa" ? "min-h-[60vh]" : undefined}
                />
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Versão atual: v{versao}. Cada "Salvar rascunho" registra uma nova versão.
            </p>
          </div>
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
