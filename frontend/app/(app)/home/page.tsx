"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { user, perms } = useAuth();
  const { data: modulos, isLoading } = useQuery({
    queryKey: ["modulos"],
    queryFn: api.modulos,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">Olá, {user?.nome}</h1>
        <p className="text-sm text-muted-foreground">
          {perms?.is_super_usuario
            ? "Você é Super Usuário deste sistema."
            : `Nível: ${perms?.nivel_valor ?? "—"}`}
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Meus módulos</h2>
        {isLoading && (
          <p className="text-sm text-muted-foreground">Carregando módulos...</p>
        )}
        {modulos && modulos.items.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum módulo configurado.</p>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {modulos?.items.map((m) => (
            <a
              key={m.id}
              href={m.url ?? "#"}
              target={m.url ? "_blank" : undefined}
              rel="noreferrer"
              className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Card className="transition-shadow hover:shadow-md">
                <CardHeader>
                  <CardTitle>{m.modulo}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="break-all text-xs text-muted-foreground">{m.url ?? "—"}</p>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
