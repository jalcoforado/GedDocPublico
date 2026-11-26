"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, LayoutTemplate, Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField } from "@/components/ui/form-field";
import { imprimirDocumento } from "@/components/ui/editor-documento";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";
import { PreVisualizacaoDocumento } from "@/components/PreVisualizacaoDocumento";
import { ModelosDeDocumentoDialog } from "@/components/protocolo/ModelosDeDocumentoDialog";
import { api, type Minuta } from "@/lib/api";

/** `{{campo}}` que sobrou: sai literal no PDF (mesma regra da pré-visualização). */
const CAMPO_PENDENTE = /\{\{\s*[\w.]+\s*\}\}/g;

function escaparHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/** O que está gravado no servidor — para saber se há alteração não salva. */
interface Salvo {
  titulo: string;
  destinatario: string;
  corpo: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  processoId: number;
  /** Minuta existente para retomar edição; ausente = criar nova. */
  minutaId?: number;
  onSaved?: () => void;
  /** SI-62 — "despacho": título fixo, sem Google Docs, e "Concluir e assinar…"
   * no rodapé, que salva e chama `onConcluirDespacho` com o id do rascunho. */
  finalidade?: "documento" | "despacho";
  onConcluirDespacho?: (minutaId: number) => void;
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
  finalidade = "documento",
  onConcluirDespacho,
}: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const despacho = finalidade === "despacho";

  const [minutaAtualId, setMinutaAtualId] = useState<number | undefined>(minutaId);
  const [titulo, setTitulo] = useState("");
  const [destinatario, setDestinatario] = useState("");
  const [origem, setOrigem] = useState<"interno" | "google">("interno");
  const [templateId, setTemplateId] = useState<string>("");
  const [corpo, setCorpo] = useState("");
  const [versao, setVersao] = useState<number | undefined>(undefined);
  const [showGoogleConnect, setShowGoogleConnect] = useState(false);
  // SI-67 — a folha do editor já é o documento (timbre, tipografia do PDF);
  // a pré-visualização do PDF (SI-30) fica a um clique, em Ver.
  const [previaAberta, setPreviaAberta] = useState(false);
  const [salvo, setSalvo] = useState<Salvo>({ titulo: "", destinatario: "", corpo: "" });
  const [modeloAtualId, setModeloAtualId] = useState<number | null | undefined>(undefined);
  const [modelosAberto, setModelosAberto] = useState(false);
  const [trocaPendente, setTrocaPendente] = useState<{ id: number | null; nome: string } | null>(null);
  const [confirmarFechar, setConfirmarFechar] = useState(false);
  // SI-53 — a pré-seleção do modelo padrão acontece UMA vez por abertura: se a
  // pessoa trocar para "Documento em branco", um refetch da lista não desfaz.
  const padraoAplicado = useRef(false);

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
      setTitulo(despacho ? "Despacho" : "");
      setDestinatario("");
      setOrigem("interno");
      setTemplateId("");
      setCorpo("");
      setVersao(undefined);
      setSalvo({ titulo: "", destinatario: "", corpo: "" });
      setModeloAtualId(undefined);
      setModelosAberto(false);
      setTrocaPendente(null);
      setConfirmarFechar(false);
      padraoAplicado.current = false;
    }
  }, [open, minutaId]);

  /** Tela e "salvo" passam a refletir o que o servidor devolveu. */
  function sincronizarCom(m: Minuta) {
    const corpoSalvo = m.corpo_html ?? "";
    setTitulo(m.titulo);
    setDestinatario(m.destinatario ?? "");
    setCorpo(corpoSalvo);
    setVersao(m.versao);
    setModeloAtualId(m.id_template_origem);
    setSalvo({ titulo: m.titulo, destinatario: m.destinatario ?? "", corpo: corpoSalvo });
  }

  const templatesQ = useQuery({
    queryKey: ["templates-documento", "ativos"],
    queryFn: () => api.templatesDocumento.list({ apenas_ativos: true }),
    enabled: open && minutaAtualId === undefined,
  });

  // SI-53 — o modelo padrão da prefeitura já vem selecionado.
  useEffect(() => {
    if (!open || minutaAtualId !== undefined || padraoAplicado.current || !templatesQ.data) return;
    padraoAplicado.current = true;
    const padrao = templatesQ.data.find((t) => t.padrao);
    if (padrao) setTemplateId(String(padrao.id));
  }, [open, minutaAtualId, templatesQ.data]);

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
    sincronizarCom(m);
  }, [open, minutaQ.data, minutaAtualId, minutaId]);

  const criarM = useMutation({
    mutationFn: () =>
      api.minutas.create(processoId, {
        titulo: titulo.trim(),
        destinatario: destinatario.trim() || null,
        origem: despacho ? "interno" : origem,
        finalidade,
        id_template_origem: origem === "interno" ? (templateId ? Number(templateId) : null) : null,
      }),
    onSuccess: (m) => {
      if (origem === "google") {
        // Criar Google Doc para a minuta
        criarGoogleM.mutate(m.id);
      } else {
        setMinutaAtualId(m.id);
        sincronizarCom(m);
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

  /** Grava o que está na tela; devolve a minuta e o que foi enviado. */
  async function gravarTela(): Promise<{ m: Minuta; enviado: Salvo }> {
    const enviado = { titulo, destinatario, corpo };
    const m = await api.minutas.update(minutaAtualId as number, {
      titulo: titulo.trim(),
      destinatario: destinatario.trim() || null,
      corpo_html: corpo,
      versao,
    });
    return { m, enviado };
  }

  function depoisDeGravar({ m, enviado }: { m: Minuta; enviado: Salvo }) {
    setVersao(m.versao);
    // O que foi ENVIADO é o que está salvo — se a pessoa digitou durante o
    // envio, isso continua aparecendo como alteração não salva.
    setSalvo(enviado);
    qc.invalidateQueries({ queryKey: ["minutas", processoId] });
    qc.invalidateQueries({ queryKey: ["minuta", m.id] });
  }

  const salvarM = useMutation({
    mutationFn: gravarTela,
    onSuccess: (r) => {
      depoisDeGravar(r);
      onSaved?.();
      toast.success(`Rascunho salvo (v${r.m.versao}).`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // SI-62 — salva o que está na tela e passa ao passo de assinar.
  const concluirM = useMutation({
    mutationFn: gravarTela,
    onSuccess: (r) => {
      depoisDeGravar(r);
      onConcluirDespacho?.(r.m.id);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // SI-67 — trocar de modelo no meio. Se há alteração não salva, ela é
  // gravada ANTES: assim o texto que vai ser substituído fica no histórico
  // da minuta, e "o anterior não se perde" vale também para o que não foi
  // salvo à mão.
  const aplicarModeloM = useMutation({
    mutationFn: async (modelo: { id: number | null; nome: string }) => {
      let versaoAtual = versao;
      if (alterado) versaoAtual = (await gravarTela()).m.versao;
      const m = await api.minutas.aplicarModelo(minutaAtualId as number, {
        id_template: modelo.id,
        destinatario: destinatario.trim() || null,
        versao: versaoAtual,
      });
      return { m, modelo };
    },
    onSuccess: ({ m, modelo }) => {
      // Título e destinatário ficam como estão na tela (o destinatário foi
      // junto); o corpo e a versão vêm do servidor.
      const corpoNovo = m.corpo_html ?? "";
      setCorpo(corpoNovo);
      setVersao(m.versao);
      setModeloAtualId(m.id_template_origem);
      setSalvo((s) => ({ ...s, destinatario, corpo: corpoNovo }));
      qc.setQueryData(["minuta", m.id], m);
      qc.invalidateQueries({ queryKey: ["minutas", processoId] });
      onSaved?.();
      toast.success(
        modelo.id === null
          ? "Documento em branco. O texto anterior ficou no histórico."
          : `Modelo "${modelo.nome}" aplicado. O texto anterior ficou no histórico.`,
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const textoVazio = corpo.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim() === "";
  const alterado =
    titulo !== salvo.titulo || destinatario !== salvo.destinatario || corpo !== salvo.corpo;
  const camposPendentes = Array.from(new Set(corpo.match(CAMPO_PENDENTE) ?? []));

  const estiloQ = useQuery({
    queryKey: ["templates-documento", "estilo-impressao"],
    queryFn: () => api.templatesDocumento.estiloImpressao(),
    staleTime: Infinity,
    enabled: open && minutaAtualId !== undefined,
    throwOnError: false,
  });

  function escolherModelo(modelo: { id: number | null; nome: string }) {
    setModelosAberto(false);
    // Nada a perder: aplica direto. Com texto, avisa que ele será substituído.
    if (textoVazio && !alterado) aplicarModeloM.mutate(modelo);
    else setTrocaPendente(modelo);
  }

  function imprimir() {
    const e = estiloQ.data;
    if (!e) return;
    imprimirDocumento({
      css: e.css,
      cabecalhoHtml: e.cabecalho_html ?? "",
      rodapeHtml: e.rodape_html ?? "",
      conteudoHtml:
        (titulo.trim() ? `<h1 class="doc-titulo">${escaparHtml(titulo.trim())}</h1>` : "") + corpo,
      titulo: titulo.trim() || "Documento",
    });
  }

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
    // SI-67 — no editor, as ações ficam no topo, como no Suite.
    undefined
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

  const noEditor = emEdicao && !ehGoogle;
  const ocupado =
    carregando || salvarM.isPending || concluirM.isPending || aplicarModeloM.isPending;

  /** Fechar o editor com alteração não salva pergunta antes. */
  function pedirFechar() {
    if (noEditor && alterado && !carregando) setConfirmarFechar(true);
    else onClose();
  }

  const statusSalvo = carregando
    ? ""
    : salvarM.isPending || concluirM.isPending
      ? "Salvando…"
      : aplicarModeloM.isPending
        ? "Aplicando o modelo…"
        : alterado
          ? "Alterações não salvas"
          : `Tudo salvo · versão ${versao ?? 1}`;

  return (
    <>
    <Dialog
      open={open}
      onClose={pedirFechar}
      title={
        despacho
          ? "Registrar despacho"
          : emEdicao ? "Editar documento" : "Redigir documento"
      }
      description={
        despacho
          ? "O processo continua nesta unidade. Até ser assinado, o despacho é um rascunho que só você vê."
          : undefined
      }
      size={noEditor ? "tela" : "xl"}
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
          {/* Despacho é redigido só aqui: no Google Docs o texto sairia do
              sistema antes de virar ato (o servidor também recusa). */}
          {!despacho && (
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
          )}
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
                    {t.padrao ? " (padrão)" : ""}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
        </div>
      ) : carregando ? (
        <p className="p-5 text-sm text-muted-foreground">Carregando rascunho…</p>
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
        <>
          {/* Barra de ações do documento — imagem 1 do Suite: "Modelos de
              documentos" e "Salvar" no topo, a qualquer momento. */}
          <div className="flex shrink-0 flex-wrap items-end gap-x-3 gap-y-2 border-b border-border bg-card px-5 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => setModelosAberto(true)}
                disabled={ocupado}
              >
                <LayoutTemplate className="h-4 w-4" aria-hidden="true" />
                Modelos de documentos
              </Button>
              <Button
                variant={despacho ? "secondary" : "primary"}
                onClick={() => salvarM.mutate()}
                disabled={ocupado}
              >
                {salvarM.isPending ? "Salvando…" : "Salvar rascunho"}
              </Button>
              {despacho && (
                <Button
                  onClick={() => concluirM.mutate()}
                  disabled={carregando || salvarM.isPending || aplicarModeloM.isPending || textoVazio}
                  loading={concluirM.isPending}
                >
                  Concluir e assinar…
                </Button>
              )}
              <span
                role="status"
                className={
                  alterado && !ocupado
                    ? "text-xs font-medium text-warning-soft-foreground"
                    : "text-xs text-foreground-muted"
                }
              >
                {statusSalvo}
              </span>
            </div>
            <div className="ml-auto grid w-full gap-3 sm:w-auto sm:grid-cols-[18rem_14rem]">
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
            </div>
          </div>
          <RichTextEditor
            variante="documento"
            value={corpo}
            onChange={setCorpo}
            placeholder="Escreva o documento aqui, ou escolha um modelo em “Modelos de documentos”."
            ariaLabel="Editor do documento"
            onUploadImage={async (file) => {
              const { url } = await api.editorImagens.upload(file);
              return url;
            }}
            documento={{
              css: estiloQ.data?.css,
              cabecalho: (
                <>
                  {estiloQ.data?.cabecalho_html && (
                    <div dangerouslySetInnerHTML={{ __html: estiloQ.data.cabecalho_html }} />
                  )}
                  {/* O título sai assim no PDF; edita-se no campo "Título". */}
                  <h1
                    className="doc-titulo"
                    title="Para mudar o título, use o campo Título acima"
                    onClick={() => document.getElementById("minuta-titulo-edit")?.focus()}
                  >
                    {titulo.trim() || "Sem título"}
                  </h1>
                </>
              ),
              rodape: estiloQ.data?.rodape_html ? (
                <div className="mt-6" dangerouslySetInnerHTML={{ __html: estiloQ.data.rodape_html }} />
              ) : undefined,
              menuArquivo: [
                { label: "Salvar rascunho (Ctrl+S)", onClick: () => salvarM.mutate(), disabled: ocupado },
                { label: "Modelos de documentos…", icon: LayoutTemplate, onClick: () => setModelosAberto(true), disabled: ocupado },
                ...(despacho
                  ? [{ label: "Concluir e assinar…", onClick: () => concluirM.mutate(), disabled: ocupado || textoVazio }]
                  : []),
                { label: "Imprimir", icon: Printer, onClick: imprimir, disabled: !estiloQ.data },
                { label: "Fechar", onClick: pedirFechar },
              ],
              onSalvar: () => {
                if (!ocupado) salvarM.mutate();
              },
              onImprimir: estiloQ.data ? imprimir : undefined,
              previaAberta,
              onAlternarPrevia: () => setPreviaAberta((v) => !v),
              previa: <PreVisualizacaoDocumento titulo={titulo} corpoHtml={corpo} className="h-full" />,
              aviso:
                camposPendentes.length > 0 ? (
                  <p
                    role="status"
                    className="rounded-md bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground"
                  >
                    {camposPendentes.length === 1
                      ? "Um campo automático não foi preenchido"
                      : `${camposPendentes.length} campos automáticos não foram preenchidos`}{" "}
                    e {camposPendentes.length === 1 ? "vai" : "vão"} sair assim no PDF:{" "}
                    {camposPendentes.join(", ")}
                  </p>
                ) : undefined,
            }}
          />
        </>
      )}
    </Dialog>

    {/* SI-67 — "Modelos de documentos" a qualquer momento. */}
    <ModelosDeDocumentoDialog
      open={modelosAberto}
      onClose={() => setModelosAberto(false)}
      onEscolher={escolherModelo}
      modeloAtualId={modeloAtualId}
    />

    <Dialog
      open={trocaPendente !== null}
      onClose={() => setTrocaPendente(null)}
      title="Trocar o modelo?"
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={() => setTrocaPendente(null)}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              const m = trocaPendente;
              setTrocaPendente(null);
              if (m) aplicarModeloM.mutate(m);
            }}
          >
            Substituir o texto
          </Button>
        </>
      }
    >
      <p className="text-sm text-foreground">
        O texto atual será substituído
        {trocaPendente?.id === null ? " por um documento em branco" : ` pelo modelo "${trocaPendente?.nome}"`}.
      </p>
      <p className="mt-2 text-sm text-foreground-muted">
        Nada se perde: o texto de agora fica guardado no histórico do documento
        {alterado ? ", inclusive o que ainda não foi salvo" : ""}.
      </p>
    </Dialog>

    <Dialog
      open={confirmarFechar}
      onClose={() => setConfirmarFechar(false)}
      title="Sair sem salvar?"
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={() => setConfirmarFechar(false)}>
            Continuar editando
          </Button>
          <Button
            variant="danger-outline"
            onClick={() => {
              setConfirmarFechar(false);
              onClose();
            }}
          >
            Sair sem salvar
          </Button>
          <Button
            loading={salvarM.isPending}
            onClick={() =>
              salvarM.mutate(undefined, {
                onSuccess: () => {
                  setConfirmarFechar(false);
                  onClose();
                },
              })
            }
          >
            Salvar e fechar
          </Button>
        </>
      }
    >
      <p className="text-sm text-foreground">
        Há alterações neste documento que ainda não foram salvas.
      </p>
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
