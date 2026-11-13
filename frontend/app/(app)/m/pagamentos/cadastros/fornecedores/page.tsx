"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Pencil, Plus, Trash2, UserCircle } from "lucide-react";
import { useState } from "react";

import { fmtDataHora } from "@/components/pagamentos/format";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Fornecedor, type DadosBancarios } from "@/lib/api";

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

const SITUACAO_LABEL: Record<Fornecedor["situacao_cadastral"], string> = {
  REGULAR: "Regular",
  PENDENTE: "Pendente",
  IRREGULAR: "Irregular",
};

function SituacaoBadge({ situacao }: { situacao: Fornecedor["situacao_cadastral"] }) {
  const intent =
    situacao === "REGULAR" ? "success" : situacao === "PENDENTE" ? "warning" : "danger";
  return (
    <Badge intent={intent} className="whitespace-nowrap">
      {SITUACAO_LABEL[situacao]}
    </Badge>
  );
}

export default function FornecedoresPage() {
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
    queryKey: ["pag-fornecedores"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
  });

  const historicoQ = useQuery({
    queryKey: ["pag-fornecedor-historico", editId],
    queryFn: () => api.pagamentos.cadastros.fornecedores.situacaoHistorico(editId as number),
    enabled: open && editId !== null,
  });

  const v = useValidacaoCampos(
    {
      cnpj_cpf:
        !form.cnpj_cpf.trim() &&
        `Informe o ${form.tipo_pessoa === "JURIDICA" ? "CNPJ" : "CPF"} do fornecedor.`,
      nome: !form.nome.trim() && "Informe o nome como está no documento.",
      // O motivo é o que quem escolhe o fornecedor numa solicitação lê.
      motivo_pendencia:
        form.situacao_cadastral !== "REGULAR" &&
        !form.motivo_pendencia.trim() &&
        "Diga o que está pendente — ex.: qual certidão venceu.",
    },
    { cnpj_cpf: "cred-doc", nome: "cred-nome", motivo_pendencia: "cred-motivo" },
  );

  function salvar() {
    if (v.conferir()) saveM.mutate();
  }

  function openNew() {
    setEditId(null);
    setForm(EMPTY);
    setErr(null);
    v.reiniciar();
    setOpen(true);
  }

  function openEdit(c: Fornecedor) {
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
    v.reiniciar();
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
        ? api.pagamentos.cadastros.fornecedores.create(payload)
        : api.pagamentos.cadastros.fornecedores.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-fornecedores"] });
      qc.invalidateQueries({ queryKey: ["pag-fornecedor-historico"] });
      toast.success(editId === null ? "Fornecedor criado." : "Fornecedor atualizado.");
      setOpen(false);
    },
    onError: (e: Error) => setErr(e.message),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.pagamentos.cadastros.fornecedores.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-fornecedores"] });
      toast.success("Fornecedor excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(c: Fornecedor) {
    const ok = await confirm({
      title: "Excluir fornecedor",
      message: "Esta ação não pode ser desfeita. Deseja realmente excluir este fornecedor?",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) removeM.mutate(c.id);
  }

  async function revelar(c: Fornecedor) {
    setRevealLoading(c.id);
    try {
      const dados = await api.pagamentos.cadastros.fornecedores.dadosBancarios(c.id);
      setRevealData(dados);
      setRevealOpen(true);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRevealLoading(null);
    }
  }

  const fornecedores = listQ.data ?? [];
  const pj = form.tipo_pessoa === "JURIDICA";

  return (
    <div className="space-y-4">
      <PageHeader
        icon={UserCircle}
        title="Fornecedores"
        description="Quem recebe os pagamentos: documento, situação cadastral e dados bancários."
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Novo fornecedor
          </Button>
        }
      />

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
          {listQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {!listQ.isLoading && fornecedores.length === 0 && (
            <TR>
              <TD colSpan={6} className="p-0">
                <EmptyState
                  icon={UserCircle}
                  title="Nenhum fornecedor cadastrado"
                  description="Cadastre quem vai receber os pagamentos da prefeitura."
                  action={
                    <Button onClick={openNew}>
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      Novo fornecedor
                    </Button>
                  }
                  className="rounded-none border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {fornecedores.map((c) => (
            <TR key={c.id}>
              <TD>{c.nome}</TD>
              <TD>{c.cnpj_cpf}</TD>
              <TD>{c.tipo_pessoa === "FISICA" ? "Física" : "Jurídica"}</TD>
              <TD>
                <SituacaoBadge situacao={c.situacao_cadastral} />
              </TD>
              <TD>{c.tem_dados_bancarios ? "Sim" : "Não"}</TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, onClick: () => openEdit(c) },
                    {
                      label: revealLoading === c.id ? "Revelando…" : "Revelar dados bancários",
                      icon: Eye,
                      onClick: () => revelar(c),
                      disabled: revealLoading === c.id,
                      oculta: !c.tem_dados_bancarios,
                    },
                    { label: "Excluir", icon: Trash2, perigo: true, onClick: () => excluir(c) },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Novo fornecedor" : "Editar fornecedor"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editId === null ? "Cadastrar fornecedor" : "Salvar alterações"}
            </Button>
          </>
        }
      >
        <div className="space-y-5">
          {/* Quem é */}
          <div className="space-y-4">
            <EscolhaSegmentada
              nome="cred-tipo"
              titulo="Tipo de pessoa"
              valor={form.tipo_pessoa}
              onChange={(v) => setForm({ ...form, tipo_pessoa: v })}
              opcoes={[
                { valor: "JURIDICA", rotulo: "Pessoa jurídica", descricao: "Empresa, com CNPJ." },
                { valor: "FISICA", rotulo: "Pessoa física", descricao: "Pessoa, com CPF." },
              ]}
              moldura={false}
            />
            <GradeCampos>
              <FormField
                label={pj ? "CNPJ" : "CPF"}
                required
                error={v.erro("cnpj_cpf")}
              >
                <Input
                  id="cred-doc"
                  value={form.cnpj_cpf}
                  onChange={(e) => setForm({ ...form, cnpj_cpf: e.target.value })}
                  onBlur={v.tocar("cnpj_cpf")}
                  inputMode={pj ? "text" : "numeric"}
                  placeholder={pj ? "Ex.: 12.345.678/0001-90" : "Ex.: 123.456.789-09"}
                />
              </FormField>
              <FormField label={pj ? "Razão social" : "Nome completo"} required error={v.erro("nome")}>
                <Input
                  id="cred-nome"
                  value={form.nome}
                  onChange={(e) => setForm({ ...form, nome: e.target.value })}
                  onBlur={v.tocar("nome")}
                  placeholder={pj ? "Ex.: Comercial Silva Ltda." : "Ex.: Maria da Silva"}
                />
              </FormField>
            </GradeCampos>
          </div>

          {/* Situação cadastral */}
          <div className="space-y-4 border-t border-border pt-4">
            <EscolhaSegmentada
              nome="cred-situacao"
              titulo="Situação cadastral"
              valor={form.situacao_cadastral}
              onChange={(situacao) =>
                setForm({
                  ...form,
                  situacao_cadastral: situacao,
                  motivo_pendencia: situacao === "REGULAR" ? "" : form.motivo_pendencia,
                })
              }
              opcoes={[
                { valor: "REGULAR", rotulo: "Regular", descricao: "Documentação em dia." },
                {
                  valor: "PENDENTE",
                  rotulo: "Pendente",
                  descricao: "Falta algum documento — diga qual no motivo.",
                },
                {
                  valor: "IRREGULAR",
                  rotulo: "Irregular",
                  descricao: "Há impedimento para receber — diga qual no motivo.",
                },
              ]}
              moldura={false}
            />
            {form.situacao_cadastral !== "REGULAR" && (
              <FormField
                label={form.situacao_cadastral === "PENDENTE" ? "Motivo da pendência" : "Motivo da irregularidade"}
                required
                error={v.erro("motivo_pendencia")}
                hint="Aparece para quem escolhe este fornecedor numa solicitação."
              >
                <Input
                  id="cred-motivo"
                  value={form.motivo_pendencia}
                  onChange={(e) => setForm({ ...form, motivo_pendencia: e.target.value })}
                  onBlur={v.tocar("motivo_pendencia")}
                  placeholder="Ex.: Certidão do FGTS vencida em 10/10/2026"
                />
              </FormField>
            )}
          </div>

          {/* Dados bancários */}
          <fieldset className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
            <legend className="px-1 text-sm font-semibold text-foreground">Dados bancários</legend>
            <p className="-mt-2 text-xs text-foreground-muted">
              {editId === null
                ? "Para onde vai o dinheiro. Informe a conta, a chave PIX ou as duas."
                : "Por segurança, os dados atuais não aparecem aqui. Preencha só para trocar; em branco, ficam como estão."}
            </p>
            <FormField label="Banco" opcional>
              <Input
                id="cred-banco"
                value={form.banco}
                onChange={(e) => setForm({ ...form, banco: e.target.value })}
                placeholder="Ex.: 001 — Banco do Brasil"
              />
            </FormField>
            <GradeCampos>
              <FormField label="Agência" opcional>
                <Input
                  id="cred-agencia"
                  value={form.agencia}
                  onChange={(e) => setForm({ ...form, agencia: e.target.value })}
                  inputMode="numeric"
                  placeholder="Ex.: 1234-5"
                />
              </FormField>
              <FormField label="Conta" opcional>
                <Input
                  id="cred-conta"
                  value={form.conta}
                  onChange={(e) => setForm({ ...form, conta: e.target.value })}
                  inputMode="numeric"
                  placeholder="Ex.: 12345-6"
                />
              </FormField>
            </GradeCampos>
            <FormField label="Chave PIX" opcional hint="CPF/CNPJ, e-mail, telefone ou chave aleatória.">
              <Input
                id="cred-pix"
                value={form.chave_pix}
                onChange={(e) => setForm({ ...form, chave_pix: e.target.value })}
              />
            </FormField>
          </fieldset>

          {editId !== null && (
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-sm font-semibold text-foreground">Histórico de situação</p>
              {historicoQ.isLoading ? (
                <Carregando className="text-xs text-foreground-muted" />
              ) : (historicoQ.data ?? []).length === 0 ? (
                <p className="text-xs text-foreground-muted">Sem registros.</p>
              ) : (
                <ul className="space-y-2">
                  {(historicoQ.data ?? []).map((h) => (
                    <li key={h.id} className="flex items-start gap-2">
                      <SituacaoBadge situacao={h.situacao} />
                      <div className="min-w-0 flex-1">
                        {h.motivo && <p className="text-sm text-foreground">{h.motivo}</p>}
                        <p className="text-xs text-muted-foreground">{fmtDataHora(h.criado_em)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

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
