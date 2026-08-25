"use client";

import { use } from "react";

import { DetalheDebitoContent } from "@/components/pagamentos/DetalheDebitoContent";

export default function DetalheDebitosPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = use(params);
  return <DetalheDebitoContent id={parseInt(idParam)} />;
}
