"use client";

import { ShieldCheck, User, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PasswordInput } from "@/components/ui/password-input";
import { api } from "@/lib/api";
import { useBranding } from "@/lib/branding";
import { destinoDaQuery } from "@/lib/destino-login";

const DEV = process.env.NODE_ENV !== "production";

// Só o E-MAIL é lembrado. Guardar a senha no navegador deixaria a credencial
// em texto claro em `localStorage`, ao alcance de qualquer script da página.
const CHAVE_EMAIL_LEMBRADO = "aprimora_login_email";

const CAMPO =
  "flex h-12 w-full rounded-full border border-input bg-card px-5 text-base text-foreground shadow-input transition-colors duration-fast placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

function emailLembrado(): string | null {
  try {
    return window.localStorage.getItem(CHAVE_EMAIL_LEMBRADO);
  } catch {
    return null;
  }
}

function gravarEmailLembrado(email: string | null): void {
  try {
    if (email) window.localStorage.setItem(CHAVE_EMAIL_LEMBRADO, email);
    else window.localStorage.removeItem(CHAVE_EMAIL_LEMBRADO);
  } catch {
    // Armazenamento bloqueado (aba anônima etc.): o login segue sem lembrar.
  }
}

export default function LoginPage() {
  const router = useRouter();
  const branding = useBranding();
  const [email, setEmail] = useState(DEV ? "admin@local.test" : "");
  const [senha, setSenha] = useState(DEV ? "admin123" : "");
  const [lembrar, setLembrar] = useState(false);
  const [ajudaSenha, setAjudaSenha] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const salvo = emailLembrado();
    if (salvo) {
      setEmail(salvo);
      setLembrar(true);
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // SEC-1 Commit 6 — otimização: redireciona direto para a tela de
      // troca quando o backend já sinaliza must_change_password no login.
      // Evita o salto extra por /modulos (onde o AuthProvider faria o
      // redirect como defesa em profundidade — que permanece intacto).
      // Sem must_change_password, o destino do login bem-sucedido é o
      // launcher de módulos (F2 Task 5) — não mais o dashboard fixo /home.
      const r = await api.login(email, senha);
      gravarEmailLembrado(lembrar ? email : null);
      // `must_change_password` tem PRECEDÊNCIA sobre o `next` (SEC-1). O
      // destino guardado na URL é conveniência de navegação; a troca de senha
      // obrigatória é decisão do backend, e deixá-la ser pulada por um
      // parâmetro de URL seria contorná-la.
      //
      // O `next` é lido de `window.location.search`, e não por
      // `useSearchParams()`, para não obrigar esta página a uma fronteira de
      // Suspense — ela é client component e só precisa do valor no submit.
      router.push(
        r.must_change_password
          ? "/alterar-senha-obrigatoria"
          : destinoDaQuery(window.location.search),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao autenticar");
    } finally {
      setLoading(false);
    }
  }

  const nome = branding?.nome ?? "Aprimora";
  // Cor do tenant quando houver; senão, a da marca. Vai por `style` porque
  // vem do banco — não há classe do Tailwind para um valor só conhecido em runtime.
  const cor = branding?.cor_primaria ?? "hsl(var(--brand))";

  return (
    <main className="grid min-h-dvh lg:grid-cols-2">
      {/* === Painel da cidade (esquerda) — só desktop === */}
      <aside
        className="relative hidden overflow-hidden lg:block"
        style={{ backgroundColor: cor }}
      >
        {branding?.imagem_login_url ? (
          <>
            {/* Duotone na cor do tenant: a foto em tons de cinza é multiplicada
                pela cor de fundo (claros viram a cor, escuros ficam escuros). */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={branding.imagem_login_url}
              alt=""
              className="absolute inset-0 h-full w-full object-cover opacity-90 mix-blend-multiply grayscale"
            />
            <div
              className="absolute inset-0 bg-gradient-to-t from-black/25 to-white/10"
              aria-hidden="true"
            />
            {branding.imagem_login_credito ? (
              // Atribuição exigida pela licença da foto: fica legível, não
              // escondida de leitor de tela.
              <p className="absolute bottom-3 left-4 right-4 text-[11px] text-white/80">
                {branding.imagem_login_credito}
              </p>
            ) : null}
          </>
        ) : (
          <div
            className="absolute inset-0 bg-gradient-to-br from-white/15 to-black/25"
            aria-hidden="true"
          />
        )}
      </aside>

      {/* === Formulário (direita) === */}
      <section className="flex flex-col bg-background p-6 sm:p-12">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm">
            <div className="flex flex-col items-center text-center">
              {branding?.logo_login_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={branding.logo_login_url}
                  alt={nome}
                  className="max-h-32 w-auto max-w-full object-contain"
                />
              ) : (
                <div className="flex items-center gap-3">
                  {branding?.logo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={branding.logo_url}
                      alt=""
                      className="h-14 w-14 rounded-lg object-contain"
                    />
                  ) : (
                    <div className="inline-flex h-14 w-14 items-center justify-center rounded-lg bg-brand-gradient text-xl font-bold text-white shadow-brand">
                      A
                    </div>
                  )}
                  <div className="text-left text-lg font-semibold tracking-tight text-foreground">
                    {nome}
                  </div>
                </div>
              )}
              <h1 className="mt-6 text-2xl font-medium tracking-tight text-foreground">
                Login
              </h1>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
              <div>
                <label htmlFor="email" className="sr-only">
                  E-mail
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  inputMode="email"
                  placeholder="E-mail"
                  required
                  className={CAMPO}
                />
              </div>
              <div>
                <label htmlFor="senha" className="sr-only">
                  Senha
                </label>
                <PasswordInput
                  id="senha"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  autoComplete="current-password"
                  placeholder="Senha"
                  required
                  // `!`: o `rounded-input` do componente vem depois no CSS e venceria.
                  className="!h-12 !rounded-full !px-5"
                />
              </div>

              <div className="flex items-center justify-between gap-3 px-2 text-sm">
                <label className="inline-flex cursor-pointer items-center gap-2 text-foreground-muted">
                  <input
                    type="checkbox"
                    checked={lembrar}
                    onChange={(e) => setLembrar(e.target.checked)}
                    className="peer sr-only"
                  />
                  <ShieldCheck
                    className="h-5 w-5 text-foreground-subtle transition-colors duration-fast peer-checked:text-success peer-focus-visible:ring-2 peer-focus-visible:ring-ring"
                    aria-hidden="true"
                  />
                  Lembrar meu usuário
                </label>
                <button
                  type="button"
                  onClick={() => setAjudaSenha((v) => !v)}
                  aria-expanded={ajudaSenha}
                  className="rounded text-foreground-muted underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Não lembro a senha
                </button>
              </div>

              {ajudaSenha && (
                <p className="rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
                  <strong className="font-medium text-foreground">Servidor:</strong>{" "}
                  peça a redefinição da senha ao administrador do sistema na sua
                  secretaria.
                </p>
              )}

              {error && (
                <div
                  role="alert"
                  className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground"
                >
                  {error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 pt-1">
                <button
                  type="submit"
                  disabled={loading}
                  aria-label="Entrar como servidor"
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-success px-4 text-base font-medium text-success-foreground transition-colors duration-fast hover:bg-success/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Users className="h-5 w-5" aria-hidden="true" />
                  {loading ? "Entrando..." : "Servidor"}
                </button>
                <Link
                  href="/cidadao/login"
                  aria-label="Entrar como solicitante (portal do cidadão)"
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-full border-2 bg-card px-4 text-base font-medium transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  style={{ borderColor: cor, color: cor }}
                >
                  <User className="h-5 w-5" aria-hidden="true" />
                  Solicitante
                </Link>
              </div>

              {DEV && (
                <p className="text-center text-[11px] text-foreground-subtle">
                  Modo dev — credenciais pré-preenchidas
                </p>
              )}
            </form>

            <p className="mt-8 text-center text-sm text-foreground-muted">
              Ainda não tem acesso?{" "}
              <Link
                href="/cidadao/cadastrar"
                className="font-semibold underline-offset-2 hover:underline"
                style={{ color: cor }}
              >
                Crie uma conta
              </Link>
            </p>
          </div>
        </div>

        <p className="pt-8 text-center text-xs text-foreground-subtle">
          Sistema desenvolvido por:{" "}
          <span className="font-semibold tracking-wide text-foreground-muted">APRIMORA</span>
        </p>
      </section>
    </main>
  );
}
