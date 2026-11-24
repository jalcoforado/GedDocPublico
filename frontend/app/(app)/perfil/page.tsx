"use client";

import { Bell, ChevronRight, UserRound } from "lucide-react";
import Link from "next/link";

import { PreferenciasAparencia } from "@/components/PreferenciasAparencia";
import { TrocarSenhaCard } from "@/components/TrocarSenhaCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth";

export default function PerfilPage() {
  const { user, perms } = useAuth();
  if (!user) return null;

  // A sessão já traz as lotações com nome; a principal é a unidade do cadastro.
  // Sem ela na lista, o número cru é melhor que nada.
  const unidade =
    user.id_unidade_trabalho == null
      ? "—"
      : (user.lotacoes?.find((l) => l.id === user.id_unidade_trabalho)?.nome ??
        `#${user.id_unidade_trabalho}`);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={UserRound}
        title="Meu perfil"
        description="Seus dados de acesso, a aparência do sistema, a senha e as permissões que você tem."
      />

      {/* Duas colunas em tela larga: cada cartão continua com largura de
          leitura, e a página não fica com a metade direita vazia. */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{user.nome}</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-foreground-muted">ID</dt>
                  <dd className="text-foreground tabular-nums">{user.id}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-foreground-muted">E-mail</dt>
                  <dd className="break-all text-foreground">{user.email}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-foreground-muted">Cargo</dt>
                  <dd className="text-foreground">{user.cargo || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-foreground-muted">Unidade</dt>
                  <dd className="text-foreground">{unidade}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {/* Superfície canônica de aparência (UX-03 fatia 3.7) — mesma
              implementação dos radiogroups do AvatarDropdown. */}
          <Card>
            <CardHeader>
              <CardTitle>Aparência</CardTitle>
            </CardHeader>
            <CardContent>
              <PreferenciasAparencia className="max-w-sm" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notificações</CardTitle>
              <CardDescription>
                Escolha por onde quer ser avisado de cada tipo de evento.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="secondary">
                <Link href="/perfil/notificacoes">
                  <Bell className="h-4 w-4" aria-hidden="true" />
                  Preferências de notificações
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <TrocarSenhaCard />

        {perms && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Permissões ({perms.permissoes.length})</CardTitle>
              <CardDescription>
                {perms.is_super_usuario
                  ? "Super usuário — todas as transações do sistema disponíveis."
                  : "Acesso conforme as permissões abaixo."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
                {perms.permissoes.map((p) => (
                  <li key={p.codigo} className="rounded-md bg-surface-2 px-2 py-1.5">
                    <span className="font-mono text-foreground">{p.codigo}</span>{" "}
                    <span className="text-foreground-muted">— {p.transacao}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
