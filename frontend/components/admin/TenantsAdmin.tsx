"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Landmark, Pencil, Plus, Power, PowerOff } from "lucide-react";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type AdminTenantCreated } from "@/lib/api";

export const PLANOS = ["basico", "profissional", "enterprise"];

/** O valor gravado é o código; a tela mostra o nome. */
export const PLANO_LABEL: Record<string, string> = {
  basico: "Básico",
  profissional: "Profissional",
  enterprise: "Enterprise",
};

export function TenantsAdmin() {
  const qc = useQueryClient();
  const toast = useToast();
  const [openCriar, setOpenCriar] = useState(false);

  const listQ = useQuery({ queryKey: ["admin-tenants"], queryFn: () => api.admin.tenants.list() });

  const toggleM = useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) =>
      ativo ? api.admin.tenants.desativar(id) : api.admin.tenants.ativar(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenants"] });
      toast.success("Status atualizado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Landmark}
        title="Prefeituras"
        description="Os municípios atendidos pela plataforma: plano, limite de usuários e situação de cada um."
        actions={
          <Button onClick={() => setOpenCriar(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova prefeitura
          </Button>
        }
      />

      <Table>
        <THead>
          <TR>
            <TH>Slug</TH>
            <TH>Nome</TH>
            <TH>Plano</TH>
            <TH className="text-right">Limite de usuários</TH>
            <TH>Situação</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {listQ.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {listQ.data && listQ.data.length === 0 && (
            <TR>
              <TD colSpan={6} className="p-0">
                <EmptyState
                  icon={Landmark}
                  title="Nenhuma prefeitura cadastrada"
                  description="Use “Nova prefeitura” para cadastrar o primeiro município."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {(listQ.data ?? []).map((t) => (
            <TR key={t.id}>
              <TD className="font-mono text-xs">{t.slug}</TD>
              <TD className="font-medium">{t.nome}</TD>
              <TD>{PLANO_LABEL[t.plano] ?? t.plano}</TD>
              <TD className="text-right tabular-nums">{t.limite_usuarios ?? "—"}</TD>
              <TD>
                <Badge intent={t.ativo ? "success" : "neutral"}>{t.ativo ? "Ativo" : "Inativo"}</Badge>
              </TD>
              <TD className="text-right">
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, href: `/admin/tenants/${t.id}` },
                    {
                      label: t.ativo ? "Desativar" : "Ativar",
                      icon: t.ativo ? PowerOff : Power,
                      // Desligar uma prefeitura derruba o acesso de todos os
                      // servidores dela: é a ação destrutiva da linha.
                      perigo: t.ativo,
                      disabled: toggleM.isPending,
                      onClick: () => toggleM.mutate({ id: t.id, ativo: t.ativo }),
                    },
                  ]}
                />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <CriarTenantDialog
        open={openCriar}
        onClose={() => setOpenCriar(false)}
        onCreated={() => qc.invalidateQueries({ queryKey: ["admin-tenants"] })}
      />
    </div>
  );
}

function CriarTenantDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    slug: "", nome: "", admin_email: "", admin_nome: "", admin_cpf: "", plano: "basico", cnpj: "", limite_usuarios: "",
  });
  const [criado, setCriado] = useState<AdminTenantCreated | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api.admin.tenants.criar({
        slug: form.slug.trim(),
        nome: form.nome.trim(),
        admin_email: form.admin_email.trim(),
        admin_nome: form.admin_nome.trim(),
        admin_cpf: form.admin_cpf.trim(),
        plano: form.plano,
        cnpj: form.cnpj.trim() || null,
        limite_usuarios: form.limite_usuarios ? Number(form.limite_usuarios) : null,
      }),
    onSuccess: (res) => {
      setCriado(res);
      onCreated();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function fechar() {
    setCriado(null);
    setForm({ slug: "", nome: "", admin_email: "", admin_nome: "", admin_cpf: "", plano: "basico", cnpj: "", limite_usuarios: "" });
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={criado ? "Prefeitura criada" : "Nova prefeitura"}
      size="lg"
      footer={
        criado ? (
          <Button onClick={fechar}>Fechar</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={fechar}>Cancelar</Button>
            <Button onClick={() => m.mutate()} disabled={m.isPending}>
              {m.isPending ? "Criando…" : "Criar"}
            </Button>
          </>
        )
      }
    >
      {criado ? (
        <div className="space-y-3 text-sm">
          <p className="text-foreground">
            Prefeitura <b>{criado.tenant.nome}</b> (<span className="font-mono">{criado.tenant.slug}</span>) criada.
          </p>
          <div className="rounded-md border border-border bg-muted p-3">
            <Label className="text-foreground-muted">Senha temporária do admin ({criado.admin_email})</Label>
            <code className="mt-1 block break-all font-mono text-base text-foreground">{criado.senha_temporaria}</code>
          </div>
          <p className="text-xs text-warning-soft-foreground">{criado.aviso}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Campo label="Slug (subdomínio, imutável)"><Input value={form.slug} onChange={set("slug")} placeholder="ex.: fortaleza" /></Campo>
          <Campo label="Nome"><Input value={form.nome} onChange={set("nome")} /></Campo>
          <Campo label="E-mail do admin"><Input value={form.admin_email} onChange={set("admin_email")} type="email" /></Campo>
          <Campo label="Nome do admin"><Input value={form.admin_nome} onChange={set("admin_nome")} /></Campo>
          <Campo label="CPF do admin"><Input value={form.admin_cpf} onChange={set("admin_cpf")} /></Campo>
          <Campo label="Plano">
            <Select value={form.plano} onChange={set("plano")}>
              {PLANOS.map((p) => <option key={p} value={p}>{PLANO_LABEL[p] ?? p}</option>)}
            </Select>
          </Campo>
          <Campo label="CNPJ (opcional)"><Input value={form.cnpj} onChange={set("cnpj")} /></Campo>
          <Campo label="Limite de usuários (opcional)"><Input value={form.limite_usuarios} onChange={set("limite_usuarios")} type="number" /></Campo>
        </div>
      )}
    </Dialog>
  );
}

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
