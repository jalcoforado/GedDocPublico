import { CheckCircle2, Pause } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/**
 * Situação de um item de cadastro (assunto, bairro, tipo…). Era "Sim"/"Não"
 * solto na coluna "Ativo"; com o selo, inativo se distingue de relance e tem
 * a mesma cor e ícone que nos relatórios do Protocolo.
 */
export function BadgeAtivo({ ativo }: { ativo: boolean | null | undefined }) {
  return ativo ? (
    <Badge intent="success" icon={CheckCircle2}>Ativo</Badge>
  ) : (
    <Badge intent="neutral" icon={Pause}>Inativo</Badge>
  );
}
