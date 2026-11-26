"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { flushSync } from "react-dom";

import { CoresDoTema, temCorInvalida } from "@/components/admin/CoresDoTema";
import { Button } from "@/components/ui/button";
import { focarPrimeiroInvalido } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { useToast } from "@/components/ui/toast";
import { tenantsApi, type TenantInstitucionalUpdate, type TenantMe } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRecarregarBranding } from "@/lib/branding";

/** Os cinco campos do tema. `""` = não definido (vale o padrão do sistema). */
interface TemaForm {
  cor_primaria: string;
  cor_destaque: string;
  cor_lateral: string;
  cor_titulos: string;
  fonte_titulos: string;
}

const VAZIO: TemaForm = {
  cor_primaria: "",
  cor_destaque: "",
  cor_lateral: "",
  cor_titulos: "",
  fonte_titulos: "",
};

const nullify = (v: string): string | null => (v.trim() === "" ? null : v.trim());

function doTenant(t: TenantMe): TemaForm {
  return {
    cor_primaria: t.cor_primaria ?? "",
    cor_destaque: t.cor_destaque ?? "",
    cor_lateral: t.cor_lateral ?? "",
    cor_titulos: t.cor_titulos ?? "",
    fonte_titulos: t.fonte_titulos ?? "",
  };
}

/**
 * Aparência do sistema para o município: cores e fonte dos títulos.
 *
 * Tela própria, com entrada no menu, porque o editor morava no meio do
 * formulário de identidade em Configurações — quatro cliques e uma rolagem até
 * achar, para a função que mais se mostra numa demonstração.
 *
 * Salva pelo mesmo `PUT /tenants/me` de Configurações, mandando SÓ os cinco
 * campos do tema: o endpoint aplica o que vier (`exclude_unset`), então salvar
 * aqui não toca nome, endereço ou logo — e salvar lá deixou de tocar as cores.
 */
export default function AparenciaPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const canEdit = can("configuracao", "atualizar");
  const recarregarBranding = useRecarregarBranding();

  const tenantQ = useQuery({ queryKey: ["tenant-me"], queryFn: () => tenantsApi.me() });
  const [form, setForm] = useState<TemaForm>(VAZIO);
  const [tentou, setTentou] = useState(false);

  useEffect(() => {
    if (tenantQ.data) setForm(doTenant(tenantQ.data));
  }, [tenantQ.data]);

  const saveM = useMutation({
    mutationFn: (payload: TenantInstitucionalUpdate) => tenantsApi.updateInstitucional(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenant-me"] });
      // As cores salvas passam a valer já, sem recarregar a página.
      recarregarBranding();
      toast.success("Aparência salva.");
      setTentou(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const alterado =
    !!tenantQ.data && JSON.stringify(form) !== JSON.stringify(doTenant(tenantQ.data));

  function salvar() {
    // O backend recusa cor fora de #RRGGBB; melhor mostrar onde está o erro
    // do que devolver um 422 genérico.
    if (temCorInvalida(form)) {
      flushSync(() => setTentou(true));
      focarPrimeiroInvalido();
      return;
    }
    saveM.mutate({
      cor_primaria: nullify(form.cor_primaria),
      cor_destaque: nullify(form.cor_destaque),
      cor_lateral: nullify(form.cor_lateral),
      cor_titulos: nullify(form.cor_titulos),
      fonte_titulos: nullify(form.fonte_titulos),
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Palette}
        title="Aparência"
        description="Cores e fonte do sistema para todos os usuários do município. O que você escolher aqui vale para o menu, o cabeçalho, os botões e os títulos."
      />

      <SectionCard
        icon={Palette}
        title="Cores e fonte do sistema"
        description="Em branco, cada item usa o padrão do sistema. A prévia ao lado mostra o resultado antes de salvar."
      >
        {tenantQ.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-foreground-muted">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Carregando…
          </p>
        ) : tenantQ.isError ? (
          <p role="alert" className="text-sm text-danger-soft-foreground">
            Não foi possível carregar a aparência atual. Recarregue a página.
          </p>
        ) : (
          <div className="space-y-5">
            <CoresDoTema
              valores={form}
              onChange={(campo, valor) => setForm((f) => ({ ...f, [campo]: valor }))}
              disabled={!canEdit}
              mostrarErros={tentou}
            />
            <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
              <Button onClick={salvar} disabled={!canEdit} loading={saveM.isPending}>
                Salvar aparência
              </Button>
              <span className="text-xs text-foreground-muted" aria-live="polite">
                {!canEdit
                  ? "Você não tem permissão para editar — somente leitura."
                  : alterado
                    ? "Há alterações não salvas."
                    : ""}
              </span>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
