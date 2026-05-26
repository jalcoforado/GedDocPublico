import "./globals.css";
import "@xyflow/react/dist/style.css";
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { BrandingProvider } from "@/lib/branding";
import { THEME_INIT_SCRIPT, ThemeProvider } from "@/lib/theme";

const fontSans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
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
