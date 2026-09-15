/** Small conversions shared by the entity modules: form strings <-> API values. */

import { format, parseISO } from "date-fns"
import { z } from "zod"
import type { FieldOption } from "@/components/actions/registry"
import { titleCase } from "@/lib/format"

export const optText = z.string().trim().max(2000).optional().or(z.literal(""))
export const reqText = (msg = "Required") => z.string().trim().min(1, msg).max(2000)
/** Number inputs report NaN when empty (valueAsNumber). */
export const optNum = z.union([z.number(), z.nan()]).optional()
export const reqNum = (msg = "Required") => z.number({ invalid_type_error: msg }).finite(msg)
export const optDate = z.string().optional().or(z.literal(""))
export const optEmail = z.string().trim().email("Enter a valid email").optional().or(z.literal(""))
export const optUuid = z.string().optional().or(z.literal(""))
export const currency = z.string().trim().length(3, "3-letter ISO code").transform((s) => s.toUpperCase())

export const nul = (s?: string | null): string | null => (s && s.trim() ? s.trim() : null)
export const numOrNull = (n?: number | null): number | null => (typeof n === "number" && Number.isFinite(n) ? n : null)
export const intOrNull = (n?: number | null): number | null => { const v = numOrNull(n); return v === null ? null : Math.round(v) }
export const toCents = (n?: number | null): number | null => { const v = numOrNull(n); return v === null ? null : Math.round(v * 100) }
export const cents = (n?: number | null): number => toCents(n) ?? 0
export const fromCents = (c?: number | null): number => (c === null || c === undefined ? NaN : c / 100)
export const numOr = (n?: number | null): number => (n === null || n === undefined ? NaN : n)
export const dateOrNull = (s?: string): string | null => (s && s.trim() ? s.slice(0, 10) : null)
export const isoOrNull = (s?: string): string | null => (s && s.trim() ? new Date(s).toISOString() : null)
export const toDateInput = (iso?: string | null): string => (iso ? iso.slice(0, 10) : "")
export const toLocalInput = (iso?: string | null): string => {
  if (!iso) return ""
  try {
    return format(parseISO(iso), "yyyy-MM-dd'T'HH:mm")
  } catch {
    return ""
  }
}
export const nowLocalInput = (): string => format(new Date(), "yyyy-MM-dd'T'HH:mm")
export const csvToList = (s?: string): string[] => (s ? s.split(",").map((x) => x.trim()).filter(Boolean) : [])
export const listToCsv = (l?: string[] | null): string => (l ?? []).join(", ")
export const upperOrNull = (s?: string): string | null => { const v = nul(s); return v ? v.toUpperCase() : null }
export const enumOptions = (values: readonly string[], labels: Record<string, string> = {}): FieldOption[] => values.map((v) => ({ value: v, label: labels[v] ?? titleCase(v) }))

export const LINE_ITEM_TYPES = ["flight_hours", "positioning", "fuel_surcharge", "federal_excise_tax", "segment_fee", "international_fee", "landing_fee", "ramp_fee", "handling", "overflight", "customs", "catering", "ground_transport", "deicing", "overnight", "crew_expense", "wifi", "pet_fee", "peak_day_surcharge", "short_notice", "discount", "commission", "credit_card_fee", "other"] as const
export const TRAVEL_DOCUMENT_TYPES = ["passport", "visa", "national_id", "drivers_license", "residence_permit", "global_entry", "known_traveler", "crew_license", "crew_medical", "other"] as const
export const CURRENCIES = ["USD", "EUR", "GBP", "CHF", "AED"] as const
