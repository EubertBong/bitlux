import "@testing-library/jest-dom/vitest"
import { afterEach, vi } from "vitest"
import { act, cleanup } from "@testing-library/react"

// jsdom lacks these; Radix, cmdk and the graph's width measurement expect them.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
Object.defineProperty(globalThis, "ResizeObserver", { value: ResizeObserverStub, writable: true })
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({ matches: false, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }),
})
Element.prototype.scrollIntoView = () => {}
Element.prototype.hasPointerCapture = () => false
Element.prototype.setPointerCapture = () => {}
Element.prototype.releasePointerCapture = () => {}
// SVG geometry used by d3-zoom/d3-drag when pointer events fire.
if (!("getScreenCTM" in SVGElement.prototype)) {
  Object.defineProperty(SVGElement.prototype, "getScreenCTM", { value: () => null })
}

afterEach(async () => {
  // Let any animation-frame / microtask work (d3-force ticks) flush while the
  // jsdom window still exists, then unmount everything.
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
  cleanup()
  vi.restoreAllMocks()
})
