/**
 * Part 1 verification: every list and detail page carries the standard action
 * vocabulary, wired where the API supports it and visibly disabled (with a
 * reason) where it does not. Writes docs/screenshots/actions-*.png.
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
const esc = async () => { await page.keyboard.press("Escape"); await settle(250) }

await page.goto(`${BASE}/login`)
await page.getByLabel("Email").fill("owner@demo.test")
await page.getByLabel("Password").fill("Demo!2026")
await page.getByRole("button", { name: "Sign in" }).click()
await page.waitForURL(`${BASE}/`)

// ---- 1. Contacts list: full header + row actions ---------------------------
await page.goto(`${BASE}/contacts`)
await page.waitForSelector("[data-testid=table-row]")
check("list: New + Actions in the header", await page.getByTestId("create-contact").isEnabled() && (await page.getByTestId("list-actions").count()) === 1)
check("list: row checkboxes", (await page.locator("[data-testid=table-row] input[type=checkbox]").count()) > 0)
const firstRow = page.locator("[data-testid=table-row]").first()
await firstRow.getByRole("button", { name: /Actions for/ }).click()
await page.waitForSelector("[role=menuitem]")
const order = await page.locator("[role=menuitem]").allInnerTexts()
check("row menu order: View / Edit / Duplicate / Archive / Delete", order.map((t) => t.replace(/Planned/g, "").trim()).join("|") === "View|Edit|Duplicate|Archive (mark dormant)|Delete", order.join(" | "))
await settle(400)
await page.screenshot({ path: path.join(OUT, "actions-contacts-list.png") })
await esc()

// Column chooser + CSV export both work.
await page.getByTestId("list-actions").click()
await page.waitForSelector("[data-testid=export-csv]")
check("list actions: export + column chooser present", (await page.getByTestId("export-csv").count()) === 1 && (await page.locator("[data-testid^=column-]").count()) > 3)
const dl = page.waitForEvent("download")
await page.getByTestId("export-csv").click()
const file = await dl
check("Export CSV downloads a file", (await file.suggestedFilename()).startsWith("contacts-"), await file.suggestedFilename())
await esc()

// ---- 2. Contact detail: header actions + More menu -------------------------
const cid = await page.locator("[data-testid=table-row] a[href^='/contacts/']").first().getAttribute("href")
await page.goto(`${BASE}${cid}`)
await page.waitForSelector("[data-testid=more-menu]")
check("detail: Back / Edit / Delete / More", (await page.getByTestId("back-link").count()) === 1 && (await page.getByTestId("edit-contact").isEnabled()) && (await page.getByTestId("delete-contact").isEnabled()))
await page.getByTestId("more-menu").click()
await page.waitForSelector("[data-testid=more-merge]")
const merge = page.getByTestId("more-merge")
const mergeText = (await merge.innerText()).toLowerCase()
check("contact More: wired items enabled, Merge disabled + labelled Planned", (await merge.getAttribute("aria-disabled")) === "true" && mergeText.includes("planned") && (await page.getByTestId("more-segment").getAttribute("aria-disabled")) === null, mergeText)
await settle(400)
await page.screenshot({ path: path.join(OUT, "actions-contact-detail.png") })
await esc()

// ---- 3. Generic detail (trip): workflow actions, wired and planned ---------
await page.goto(`${BASE}/trips`)
await page.waitForSelector("[data-testid=table-row]")
const tid = await page.locator("[data-testid=table-row] a[href^='/trips/']").first().getAttribute("href")
await page.goto(`${BASE}${tid}`)
await page.waitForSelector("[data-testid=section-legs]")
check("trip detail: sections render", (await page.getByTestId("section-legs").count()) === 1 && (await page.getByTestId("section-quotes").count()) === 1)
await page.getByTestId("more-menu").click()
await page.waitForSelector("[data-testid=more-advance]")
check("trip More: Advance status wired, Generate quote planned", (await page.getByTestId("more-advance").getAttribute("aria-disabled")) === null && (await page.getByTestId("more-generate-quote").getAttribute("aria-disabled")) === "true")
await settle(400)
await page.screenshot({ path: path.join(OUT, "actions-trip-detail.png") })
await esc()

// ---- 4. A read-only-ish entity: New disabled with an explaining tooltip ----
await page.goto(`${BASE}/airports`)
await page.waitForSelector("[data-testid=table-row]")
const newBtn = page.getByTestId("create-airport")
check("airports: New is present but disabled", await newBtn.isDisabled())
await newBtn.locator("xpath=ancestor::*[@data-testid='planned']").hover()
await settle(500)
const tip = await page.locator("[role=tooltip]").first().innerText().catch(() => "")
check("disabled New explains itself", tip.includes("future sprint"), tip || "(no tooltip)")
await page.screenshot({ path: path.join(OUT, "actions-planned-tooltip.png") })

// ---- 5. Empty state on a list ---------------------------------------------
await page.route("**/api/v1/tasks?**", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 25 }) }))
await page.goto(`${BASE}/tasks`)
await page.waitForSelector("[data-testid=empty-state]")
const emptyText = await page.getByTestId("empty-state").innerText()
check("empty state: headline, description, action", emptyText.includes("No tasks yet") && emptyText.includes("Get started") && (await page.getByTestId("empty-state").getByTestId("create-task").count()) === 1)
await page.screenshot({ path: path.join(OUT, "actions-empty-state.png") })
await page.unroute("**/api/v1/tasks?**")

// ---- 6. Graph tab on a generic detail page --------------------------------
await page.goto(`${BASE}${tid}?tab=relationship`)
await page.waitForSelector("[data-testid=relationship-graph]")
await page.waitForFunction(() => document.querySelectorAll("[data-node]").length > 2, null, { timeout: 15000 })
await settle(3000)
await page.getByRole("button", { name: "Fit to view" }).click()
await settle(600)
check("graph tab renders nodes on a generic detail page", (await page.locator("[data-node]").count()) > 2)
await page.screenshot({ path: path.join(OUT, "actions-graph-tab.png") })

check("no console/page errors", errors.length === 0, errors.slice(0, 3).join(" | "))
await browser.close()
console.log(failures ? `\n${failures} check(s) FAILED` : "\nall checks passed")
process.exit(failures ? 1 : 0)
