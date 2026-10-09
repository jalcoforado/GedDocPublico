import "./globals.css";
import "@xyflow/react/dist/style.css";
import type { Metadata } from "next";
import localFont from "next/font/local";

import { BrandingProvider } from "@/lib/branding";
import { TEMA_CORES_INIT_SCRIPT } from "@/lib/tema-cores";
import { THEME_INIT_SCRIPT, ThemeProvider } from "@/lib/theme";

// Fontes self-hosted (woff2 variáveis) — sem dependência de rede no build,
// diferente de next/font/google que falha o build offline.
const fontSans = localFont({
  src: "./fonts/inter.woff2",
  variable: "--font-sans",
  display: "swap",
  weight: "100 900",
});

// Títulos: Montserrat, a fonte do layout de referência (Figma). O corpo segue
// Inter, que é quem lê bem a 13–14px em tabela densa; a display entra onde há
// tamanho para ela ter caráter.
const fontDisplay = localFont({
  src: "./fonts/montserrat.woff2",
  variable: "--font-display",
  display: "swap",
  weight: "100 900",
});

// Fontes de título OPCIONAIS do tema por município (`lib/tema-cores.ts::FONTES`).
// `preload: false`: só o município que escolher uma delas a baixa — o
// `@font-face` fica declarado, e o navegador busca o arquivo quando alguma
// regra passa a usá-lo.
const fontRobotoSlab = localFont({
  src: "./fonts/roboto-slab.woff2",
  variable: "--font-roboto-slab",
  display: "swap",
  weight: "100 900",
  preload: false,
});

const fontNunito = localFont({
  src: "./fonts/nunito.woff2",
  variable: "--font-nunito",
  display: "swap",
  weight: "200 1000",
  preload: false,
});

const fontMono = localFont({
  src: "./fonts/jetbrains-mono.woff2",
  variable: "--font-mono",
  display: "swap",
  weight: "100 800",
});

export const metadata: Metadata = {
  title: "Aprimora",
  description: "Aprimora — gestão de processos",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      className={`${fontSans.variable} ${fontDisplay.variable} ${fontMono.variable} ${fontRobotoSlab.variable} ${fontNunito.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        {/* Depois do script de tema: ele decide claro/escuro, e a paleta do
            município depende do modo. */}
        <script dangerouslySetInnerHTML={{ __html: TEMA_CORES_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <BrandingProvider>{children}</BrandingProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
