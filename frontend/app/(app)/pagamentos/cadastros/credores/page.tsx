"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Credor, type DadosBancarios } from "@/lib/api";

interface FormState {
  tipo_pessoa: "FISICA" | "JURIDICA";
  cnpj_cpf: string;
  nome: string;
  situacao_cadastral: "REGULAR" | "PENDENTE" | "IRREGULAR";
  motivo_pendencia: string;
  banco: string;
  agencia: string;
  conta: string;
  chave_pix: string;
}

const EMPTY: FormState = {
  tipo_pessoa: "JURIDICA",
  cnpj_cpf: "",
  nome: "",
  situacao_cadastral: "REGULAR",
  motivo_pendencia: "",
  banco: "",
  agencia: "",
  conta: "",
  chave_pix: "",
};

export default function CredoresPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const [revealOpen, setRevealOpen] = useState(false);
  const [revealData, setRevealData] = useState<DadosBancarios | null>(null);
  const [revealLoading, setRevealLoading] = useState<number | null>(null);

  const listQ = useQuery({
    queryKey: ["pag-credores"],
    queryFn: () => api.pagamentos.cadastros.credores.list(),
  });

  function openNew() {
    setEditId(null);
    setForm(EMPTY);
    setErr(null);
    setOpen(true);
  }

  function openEdit(c: Credor) {
    setEditId(c.id);
    setForm({
      tipo_pessoa: c.tipo_pessoa,
      cnpj_cpf: c.cnpj_cpf,
      nome: c.nome,
      situacao_cadastral: c.situacao_cadastral,
      motivo_pendencia: c.motivo_pendencia ?? "",
      banco: "",
      agencia: "",
      conta: "",
      chave_pix: "",
    });
    setErr(null);
    setOpen(true);
  }

  const saveM = useMutation({
    mutationFn: () => {
      const temDadosBancarios =
        form.banco.trim() || form.agencia.trim() || form.conta.trim() || form.chave_pix.trim();
      const payload: Record<string, unknown> = {
        tipo_pessoa: form.tipo_pessoa,
        cnpj_cpf: form.cnpj_cpf.trim(),
        nome: form.nome.trim(),
        situacao_cadastral: form.situacao_cadastral,
        motivo_pendencia: form.motivo_pendencia.trim() || null,
      };
      if (temDadosBancarios) {
        payload.dados_bancarios = {
          banco: form.banco.trim() || null,
          agencia: form.agencia.trim() || null,
          conta: form.conta.trim() || null,
          chave_pix: form.chave_pix.trim() || null,
        };
      }
      return editId === null
        ? api.pagamentos.cadastros.credores.create(payload)
        : api.pagamentos.cadastros.credores.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-credores"] });
      toast.success(editId === null ? "Credor criado." : "Credor atualizado.");
      setOpen(false);
    },
    onError: (e: Error) => setErr(e.message),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.pagamentos.cadastros.credores.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-credores"] });
      toast.success("Credor excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(c: Credor) {
    const ok = await confirm({
      title: "Excluir credor",
      message: "Esta ação não pode ser desfeita. Deseja realmente excluir este credor?",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) removeM.mutate(c.id);
  }

  async function revelar(c: Credor) {
    setRevealLoading(c.id);
    try {
      const dados = await api.pagamentos.cadastros.credores.dadosBancarios(c.id);
      setRevealData(dados);
      setRevealOpen(true);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRevealLoading(null);
    }
  }

  const credores = listQ.data ?? [];
  const podeSalvar = form.cnpj_cpf.trim().length > 0 && form.nome.trim().length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-aprimora">Credores</h1>
        <Button onClick={openNew}>Novo</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>CNPJ/CPF</TH>
            <TH>Tipo</TH>
            <TH>Situação</TH>
            <TH>Bancário</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {!listQ.isLoading && credores.length === 0 && (
            <TR>
              <TD colSpan={6} className="py-6 text-center text-sm text-muted-foreground">
                Nenhum credor cadastrado.
              </TD>
            </TR>
          )}
          {credores.map((c) => (
            <TR key={c.id}>
              <TD>{c.nome}</TD>
              <TD>{c.cnpj_cpf}</TD>
              <TD>{c.tipo_pessoa === "FISICA" ? "Física" : "Jurídica"}</TD>
              <TD>{c.situacao_cadastral}</TD>
              <TD>{c.tem_dados_bancarios ? "Sim" : "Não"}</TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  {c.tem_dados_bancarios && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => revelar(c)}
                      disabled={revealLoading === c.id}
                    >
                      {revealLoading === c.id ? "Revelando..." : "Revelar dados bancários"}
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={() => openEdit(c)}>
                    Editar
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => excluir(c)}>
                    Excluir
                  </Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Novo credor" : "Editar credor"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => saveM.mutate()} disabled={!podeSalvar || saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="cred-tipo" required>
              Tipo de pessoa
            </Label>
            <Select
              id="cred-tipo"
              value={form.tipo_pessoa}
              onChange={(e) =>
                setForm({ ...form, tipo_pessoa: e.target.value as FormState["tipo_pessoa"] })
              }
              required
            >
              <option value="FISICA">Física</option>
              <option value="JURIDICA">Jurídica</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="cred-doc" required>
              CNPJ/CPF
            </Label>
            <Input
              id="cred-doc"
              value={form.cnpj_cpf}
              onChange={(e) => setForm({ ...form, cnpj_cpf: e.target.value })}
              required
            />
          </div>
          <div className="col-span-2">
            <Label htmlFor="cred-nome" required>
              Nome
            </Label>
            <Input
              id="cred-nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="cred-situacao" required>
              Situação cadastral
            </Label>
            <Select
              id="cred-situacao"
              value={form.situacao_cadastral}
              onChange={(e) =>
                setForm({
                  ...form,
                  situacao_cadastral: e.target.value as FormState["situacao_cadastral"],
                })
              }
              required
            >
              <option value="REGULAR">Regular</option>
              <option value="PENDENTE">Pendente</option>
              <option value="IRREGULAR">Irregular</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="cred-motivo">Motivo da pendência</Label>
            <Input
              id="cred-motivo"
              value={form.motivo_pendencia}
              onChange={(e) => setForm({ ...form, motivo_pendencia: e.target.value })}
            />
          </div>

          <div className="col-span-2 mt-2 border-t border-border pt-3">
            <p className="mb-2 text-sm font-semibold text-foreground">Dados bancários</p>
            <p className="mb-2 text-xs text-muted-foreground">
              Preencha para atualizar. Deixe em branco para manter os dados atuais.
            </p>
          </div>
          <div>
            <Label htmlFor="cred-banco">Banco</Label>
            <Input
              id="cred-banco"
              value={form.banco}
              onChange={(e) => setForm({ ...form, banco: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="cred-agencia">Agência</Label>
            <Input
              id="cred-agencia"
              value={form.agencia}
              onChange={(e) => setForm({ ...form, agencia: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="cred-conta">Conta</Label>
            <Input
              id="cred-conta"
              value={form.conta}
              onChange={(e) => setForm({ ...form, conta: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="cred-pix">Chave PIX</Label>
            <Input
              id="cred-pix"
              value={form.chave_pix}
              onChange={(e) => setForm({ ...form, chave_pix: e.target.value })}
            />
          </div>

          {err && (
            <div
              role="alert"
              className="col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={revealOpen}
        onClose={() => setRevealOpen(false)}
        title="Dados bancários"
        size="sm"
        footer={
          <Button variant="secondary" onClick={() => setRevealOpen(false)}>
            Fechar
          </Button>
        }
      >
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium">Banco:</span> {revealData?.banco ?? "—"}
          </div>
          <div>
            <span className="font-medium">Agência:</span> {revealData?.agencia ?? "—"}
          </div>
          <div>
            <span className="font-medium">Conta:</span> {revealData?.conta ?? "—"}
          </div>
          <div>
            <span className="font-medium">Chave PIX:</span> {revealData?.chave_pix ?? "—"}
          </div>
        </div>
      </Dialog>
    </div>
  );
}
