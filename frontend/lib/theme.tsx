"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Theme = "light" | "dark";
export type ThemePreference = Theme | "system";

interface ThemeCtx {
  theme: Theme; // resolvido (light/dark) — segue sistema quando pref="system"
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeCtx | null>(null);

const STORAGE_THEME = "aprimora.theme";

function readPreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const raw = localStorage.getItem(STORAGE_THEME);
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return "system";
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveTheme(pref: ThemePreference): Theme {
  if (pref === "system") return systemPrefersDark() ? "dark" : "light";
  return pref;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPrefState] = useState<ThemePreference>("system");
  const [theme, setThemeState] = useState<Theme>("light");

  // Hidrata do localStorage no mount
  useEffect(() => {
    const p = readPreference();
    setPrefState(p);
    setThemeState(resolveTheme(p));
  }, []);

  // Aplica class no <html>
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.dataset.theme = theme;
    // color-scheme avisa o browser pra inverter scrollbars/inputs nativos
    root.style.colorScheme = theme;
  }, [theme]);

  // Escuta mudança do sistema quando preference=system
  useEffect(() => {
    if (preference !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) =>
      setThemeState(e.matches ? "dark" : "light");
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [preference]);

  const setPreference = useCallback((p: ThemePreference) => {
    setPrefState(p);
    setThemeState(resolveTheme(p));
    try {
      localStorage.setItem(STORAGE_THEME, p);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ theme, preference, setPreference }),
    [theme, preference, setPreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme deve ser usado dentro de <ThemeProvider>");
  return ctx;
}

/**
 * Script inline para o `<head>` que evita FOUC (flash of unstyled content):
 * aplica `dark` class no `<html>` antes do JS carregar.
 * Renderize via `<Script id="theme-init" strategy="beforeInteractive">`.
 */
export const THEME_INIT_SCRIPT = `
(function() {
  try {
    var p = localStorage.getItem("${STORAGE_THEME}") || "system";
    var dark = p === "dark" || (p === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    // O "modo compacto" saiu (2026-11-06): limpa a escolha que ficou guardada.
    localStorage.removeItem("aprimora.density");
    // Sidebar colapsada (UX-03 fatia 3.2): a marca no <html> deixa a Sidebar
    // nascer no estado certo em vez de pintar larga e encolher um frame depois.
    if (localStorage.getItem("aprimora.sidebar.collapsed") === "1") {
      document.documentElement.dataset.sidebarCollapsed = "1";
    }
  } catch (e) {}
})();
`.trim();
