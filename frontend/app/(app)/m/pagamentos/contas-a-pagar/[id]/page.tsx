import { redirect } from "next/navigation";

export default async function ContaAPagarRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/m/pagamentos/solicitacoes/${id}`);
}
