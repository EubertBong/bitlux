import { describe, expect, it } from "vitest"
import { visibleGroups } from "@/components/layout/nav"
import { hasPermission } from "@/lib/auth"
import { initials, money } from "@/lib/format"

describe("navigation gating", () => {
  it("hides items and empty groups the user lacks permission for", () => {
    const perms = new Set(["trips.view", "tasks.view"])
    const groups = visibleGroups((k) => hasPermission(perms, k))
    expect(groups.map((g) => g.label)).toEqual(["CRM", "Trips", "Commerce"]) // Dashboard is public; Fleet/Admin vanish
    expect(groups.find((g) => g.label === "Commerce")?.items.map((i) => i.label)).toEqual(["Tasks"])
  })
})

describe("format helpers", () => {
  it("formats integer cents as currency", () => {
    expect(money(4_419_000)).toBe("$44,190.00")
    expect(money(354_000_000, "EUR")).toBe("€3,540,000.00")
    expect(money(null)).toBe("—")
  })
  it("builds initials", () => {
    expect(initials("Ben Carter")).toBe("BC")
    expect(initials("Cher")).toBe("C")
  })
})
