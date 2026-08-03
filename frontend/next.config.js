/** @type {import('next').NextConfig} */

/**
 * Redirects 308 das URLs legadas para o prefixo `/m/<slug>` (F3).
 *
 * `permanent: true` emite **308**, e não 302, porque preserva método e corpo —
 * há caminhos aqui que recebem POST de formulário. O preço é que **navegador
 * guarda 308 em cache de forma agressiva**: um destino errado que chegue a
 * produção não se conserta com redeploy, só com cada usuário limpando o cache.
 * Por isso cada regra é conferida com `curl -I` antes de entrar.
 *
 * Estas regras NÃO expiram. `notificacao.link_url` é registro histórico
 * permanente (spec §7.3): há links de 2026 gravados em e-mail e SMS que
 * continuarão chegando. Remover uma regra aqui mata os links dela.
 *
 * A fonte da verdade é `ROTA_MODULO` em `lib/modulos.ts`; o teste
 * `__tests__/rotas-modulo.test.ts` reprova quem acrescentar prefixo lá sem
 * acrescentar regra aqui.
 */
const redirectsModulo = [
  { source: '/transporte-regulado/:path*', destination: '/m/transporte/:path*', permanent: true },
  { source: '/frotas/:path*', destination: '/m/frota/:path*', permanent: true },
];

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // O gate de correção é o tsc (0 erros). O ESLint nunca foi aplicado no fluxo
  // de dev; não bloquear o build de produção por lint.
  eslint: { ignoreDuringBuilds: true },
  async redirects() {
    return redirectsModulo;
  },
};

module.exports = nextConfig;
