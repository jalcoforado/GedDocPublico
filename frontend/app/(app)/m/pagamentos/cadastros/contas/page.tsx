"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { AtivoBadge } from "@/components/pagamentos/Rotulos";
import { useValidacaoCampos } from "@/components/pagamentos/useValidacaoCampos";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type ContaBancaria } from "@/lib/api";

const GRUPO_LABELS: Record<string, string> = {
  PESSOAL: "Pessoal",
  CUSTEIO: "Custeio",
  INVESTIMENTO: "Investimento",
  DIVIDA: "Dívida",
  OUTRAS: "Outras",
};

type ModoMovimentacao = "PAGA" | "RECEBE" | "TRANSFERE" | "RESTRITA";

interface FormState {
  nome: string;
  banco: string;
  agencia: string;
  conta: string;
  id_fonte_recursos: number | null;
  grupo_despesa: string;
  saldo_minimo_alerta: number;
  ativa: boolean;
  modo_movimentacao: ModoMovimentacao;
  digito: string;
  tipo: string;
  titularidade: string;
  orgao_gestor: string;
  finalidade: string;
  data_abertura: string;
}

const EMPTY: FormState = {
  nome: "",
  banco: "",
  agencia: "",
  conta: "",
  id_fonte_recursos: null,
  grupo_despesa: "CUSTEIO",
  saldo_minimo_alerta: 0,
  ativa: true,
  modo_movimentacao: "PAGA",
  digito: "",
  tipo: "",
  titularidade: "",
  orgao_gestor: "",
  finalidade: "",
  data_abertura: "",
};

export default function ContasPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);

  const listQ = useQuery({
    queryKey: ["pag-contas"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const fontesQ = useQuery({
    queryKey: ["pag-fontes-select"],
    queryFn: () => api.pagamentos.cadastros.fontes.list(),
  });
  const enumsQ = useQuery({
    queryKey: ["pag-enums"],
    queryFn: () => api.pagamentos.cadastros.enums(),
  });

  function openNew() {
    setEditId(null);
    // Com uma fonte só, ela já vem escolhida; com várias, a pessoa escolhe
    // (a primeira da lista era um palpite que passava despercebido).
    const fontes = fontesQ.data ?? [];
    setForm({ ...EMPTY, id_fonte_recursos: fontes.length === 1 ? fontes[0].id : null });
    v.reiniciar();
    setOpen(true);
  }

  function openEdit(c: ContaBancaria) {
    setEditId(c.id);
    setForm({
      nome: c.nome,
      banco: c.banco,
      agencia: c.agencia,
      conta: c.conta,
      id_fonte_recursos: c.id_fonte_recursos,
      grupo_despesa: c.grupo_despesa,
      saldo_minimo_alerta: Number(c.saldo_minimo_alerta),
      ativa: c.ativa,
      modo_movimentacao: c.modo_movimentacao ?? "PAGA",
      digito: c.digito ?? "",
      tipo: c.tipo ?? "",
      titularidade: c.titularidade ?? "",
      orgao_gestor: c.orgao_gestor ?? "",
      finalidade: c.finalidade ?? "",
      data_abertura: c.data_abertura ?? "",
    });
    v.reiniciar();
    setOpen(true);
  }

  const saveM = useMutation({
    mutationFn: () => {
      const payload = {
        nome: form.nome.trim(),
        banco: form.banco.trim(),
        agencia: form.agencia.trim(),
        conta: form.conta.trim(),
        id_fonte_recursos: form.id_fonte_recursos,
        grupo_despesa: form.grupo_despesa,
        saldo_minimo_alerta: form.saldo_minimo_alerta ?? 0,
        ativa: form.ativa,
        modo_movimentacao: form.modo_movimentacao,
        digito: form.digito.trim() || null,
        tipo: form.tipo.trim() || null,
        titularidade: form.titularidade.trim() || null,
        orgao_gestor: form.orgao_gestor.trim() || null,
        finalidade: form.finalidade.trim() || null,
        data_abertura: form.data_abertura || null,
      };
      return editId === null
        ? api.pagamentos.cadastros.contas.create(payload)
        : api.pagamentos.cadastros.contas.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-contas"] });
      toast.success(editId === null ? "Conta criada." : "Conta atualizada.");
      setOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.pagamentos.cadastros.contas.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-contas"] });
      toast.success("Conta excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(c: ContaBancaria) {
    const ok = await confirm({
      title: "Excluir conta bancária",
      message: "Esta ação não pode ser desfeita. Deseja realmente excluir esta conta?",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) removeM.mutate(c.id);
  }

  const contas = listQ.data ?? [];
  const grupoOptions = enumsQ.data?.grupo_despesa ?? Object.keys(GRUPO_LABELS);
  // Grupos que a fonte escolhida aceita (vazio = todos).
  const gruposDaFonte =
    fontesQ.data?.find((f) => f.id === form.id_fonte_recursos)?.grupos_despesa_permitidos ?? [];

  const v = useValidacaoCampos(
    {
      nome: !form.nome.trim() && "Dê um nome para reconhecer a conta nas listas.",
      banco: !form.banco.trim() && "Informe o banco.",
      agencia: !form.agencia.trim() && "Informe a agência.",
      conta: !form.conta.trim() && "Informe o número da conta.",
      id_fonte_recursos: form.id_fonte_recursos === null && "Escolha a fonte de recursos da conta.",
      // Mesma regra do backend (`_validar_fonte_grupo`), dita antes de salvar.
      grupo_despesa:
        gruposDaFonte.length > 0 &&
        !gruposDaFonte.includes(form.grupo_despesa) &&
        "Esta fonte não aceita este grupo de despesa. Escolha um dos grupos da fonte.",
    },
    {
      nome: "conta-nome",
      banco: "conta-banco",
      agencia: "conta-agencia",
      conta: "conta-conta",
      id_fonte_recursos: "conta-fonte",
      grupo_despesa: "conta-grupo",
    },
  );

  function salvar() {
    if (v.conferir()) saveM.mutate();
  }

  function fonteNome(id: number) {
    return fontesQ.data?.find((f) => f.id === id)?.descricao ?? String(id);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Building2}
        title="Contas bancárias"
        description="Contas da prefeitura por fonte de recursos, com o saldo mínimo que dispara alerta."
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova conta bancária
          </Button>
        }
      />

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Banco / Agência / Conta</TH>
            <TH>Fonte</TH>
            <TH>Grupo</TH>
            <TH>Situação</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {!listQ.isLoading && contas.length === 0 && (
            <TR>
              <TD colSpan={6} className="p-0">
                <EmptyState
                  icon={Building2}
                  title="Nenhuma conta bancária cadastrada"
                  description="Cadastre as contas de onde saem os pagamentos."
                  action={
                    <Button onClick={openNew}>
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      Nova conta bancária
                    </Button>
                  }
                  className="rounded-none border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {contas.map((c) => (
            <TR key={c.id}>
              <TD>{c.nome}</TD>
              <TD>
                {c.banco} / {c.agencia} / {c.conta}
              </TD>
              <TD>{fonteNome(c.id_fonte_recursos)}</TD>
              <TD>{GRUPO_LABELS[c.grupo_despesa] ?? c.grupo_despesa}</TD>
              <TD>
                <AtivoBadge ativo={c.ativa} feminino />
              </TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, onClick: () => openEdit(c) },
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
        title={editId === null ? "Nova conta bancária" : "Editar conta bancária"}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={salvar} loading={saveM.isPending}>
              {editId === null ? "Cadastrar conta" : "Salvar alterações"}
            </Button>
          </>
        }
      >
        <div className="space-y-5">
          {/* Qual conta */}
          <div className="space-y-4">
            <FormField
              label="Nome"
              required
              error={v.erro("nome")}
              hint="Como a conta aparece nas filas e no painel do caixa."
            >
              <Input
                id="conta-nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                onBlur={v.tocar("nome")}
                maxLength={150}
                placeholder="Ex.: FUNDEB 70% — Banco do Brasil"
              />
            </FormField>
            <FormField label="Banco" required error={v.erro("banco")}>
              <Input
                id="conta-banco"
                value={form.banco}
                onChange={(e) => setForm({ ...form, banco: e.target.value })}
                onBlur={v.tocar("banco")}
                maxLength={100}
                placeholder="Ex.: 001 — Banco do Brasil"
              />
            </FormField>
            <GradeCampos colunas={3}>
              <FormField label="Agência" required error={v.erro("agencia")}>
                <Input
                  id="conta-agencia"
                  value={form.agencia}
                  onChange={(e) => setForm({ ...form, agencia: e.target.value })}
                  onBlur={v.tocar("agencia")}
                  maxLength={20}
                  inputMode="numeric"
                  placeholder="Ex.: 1234"
                />
              </FormField>
              <FormField label="Conta" required error={v.erro("conta")}>
                <Input
                  id="conta-conta"
                  value={form.conta}
                  onChange={(e) => setForm({ ...form, conta: e.target.value })}
                  onBlur={v.tocar("conta")}
                  maxLength={30}
                  inputMode="numeric"
                  placeholder="Ex.: 56789"
                />
              </FormField>
              <FormField label="Dígito" opcional>
                <Input
                  id="conta-digito"
                  value={form.digito}
                  onChange={(e) => setForm({ ...form, digito: e.target.value })}
                  maxLength={5}
                  placeholder="Ex.: 0"
                />
              </FormField>
            </GradeCampos>
          </div>

          {/* Para que serve */}
          <div className="space-y-4 border-t border-border pt-4">
            <GradeCampos>
              <FormField
                label="Fonte de recursos"
                required
                error={v.erro("id_fonte_recursos")}
                hint="Só pagam por esta conta as despesas desta fonte."
              >
                <Select
                  id="conta-fonte"
                  value={form.id_fonte_recursos ?? ""}
                  onChange={(e) => {
                    setForm({
                      ...form,
                      id_fonte_recursos: e.target.value === "" ? null : Number(e.target.value),
                    });
                    v.tocar("id_fonte_recursos")();
                  }}
                >
                  <option value="">Escolha a fonte</option>
                  {fontesQ.data?.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.codigo} — {f.descricao}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField
                label="Grupo de despesa"
                required
                error={v.erro("grupo_despesa")}
                hint={
                  gruposDaFonte.length > 0
                    ? `Esta fonte aceita: ${gruposDaFonte.map((g) => GRUPO_LABELS[g] ?? g).join(", ")}.`
                    : undefined
                }
              >
                <Select
                  id="conta-grupo"
                  value={form.grupo_despesa}
                  onChange={(e) => setForm({ ...form, grupo_despesa: e.target.value })}
                >
                  {grupoOptions.map((g) => (
                    <option key={g} value={g}>
                      {GRUPO_LABELS[g] ?? g}
                    </option>
                  ))}
                </Select>
              </FormField>
            </GradeCampos>
            <EscolhaSegmentada
              nome="conta-modo"
              titulo="Modo de movimentação"
              valor={form.modo_movimentacao}
              onChange={(m) => setForm({ ...form, modo_movimentacao: m })}
              opcoes={[
                {
                  valor: "PAGA",
                  rotulo: "Paga",
                  descricao: "Pode ser escolhida como conta pagadora na autorização.",
                },
                {
                  valor: "RECEBE",
                  rotulo: "Recebe",
                  descricao: "Só recebe recursos: não aparece como conta pagadora.",
                },
                {
                  valor: "TRANSFERE",
                  rotulo: "Transfere",
                  descricao: "Conta de passagem entre contas: não aparece como conta pagadora.",
                },
                {
                  valor: "RESTRITA",
                  rotulo: "Restrita",
                  descricao: "Movimentação restrita: não aparece como conta pagadora.",
                },
              ]}
              moldura={false}
            />
            <FormField
              label="Saldo mínimo de alerta"
              opcional
              hint="Abaixo deste saldo, a conta aparece em alerta no painel do caixa."
            >
              <CampoComUnidade
                id="conta-saldo"
                prefixo="R$"
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={form.saldo_minimo_alerta}
                onChange={(e) =>
                  setForm({
                    ...form,
                    saldo_minimo_alerta: e.target.value === "" ? 0 : Number(e.target.value),
                  })
                }
              />
            </FormField>
          </div>

          {/* Detalhes de cadastro (todos opcionais) */}
          <div className="space-y-4 border-t border-border pt-4">
            <p className="text-sm font-semibold text-foreground">
              Detalhes do cadastro{" "}
              <span className="text-xs font-normal text-foreground-subtle">opcionais</span>
            </p>
            <GradeCampos>
              <FormField label="Tipo">
                <Input
                  id="conta-tipo"
                  value={form.tipo}
                  onChange={(e) => setForm({ ...form, tipo: e.target.value })}
                  maxLength={20}
                  placeholder="Ex.: Corrente"
                />
              </FormField>
              <FormField label="Data de abertura">
                <Input
                  id="conta-abertura"
                  type="date"
                  value={form.data_abertura}
                  onChange={(e) => setForm({ ...form, data_abertura: e.target.value })}
                />
              </FormField>
              <FormField label="Titularidade">
                <Input
                  id="conta-titularidade"
                  value={form.titularidade}
                  onChange={(e) => setForm({ ...form, titularidade: e.target.value })}
                  maxLength={150}
                  placeholder="Ex.: Fundo Municipal de Saúde"
                />
              </FormField>
              <FormField label="Órgão gestor">
                <Input
                  id="conta-orgao"
                  value={form.orgao_gestor}
                  onChange={(e) => setForm({ ...form, orgao_gestor: e.target.value })}
                  maxLength={150}
                  placeholder="Ex.: Secretaria de Saúde"
                />
              </FormField>
            </GradeCampos>
            <FormField label="Finalidade">
              <Input
                id="conta-finalidade"
                value={form.finalidade}
                onChange={(e) => setForm({ ...form, finalidade: e.target.value })}
                maxLength={255}
                placeholder="Ex.: Repasses do SUS para a atenção básica"
              />
            </FormField>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Checkbox
                id="conta-ativa"
                checked={form.ativa}
                onChange={(e) => setForm({ ...form, ativa: e.target.checked })}
              />
              <Label htmlFor="conta-ativa" className="mb-0">
                Ativa
              </Label>
            </div>
            <p className="pl-7 text-xs text-foreground-muted">
              Conta inativa deixa de ser oferecida como conta pagadora.
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
