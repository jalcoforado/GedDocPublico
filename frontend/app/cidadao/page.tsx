"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useCidadao } from "@/lib/cidadao-auth";

export default function CidadaoLandingPage() {
  const router = useRouter();
  const { cidadao, loading } = useCidadao();

  useEffect(() => {
    if (loading) return;
    router.replace(cidadao ? "/cidadao/processos" : "/cidadao/login");
  }, [router, cidadao, loading]);

  return <p className="text-sm text-muted-foreground">Carregando...</p>;
}
