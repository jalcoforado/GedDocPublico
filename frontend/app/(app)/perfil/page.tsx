"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";

export default function PerfilPage() {
  const { user, perms } = useAuth();
  if (!user) return null;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-primary">Meu perfil</h1>

      <Card>
        <CardHeader>
          <CardTitle>{user.nome}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">ID</dt>
              <dd className="text-foreground tabular-nums">{user.id}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">E-mail</dt>
              <dd className="text-foreground">{user.email}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Cargo</dt>
              <dd className="text-foreground">{user.cargo ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Unidade</dt>
              <dd className="text-foreground">{user.id_unidade_trabalho ?? "—"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {perms && (
        <Card>
          <CardHeader>
            <CardTitle>Permissões ({perms.permissoes.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-sm text-muted-foreground">
              {perms.is_super_usuario
                ? "Super Usuário — todas as transações do sistema disponíveis"
                : `Nível ${perms.nivel_valor}`}
            </p>
            <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
              {perms.permissoes.map((p) => (
                <li key={p.codigo} className="rounded bg-muted px-2 py-1.5">
                  <span className="font-mono text-foreground">{p.codigo}</span>{" "}
                  <span className="text-muted-foreground">— {p.transacao}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
