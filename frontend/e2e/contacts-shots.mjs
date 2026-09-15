/**
 * Contacts CRUD walkthrough against the running app (vite :5173, API :8000) with
 * the system Chrome. Writes docs/screenshots/contacts-{empty,list,create,detail-edit}.png
 * and exercises the real actions layer: create → log a call → delete → Undo → delete.
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

await page.goto(`${BASE}/login`)
await page.getByLabel("Email").fill("owner@demo.test")
await page.getByLabel("Password").fill("Demo!2026")
await page.getByRole("button", { name: "Sign in" }).click()
await page.waitForURL(`${BASE}/`)

// 1. EMPTY: the first-run state, by answering the list request with an empty book.
await page.route("**/api/v1/contacts?**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 25 }) }))
await page.goto(`${BASE}/contacts`)
await page.waitForSelector("[data-testid=empty-state]")
check("empty state headline", await page.locator("[data-testid=empty-state]").innerText().then((t) => t.includes("No contacts yet")))
await page.screenshot({ path: path.join(OUT, "contacts-empty.png") })
await page.unroute("**/api/v1/contacts?**")

// 2. LIST: real data.
await page.goto(`${BASE}/contacts`)
await page.waitForSelector("[data-testid=table-row]")
const rows = await page.locator("[data-testid=table-row]").count()
check("list renders rows", rows > 5, `${rows} rows`)
await page.screenshot({ path: path.join(OUT, "contacts-list.png") })

// search hits the API's q=
await page.getByLabel("Search contacts").fill("halcyon")
await page.waitForFunction(() => document.querySelectorAll("[data-testid=table-row]").length <= 2)
check("search narrows via q=", (await page.locator("[data-testid=table-row]").count()) >= 1 && (await page.locator("[data-testid=table-row]").first().innerText()).toLowerCase().includes("halcyon"))
await page.getByLabel("Search contacts").fill("")
await page.waitForFunction((n) => document.querySelectorAll("[data-testid=table-row]").length === n, rows)

// 2b. Row-menu Edit on a contact whose status is NOT the form default: the selects must show the record's values.
const marcus = page.locator("[data-testid=table-row]", { hasText: "Marcus Chen" })
await marcus.getByRole("button", { name: /Actions for/ }).click()
await page.getByRole("menuitem", { name: "Edit" }).click()
await page.waitForSelector("[data-testid=contact-form-dialog]")
await page.waitForFunction(() => document.querySelector("#f-first_name")?.value === "Marcus")
const statusText = await page.locator("[data-testid=contact-form-dialog] [data-testid=field-status]").innerText()
const ownerText = await page.locator("[data-testid=contact-form-dialog] [data-testid=field-owner_user_id]").innerText()
check("edit dialog shows the record's status and owner", statusText.trim() === "Prospect" && ownerText.trim() === "Ben Carter", `status=${statusText.trim()} owner=${ownerText.trim()}`)
await page.keyboard.press("Escape")
await page.waitForSelector("[data-testid=contact-form-dialog]", { state: "detached" })

// 3. CREATE dialog (screenshot), then actually create.
await page.getByTestId("create-contact").first().click()
await page.waitForSelector("[data-testid=contact-form-dialog]")
await page.getByLabel("First name").fill("Playwright")
await page.getByLabel("Last name").fill("Testcontact")
await page.getByLabel("Email").fill("playwright@example.test")
await page.getByLabel("Job title").fill("Chief Pilot")
await settle(200)
await page.screenshot({ path: path.join(OUT, "contacts-create.png") })
const createResp = page.waitForResponse((r) => r.url().includes("/api/v1/contacts") && r.request().method() === "POST")
await page.getByTestId("submit-button").click()
const created = await (await createResp).json()
check("create returns 201 with derived display_name", created.display_name === "Playwright Testcontact", JSON.stringify({ id: created.id, display_name: created.display_name }))
await page.waitForSelector("[data-sonner-toast]")
check("success toast names the contact", (await page.locator("[data-sonner-toast]").first().innerText()).includes("Playwright Testcontact"))
await page.waitForFunction(() => [...document.querySelectorAll("[data-testid=table-row]")].some((r) => r.textContent.includes("Playwright Testcontact")))
check("list refreshed with the new row", true)

// 4. DETAIL + log a call + edit page.
await page.goto(`${BASE}/contacts/${created.id}?tab=activities`)
await page.getByTestId("log-call").first().click()
await page.getByLabel("Subject").fill("Intro call from the walkthrough")
const actResp = page.waitForResponse((r) => r.url().includes("/api/v1/activities") && r.request().method() === "POST")
await page.getByTestId("submit-button").click()
check("log call -> 201", (await actResp).status() === 201)
await page.waitForSelector("[data-testid=activity-list]")
check("activity appears on the contact", (await page.locator("[data-testid=activity-list]").innerText()).includes("Intro call from the walkthrough"))

await page.getByTestId("edit-contact").click()
await page.waitForURL(`${BASE}/contacts/${created.id}/edit`)
await page.waitForFunction(() => document.querySelector("#f-last_name")?.value === "Testcontact")
await page.getByLabel("Job title").fill("Director of Aviation")
await settle(200)
await page.screenshot({ path: path.join(OUT, "contacts-detail-edit.png") })
const patchResp = page.waitForResponse((r) => r.url().includes(`/api/v1/contacts/${created.id}`) && r.request().method() === "PATCH")
await page.getByTestId("submit-button").click()
check("edit page PATCHes and returns to detail", (await patchResp).status() === 200)
await page.waitForURL(`${BASE}/contacts/${created.id}`)
await page.waitForFunction(() => document.body.innerText.includes("Director of Aviation"))

// 5. DELETE with Undo, then delete for real.
await page.getByTestId("delete-contact").click()
const delResp = page.waitForResponse((r) => r.url().includes(`/api/v1/contacts/${created.id}`) && r.request().method() === "DELETE")
await page.getByTestId("confirm-button").click()
check("delete -> 204", (await delResp).status() === 204)
await page.waitForURL(`${BASE}/contacts`)
const restoreResp = page.waitForResponse((r) => r.url().includes(`/restore`) && r.request().method() === "POST")
await page.locator("[data-sonner-toast] button", { hasText: "Undo" }).first().click()
check("Undo -> POST restore 200", (await restoreResp).status() === 200)
await page.waitForFunction(() => [...document.querySelectorAll("[data-testid=table-row]")].some((r) => r.textContent.includes("Playwright Testcontact")))
check("restored row is back in the list", true)
// Clean up via the row menu this time (exercises ActionMenu in a real browser).
const row = page.locator("[data-testid=table-row]", { hasText: "Playwright Testcontact" })
await row.getByRole("button", { name: /Actions for/ }).click()
await page.getByRole("menuitem", { name: "Delete" }).click()
const delResp2 = page.waitForResponse((r) => r.url().includes(`/api/v1/contacts/${created.id}`) && r.request().method() === "DELETE")
await page.getByTestId("confirm-button").click()
check("row-menu delete -> 204", (await delResp2).status() === 204)
await page.waitForFunction(() => ![...document.querySelectorAll("[data-testid=table-row]")].some((r) => r.textContent.includes("Playwright Testcontact")))

check("no console/page errors", errors.length === 0, errors.slice(0, 3).join(" | "))
await browser.close()
console.log(failures ? `\n${failures} check(s) FAILED` : "\nall checks passed")
process.exit(failures ? 1 : 0)
