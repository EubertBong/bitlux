/**
 * Navigation + affordance verification in a real browser, and the review
 * screenshots. Writes docs/screenshots/nav-*.png.
 */
import { chromium } from "playwright"
import { mkdirSync } from "node:fs"
import path from "node:path"

const BASE = process.env.FRONTEND_URL ?? "http://localhost:5173"
const OUT = path.resolve(process.cwd(), "../docs/screenshots")
mkdirSync(OUT, { recursive: true })
let failures = 0
const check = (name, ok, detail = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`); if (!ok) failures++ }

const browser = await chromium.launch({ channel: "chrome", headless: true, ignoreDefaultArgs: ["--hide-scrollbars"] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const errors = []
page.on("pageerror", (e) => errors.push(e.message))
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()) })
const settle = (ms) => page.waitForTimeout(ms)
const cursorAt = (sel) => page.evaluate((s) => getComputedStyle(document.querySelector(s)).cursor, sel)

await page.goto(`${BASE}/login`)
await page.getByLabel("Email").fill("owner@demo.test")
await page.getByLabel("Password").fill("Demo!2026")
await page.getByRole("button", { name: "Sign in" }).click()
await page.waitForURL(`${BASE}/`)

// ---- 1. Dashboard: KPI tiles are links, with a hover state -----------------
await page.waitForSelector("[data-testid=kpi]")
const tiles = await page.locator("a[data-clickable-card]").count()
check("dashboard: KPI tiles are links", tiles >= 5, `${tiles} tiles`)
check("KPI tile cursor is pointer", (await cursorAt("a[data-clickable-card]")) === "pointer")
const before = await page.locator("a[data-clickable-card]").first().evaluate((el) => getComputedStyle(el).boxShadow)
await page.locator("a[data-clickable-card]").first().hover()
await settle(400)
const after = await page.locator("a[data-clickable-card]").first().evaluate((el) => getComputedStyle(el).boxShadow)
check("KPI tile has a visible hover state", before !== after, `${before} -> ${after}`)
await page.screenshot({ path: path.join(OUT, "nav-dashboard-kpi-hover.png") })

// Each tile navigates where it says.
for (const [label, expected] of [["Active clients", "/clients"], ["Contacts", "/contacts"], ["Documents expiring", "/documents?expiring=30"], ["Tasks due", "/tasks?assigned=me"]]) {
  const href = await page.locator(`a[data-clickable-card][aria-label^="${label}"]`).getAttribute("href")
  check(`KPI "${label}" links to ${expected}`, href === expected, href ?? "(missing)")
}

// ---- 2. Deep-linked views actually filter ----------------------------------
await page.goto(`${BASE}/documents?expiring=30`)
await page.waitForSelector("[data-testid=view-chip]")
check("/documents?expiring=30 shows a removable view chip", (await page.getByTestId("view-chip").innerText()).includes("Expiring within 30 days"))
await page.goto(`${BASE}/tasks?assigned=me`)
await page.waitForSelector("[data-testid=view-chip]")
check("/tasks?assigned=me shows a removable view chip", (await page.getByTestId("view-chip").innerText()).includes("Assigned to me"))

// ---- 3. Sidebar: active state + pointer ------------------------------------
await page.goto(`${BASE}/trips`)
await page.waitForSelector("[data-testid=table-row]")
const active = await page.locator("nav[aria-label=Primary] a[aria-current=page]").innerText()
check("sidebar marks the current section active", active.trim() === "Trips", active.trim())
check("sidebar link cursor is pointer", (await cursorAt("nav[aria-label=Primary] a")) === "pointer")
await page.screenshot({ path: path.join(OUT, "nav-sidebar-active.png"), clip: { x: 0, y: 0, width: 520, height: 900 } })

// ---- 4. Table primary column is a link -------------------------------------
const firstCell = page.locator("[data-testid=table-row]").first().locator("a[href^='/trips/']").first()
check("table primary column is a link", (await firstCell.count()) === 1)
check("table link cursor is pointer", (await firstCell.evaluate((el) => getComputedStyle(el).cursor)) === "pointer")
await firstCell.hover()
await settle(300)
await page.screenshot({ path: path.join(OUT, "nav-table-links.png") })
const tripHref = await firstCell.getAttribute("href")

// ---- 5. Detail: explicit Back, tab deep link, tab survives refresh ---------
await page.goto(`${BASE}${tripHref}`)
await page.waitForSelector("[data-testid=back-link]")
check("detail Back is a real link to the list", (await page.getByTestId("back-link").getAttribute("href")) === "/trips")
check("detail Back names the parent", (await page.getByTestId("back-link").innerText()).includes("Back to Trips"))
await page.goto(`${BASE}${tripHref}?tab=relationship`)
await page.waitForSelector("[data-testid=relationship-graph]")
check("deep link opens the right tab", (await page.locator("[data-testid=tab-relationship]").getAttribute("data-state")) === "active")
await page.reload()
await page.waitForSelector("[data-testid=relationship-graph]")
check("tab survives a refresh", (await page.locator("[data-testid=tab-relationship]").getAttribute("data-state")) === "active")

// ---- 6. Graph: node and edge navigation ------------------------------------
await page.waitForFunction(() => document.querySelectorAll("[data-node]").length > 2, null, { timeout: 15000 })
await settle(2500)
check("graph node cursor is pointer", (await cursorAt("[data-node]")) === "pointer")
check("graph edge is clickable and has a pointer", (await page.locator("[data-edge-clickable]").count()) > 0 && (await cursorAt("[data-edge-clickable]")) === "pointer")
await page.locator("[data-edge-clickable]").first().click()
await page.waitForFunction((from) => location.pathname !== from, tripHref, { timeout: 5000 }).catch(() => {})
check("clicking an edge navigates to the target record", page.url() !== `${BASE}${tripHref}?tab=relationship`, page.url().replace(BASE, ""))

// ---- 7. Search results navigate --------------------------------------------
await page.goto(`${BASE}/`)
await page.locator('button[aria-label^="Search"]').click()
await page.waitForSelector("[aria-label='Search query']", { timeout: 10000 })
await page.locator("[aria-label='Search query']").fill("gulf")
await page.waitForSelector("[cmdk-item]")
const firstHit = page.locator("[cmdk-item]").first()
await firstHit.click()
await page.waitForFunction(() => location.pathname !== "/", null, { timeout: 5000 })
check("⌘K result navigates to a detail page", /\/(aircraft|aircraft-models|manufacturers|contacts|trips|quotes|documents|passengers|operators|airports)\/[0-9a-f-]{36}/.test(page.url()), page.url().replace(BASE, ""))

// ---- 8. User menu ----------------------------------------------------------
await page.goto(`${BASE}/`)
await page.getByRole("button", { name: "User menu" }).click()
await page.getByTestId("menu-profile").click()
await page.waitForURL(`${BASE}/settings/profile`)
await page.waitForSelector("[data-testid=profile-details]")
check("user menu: Profile opens the profile page", (await page.locator("h1").innerText()).trim() === "Profile", (await page.locator("h1").innerText()).trim())
await page.getByRole("button", { name: "User menu" }).click()
await page.getByTestId("menu-admin").click()
await page.waitForURL(`${BASE}/admin/users`)
check("user menu: Admin opens the user admin", (await page.locator("h1").innerText()) === "Users")

// ---- 9. Nothing claims to be clickable without being operable --------------
await page.goto(`${BASE}/contacts`)
await page.waitForSelector("[data-testid=table-row]")
const offenders = await page.evaluate(() =>
  [...document.querySelectorAll("body *")]
    .filter((el) => getComputedStyle(el).cursor === "pointer")
    // `cursor` inherits, so a <span> inside a <button> reports pointer too. Only
    // flag elements with no operable ancestor -- those are the real offenders.
    .filter((el) => !el.closest('button, a[href], summary, [role="button"][tabindex], [data-clickable], [data-clickable-card], label[for]'))
    .filter((el) => !(el.tagName === "INPUT" && el.type === "checkbox"))
    .map((el) => `${el.tagName.toLowerCase()}.${String(el.className || "").split(" ")[0]}`)
    .slice(0, 8),
)
check("no pointer cursor on inoperable elements", offenders.length === 0, offenders.join(", "))

check("no console/page errors", errors.length === 0, errors.slice(0, 3).join(" | "))
await browser.close()
console.log(failures ? `\n${failures} check(s) FAILED` : "\nall checks passed")
process.exit(failures ? 1 : 0)
