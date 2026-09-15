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
