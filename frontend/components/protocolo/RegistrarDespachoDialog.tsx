"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

/** Texto do editor sem marcação — para saber se o despacho está vazio. */
function textoDe(html: string): string {
  return html.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim();
}

/**
 * Registrar despacho sem encaminhar (SI-62).
 *
 * Duas etapas. Em **escrever**, o rascunho é salvo como minuta de finalidade
 * "despacho": só quem escreve o vê, e ele não aparece na linha do tempo. Em
 * **assinar**, a pessoa confirma com a senha (e, se quiser, junta arquivos):
 * o despacho vira PDF assinado e entra na linha do tempo, e o processo
 * continua na mesma unidade. Quem decide se pode (lotação, trânsito,
 * arquivado) é o servidor; a mensagem dele aparece aqui.
 */
export function RegistrarDespachoDialog({
  open,
  onClose,
  processoId,
  minutaId,
}: {
  open: boolean;
  onClose: () => void;
  processoId: number;
  /** Rascunho já existente (continuar). Sem ele, começa um novo. */
  minutaId?: number;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [idAtual, setIdAtual] = useState<number | undefined>(minutaId);
  const [corpo, setCorpo] = useState("");
  const [versao, setVersao] = useState<number | undefined>(undefined);
  const [etapa, setEtapa] = useState<"escrever" | "assinar">("escrever");
  const [senha, setSenha] = useState("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setIdAtual(minutaId);
    setCorpo("");
    setVersao(undefined);
    setEtapa("escrever");
    setSenha("");
    setArquivos([]);
    setErro(null);
  }, [open, minutaId]);

  const rascunhoQ = useQuery({
    queryKey: ["minuta", minutaId],
    queryFn: () => api.minutas.get(minutaId as number),
    enabled: open && minutaId !== undefined,
  });
  useEffect(() => {
    if (open && rascunhoQ.data && rascunhoQ.data.id === minutaId) {
      setCorpo(rascunhoQ.data.corpo_html ?? "");
      setVersao(rascunhoQ.data.versao);
    }
  }, [open, rascunhoQ.data, minutaId]);

  function atualizarListas() {
    qc.invalidateQueries({ queryKey: ["minutas", processoId] });
    qc.invalidateQueries({ queryKey: ["processo", processoId] });
  }

  /** Cria ou atualiza o rascunho; devolve o id. */
  async function salvar(): Promise<number> {
    if (idAtual === undefined) {
      const m = await api.minutas.create(processoId, {
        titulo: "Despacho",
        finalidade: "despacho",
        corpo_html: corpo,
      });
      setIdAtual(m.id);
      setVersao(m.versao);
      return m.id;
    }
    const m = await api.minutas.update(idAtual, { corpo_html: corpo, versao });
    setVersao(m.versao);
    return m.id;
  }

  const salvarM = useMutation({
    mutationFn: salvar,
    onSuccess: () => {
      atualizarListas();
      toast.success("Rascunho do despacho salvo. Só você vê.");
    },
    onError: (e: Error) => setErro(e.message),
  });

  const irParaAssinarM = useMutation({
    mutationFn: salvar,
    onSuccess: () => {
      setErro(null);
      setEtapa("assinar");
      atualizarListas();
    },
    onError: (e: Error) => setErro(e.message),
  });

  const concluirM = useMutation({
    mutationFn: () => api.minutas.concluirDespacho(idAtual as number, senha, arquivos),
    onSuccess: () => {
      atualizarListas();
      toast.success("Despacho assinado e registrado no processo.");
      onClose();
    },
    onError: (e: Error) => {
      setSenha("");
      setErro(e.message);
    },
  });

  const vazio = textoDe(corpo).length === 0;
  const ocupado = salvarM.isPending || irParaAssinarM.isPending || concluirM.isPending;

  const footer =
    etapa === "escrever" ? (
      <>
        <Button variant="ghost" onClick={onClose}>
          Fechar
        </Button>
        <Button variant="secondary" onClick={() => salvarM.mutate()} disabled={vazio || ocupado}
          loading={salvarM.isPending}>
          Salvar rascunho
        </Button>
        <Button onClick={() => irParaAssinarM.mutate()} disabled={vazio || ocupado}
          loading={irParaAssinarM.isPending}>
          Concluir e assinar…
        </Button>
      </>
    ) : (
      <>
        <Button variant="ghost" onClick={() => { setErro(null); setEtapa("escrever"); }}
          disabled={concluirM.isPending}>
          Voltar ao texto
        </Button>
        <Button
          onClick={() => concluirM.mutate()}
          disabled={!senha || concluirM.isPending}
          loading={concluirM.isPending}
        >
          Assinar e registrar
        </Button>
      </>
    );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={etapa === "escrever" ? "Registrar despacho" : "Assinar despacho"}
      description={
        etapa === "escrever"
          ? "O processo continua nesta unidade. Enquanto não for assinado, o despacho é um rascunho que só você vê."
          : "Confira antes de assinar: depois disso o despacho entra na linha do tempo e não pode mais ser editado."
      }
      size="lg"
      footer={footer}
    >
      <div className="space-y-4">
        {erro && (
          <Alert intent="danger" title="Não foi possível concluir">
            {erro}
          </Alert>
        )}

        {etapa === "escrever" ? (
          <RichTextEditor
            value={corpo}
            onChange={setCorpo}
            placeholder="Ex.: Analisei a documentação. Aguardando parecer jurídico."
          />
        ) : (
          <>
            <div
              className="max-h-48 overflow-y-auto rounded-md border border-border bg-muted p-3 text-sm"
              aria-label="Texto do despacho"
            >
              {textoDe(corpo.replace(/<\/p>/g, "\n"))}
            </div>
            <FormField label="Anexos" opcional hint="Arquivos que acompanham o despacho. Entram junto com ele.">
              <Input
                id="despacho-anexos"
                type="file"
                multiple
                onChange={(e) => setArquivos(Array.from(e.target.files ?? []))}
              />
            </FormField>
            <FormField label="Sua senha" hint="A mesma do login. É ela que assina o despacho.">
              <Input
                id="despacho-senha"
                type="password"
                autoComplete="current-password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && senha && !concluirM.isPending) concluirM.mutate();
                }}
              />
            </FormField>
          </>
        )}
      </div>
    </Dialog>
  );
}
