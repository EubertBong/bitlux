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

  // The menu itself is not opened here: any Radix DropdownMenu (theme-related or
  // not) that is opened under jsdom in this suite leaves work pending that stalls
  // the afterEach act() flush for ~15s. Selecting an item calls setTheme(), which
  // is covered above; the open/select/persist path is exercised in a real browser
  // by e2e/ui-polish.mjs.
  it("ThemeToggle reflects the stored mode in its accessible label", () => {
    mockPrefersDark(true)
    const { unmount } = render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(screen.getByTestId("theme-toggle")).toHaveAttribute("aria-label", "Theme: System (dark). Change theme")
    unmount()
    localStorage.setItem(THEME_STORAGE_KEY, "light")
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(screen.getByTestId("theme-toggle")).toHaveAttribute("aria-label", "Theme: Light. Change theme")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })
})
