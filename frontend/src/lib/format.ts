import { format, formatDistanceToNowStrict, parseISO } from "date-fns"

/** Money is integer minor units in the API (DATA_MODEL 1.2); format at the edge. */
export function money(cents: number | null | undefined, currency = "USD"): string {
  if (cents === null || cents === undefined) return "—"
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(cents / 100)
}

export function fmtDate(iso: string | null | undefined, pattern = "d MMM yyyy"): string {
  if (!iso) return "—"
  try {
    return format(parseISO(iso), pattern)
  } catch {
    return iso
  }
}

export function fmtDateTime(iso: string | null | undefined): string {
  return fmtDate(iso, "d MMM yyyy HH:mm")
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—"
  try {
    return formatDistanceToNowStrict(parseISO(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("")
}
