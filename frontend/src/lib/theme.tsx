/**
 * Light / dark / system theme.
 *
 * The choice lives in localStorage under "bitlux-theme" (never a token -- see
 * lib/api.ts for what does not go there), defaults to "system", and is applied
 * as the `dark` class on <html> plus `color-scheme`, which is all the CSS
 * variables in index.css need. index.html applies the same rule inline before
 * first paint so there is no flash; this provider takes over from there and
 * follows the OS while in "system" mode.
 */

import * as React from "react"

export type Theme = "light" | "dark" | "system"
export type ResolvedTheme = "light" | "dark"

export const THEME_STORAGE_KEY = "bitlux-theme"
export const THEMES: readonly Theme[] = ["light", "dark", "system"]
const MEDIA = "(prefers-color-scheme: dark)"

export function isTheme(v: unknown): v is Theme {
  return v === "light" || v === "dark" || v === "system"
}

export function readStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY)
    return isTheme(v) ? v : "system"
  } catch {
    return "system"
  }
}

export function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(MEDIA).matches
}

export function resolveTheme(theme: Theme): ResolvedTheme {
  return theme === "system" ? (systemPrefersDark() ? "dark" : "light") : theme
}

/** Put the theme on <html>. Returns what was actually applied. */
export function applyTheme(theme: Theme): ResolvedTheme {
  const resolved = resolveTheme(theme)
  const el = document.documentElement
  el.classList.toggle("dark", resolved === "dark")
  el.style.colorScheme = resolved
  el.dataset.theme = theme
  return resolved
}

export interface ThemeContextValue {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
  /** light -> dark -> system -> light */
  cycleTheme: () => void
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children, defaultTheme }: { children: React.ReactNode; defaultTheme?: Theme }) {
  const [theme, setThemeState] = React.useState<Theme>(() => defaultTheme ?? readStoredTheme())
  const [resolvedTheme, setResolved] = React.useState<ResolvedTheme>(() => resolveTheme(theme))

  React.useEffect(() => {
    setResolved(applyTheme(theme))
    if (theme !== "system" || typeof window.matchMedia !== "function") return
    const mql = window.matchMedia(MEDIA)
    const onChange = () => setResolved(applyTheme("system"))
    mql.addEventListener?.("change", onChange)
    return () => mql.removeEventListener?.("change", onChange)
  }, [theme])

  const setTheme = React.useCallback((next: Theme) => {
    setThemeState(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      /* private mode etc.: the choice just does not persist */
    }
  }, [])

  const cycleTheme = React.useCallback(() => {
    setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length] ?? "system")
  }, [theme, setTheme])

  const value = React.useMemo<ThemeContextValue>(() => ({ theme, resolvedTheme, setTheme, cycleTheme }), [theme, resolvedTheme, setTheme, cycleTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = React.useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>")
  return ctx
}
