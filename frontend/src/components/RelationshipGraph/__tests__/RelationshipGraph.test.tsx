import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { api, ApiError } from "@/lib/api"
import { MOCK_GRAPH, renderWithProviders } from "@/test/utils"
import { RelationshipGraph } from "../RelationshipGraph"

describe("RelationshipGraph", () => {
  it("renders one node per graph node and one line per edge from the API payload", async () => {
    vi.spyOn(api, "get").mockResolvedValue(MOCK_GRAPH)
    const { container } = renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" />)
    await waitFor(() => expect(container.querySelectorAll("[data-node]")).toHaveLength(5))
    expect(container.querySelectorAll("line[data-edge]")).toHaveLength(4)
    expect(screen.getByRole("img", { name: "Relationship graph for Client n-client" })).toBeInTheDocument()
    expect(screen.getByTestId("graph-status")).toHaveTextContent("Showing 5 nodes and 4 edges at depth 1")
    expect(api.get).toHaveBeenCalledWith("/graph/client/n-client?depth=1", expect.anything())
  })

  it("hides a node type when it is toggled off in the legend and announces it", async () => {
    vi.spyOn(api, "get").mockResolvedValue(MOCK_GRAPH)
    const user = userEvent.setup()
    const { container } = renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" />)
    await waitFor(() => expect(container.querySelectorAll("[data-node]")).toHaveLength(5))
    await user.click(within(screen.getByTestId("graph-legend")).getByRole("button", { name: /Contact/ }))
    await waitFor(() => expect(container.querySelectorAll("[data-node-type='contact']")).toHaveLength(0))
    expect(container.querySelectorAll("[data-node]")).toHaveLength(3)
    expect(container.querySelectorAll("line[data-edge]")).toHaveLength(2)
    expect(screen.getByTestId("graph-status")).toHaveTextContent("2 nodes hidden by type filter")
  })

  it("refetches with depth=2 when the depth toggle changes", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue(MOCK_GRAPH)
    const user = userEvent.setup()
    renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" />)
    await screen.findByTestId("relationship-graph")
    await user.click(screen.getByTestId("depth-2"))
    await waitFor(() => expect(get).toHaveBeenCalledWith("/graph/client/n-client?depth=2", expect.anything()))
  })

  it("shows 'Graph unavailable' with a retry button when the request fails", async () => {
    const get = vi.spyOn(api, "get").mockRejectedValueOnce(new ApiError(500, "internal_error", "boom")).mockResolvedValue(MOCK_GRAPH)
    const user = userEvent.setup()
    const { container } = renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" />)
    expect(await screen.findByText("Graph unavailable")).toBeInTheDocument()
    await user.click(screen.getByTestId("graph-retry"))
    await waitFor(() => expect(container.querySelectorAll("[data-node]")).toHaveLength(5))
    expect(get).toHaveBeenCalledTimes(2)
  })

  it("navigates to the node's route on click, mapping table names to route paths", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ ...MOCK_GRAPH, nodes: [...MOCK_GRAPH.nodes, { id: "n-ah", type: "account_holder", label: "Halcyon", subtitle: null, url: "/account_holders/n-ah" }] })
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    const { container } = renderWithProviders(<RelationshipGraph entityType="client" entityId="n-client" onNavigate={onNavigate} />)
    await waitFor(() => expect(container.querySelectorAll("[data-node]")).toHaveLength(6))
    await user.click(container.querySelector("[data-node='n-ah']") as Element)
    expect(onNavigate).toHaveBeenCalledWith("/account-holders/n-ah")
  })
})
