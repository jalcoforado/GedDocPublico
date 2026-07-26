import "./globals.css";
import "@xyflow/react/dist/style.css";
import type { Metadata } from "next";
import localFont from "next/font/local";

import { BrandingProvider } from "@/lib/branding";
import { THEME_INIT_SCRIPT, ThemeProvider } from "@/lib/theme";

// Fontes self-hosted (woff2 variáveis) — sem dependência de rede no build,
// diferente de next/font/google que falha o build offline.
const fontSans = localFont({
  src: "./fonts/inter.woff2",
  variable: "--font-sans",
  display: "swap",
  weight: "100 900",
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
    <html lang="pt-BR" className={`${fontSans.variable} ${fontMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <BrandingProvider>{children}</BrandingProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
