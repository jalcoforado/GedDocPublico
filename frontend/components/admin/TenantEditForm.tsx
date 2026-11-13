"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { PLANO_LABEL, PLANOS } from "@/components/admin/TenantsAdmin";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { nomeDoModulo } from "@/lib/modulos";
import { corValida } from "@/lib/tema-cores";

export function TenantEditForm({ tenantId }: { tenantId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["admin-tenant", tenantId], queryFn: () => api.admin.tenants.detalhe(tenantId) });
  const [form, setForm] = useState({ nome: "", cnpj: "", plano: "basico", cor_primaria: "", limite_usuarios: "", limite_armazenamento_mb: "" });
  // Erros só depois da tentativa (saiu do campo ou tentou salvar).
  const [tocados, setTocados] = useState<Set<"nome" | "cor_primaria">>(new Set());
  const [tentou, setTentou] = useState(false);

  useEffect(() => {
    if (q.data) {
      setForm({
        nome: q.data.nome ?? "",
        cnpj: q.data.cnpj ?? "",
        plano: q.data.plano ?? "basico",
        cor_primaria: q.data.cor_primaria ?? "",
        limite_usuarios: q.data.limite_usuarios?.toString() ?? "",
        limite_armazenamento_mb: q.data.limite_armazenamento_mb?.toString() ?? "",
      });
    }
  }, [q.data]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api.admin.tenants.editar(tenantId, {
        nome: form.nome.trim(),
        cnpj: form.cnpj.trim() || null,
        plano: form.plano,
        cor_primaria: form.cor_primaria.trim() || null,
        limite_usuarios: form.limite_usuarios ? Number(form.limite_usuarios) : null,
        limite_armazenamento_mb: form.limite_armazenamento_mb ? Number(form.limite_armazenamento_mb) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-tenant", tenantId] });
      qc.invalidateQueries({ queryKey: ["admin-tenants"] });
      toast.success("Prefeitura atualizada.");
      setTentou(false);
      setTocados(new Set());
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) return <Carregando className="text-sm text-foreground-muted" />;
  if (!q.data) return <p className="text-sm text-foreground-muted">Prefeitura não encontrada.</p>;

  const cor = form.cor_primaria.trim();
  const erros = {
    nome: form.nome.trim() ? undefined : "Informe o nome da prefeitura.",
    // A mesma coluna, pela tela Aparência do município, só aceita #RRGGBB.
    cor_primaria: cor && !corValida(cor) ? "Use o formato #RRGGBB: # e seis dígitos de 0 a 9 ou A a F." : undefined,
  };
  const erroVisivel = (c: keyof typeof erros) => (tentou || tocados.has(c) ? erros[c] : undefined);
  const tocar = (c: keyof typeof erros) => () => setTocados((s) => new Set(s).add(c));

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (erros.nome || erros.cor_primaria) {
      setTentou(true);
      document.getElementById(erros.nome ? "tenant-nome" : "tenant-cor")?.focus();
      return;
    }
    m.mutate();
  }

  return (
    <form onSubmit={salvar} noValidate className="max-w-2xl space-y-5">
      <FormField
        label="Endereço no sistema (slug)"
        hint="Identifica o subdomínio e os links públicos; não muda depois de criado."
      >
        {/* Slug NÃO é editável: identifica o subdomínio / URLs públicas. */}
        <Input value={q.data.slug} readOnly disabled className="font-mono" />
      </FormField>

      <GradeCampos>
        <FormField label="Nome" required error={erroVisivel("nome")}>
          <Input id="tenant-nome" value={form.nome} onChange={set("nome")} onBlur={tocar("nome")} />
        </FormField>
        <FormField label="CNPJ" opcional>
          <Input value={form.cnpj} onChange={set("cnpj")} maxLength={20} placeholder="Ex.: 00.000.000/0001-00" />
        </FormField>
      </GradeCampos>

      <EscolhaSegmentada
        nome="plano-edicao"
        titulo="Plano"
        valor={form.plano}
        onChange={(plano) => setForm((f) => ({ ...f, plano }))}
        opcoes={PLANOS.map((p) => ({ valor: p, rotulo: PLANO_LABEL[p] ?? p }))}
        moldura={false}
      />

      <FormField
        label="Cor primária"
        opcional
        error={erroVisivel("cor_primaria")}
        hint="Código hexadecimal, com #. O município também pode trocar em Aparência."
        className="max-w-xs"
      >
        <CorComAmostra id="tenant-cor" valor={form.cor_primaria} onChange={set("cor_primaria")} onBlur={tocar("cor_primaria")} />
      </FormField>

      <GradeCampos>
        <FormField label="Limite de usuários" opcional hint="Em branco, sem limite definido.">
          <CampoComUnidade
            type="number"
            min={0}
            sufixo="usuários"
            value={form.limite_usuarios}
            onChange={set("limite_usuarios")}
            placeholder="Ex.: 50"
          />
        </FormField>
        <FormField label="Limite de armazenamento" opcional hint="Em branco, sem limite definido.">
          <CampoComUnidade
            type="number"
            min={0}
            sufixo="MB"
            value={form.limite_armazenamento_mb}
            onChange={set("limite_armazenamento_mb")}
            placeholder="Ex.: 10240"
          />
        </FormField>
      </GradeCampos>

      <p className="text-xs text-foreground-muted">
        Módulos do plano: {q.data.modulos.map(nomeDoModulo).join(", ") || "—"}. A contratação
        de cada módulo fica na aba Módulos.
      </p>

      <div className="border-t border-border pt-4">
        <Button type="submit" loading={m.isPending}>
          {m.isPending ? "Salvando…" : "Salvar alterações"}
        </Button>
      </div>
    </form>
  );
}

/** Campo de texto da cor com a amostra ao lado — o hexadecimal sozinho não diz que cor é. */
function CorComAmostra({
  id,
  valor,
  onChange,
  onBlur,
  ...aria
}: {
  id?: string;
  valor: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onBlur: () => void;
  "aria-invalid"?: boolean | "true" | "false";
  "aria-describedby"?: string;
}) {
  const ok = corValida(valor.trim());
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="h-9 w-9 shrink-0 rounded-md border border-border bg-surface-2"
        style={ok ? { backgroundColor: valor.trim() } : undefined}
      />
      <Input
        id={id}
        value={valor}
        onChange={onChange}
        onBlur={onBlur}
        maxLength={7}
        placeholder="#RRGGBB"
        className="font-mono"
        {...aria}
      />
    </div>
  );
}
