"use client";

import { ArrowRight, Lock, Mail, ShieldCheck, User } from "lucide-react";
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
  "flex h-12 w-full rounded-full border border-input bg-card pl-12 pr-5 text-base text-foreground shadow-input transition-colors duration-fast placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const ICONE_DO_CAMPO =
  "pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground-subtle";

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
  // Tinta do painel da cidade: a cor de destaque do município, senão a
  // primária, senão a marca. Vai por `style` porque vem do banco — não há
  // classe do Tailwind para um valor só conhecido em runtime.
  const tinta = branding?.cor_destaque ?? branding?.cor_primaria ?? "hsl(var(--brand))";

  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      {/* === Painel da cidade (esquerda) — só desktop ===
          Empilhamento pela ORDEM do DOM (foto → véus → anéis → texto), sem
          z-index local: cada camada posicionada cobre a anterior. */}
      <aside
        className="relative hidden overflow-hidden text-white lg:flex lg:flex-col lg:justify-between"
        style={{ backgroundColor: tinta }}
      >
        {branding?.imagem_login_url ? (
          // Duotone na cor do município: a foto em tons de cinza é
          // multiplicada pela cor de fundo (claros viram a cor, escuros ficam
          // escuros).
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={branding.imagem_login_url}
            alt=""
            className="absolute inset-0 h-full w-full object-cover opacity-90 mix-blend-multiply grayscale"
          />
        ) : null}
        {/* Véus: escurece a base, onde o texto assenta, e abre o topo. */}
        <div
          className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-white/10"
          aria-hidden="true"
        />
        {/* Anéis concêntricos — assinatura gráfica discreta no canto. */}
        <div
          className="absolute -right-40 -top-40 h-[34rem] w-[34rem] rounded-full border border-white/15"
          aria-hidden="true"
        />
        <div
          className="absolute -right-24 -top-24 h-[22rem] w-[22rem] rounded-full border border-white/10"
          aria-hidden="true"
        />

        <div className="relative p-10 xl:p-14">
          <div className="inline-flex items-center gap-3 rounded-full border border-white/20 bg-white/10 py-2 pl-2 pr-5 backdrop-blur-md">
            {branding?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={branding.logo_url}
                alt=""
                className="h-9 w-9 rounded-full bg-white object-contain p-0.5"
              />
            ) : (
              <span
                className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/20 font-display text-sm font-bold"
                aria-hidden="true"
              >
                A
              </span>
            )}
            <span className="text-sm font-medium tracking-tight">{nome}</span>
          </div>
        </div>

        <div className="relative p-10 xl:p-14">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-white/75">
            Gestão pública digital
          </p>
          <h2 className="mt-4 max-w-lg text-4xl font-semibold leading-[1.1] xl:text-5xl">
            Serviços e processos do município em um só lugar.
          </h2>
          <span className="mt-6 block h-px w-16 bg-white/50" aria-hidden="true" />
          <p className="mt-6 max-w-md text-base leading-relaxed text-white/85">
            Protocolo, frota, transporte regulado e pagamentos, com tramitação
            rastreável e assinatura eletrônica.
          </p>
          {branding?.imagem_login_credito ? (
            // Atribuição exigida pela licença da foto: fica legível, não
            // escondida de leitor de tela.
            <p className="mt-10 text-[11px] text-white/65">{branding.imagem_login_credito}</p>
          ) : null}
        </div>
      </aside>

      {/* === Formulário (direita) === */}
      <section className="relative flex flex-col overflow-hidden bg-background p-6 sm:p-12">
        {/* Luz ambiente na cor da marca — tira o fundo do branco chapado. */}
        <div
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand/10 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-accent/10 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm motion-safe:animate-slide-up">
            <div className="flex flex-col items-center text-center">
              {branding?.logo_login_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={branding.logo_login_url}
                  alt={nome}
                  className="max-h-28 w-auto max-w-full object-contain"
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
                    <div className="inline-flex h-14 w-14 items-center justify-center rounded-lg bg-brand-gradient font-display text-xl font-bold text-white shadow-brand">
                      A
                    </div>
                  )}
                  <div className="text-left font-display text-lg font-semibold tracking-tight text-foreground">
                    {nome}
                  </div>
                </div>
              )}
              <h1 className="mt-8 text-3xl font-semibold text-foreground">Acesse sua conta</h1>
              <p className="mt-2 text-md text-foreground-muted">
                Entre com seu e-mail institucional e sua senha.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
              <div className="relative">
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
                <Mail className={ICONE_DO_CAMPO} aria-hidden="true" />
              </div>
              <div className="relative">
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
                  // `!`: as classes de raio/altura/padding do componente vêm
                  // depois no CSS e venceriam.
                  className="!h-12 !rounded-full !pl-12"
                />
                <Lock className={ICONE_DO_CAMPO} aria-hidden="true" />
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

              <button
                type="submit"
                disabled={loading}
                aria-label="Entrar como servidor"
                className="group inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-brand px-4 text-base font-semibold text-primary-foreground shadow-brand transition-all duration-fast hover:bg-brand-dark hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Entrando..." : "Entrar como servidor"}
                <ArrowRight
                  className="h-5 w-5 transition-transform duration-fast group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </button>

              <div className="flex items-center gap-3 py-1" aria-hidden="true">
                <span className="h-px flex-1 bg-border" />
                <span className="text-xs uppercase tracking-widest text-foreground-subtle">ou</span>
                <span className="h-px flex-1 bg-border" />
              </div>

              <Link
                href="/cidadao/login"
                aria-label="Acessar como solicitante (portal do cidadão)"
                className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border border-accent bg-card px-4 text-base font-semibold text-accent-dark transition-colors duration-fast hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <User className="h-5 w-5" aria-hidden="true" />
                Sou solicitante
              </Link>

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
                className="font-semibold text-accent-dark underline-offset-2 hover:underline"
              >
                Crie uma conta
              </Link>
            </p>
          </div>
        </div>

        <p className="relative pt-8 text-center text-xs text-foreground-subtle">
          Sistema desenvolvido por{" "}
          <span className="font-display font-bold tracking-[0.18em] text-foreground-muted">
            APRIMORA
          </span>
        </p>
      </section>
    </main>
  );
}
