/**
 * Drives the running app (vite on :5173, API on :8000) with the system Chrome
 * and writes the screenshots the sprint review asks for to docs/screenshots/.
 *
 *   node e2e/screenshots.mjs            # after `make api` and `npm run dev`
 */
import { chromium } from "playwright"
import { mkdirSync } from "node:fs"
import path from "node:path"

const BASE = process.env.FRONTEND_URL ?? "http://localhost:5173"
const DEMO = "867278a8-ba28-51cd-8240-1f48423fe086"
const OUT = path.resolve(process.cwd(), "../docs/screenshots")
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({ channel: "chrome", headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const settle = (ms) => page.waitForTimeout(ms)

// 1. login
await page.goto(`${BASE}/login`)
await page.getByLabel("Email").fill("owner@demo.test")
await page.getByLabel("Password").fill("Demo!2026")
await page.getByRole("button", { name: "Sign in" }).click()
await page.waitForURL(`${BASE}/`)
await page.waitForSelector("text=Good day")

// Token storage check: nothing in localStorage/sessionStorage, refresh cookie not readable.
const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), cookie: document.cookie }))
console.log("storage after login:", JSON.stringify(storage))
const cookies = await page.context().cookies()
const refresh = cookies.find((c) => c.name === "bitlux_refresh")
console.log("refresh cookie:", refresh ? { httpOnly: refresh.httpOnly, sameSite: refresh.sameSite, path: refresh.path } : "MISSING")

// 2. client detail, Relationship tab, depth 1
await page.goto(`${BASE}/clients/${DEMO}?tab=relationship`)
await page.waitForSelector("[data-testid=relationship-graph]")
await page.waitForFunction(() => document.querySelectorAll("[data-node]").length > 5)
await settle(3500)
await page.getByRole("button", { name: "Fit to view" }).click()
await settle(800)
await page.screenshot({ path: path.join(OUT, "client-relationship-depth1.png") })
console.log("depth1 nodes:", await page.locator("[data-node]").count(), "edges:", await page.locator("line[data-edge]").count())

// 3. depth 2
await page.getByTestId("depth-2").click()
await page.waitForFunction(() => document.querySelectorAll("[data-node]").length > 40)
await settle(5000)
await page.getByRole("button", { name: "Fit to view" }).click()
await settle(800)
await page.screenshot({ path: path.join(OUT, "client-relationship-depth2.png") })
console.log("depth2 nodes:", await page.locator("[data-node]").count(), "edges:", await page.locator("line[data-edge]").count())

// 4. global search, from the dashboard. The Cmd/Ctrl+K shortcut is covered by the vitest
// suite; in headless Chrome Ctrl+K is a *browser* shortcut that navigates away, so the
// palette is opened by its top-bar button.
await page.goto(`${BASE}/`)
await page.waitForSelector("text=Good day")
await page.getByRole("button", { name: "Search (Ctrl+K)" }).click()
const input = page.getByPlaceholder("Search everything…")
if (!(await input.waitFor({ timeout: 5000 }).then(() => true).catch(() => false))) {
  console.log("palette did not open:", await page.evaluate(() => ({ dialogs: document.querySelectorAll("[role=dialog]").length, inputs: document.querySelectorAll("input").length })))
  process.exit(2)
}
await input.fill("gulf")
await page.waitForSelector("[data-testid=search-hit]")
await settle(400)
await page.screenshot({ path: path.join(OUT, "global-search-gulf.png") })
console.log("search hits:", await page.locator("[data-testid=search-hit]").allInnerTexts())
await page.keyboard.press("Escape")

// 5. client overview + dashboard for good measure
await page.goto(`${BASE}/clients/${DEMO}`)
await page.waitForSelector("[data-testid=kpi]")
await settle(800)
await page.screenshot({ path: path.join(OUT, "client-overview.png") })
await page.goto(`${BASE}/`)
await page.waitForSelector("text=Good day")
await settle(800)
await page.screenshot({ path: path.join(OUT, "dashboard.png") })

await browser.close()
console.log("screenshots written to", OUT)
