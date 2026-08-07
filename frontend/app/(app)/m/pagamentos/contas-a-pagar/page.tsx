import { redirect } from "next/navigation";

export default function ContasAPagarRedirect() {
  redirect("/m/pagamentos/solicitacoes");
}
