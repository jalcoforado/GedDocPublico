"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { CommandPaletteProvider } from "@/components/CommandPalette";
import { Header } from "@/components/Header";
import { LoadingBar } from "@/components/LoadingBar";
import { Sidebar } from "@/components/Sidebar";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Providers } from "@/lib/providers";

function Shell({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-foreground-muted">
        Carregando...
      </div>
    );
  }
  if (!user) return null;
  return (
    <div className="flex h-dvh bg-background">
      <LoadingBar />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onOpenSidebar={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div key={pathname} className="animate-page-in motion-reduce:animate-none">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AuthProvider>
        <CommandPaletteProvider>
          <Shell>{children}</Shell>
        </CommandPaletteProvider>
      </AuthProvider>
    </Providers>
  );
}
