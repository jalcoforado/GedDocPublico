"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Carregando } from "@/components/ui/carregando";

/**
 * `/modulos` — o launcher "Meus módulos" SAIU em 2026-11-05 com o menu único
 * (a barra lateral lista todos os módulos contratados em toda tela). A rota
 * fica, por dois motivos: favoritos e links antigos continuam funcionando, e
 * a regex de rotas do nginx só cresce (CLAUDE.md, F3).
 *
 * Redirecionamento no cliente e com `replace`, de propósito: um 308 no
 * `next.config` vira cache permanente do navegador, e se um dia `/modulos`
 * voltar a ser tela, quem já passou por aqui ficaria preso no destino velho.
 * A versão anterior desta página está no histórico do git.
 */
export default function ModulosRetirado() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/home");
  }, [router]);
  return <Carregando className="pt-2" />;
}
