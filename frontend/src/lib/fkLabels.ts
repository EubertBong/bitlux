/**
 * Resolve the `*_id` columns on a record to human labels (and routes).
 *
 * Detail pages render whatever the API returns, and a raw UUID is plumbing, not
 * information. This looks up only the collections a given record actually needs,
 * skips any the role cannot read, and falls back to the shortened id.
 */

import { useQueries } from "@tanstack/react-query"
import { api, qs } from "./api"
import { useAuth } from "./auth"
import type { Page, UserLookup } from "./types"

interface Source {
  key: string
  endpoint: string
  permission: string
  path?: string
  label: (row: Record<string, unknown>) => string
  /** /admin/users/lookup returns a bare array, not a Page. */
  bare?: boolean
}

const str = (v: unknown) => (typeof v === "string" ? v : "")

const SOURCES: Record<string, Source> = {
  contacts: { key: "contacts", endpoint: "/contacts", permission: "contacts.view", path: "/contacts", label: (r) => str(r.display_name) },
  users: { key: "users", endpoint: "/admin/users/lookup", permission: "", label: (r) => str((r as unknown as UserLookup).full_name), bare: true },
  operators: { key: "operators", endpoint: "/operators", permission: "operators.view", path: "/operators", label: (r) => str(r.dba_name) || str(r.legal_name) },
  aircraft: { key: "aircraft", endpoint: "/aircraft", permission: "aircraft.view", path: "/aircraft", label: (r) => str(r.tail_number) },
  aircraft_models: { key: "aircraft_models", endpoint: "/aircraft_models", permission: "aircraft_models.view", path: "/aircraft-models", label: (r) => str(r.name) },
  airports: { key: "airports", endpoint: "/airports", permission: "airports.view", path: "/airports", label: (r) => `${str(r.icao_code) || str(r.iata_code)} ${str(r.name)}`.trim() },
  account_holders: { key: "account_holders", endpoint: "/account_holders", permission: "account_holders.view", path: "/account-holders", label: (r) => str(r.name) },
  trips: { key: "trips", endpoint: "/trips", permission: "trips.view", path: "/trips", label: (r) => str(r.trip_number) },
  segments: { key: "segments", endpoint: "/segments", permission: "segments.view", path: "/segments", label: (r) => str(r.name) },
  passengers: { key: "passengers", endpoint: "/passengers", permission: "passengers.view", path: "/passengers", label: (r) => `${str(r.first_name)} ${str(r.last_name)}`.trim() },
  quotes: { key: "quotes", endpoint: "/quotes", permission: "quotes.view", path: "/quotes", label: (r) => `${str(r.quote_number)} r${Number(r.revision ?? 1)}` },
  invoices: { key: "invoices", endpoint: "/invoices", permission: "invoices.view", path: "/invoices", label: (r) => str(r.invoice_number) },
  bookings: { key: "bookings", endpoint: "/bookings", permission: "bookings.view", path: "/bookings", label: (r) => str(r.booking_number) },
  crew: { key: "crew", endpoint: "/crew", permission: "crew.view", path: "/crew", label: (r) => `${str(r.first_name)} ${str(r.last_name)}`.trim() },
  manufacturers: { key: "manufacturers", endpoint: "/manufacturers", permission: "manufacturers.view", path: "/manufacturers", label: (r) => str(r.name) },
  documents: { key: "documents", endpoint: "/documents", permission: "documents.view", path: "/documents", label: (r) => str(r.title) },
  empty_legs: { key: "empty_legs", endpoint: "/empty_legs", permission: "empty_legs.view", path: "/empty-legs", label: (r) => `Empty leg ${str(r.id).slice(0, 8)}` },
}

/** Column name -> which collection it points at. */
export const FK_SOURCE: Record<string, string> = {
  contact_id: "contacts", primary_contact_id: "contacts", owner_contact_id: "contacts", billing_contact_id: "contacts", signed_by_contact_id: "contacts", parent_contact_id: "contacts", referred_by_contact_id: "contacts",
  owner_user_id: "users", ops_user_id: "users", assigned_to_user_id: "users", prepared_by_user_id: "users", completed_by_user_id: "users", verified_by_user_id: "users", uploaded_by_user_id: "users", actor_user_id: "users", user_id: "users",
  operator_id: "operators",
  aircraft_id: "aircraft",
  aircraft_model_id: "aircraft_models",
  airport_id: "airports", departure_airport_id: "airports", arrival_airport_id: "airports", home_base_airport_id: "airports", base_airport_id: "airports",
  account_holder_id: "account_holders",
  trip_id: "trips", booked_trip_id: "trips",
  segment_id: "segments", parent_segment_id: "segments",
  passenger_id: "passengers", lead_passenger_id: "passengers", guardian_passenger_id: "passengers",
  quote_id: "quotes", accepted_quote_id: "quotes", parent_quote_id: "quotes",
  invoice_id: "invoices", parent_invoice_id: "invoices",
  booking_id: "bookings",
  crew_member_id: "crew",
  manufacturer_id: "manufacturers",
  document_id: "documents", scan_document_id: "documents", report_document_id: "documents", pdf_document_id: "documents", contract_document_id: "documents", management_agreement_document_id: "documents",
  source_empty_leg_id: "empty_legs",
}

export interface FkLabel {
  label: string
  to?: string
}

/** Looks up only the collections this record references. */
export function useFkLabels(row: Record<string, unknown> | undefined): (field: string, id: string) => FkLabel | null {
  const { can } = useAuth()
  const needed = new Set<string>()
  if (row) {
    for (const [k, v] of Object.entries(row)) {
      const src = FK_SOURCE[k]
      if (src && typeof v === "string" && v) needed.add(src)
    }
  }
  const sources = [...needed].map((k) => SOURCES[k]!).filter((s) => s && (s.permission === "" || can(s.permission)))
  const results = useQueries({
    queries: sources.map((s) => ({
      queryKey: [s.key, "fk-labels"],
      queryFn: () => api.get<Page<Record<string, unknown>> | Record<string, unknown>[]>(`${s.endpoint}${s.bare ? "" : qs({ page_size: 200 })}`),
      staleTime: 60_000,
    })),
  })

  const byId = new Map<string, FkLabel>()
  sources.forEach((s, i) => {
    const data = results[i]?.data
    const rows = Array.isArray(data) ? data : data && "items" in data ? data.items : []
    for (const r of rows as Record<string, unknown>[]) {
      const id = str(r.id)
      if (id) byId.set(`${s.key}:${id}`, { label: s.label(r) || id.slice(0, 8), to: s.path ? `${s.path}/${id}` : undefined })
    }
  })

  return (field: string, id: string) => {
    const src = FK_SOURCE[field]
    return src ? (byId.get(`${src}:${id}`) ?? null) : null
  }
}
