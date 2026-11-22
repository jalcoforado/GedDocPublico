"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip } from "lucide-react";
import { useEffect, useState } from "react";

import { PreVisualizacaoDocumento } from "@/components/PreVisualizacaoDocumento";
import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

/**
 * Registrar despacho sem encaminhar (SI-62) — dois passos.
 *
 * 1. **Escrever**, no mesmo "Redigir documento" dos outros documentos (modelos
 *    e pré-visualização do PDF), em modo despacho: título "Despacho", sem
 *    Google Docs. O rascunho é uma minuta de finalidade "despacho": só quem
 *    escreve a vê, e ela não aparece na linha do tempo.
 * 2. **Assinar** (`AssinarDespacho`): a pessoa vê o PDF como vai sair, junta
 *    os arquivos que acompanham o despacho e confirma com a senha. O despacho
 *    entra na linha do tempo e o processo continua na mesma unidade.
 *
 * Quem decide se pode (lotação, trânsito, arquivado) é o servidor; a mensagem
 * dele aparece no passo de assinar.
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
  const [rascunhoId, setRascunhoId] = useState<number | undefined>(minutaId);
  const [etapa, setEtapa] = useState<"escrever" | "assinar">("escrever");

  useEffect(() => {
    if (!open) return;
    setRascunhoId(minutaId);
    setEtapa("escrever");
  }, [open, minutaId]);

  if (etapa === "assinar" && rascunhoId !== undefined) {
    return (
      <AssinarDespacho
        open={open}
        minutaId={rascunhoId}
        processoId={processoId}
        onVoltar={() => setEtapa("escrever")}
        onClose={onClose}
      />
    );
  }
  return (
    <RedigirDocumentoDialog
      open={open}
      onClose={onClose}
      processoId={processoId}
      minutaId={rascunhoId}
      finalidade="despacho"
      onConcluirDespacho={(id) => {
        setRascunhoId(id);
        setEtapa("assinar");
      }}
    />
  );
}

function AssinarDespacho({
  open,
  minutaId,
  processoId,
  onVoltar,
  onClose,
}: {
  open: boolean;
  minutaId: number;
  processoId: number;
  onVoltar: () => void;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [senha, setSenha] = useState("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  const minutaQ = useQuery({
    queryKey: ["minuta", minutaId],
    queryFn: () => api.minutas.get(minutaId),
  });

  const concluirM = useMutation({
    mutationFn: () => api.minutas.concluirDespacho(minutaId, senha, arquivos),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["minutas", processoId] });
      qc.invalidateQueries({ queryKey: ["processo", processoId] });
      toast.success("Despacho assinado e registrado no processo.");
      onClose();
    },
    onError: (e: Error) => {
      setSenha("");
      setErro(e.message);
    },
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Assinar despacho"
      description="Confira antes de assinar: depois disso o despacho entra na linha do tempo e não pode mais ser editado. O processo continua nesta unidade."
      size="xl"
      footer={
        <>
          <Button variant="ghost" onClick={onVoltar} disabled={concluirM.isPending}>
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
      }
    >
      <div className="space-y-4">
        {erro && (
          <Alert intent="danger" title="Não foi possível concluir">
            {erro}
          </Alert>
        )}
        {minutaQ.data ? (
          // Sem altura fixa: a prévia tem `min-h-[420px]` própria; numa caixa
          // menor ela transbordava por cima do campo de arquivos.
          <PreVisualizacaoDocumento
            titulo={minutaQ.data.titulo}
            corpoHtml={minutaQ.data.corpo_html ?? ""}
          />
        ) : (
          <p className="text-sm text-muted-foreground">Carregando o despacho…</p>
        )}
        <FormField
          label="Arquivos que acompanham o despacho"
          opcional
          hint="Ficam ligados ao despacho e aparecem junto dele na linha do tempo. A assinatura cobre o texto do despacho, não estes arquivos."
        >
          <Input
            id="despacho-anexos"
            type="file"
            multiple
            onChange={(e) => setArquivos(Array.from(e.target.files ?? []))}
          />
        </FormField>
        {arquivos.length > 0 && (
          <ul className="space-y-1 text-sm" aria-label="Arquivos escolhidos">
            {arquivos.map((f) => (
              <li key={f.name} className="flex items-center gap-2 text-foreground">
                <Paperclip className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                {f.name}
              </li>
            ))}
          </ul>
        )}
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
      </div>
    </Dialog>
  );
}
