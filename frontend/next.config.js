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
  { source: '/pagamentos/:path*', destination: '/m/pagamentos/:path*', permanent: true },
  // administracao: 7 diretorios de topo, uma regra cada.
  { source: '/usuarios/:path*', destination: '/m/administracao/usuarios/:path*', permanent: true },
  { source: '/grupos/:path*', destination: '/m/administracao/grupos/:path*', permanent: true },
  { source: '/unidades-trabalho/:path*', destination: '/m/administracao/unidades-trabalho/:path*', permanent: true },
  { source: '/organograma/:path*', destination: '/m/administracao/organograma/:path*', permanent: true },
  { source: '/auditoria/:path*', destination: '/m/administracao/auditoria/:path*', permanent: true },
  { source: '/configuracoes/:path*', destination: '/m/administracao/configuracoes/:path*', permanent: true },
  { source: '/jobs/:path*', destination: '/m/administracao/jobs/:path*', permanent: true },
  // protocolo: 14 diretorios de topo.
  { source: '/processos/:path*', destination: '/m/protocolo/processos/:path*', permanent: true },
  { source: '/protocolo/:path*', destination: '/m/protocolo/protocolo/:path*', permanent: true },
  { source: '/workflow/:path*', destination: '/m/protocolo/workflow/:path*', permanent: true },
  { source: '/relatorios/:path*', destination: '/m/protocolo/relatorios/:path*', permanent: true },
  { source: '/servicos/:path*', destination: '/m/protocolo/servicos/:path*', permanent: true },
  { source: '/manifestantes/:path*', destination: '/m/protocolo/manifestantes/:path*', permanent: true },
  { source: '/tipos-manifestante/:path*', destination: '/m/protocolo/tipos-manifestante/:path*', permanent: true },
  { source: '/tipos-processo/:path*', destination: '/m/protocolo/tipos-processo/:path*', permanent: true },
  { source: '/tipos-anexo/:path*', destination: '/m/protocolo/tipos-anexo/:path*', permanent: true },
  { source: '/assuntos/:path*', destination: '/m/protocolo/assuntos/:path*', permanent: true },
  { source: '/templates-documento/:path*', destination: '/m/protocolo/templates-documento/:path*', permanent: true },
  { source: '/cidades/:path*', destination: '/m/protocolo/cidades/:path*', permanent: true },
  { source: '/bairros/:path*', destination: '/m/protocolo/bairros/:path*', permanent: true },
  { source: '/enderecos/:path*', destination: '/m/protocolo/enderecos/:path*', permanent: true },
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
