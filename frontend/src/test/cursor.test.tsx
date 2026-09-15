/**
 * Affordance test: everything clickable shows a hand cursor, everything disabled
 * shows not-allowed, and nothing decorative claims to be clickable.
 *
 * jsdom has no Tailwind, so utility classes resolve to nothing. The rules under
 * test therefore live in src/styles/interactive.css as plain CSS, and this file
 * loads that exact file — a failing selector here is a failing selector in the app.
 */

import { readFileSync } from "node:fs"
import path from "node:path"
import { render, screen, within } from "@testing-library/react"
import { beforeAll, describe, expect, it, vi } from "vitest"
import { Button } from "@/components/ui/button"
import { DashboardPage } from "@/pages/DashboardPage"
import { RelationshipGraph } from "@/components/RelationshipGraph"
import { NAV_GROUPS } from "@/components/layout/nav"
import { api } from "@/lib/api"
import { MOCK_GRAPH, renderWithProviders } from "./utils"
import { AppShell } from "@/components/layout/AppShell"

const CSS_PATH = path.resolve(__dirname, "../styles/interactive.css")

beforeAll(() => {
  const style = document.createElement("style")
  style.textContent = readFileSync(CSS_PATH, "utf8")
  document.head.appendChild(style)
})

const cursorOf = (el: Element) => window.getComputedStyle(el).cursor

describe("the shipped stylesheet", () => {
  it("covers buttons, links, roles and disabled states", () => {
    render(
      <div>
        <button data-testid="btn">go</button>
        <button disabled data-testid="btn-disabled">go</button>
        <a href="/x" data-testid="anchor">go</a>
        <a data-testid="anchor-no-href">not a link</a>
        <div role="button" tabIndex={0} data-testid="role-btn">go</div>
        <div role="button" aria-disabled="true" data-testid="role-btn-disabled">go</div>
        <span data-testid="text">just text</span>
        <span aria-current="page" data-testid="current-crumb">Current page</span>
      </div>,
    )
    expect(cursorOf(screen.getByTestId("btn"))).toBe("pointer")
    expect(cursorOf(screen.getByTestId("btn-disabled"))).toBe("not-allowed")
    expect(cursorOf(screen.getByTestId("anchor"))).toBe("pointer")
    expect(cursorOf(screen.getByTestId("role-btn"))).toBe("pointer")
    expect(cursorOf(screen.getByTestId("role-btn-disabled"))).toBe("not-allowed")
    // Decorative things must not claim to be clickable.
    expect(cursorOf(screen.getByTestId("anchor-no-href"))).not.toBe("pointer")
    expect(cursorOf(screen.getByTestId("text"))).not.toBe("pointer")
    expect(cursorOf(screen.getByTestId("current-crumb"))).toBe("default")
  })

  it("a disabled Button still reports not-allowed through the component layer", () => {
    render(<Button disabled data-testid="ui-btn">Planned</Button>)
    expect(cursorOf(screen.getByTestId("ui-btn"))).toBe("not-allowed")
  })
})

describe("sidebar", () => {
  it("every nav item is a link with a pointer; group labels are not", () => {
    renderWithProviders(<AppShell />, { route: "/contacts", path: "*" })
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0]!
    for (const item of NAV_GROUPS.flatMap((g) => g.items)) {
      const link = within(nav).queryByRole("link", { name: item.label })
      if (!link) continue // hidden for this role
      expect(cursorOf(link)).toBe("pointer")
    }
    for (const g of NAV_GROUPS) {
      const label = within(nav).queryByText(g.label.toUpperCase(), { exact: false, selector: "div" })
      if (label) expect(cursorOf(label)).not.toBe("pointer")
    }
  })
})

describe("dashboard KPI tiles", () => {
  it("are whole-card links with a pointer and a hover rule", () => {
    vi.spyOn(api, "get").mockImplementation(async (p: string) => {
      if (p.startsWith("/invoices/ar-aging")) return { as_of: "2026-09-15", buckets: {} }
      if (p.startsWith("/tasks/my-queue") || p.startsWith("/documents/expiring")) return []
      return { items: [], total: 3, page: 1, page_size: 25 }
    })
    renderWithProviders(<DashboardPage />, { route: "/", path: "/" })
    const tiles = screen.getAllByTestId("kpi")
    expect(tiles.length).toBeGreaterThan(0)
    for (const tile of tiles) {
      const link = tile.closest("a[data-clickable-card]")
      expect(link, `KPI "${tile.textContent}" should be a link`).not.toBeNull()
      expect(cursorOf(link!)).toBe("pointer")
      expect(link).toHaveAttribute("href")
    }
  })
})

describe("relationship graph", () => {
  it("nodes and edges are keyboard-reachable buttons with a pointer", async () => {
    vi.spyOn(api, "get").mockResolvedValue(MOCK_GRAPH)
    const { container } = renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" />, { route: "/clients/n-client", path: "*" })
    const node = await screen.findByLabelText(/Client: Demo Brokerage/)
    expect(cursorOf(node)).toBe("pointer")
    expect(node).toHaveAttribute("tabindex", "0")
    expect(node).toHaveAttribute("role", "button")

    const edge = container.querySelector("[data-edge-clickable]")!
    expect(edge).not.toBeNull()
    expect(cursorOf(edge)).toBe("pointer")
    expect(edge).toHaveAttribute("tabindex", "0")
    expect(edge).toHaveAttribute("role", "button")
  })
})

describe("no element claims to be clickable without being operable", () => {
  it("every pointer-cursor element in the shell is a button, a link, or has a role and tabindex", () => {
    const { container } = renderWithProviders(<AppShell />, { route: "/contacts", path: "*" })
    // `cursor` is inherited, so judge only elements with no operable ancestor.
    const OPERABLE = 'button, a[href], summary, [role="button"][tabindex], [data-clickable], [data-clickable-card], label[for]'
    const offenders: string[] = []
    for (const el of container.querySelectorAll("*")) {
      if (cursorOf(el) !== "pointer") continue
      if (el.closest(OPERABLE)) continue
      offenders.push(`${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).split(" ")[0]}` : ""}`)
    }
    expect(offenders).toEqual([])
  })
})
