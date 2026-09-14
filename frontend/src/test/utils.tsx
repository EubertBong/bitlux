import * as React from "react"
import { render, type RenderOptions } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AuthProvider } from "@/lib/auth"
import { ThemeProvider } from "@/lib/theme"
import type { Me } from "@/lib/types"

export const DEMO_ID = "867278a8-ba28-51cd-8240-1f48423fe086"

export const BROKER: Me = {
  id: "14b66518-1136-52cc-9474-7f3adfefc800",
  client_id: DEMO_ID,
  email: "broker@demo.test",
  full_name: "Ben Carter",
  role: "broker",
  status: "active",
  timezone: "America/New_York",
  permissions: [
    "clients.view", "clients.create", "clients.edit", "contacts.view", "contacts.create", "passengers.view", "trips.view",
    "quotes.view", "bookings.view", "documents.view", "tasks.view", "activities.view", "empty_legs.view", "segments.view", "account_holders.view",
  ],
}

export function makeTestQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 }, mutations: { retry: false } } })
}

interface Options extends Omit<RenderOptions, "wrapper"> {
  route?: string
  /** Route pattern the element is mounted at (for useParams); defaults to "*". */
  path?: string
  user?: Me | null
  queryClient?: QueryClient
}

export function renderWithProviders(ui: React.ReactElement, { route = "/", path = "*", user = BROKER, queryClient = makeTestQueryClient(), ...options }: Options = {}) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <ThemeProvider defaultTheme="light">
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider initialUser={user}>
            <TooltipProvider>
              <Routes>
                <Route path={path} element={children} />
                <Route path="/login" element={<div>LOGIN PAGE</div>} />
              </Routes>
            </TooltipProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
      </ThemeProvider>
    )
  }
  return render(ui, { wrapper: Wrapper, ...options })
}

export const MOCK_GRAPH = {
  nodes: [
    { id: "n-client", type: "client", label: "Demo Brokerage", subtitle: "demo", url: "/clients/n-client" },
    { id: "n-seg", type: "segment", label: "UHNW", subtitle: "uhnw", url: "/segments/n-seg" },
    { id: "n-c1", type: "contact", label: "Victoria Ashworth", subtitle: "Principal", url: "/contacts/n-c1" },
    { id: "n-c2", type: "contact", label: "Halcyon Capital Partners", subtitle: null, url: "/contacts/n-c2" },
    { id: "n-trip", type: "trip", label: "BLX-2026-001", subtitle: "confirmed", url: "/trips/n-trip" },
  ],
  edges: [
    { from: "n-client", to: "n-seg", type: "has_segment", label: "segment" },
    { from: "n-client", to: "n-c1", type: "has_contact", label: "contact" },
    { from: "n-client", to: "n-c2", type: "has_contact", label: "contact" },
    { from: "n-client", to: "n-trip", type: "has_trip", label: "trip" },
  ],
}
