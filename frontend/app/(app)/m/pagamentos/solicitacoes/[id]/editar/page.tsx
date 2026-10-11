"use client";

import { use } from "react";

import { EditarDebitoContent } from "@/components/pagamentos/EditarDebitoContent";

export default function EditarDebitoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = use(params);
  return <EditarDebitoContent id={parseInt(idParam)} />;
}
