"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, Tags } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type OcorrenciaTipoTransporte,
  type OcorrenciaTipoTransporteCreate,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface TipoForm {
  nome: string;
  descricao: string;
  ativo: boolean;
}

const EMPTY: TipoForm = { nome: "", descricao: "", ativo: true };

/** `""` vira `null` — o backend distingue "não informado" de string vazia. */
function limpo(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function paraPayload(f: TipoForm): OcorrenciaTipoTransporteCreate {
  return { nome: f.nome.trim(), descricao: limpo(f.descricao), ativo: f.ativo };
}

function paraForm(t: OcorrenciaTipoTransporte): TipoForm {
  return { nome: t.nome, descricao: t.descricao ?? "", ativo: t.ativo };
}

export default function OcorrenciasTiposPage() {
  const { can } = useAuth();
  const canCreate = can("transporte_regulado", "inserir");
  const canEdit = can("transporte_regulado", "atualizar");
  const canDelete = can("transporte_regulado", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<OcorrenciaTipoTransporte | null>(null);
  const [form, setForm] = useState<TipoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["tr-ocorrencias-tipos"],
    queryFn: () => api.ocorrenciasTransporte.tipos.list(),
  });

  function invalidar() {
    qc.invalidateQueries({ queryKey: ["tr-ocorrencias-tipos"] });
  }

  const salvarM = useMutation({
    mutationFn: () =>
      editing
        ? api.ocorrenciasTransporte.tipos.update(editing.id, paraPayload(form))
        : api.ocorrenciasTransporte.tipos.create(paraPayload(form)),
    onSuccess: () => {
      toast.success(editing ? "Tipo atualizado." : "Tipo criado.");
      setDialogOpen(false);
      invalidar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const excluirM = useMutation({
    mutationFn: (id: number) => api.ocorrenciasTransporte.tipos.remove(id),
    onSuccess: () => {
      toast.success("Tipo excluído.");
      invalidar();
    },
    // O 409 de "tipo em uso por alguma ocorrência" traz instrução acionável;
    // mostrar a mensagem do servidor é melhor do que traduzir para um genérico.
    onError: (e: Error) => toast.error(e.message),
  });

  function abrirNovo() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function abrirEdicao(t: OcorrenciaTipoTransporte) {
    setEditing(t);
    setForm(paraForm(t));
    setErr(null);
    setDialogOpen(true);
  }

  async function pedirExclusao(t: OcorrenciaTipoTransporte) {
    const ok = await confirm({
      title: `Excluir "${t.nome}"?`,
      message: "O tipo sai do catálogo. Ocorrências já registradas com ele não são afetadas.",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) excluirM.mutate(t.id);
  }

  function set<K extends keyof TipoForm>(k: K, v: TipoForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    salvarM.mutate();
  }

  const itens = q.data ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Tags}
        title="Tipos de Ocorrência"
        description="Catálogo dos tipos usados para registrar fiscalizações e denúncias."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Ocorrências", href: "/m/transporte/ocorrencias" },
          { label: "Tipos" },
        ]}
        actions={
          canCreate ? (
            <Button onClick={abrirNovo}>
              <Plus className="mr-1 h-4 w-4" />
              Novo tipo
            </Button>
          ) : undefined
        }
      />

      {q.isLoading ? (
        <div className="py-8 text-center text-muted-foreground">Carregando...</div>
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum tipo cadastrado"
          description="Cadastre os tipos de ocorrência do transporte regulado."
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Nome</TH>
              <TH>Descrição</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((t) => (
              <TR key={t.id}>
                <TD className="font-medium">{t.nome}</TD>
                <TD className="text-sm text-muted-foreground">{t.descricao ?? "—"}</TD>
                <TD>
                  <Badge intent={t.ativo ? "success" : "neutral"}>
                    {t.ativo ? "Ativo" : "Inativo"}
                  </Badge>
                </TD>
                <TD className="space-x-2 text-right">
                  {canEdit && (
                    <Button variant="ghost" size="sm" onClick={() => abrirEdicao(t)}>
                      Editar
                    </Button>
                  )}
                  {canDelete && (
                    <Button variant="ghost" size="sm" onClick={() => pedirExclusao(t)}>
                      Excluir
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? "Editar tipo" : "Novo tipo"}
      >
        <form className="space-y-3" onSubmit={submeter}>
          {err && (
            <div className="rounded-md border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
              {err}
            </div>
          )}
          <div>
            <Label htmlFor="nome">Nome</Label>
            <Input
              id="nome"
              required
              value={form.nome}
              onChange={(e) => set("nome", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="descricao">Descrição</Label>
            <Textarea
              id="descricao"
              rows={3}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="ativo"
              checked={form.ativo}
              onChange={(e) => set("ativo", e.target.checked)}
            />
            <Label htmlFor="ativo" className="!mb-0">
              Ativo
            </Label>
          </div>
          {editing && !form.ativo && (
            <p className="text-xs text-muted-foreground">
              Tipo inativo não aparece mais no registro de novas ocorrências.
            </p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={salvarM.isPending}>
              {salvarM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
