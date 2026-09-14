import { act, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { renderWithProviders } from "@/test/utils"
import { GlobalSearch, SEARCH_DEBOUNCE_MS, hitRoute } from "../GlobalSearch"

const RESULTS = {
  query: "gulf",
  results: {
    manufacturers: [{ id: "m1", type: "manufacturers", label: "Gulfstream Aerospace", subtitle: "US", url: "/manufacturers/m1", rank: 0.07 }],
    contacts: [{ id: "c1", type: "contacts", label: "Gulf Coast Charters", subtitle: null, url: "/contacts/c1", rank: 0.05 }],
  },
}

describe("GlobalSearch", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
  afterEach(() => {
    // Flush any debounce/query timers before the jsdom window is torn down,
    // otherwise React's act() sees a timer fire against a null document.
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it("debounces input by 200ms and issues one request for the settled query", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue(RESULTS)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderWithProviders(<GlobalSearch />)
    await user.keyboard("{Control>}k{/Control}")
    const input = await screen.findByLabelText("Search query")
    await user.type(input, "gulf")
    expect(get).not.toHaveBeenCalled()
    await act(async () => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS + 10)
    })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(String(get.mock.calls[0]?.[0])).toContain("/search?q=gulf&types=")
    expect(String(get.mock.calls[0]?.[0])).toContain("limit=20")
  })

  it("renders grouped results in the configured order and maps hit urls to routes", async () => {
    vi.spyOn(api, "get").mockResolvedValue(RESULTS)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderWithProviders(<GlobalSearch />)
    await user.click(screen.getByRole("button", { name: /Search/ }))
    await user.type(await screen.findByLabelText("Search query"), "gulf")
    await act(async () => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS + 10)
    })
    const hits = await screen.findAllByTestId("search-hit")
    expect(hits).toHaveLength(2)
    expect(hits[0]).toHaveTextContent("Gulf Coast Charters") // Contacts group is configured before Manufacturers
    expect(hits[1]).toHaveTextContent("Gulfstream Aerospace")
    expect(hitRoute({ id: "x", type: "aircraft_models", label: "", subtitle: null, url: "/aircraft_models/x", rank: 1 })).toBe("/aircraft-models/x")
  })
})
