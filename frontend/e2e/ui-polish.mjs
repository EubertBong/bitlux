/**
 * Verifies the four UI polish fixes against the running app (vite :5173, API :8000)
 * with the system Chrome, and writes the review screenshots to docs/screenshots/.
 *
 *   node e2e/ui-polish.mjs
 *
 * Checks (each prints PASS/FAIL, exit code 1 on any FAIL):
 *   1. sidebar scrollbar: thin, transparent at rest, themed thumb on hover, no label overlap
 *   2. no gap under the sidebar when a long page is scrolled to the bottom
 *   3. top bar has vertical padding, a bottom border, and a search input of consistent height
 *   4. theme toggle: light -> dark -> system, persisted in localStorage["bitlux-theme"],
 *      survives a reload, follows the OS in "system" mode
 *   5. no console errors in either theme
 */
import { chromium } from "playwright"
import { mkdirSync } from "node:fs"
import path from "node:path"

const BASE = process.env.FRONTEND_URL ?? "http://localhost:5173"
const DEMO = "867278a8-ba28-51cd-8240-1f48423fe086"
const OUT = path.resolve(process.cwd(), "../docs/screenshots")
mkdirSync(OUT, { recursive: true })

let failures = 0
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`)
  if (!ok) failures++
}

// Headless Chrome hides scrollbars by default; keep them so the sidebar capture shows the thumb.
const browser = await chromium.launch({ channel: "chrome", headless: true, ignoreDefaultArgs: ["--hide-scrollbars"] })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "light" })
const page = await context.newPage()
const consoleErrors = []
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()) })
page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`))
const settle = (ms) => page.waitForTimeout(ms)

// login
await page.goto(`${BASE}/login`)
await page.getByLabel("Email").fill("owner@demo.test")
await page.getByLabel("Password").fill("Demo!2026")
await page.getByRole("button", { name: "Sign in" }).click()
await page.waitForURL(`${BASE}/`)
await page.waitForSelector("text=Good day")

// A long page: the client detail (overview + tabs) is the longest we have.
const LONG = `${BASE}/clients/${DEMO}`
await page.goto(LONG)
await page.waitForSelector("[data-testid=main]")
await settle(800)

// ---- 3. top bar -----------------------------------------------------------
const topbar = await page.evaluate(() => {
  const h = document.querySelector("[data-testid=topbar]")
  const cs = getComputedStyle(h)
  const search = h.querySelector("button[aria-label^='Search']")
  const sr = search.getBoundingClientRect()
  const hr = h.getBoundingClientRect()
  const avatar = h.querySelector("[data-testid=user-menu], [data-slot=avatar]")?.getBoundingClientRect()
  return {
    paddingTop: parseFloat(cs.paddingTop), paddingBottom: parseFloat(cs.paddingBottom),
    borderBottom: cs.borderBottomWidth, boxShadow: cs.boxShadow !== "none",
    height: hr.height, searchHeight: sr.height, searchTop: sr.top - hr.top,
    avatarCentreOffset: avatar ? Math.abs((avatar.top + avatar.height / 2) - (hr.top + hr.height / 2)) : null,
  }
})
check("top bar vertical padding >= 12px", topbar.paddingTop >= 12 && topbar.paddingBottom >= 12, `py=${topbar.paddingTop}/${topbar.paddingBottom}`)
check("top bar has bottom border", parseFloat(topbar.borderBottom) >= 1, `border=${topbar.borderBottom} shadow=${topbar.boxShadow}`)
check("search input h-9 and not touching top edge", Math.round(topbar.searchHeight) === 36 && topbar.searchTop >= 12, `h=${topbar.searchHeight} top=${topbar.searchTop}`)
check("avatar vertically centred", topbar.avatarCentreOffset !== null && topbar.avatarCentreOffset < 2, `offset=${topbar.avatarCentreOffset}`)
await page.screenshot({ path: path.join(OUT, "polish-topbar.png"), clip: { x: 0, y: 0, width: 1440, height: 120 } })

// ---- 2. no gap under the sidebar on a long page ----------------------------
// The client page only overflows on a shorter viewport; 1440x640 is a common laptop
// browser height once the OS and browser chrome are subtracted.
await page.setViewportSize({ width: 1440, height: 640 })
await settle(300)
const scrolled = await page.evaluate(() => {
  const main = document.querySelector("[data-testid=main]")
  main.scrollTop = main.scrollHeight
  const side = document.querySelector("[data-testid=sidebar]").getBoundingClientRect()
  const px = (x, y) => { const el = document.elementFromPoint(x, y); return el ? getComputedStyle(el).backgroundColor : null }
  return {
    mainScrollable: main.scrollHeight > main.clientHeight,
    mainScrollTop: main.scrollTop,
    windowScrollY: window.scrollY, docScrollable: document.documentElement.scrollHeight > window.innerHeight,
    sidebarBottom: side.bottom, viewportH: window.innerHeight,
    sidebarBg: getComputedStyle(document.querySelector("[data-testid=sidebar]")).backgroundColor,
    bottomLeftPixelBg: px(8, window.innerHeight - 4),
  }
})
check("long page: <main> is the scroller, window does not scroll", scrolled.mainScrollable && scrolled.mainScrollTop > 0 && !scrolled.docScrollable && scrolled.windowScrollY === 0, `mainScrollTop=${scrolled.mainScrollTop} docScrollable=${scrolled.docScrollable}`)
check("sidebar reaches the viewport bottom", Math.round(scrolled.sidebarBottom) === scrolled.viewportH, `bottom=${scrolled.sidebarBottom} vh=${scrolled.viewportH}`)
await settle(300)
await page.screenshot({ path: path.join(OUT, "polish-long-page-bottom.png") })
await page.setViewportSize({ width: 1440, height: 900 })

// ---- 1. sidebar scrollbar --------------------------------------------------
// Shrink the viewport so the nav overflows and the sidebar must scroll.
await page.setViewportSize({ width: 1440, height: 520 })
await settle(300)
const sb = await page.evaluate(() => {
  const el = document.querySelector("[data-testid=sidebar-scroll]")
  const cs = getComputedStyle(el)
  el.scrollTop = 80
  const labels = [...el.querySelectorAll("a")].map((a) => a.getBoundingClientRect().right)
  return {
    overflows: el.scrollHeight > el.clientHeight, scrollTop: el.scrollTop,
    scrollbarWidth: cs.scrollbarWidth, scrollbarColorRest: cs.scrollbarColor, gutter: cs.scrollbarGutter,
    trackPx: el.offsetWidth - el.clientWidth, maxLabelRight: Math.max(...labels), clientRight: el.getBoundingClientRect().left + el.clientWidth,
  }
})
check("sidebar nav overflows and scrolls internally", sb.overflows && sb.scrollTop > 0, `scrollTop=${sb.scrollTop}`)
check("scrollbar-width: thin", sb.scrollbarWidth === "thin", sb.scrollbarWidth)
check("scrollbar transparent at rest", /transparent transparent|rgba\(0, 0, 0, 0\) rgba\(0, 0, 0, 0\)/.test(sb.scrollbarColorRest), sb.scrollbarColorRest)
check("thin track (<= 12px) reserved, labels do not overlap it", sb.trackPx > 0 && sb.trackPx <= 12 && sb.maxLabelRight <= sb.clientRight + 0.5, `track=${sb.trackPx}px labelRight=${sb.maxLabelRight} clientRight=${sb.clientRight}`)
await page.hover("[data-testid=sidebar-scroll]")
await settle(400)
const hovered = await page.evaluate(() => getComputedStyle(document.querySelector("[data-testid=sidebar-scroll]")).scrollbarColor)
check("themed thumb visible on hover", !/transparent transparent|rgba\(0, 0, 0, 0\) rgba\(0, 0, 0, 0\)/.test(hovered), hovered)
await page.screenshot({ path: path.join(OUT, "polish-sidebar-scrollbar.png"), clip: { x: 0, y: 0, width: 480, height: 520 } })
await page.setViewportSize({ width: 1440, height: 900 })

// ---- 4. theme toggle -------------------------------------------------------
const state = () => page.evaluate(() => ({
  stored: localStorage.getItem("bitlux-theme"),
  dark: document.documentElement.classList.contains("dark"),
  colorScheme: document.documentElement.style.colorScheme,
  label: document.querySelector("[data-testid=theme-toggle]").getAttribute("aria-label"),
}))
const pick = async (mode) => {
  await page.click("[data-testid=theme-toggle]")
  await page.click(`[data-testid=theme-${mode}]`)
  await settle(250)
}
const s0 = await state()
check("default is system (nothing stored, OS light -> light)", s0.stored === null && !s0.dark && /System/.test(s0.label), JSON.stringify(s0))

await page.goto(`${BASE}/clients/${DEMO}?tab=relationship`)
await page.waitForFunction(() => document.querySelectorAll("[data-node]").length > 5)
await settle(3000)
await page.getByRole("button", { name: "Fit to view" }).click()
await settle(600)
await page.screenshot({ path: path.join(OUT, "polish-theme-light.png") })

await pick("dark")
const s1 = await state()
check("choose dark: class on <html> and stored", s1.dark && s1.stored === "dark" && s1.colorScheme === "dark" && /Dark/.test(s1.label), JSON.stringify(s1))
await page.screenshot({ path: path.join(OUT, "polish-theme-dark.png") })
const graphDark = await page.evaluate(() => {
  // The wrapper also holds lucide icons, so pick the SVG that has graph nodes in it.
  const svg = document.querySelector("[data-testid=relationship-graph] svg:has([data-node])")
  const label = svg.querySelector("[data-node] text")
  const line = svg.querySelector("line")
  const card = getComputedStyle(document.documentElement).getPropertyValue("--card").trim()
  return { container: getComputedStyle(svg.parentElement).backgroundColor, label: getComputedStyle(label).fill, edge: getComputedStyle(line).stroke, card }
})
check("graph background/label/edge follow the dark theme", graphDark.card !== "oklch(1 0 0)" && graphDark.container !== "rgb(255, 255, 255)" && graphDark.label !== "rgb(0, 0, 0)" && graphDark.edge !== "none", JSON.stringify(graphDark))

await page.reload()
await page.waitForSelector("[data-testid=theme-toggle]")
const s2 = await state()
check("dark persists across reload", s2.dark && s2.stored === "dark", JSON.stringify(s2))

await pick("light")
const s3 = await state()
check("choose light", !s3.dark && s3.stored === "light", JSON.stringify(s3))

await pick("system")
await page.emulateMedia({ colorScheme: "dark" })
await settle(250)
const s4 = await state()
check("system mode follows OS dark", s4.dark && s4.stored === "system", JSON.stringify(s4))
await page.emulateMedia({ colorScheme: "light" })
await settle(250)
const s5 = await state()
check("system mode follows OS light", !s5.dark && s5.stored === "system", JSON.stringify(s5))
await page.reload()
await page.waitForSelector("[data-testid=theme-toggle]")
const s6 = await state()
check("system persists across reload", s6.stored === "system" && /System/.test(s6.label), JSON.stringify(s6))

// ---- mobile: bottom tab layout has no gap either ---------------------------
await page.setViewportSize({ width: 390, height: 780 })
await page.goto(LONG)
await page.waitForSelector("[data-testid=main]")
await settle(600)
const mobile = await page.evaluate(() => {
  const main = document.querySelector("[data-testid=main]")
  main.scrollTop = main.scrollHeight
  const nav = document.querySelector("nav[aria-label=Mobile]").getBoundingClientRect()
  const h = document.querySelector("[data-testid=topbar]")
  const cs = getComputedStyle(h)
  return { navBottom: nav.bottom, vh: window.innerHeight, docScrollable: document.documentElement.scrollHeight > window.innerHeight, py: [cs.paddingTop, cs.paddingBottom], searchVisible: !!h.querySelector("button[aria-label^='Search']") }
})
check("mobile: bottom tabs flush with viewport, window does not scroll", Math.round(mobile.navBottom) === mobile.vh && !mobile.docScrollable, JSON.stringify(mobile))
check("mobile: top bar keeps py-3", mobile.py[0] === "12px" && mobile.py[1] === "12px", mobile.py.join("/"))
await page.screenshot({ path: path.join(OUT, "polish-mobile-bottom.png") })

check("no console errors in either theme", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "))
await browser.close()
console.log(failures ? `\n${failures} check(s) FAILED` : "\nall checks passed")
process.exit(failures ? 1 : 0)
