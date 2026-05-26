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
export type Density = "comfortable" | "compact";

interface ThemeCtx {
  theme: Theme; // resolvido (light/dark) — segue sistema quando pref="system"
  preference: ThemePreference;
  setPreference: (p: ThemePreference) => void;
  density: Density;
  setDensity: (d: Density) => void;
}

const ThemeContext = createContext<ThemeCtx | null>(null);

const STORAGE_THEME = "aprimora.theme";
const STORAGE_DENSITY = "aprimora.density";

function readPreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const raw = localStorage.getItem(STORAGE_THEME);
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return "system";
}

function readDensity(): Density {
  if (typeof window === "undefined") return "comfortable";
  const raw = localStorage.getItem(STORAGE_DENSITY);
  return raw === "compact" ? "compact" : "comfortable";
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
  const [density, setDensityState] = useState<Density>("comfortable");
  const [theme, setThemeState] = useState<Theme>("light");

  // Hidrata do localStorage no mount
  useEffect(() => {
    const p = readPreference();
    const d = readDensity();
    setPrefState(p);
    setDensityState(d);
    setThemeState(resolveTheme(p));
  }, []);

  // Aplica class no <html>
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.dataset.theme = theme;
    root.dataset.density = density;
    // color-scheme avisa o browser pra inverter scrollbars/inputs nativos
    root.style.colorScheme = theme;
  }, [theme, density]);

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

  const setDensity = useCallback((d: Density) => {
    setDensityState(d);
    try {
      localStorage.setItem(STORAGE_DENSITY, d);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ theme, preference, setPreference, density, setDensity }),
    [theme, preference, setPreference, density, setDensity],
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
    var d = localStorage.getItem("${STORAGE_DENSITY}") || "comfortable";
    var dark = p === "dark" || (p === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.dataset.density = d;
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
  } catch (e) {}
})();
`.trim();
