/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // O gate de correção é o tsc (0 erros). O ESLint nunca foi aplicado no fluxo
  // de dev; não bloquear o build de produção por lint.
  eslint: { ignoreDuringBuilds: true },
};

module.exports = nextConfig;
