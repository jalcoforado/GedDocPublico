"use client";

import { useState } from "react";

import { TenantEditForm } from "@/components/admin/TenantEditForm";
import { TenantModulosTab } from "@/components/admin/TenantModulosTab";
import { TabList, TabPanel, Tabs, type TabDef } from "@/components/ui/tabs";

const ABAS: TabDef[] = [
  { value: "dados", label: "Dados" },
  { value: "modulos", label: "Módulos" },
];

/**
 * Abas "Dados" / "Módulos" da edição de tenant. Extraído de `page.tsx` (que
 * só pode exportar os nomes que o App Router reconhece — ver comentário lá)
 * para poder ser testado sem a ginástica de `use(params)`/Suspense da rota.
 *
 * Usa o primitivo `components/ui/tabs`. Antes reimplementava `role="tablist"`
 * à mão, **sem** `aria-controls`, sem `role="tabpanel"` e sem navegação por
 * setas — resíduo 1.0.9 da F2. O sintoma para quem usa leitor de tela: o
 * componente anuncia "aba" e o leitor não encontra painel associado, então não
 * há como saber o que aquela aba controla nem pular para o conteúdo.
 *
 * O primitivo existia desde a UX-02 (fatia 2.5), com ARIA completo e testado —
 * e **nenhum consumidor em produção**. Duas implementações do mesmo widget
 * conviveram, e a pior era a que estava na tela.
 *
 * `keepMounted` preserva a decisão original desta tela: as duas abas ficam
 * montadas o tempo todo, só a visível troca de `hidden`. Desmontar a inativa
 * faria o admin marcar módulos, olhar "Dados", voltar e achar as marcações
 * perdidas — sem erro e sem aviso. Nenhuma das duas tem efeito colateral ao
 * montar (sem toast, sem redirect), então o custo é as duas queries dispararem
 * um pouco mais cedo.
 */
export function TenantEditTabs({ tenantId }: { tenantId: number }) {
  const [aba, setAba] = useState("dados");

  return (
    <Tabs value={aba} onChange={setAba} className="max-w-2xl space-y-4">
      <TabList tabs={ABAS} aria-label="Seções do tenant" />

      <TabPanel value="dados" keepMounted>
        <TenantEditForm tenantId={tenantId} />
      </TabPanel>
      <TabPanel value="modulos" keepMounted>
        <TenantModulosTab tenantId={tenantId} />
      </TabPanel>
    </Tabs>
  );
}
