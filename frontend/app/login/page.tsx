"use client";

import { ArrowRight, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { api } from "@/lib/api";
import { useBranding } from "@/lib/branding";

const DEV = process.env.NODE_ENV !== "production";

export default function LoginPage() {
  const router = useRouter();
  const branding = useBranding();
  const [email, setEmail] = useState(DEV ? "admin@local.test" : "");
  const [senha, setSenha] = useState(DEV ? "admin123" : "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // SEC-1 Commit 6 — otimização: redireciona direto para a tela de
      // troca quando o backend já sinaliza must_change_password no login.
      // Evita o salto extra por /home (onde o AuthProvider faria o redirect
      // como defesa em profundidade — que permanece intacto).
      const r = await api.login(email, senha);
      router.push(
        r.must_change_password ? "/alterar-senha-obrigatoria" : "/home",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao autenticar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-2">
      {/* === Hero (esquerda) — só desktop === */}
      <aside
        className="
          relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex
        "
        style={{
          background: branding?.cor_primaria
            ? `linear-gradient(135deg, ${branding.cor_primaria} 0%, ${branding.cor_primaria}dd 50%, hsl(var(--accent)) 200%)`
            : "linear-gradient(135deg, hsl(var(--brand)) 0%, hsl(var(--brand-light)) 60%, hsl(var(--accent)) 200%)",
        }}
      >
        {/* Dot grid decorativo */}
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "radial-gradient(white 1.5px, transparent 1.5px)",
            backgroundSize: "24px 24px",
          }}
          aria-hidden="true"
        />
        {/* Glow round decorativo */}
        <div
          className="absolute -right-32 -top-32 h-96 w-96 rounded-full opacity-25 blur-3xl"
          style={{ background: "hsl(var(--accent))" }}
          aria-hidden="true"
        />

        {/* Brand mark */}
        <div className="relative z-10 flex items-center gap-3">
          {branding?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={branding.logo_url}
              alt={branding.nome}
              className="h-12 w-12 rounded-lg object-cover ring-1 ring-white/20"
            />
          ) : (
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-lg bg-white/10 backdrop-blur ring-1 ring-white/20">
              <span className="text-lg font-bold tracking-tight">A</span>
            </div>
          )}
          <div>
            <div className="text-sm font-semibold tracking-tight">
              {branding?.nome ?? "Aprimora"}
            </div>
            <div className="text-[11px] uppercase tracking-wider opacity-70">
              Plataforma de Gestão
            </div>
          </div>
        </div>

        {/* Tagline */}
        <div className="relative z-10 max-w-md space-y-6">
          <h1 className="text-4xl font-bold leading-tight tracking-tight">
            Processos administrativos,{" "}
            <span className="text-accent-light">com fluidez de software moderno.</span>
          </h1>
          <p className="text-base leading-relaxed opacity-80">
            Workflow visual, SLA por etapa, notificações multi-canal e
            auditoria completa — feito sob medida para prefeituras.
          </p>

          {/* Pills com features-chave */}
          <ul className="flex flex-wrap gap-2 pt-2">
            {[
              { icon: Zap, label: "Workflow visual" },
              { icon: ShieldCheck, label: "Auditoria completa" },
              { icon: Sparkles, label: "BI executivo" },
            ].map(({ icon: Icon, label }) => (
              <li
                key={label}
                className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium backdrop-blur ring-1 ring-white/15"
              >
                <Icon className="h-3 w-3" aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
        </div>

        {/* Footer credit */}
        <div className="relative z-10 text-[10px] uppercase tracking-wider opacity-50">
          © {new Date().getFullYear()} Aprimora — todos os direitos reservados
        </div>
      </aside>

      {/* === Form (direita) === */}
      <section className="flex items-center justify-center bg-background p-6 sm:p-12">
        <div className="w-full max-w-sm">
          {/* Brand mark mobile-only */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            {branding?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={branding.logo_url}
                alt={branding.nome}
                className="h-11 w-11 rounded-lg object-cover"
              />
            ) : (
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-brand-gradient text-base font-bold text-white shadow-brand">
                A
              </div>
            )}
            <div>
              <div className="text-base font-semibold tracking-tight">
                {branding?.nome ?? "Aprimora"}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-foreground-subtle">
                Gestão de processos
              </div>
            </div>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            Bem-vindo de volta
          </h2>
          <p className="mt-1 text-sm text-foreground-muted">
            Entre com seu acesso institucional pra continuar.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
            <div>
              <Label htmlFor="email" required>
                E-mail
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                inputMode="email"
                placeholder="seu.nome@prefeitura.gov.br"
                required
              />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="senha" required>
                  Senha
                </Label>
                {/* Slot pra "Esqueci minha senha" futuro */}
                {/* <Link className="text-xs text-brand hover:underline" href="/recuperar-senha">
                  Esqueci minha senha
                </Link> */}
              </div>
              <PasswordInput
                id="senha"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              size="lg"
              className="w-full justify-center gap-2"
            >
              {loading ? (
                "Entrando..."
              ) : (
                <>
                  Entrar
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </>
              )}
            </Button>

            {DEV && (
              <p className="text-center text-[11px] text-foreground-subtle">
                Modo dev — credenciais pré-preenchidas
              </p>
            )}
          </form>

          <p className="mt-8 text-center text-[11px] text-foreground-subtle">
            Acesso seguro com auditoria de ações. Em caso de problemas, contate a
            TI da prefeitura.
          </p>
        </div>
      </section>
    </main>
  );
}
