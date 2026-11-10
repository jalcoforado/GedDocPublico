"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Pencil, Plus, Tags, Trash2 } from "lucide-react";
import { useState } from "react";

import { useValidacao } from "@/components/transporte/formulario";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
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
    val.reiniciar();
    setDialogOpen(true);
  }

  function abrirEdicao(t: OcorrenciaTipoTransporte) {
    setEditing(t);
    setForm(paraForm(t));
    setErr(null);
    val.reiniciar();
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

  const val = useValidacao<"nome">({
    nome: form.nome.trim() === "" ? "Informe o nome do tipo." : undefined,
  });

  function submeter() {
    setErr(null);
    if (!val.conferir()) return;
    salvarM.mutate();
  }

  const itens = q.data ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Tags}
        title="Tipos de ocorrência"
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
              Novo tipo de ocorrência
            </Button>
          ) : undefined
        }
      />

      {q.isLoading ? (
        <Carregando className="py-8 text-center text-muted-foreground" />
      ) : itens.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum tipo cadastrado"
          description="Cadastre os tipos de ocorrência do transporte regulado."
          action={
            canCreate ? (
              <Button onClick={abrirNovo}>
                <Plus className="mr-1 h-4 w-4" />
                Cadastrar tipo
              </Button>
            ) : undefined
          }
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
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Editar",
                        icon: Pencil,
                        onClick: () => abrirEdicao(t),
                        oculta: !canEdit,
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        onClick: () => pedirExclusao(t),
                        oculta: !canDelete,
                      },
                    ]}
                  />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? `Editar tipo — ${editing.nome}` : "Novo tipo de ocorrência"}
        description={editing ? undefined : "O tipo aparece na lista ao registrar uma ocorrência."}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={submeter} loading={salvarM.isPending}>
              {editing ? "Salvar alterações" : "Criar tipo"}
            </Button>
          </>
        }
      >
        <div ref={val.ref} className="space-y-4">
          <FormField label="Nome" required error={val.erro("nome")}>
            <Input
              id="nome"
              value={form.nome}
              onChange={(e) => set("nome", e.target.value)}
              onBlur={val.sair("nome")}
              placeholder="Ex.: Transporte sem alvará"
            />
          </FormField>
          <FormField
            label="Descrição"
            opcional
            hint="Aparece como dica para quem registra a ocorrência."
          >
            <Textarea
              id="descricao"
              rows={3}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
              placeholder="Ex.: veículo operando serviço regulado sem alvará válido"
            />
          </FormField>
          <EscolhaSegmentada<"ativo" | "inativo">
            nome="tipo-ativo"
            titulo="Situação"
            valor={form.ativo ? "ativo" : "inativo"}
            onChange={(v) => set("ativo", v === "ativo")}
            opcoes={[
              { valor: "ativo", rotulo: "Ativo", descricao: "Aparece no registro de novas ocorrências." },
              { valor: "inativo", rotulo: "Inativo", descricao: "Sai do registro de novas ocorrências; as já registradas não mudam." },
            ]}
          />
          {err && <Alert intent="danger">{err}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}
