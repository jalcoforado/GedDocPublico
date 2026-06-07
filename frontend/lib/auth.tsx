"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { api, type MeResponse, type PermissaoMeResponse } from "@/lib/api";

interface AuthContextValue {
  user: MeResponse | null;
  perms: PermissaoMeResponse | null;
  loading: boolean;
  logout: () => void;
  can: (codigo: string, action?: "inserir" | "atualizar" | "excluir") => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [perms, setPerms] = useState<PermissaoMeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Cookie HttpOnly: JS não pode ler, mas o navegador envia em /auth/me automaticamente.
    // Se 401, redireciona pra login.
    Promise.all([api.me(), api.permissoes()])
      .then(([u, p]) => {
        setUser(u);
        setPerms(p);
        // SEC-1 Commit 5 — se o servidor diz que a senha é temporária,
        // empurra para a tela obrigatória. Não redireciona se já estiver
        // lá (evita loop). Sem `pathname` no array de deps: evita re-run
        // a cada navegação interna; o redirect roda uma vez por mount.
        if (
          u.must_change_password &&
          typeof window !== "undefined" &&
          window.location.pathname !== "/alterar-senha-obrigatoria"
        ) {
          router.replace("/alterar-senha-obrigatoria");
        }
      })
      .catch(() => {
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  function logout() {
    api.logout().finally(() => {
      setUser(null);
      setPerms(null);
      router.push("/login");
    });
  }

  function can(codigo: string, action?: "inserir" | "atualizar" | "excluir") {
    if (!perms) return false;
    if (perms.is_super_usuario) return true;
    const p = perms.permissoes.find((x) => x.codigo === codigo);
    if (!p) return false;
    if (!action) return true;
    return p[action];
  }

  return (
    <AuthContext.Provider value={{ user, perms, loading, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}
