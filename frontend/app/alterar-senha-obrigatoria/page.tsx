"use client";

/**
 * SEC-1 Commit 5 — tela de troca obrigatória de senha.
 *
 * Fora do grupo `(app)` propositalmente: não usa o layout principal com
 * sidebar. O usuário em estado `must_change_password=true` não tem acesso
 * a nada além desta tela (whitelist do guard backend cobre apenas as 4
 * rotas necessárias).
 *
 * Fluxo:
 *  - Mount → GET /auth/me (whitelist do Commit 2).
 *    - 401 / erro → /login.
 *    - flag=false → /home (não precisa estar aqui).
 *    - flag=true → mostra o form.
 *  - Sucesso na troca → /home (AuthProvider revalida e libera as rotas).
 *  - Botão Sair → /auth/logout → /login.
 *
 * Não exibe senha temporária. Não persiste qualquer estado de senha
 * fora dos states do form (limpos no sucesso pelo TrocarSenhaCard).
 */
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { TrocarSenhaCard } from "@/components/TrocarSenhaCard";
import { Button } from "@/components/ui/button";
import { ApiError, api, type MeResponse } from "@/lib/api";
import { Providers } from "@/lib/providers";

function Inner() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((u) => {
        if (!u.must_change_password) {
          // Usuário já trocou (ou nunca precisou) — não tem o que fazer aqui.
          router.replace("/home");
          return;
        }
        setMe(u);
      })
      .catch((e: unknown) => {
        // 401 ou outro erro: trata como sessão inválida.
        if (e instanceof ApiError && e.status === 401) {
          router.replace("/login");
          return;
        }
        router.replace("/login");
      })
      .finally(() => setChecking(false));
  }, [router]);

  if (checking || !me) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-foreground-muted">
        Carregando...
      </div>
    );
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="w-full max-w-md space-y-6">
        {/* Usar <div> em vez de <header> para evitar role=banner, que sinalizaria
            o cabeçalho do layout principal. Esta página é standalone. */}
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Troca de senha obrigatória
          </h1>
          <p className="text-sm text-foreground-muted">
            Por segurança, altere sua senha temporária antes de continuar.
          </p>
        </div>

        <TrocarSenhaCard
          successMessage="Senha alterada. Você já pode acessar o sistema."
          onSuccess={() => router.replace("/home")}
        />

        <div className="text-center">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              api.logout().finally(() => router.replace("/login"));
            }}
          >
            Sair
          </Button>
        </div>
      </div>
    </main>
  );
}

export default function AlterarSenhaObrigatoriaPage() {
  return (
    <Providers>
      <Inner />
    </Providers>
  );
}
