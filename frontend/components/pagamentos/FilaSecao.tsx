"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/section-card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { DebitoOut } from "@/lib/api";
import { TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { fmtMoeda } from "@/components/pagamentos/format";

interface FilaSecaoProps {
  titulo: string;
  icon: LucideIcon;
  itens: DebitoOut[];
  acaoLabel: string;
}

/**
 * Sub-lista titulada usada nas quatro filas (gestor/validação/autoridade/
 * concluídas): mesma tabela de débitos, um título e rótulo de ação distintos.
 * Some sozinha quando `itens` está vazio — quem decide se mostra "vazio" pra
 * fila inteira é a página.
 */
export function FilaSecao({ titulo, icon, itens, acaoLabel }: FilaSecaoProps) {
  if (itens.length === 0) return null;

  return (
    <SectionCard title={titulo} icon={icon}>
      <div className="overflow-x-auto">
        <Table>
          <THead>
            <TR>
              <TH>ID</TH>
              <TH>Fornecedor</TH>
              <TH className="text-right">Valor</TH>
              <TH>Situação</TH>
              <TH className="text-right">Ação</TH>
            </TR>
          </THead>
          <TBody>
            {itens.map((d) => {
              const rotulo = TRAMITACAO_ROTULO[d.situacao_tramitacao];
              return (
                <TR key={d.id}>
                  <TD className="font-mono text-sm">#{d.id}</TD>
                  <TD>{d.nome_fornecedor}</TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
                  <TD>
                    <Badge intent={rotulo.intent} icon={rotulo.icon}>{rotulo.label}</Badge>
                  </TD>
                  <TD className="text-right">
                    <Button asChild size="sm" variant="secondary">
                      <Link href={`/m/pagamentos/solicitacoes/${d.id}`}>{acaoLabel}</Link>
                    </Button>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </div>
    </SectionCard>
  );
}
