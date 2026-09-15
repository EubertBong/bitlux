import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from "@/lib/theme"

function mockPrefersDark(matches: boolean) {
  const listeners = new Set<() => void>()
  const mql = {
    matches,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_: string, fn: () => void) => listeners.add(fn),
    removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }
  vi.spyOn(window, "matchMedia").mockImplementation(() => mql as unknown as MediaQueryList)
  return { setMatches: (m: boolean) => { mql.matches = m; listeners.forEach((fn) => fn()) } }
}

function Probe() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}/{resolvedTheme}</span>
      <button onClick={() => setTheme("dark")}>go dark</button>
      <button onClick={() => setTheme("light")}>go light</button>
      <button onClick={() => setTheme("system")}>go system</button>
    </div>
  )
}

describe("theme", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove("dark")
  })
  afterEach(() => localStorage.clear())

  it("defaults to system, follows the OS preference, and does not write until the user chooses", () => {
    const os = mockPrefersDark(true)
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId("theme")).toHaveTextContent("system/dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
    act(() => os.setMatches(false))
    expect(screen.getByTestId("theme")).toHaveTextContent("system/light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("persists an explicit choice under bitlux-theme and applies the class on <html>", async () => {
    mockPrefersDark(false)
    const user = userEvent.setup()
    render(<ThemeProvider><Probe /></ThemeProvider>)
    await user.click(screen.getByText("go dark"))
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe("dark")
    await user.click(screen.getByText("go light"))
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("reads the stored choice on mount (a reload keeps the theme)", () => {
    mockPrefersDark(false)
    localStorage.setItem(THEME_STORAGE_KEY, "dark")
    render(<ThemeProvider><Probe /></ThemeProvider>)
    expect(screen.getByTestId("theme")).toHaveTextContent("dark/dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("ThemeToggle switches via the menu and announces the change", async () => {
    mockPrefersDark(false)
    const user = userEvent.setup()
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    const btn = screen.getByTestId("theme-toggle")
    expect(btn).toHaveAttribute("aria-label", "Theme: System (light). Change theme")
    await user.click(btn)
    await user.click(await screen.findByTestId("theme-dark"))
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(screen.getByTestId("theme-toggle")).toHaveAttribute("aria-label", "Theme: Dark. Change theme")
    expect(screen.getByRole("status")).toHaveTextContent("Theme set to Dark")
  })
})
