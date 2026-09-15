/** Option lists for pickers. Each degrades to `unavailable` when the role cannot list the source. */

import { useQuery } from "@tanstack/react-query"
import { api, qs } from "./api"
import { useAuth } from "./auth"
import type { Contact, Page, Segment, UserLookup } from "./types"

export function useUserOptions() {
  const q = useQuery({ queryKey: ["users", "lookup"], queryFn: () => api.get<UserLookup[]>("/admin/users/lookup"), staleTime: 5 * 60_000 })
  return { options: (q.data ?? []).map((u) => ({ value: u.id, label: u.full_name })), isLoading: q.isPending, unavailable: q.isError }
}

export function useSegmentOptions() {
  const { can } = useAuth()
  const allowed = can("segments.view")
  const q = useQuery({ queryKey: ["segments", "options"], queryFn: () => api.get<Page<Segment>>(`/segments${qs({ page_size: 200, order_by: "name" })}`), enabled: allowed, staleTime: 5 * 60_000 })
  return { options: (q.data?.items ?? []).map((s) => ({ value: s.id, label: s.name })), isLoading: allowed && q.isPending, unavailable: !allowed || q.isError }
}

export function useContactOptions() {
  const { can } = useAuth()
  const allowed = can("contacts.view")
  const q = useQuery({ queryKey: ["contacts", "options"], queryFn: () => api.get<Page<Contact>>(`/contacts${qs({ page_size: 200, order_by: "display_name" })}`), enabled: allowed, staleTime: 60_000 })
  return { options: (q.data?.items ?? []).map((c) => ({ value: c.id, label: c.display_name })), isLoading: allowed && q.isPending, unavailable: !allowed || q.isError }
}

type Labeller<T> = (row: T) => string

/** A picker over any list endpoint: `{ value: id, label }`, hidden when the role cannot list it. */
export function makeOptionsHook<T extends { id: string }>(key: string, endpoint: string, permission: string, label: Labeller<T>, orderBy?: string) {
  return function useOptions() {
    const { can } = useAuth()
    const allowed = can(permission)
    const q = useQuery({ queryKey: [key, "options"], queryFn: () => api.get<Page<T>>(`${endpoint}${qs({ page_size: 200, order_by: orderBy ?? null })}`), enabled: allowed, staleTime: 60_000 })
    return { options: (q.data?.items ?? []).map((r) => ({ value: r.id, label: label(r) })), isLoading: allowed && q.isPending, unavailable: !allowed || q.isError }
  }
}

export const useOperatorOptions = makeOptionsHook<{ id: string; legal_name: string; dba_name: string | null }>("operators", "/operators", "operators.view", (o) => o.dba_name ?? o.legal_name, "legal_name")
export const useAircraftOptions = makeOptionsHook<{ id: string; tail_number: string }>("aircraft", "/aircraft", "aircraft.view", (a) => a.tail_number, "tail_number")
export const useAircraftModelOptions = makeOptionsHook<{ id: string; name: string; family: string | null }>("aircraft_models", "/aircraft_models", "aircraft_models.view", (m) => m.name, "name")
export const useAirportOptions = makeOptionsHook<{ id: string; icao_code: string | null; iata_code: string | null; name: string }>("airports", "/airports", "airports.view", (a) => `${a.icao_code ?? a.iata_code ?? ""} ${a.name}`.trim(), "icao_code")
export const useAccountHolderOptions = makeOptionsHook<{ id: string; account_number: string; name: string }>("account_holders", "/account_holders", "account_holders.view", (a) => `${a.name} (${a.account_number})`, "name")
export const useTripOptions = makeOptionsHook<{ id: string; trip_number: string }>("trips", "/trips", "trips.view", (t) => t.trip_number, "-departure_date")
export const usePassengerOptions = makeOptionsHook<{ id: string; first_name: string; last_name: string }>("passengers", "/passengers", "passengers.view", (p) => `${p.first_name} ${p.last_name}`, "last_name")
