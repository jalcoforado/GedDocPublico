import { Badge } from "@/components/ui/badge";

import { CRITICIDADE_ROTULO } from "./situacoes";

/** Criticidade por rótulo e cor — a tabela mostrava o código cru ("MEDIA"). */
export function CriticidadeBadge({ valor }: { valor: string | null | undefined }) {
  if (!valor) return <>—</>;
  const r = CRITICIDADE_ROTULO[valor];
  if (!r) return <Badge>{valor}</Badge>;
  return (
    <Badge intent={r.intent} icon={r.icon}>
      {r.label}
    </Badge>
  );
}

/**
 * Situação do cadastro. "Sim/Não" numa coluna "Ativa" obrigava a ler o
 * cabeçalho; o selo diz a situação sozinho. `feminino` acompanha o substantivo
 * (conta, natureza → "Ativa"; item, fornecedor → "Ativo").
 */
export function AtivoBadge({ ativo, feminino = false }: { ativo: boolean; feminino?: boolean }) {
  const fim = feminino ? "a" : "o";
  return ativo ? (
    <Badge intent="success">{`Ativ${fim}`}</Badge>
  ) : (
    <Badge>{`Inativ${fim}`}</Badge>
  );
}
