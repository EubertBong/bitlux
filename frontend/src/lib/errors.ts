/** Turn API failures into something a form or a toast can show. */

import { toast } from "sonner"
import { ApiError } from "./api"

export type FieldErrors = Record<string, string>

interface ValidationItem {
  loc?: string[]
  msg?: string
}

/** 422 → { field: message }. FastAPI locs look like ["body", "primary_email"]; nested ones are joined with ".". */
export function fieldErrorsFrom(err: unknown): FieldErrors {
  if (!(err instanceof ApiError) || err.status !== 422) return {}
  const items = (err.details as { errors?: ValidationItem[] }).errors
  if (!Array.isArray(items)) return {}
  const out: FieldErrors = {}
  for (const item of items) {
    const loc = (item.loc ?? []).filter((p) => p !== "body" && p !== "query")
    const field = loc.join(".")
    if (field && !(field in out)) out[field] = item.msg ?? "Invalid value"
  }
  return out
}

export interface ErrorDescription {
  title: string
  description?: string
}

/** Human wording per status, always carrying the API's own code and message. */
export function describeError(err: unknown, fallbackTitle = "Something went wrong"): ErrorDescription {
  if (err instanceof ApiError) {
    const codeLine = `${err.code} (HTTP ${err.status})`
    switch (err.status) {
      case 403:
        return { title: err.message || "Not allowed", description: `${codeLine} · Your role lacks this permission, or the record belongs to another tenant.` }
      case 404:
        return { title: err.message || "Not found", description: `${codeLine} · It may have been deleted or never belonged to your tenant.` }
      case 422: {
        const fields = fieldErrorsFrom(err)
        const first = Object.entries(fields)[0]
        return { title: err.message || "Validation failed", description: first ? `${codeLine} · ${first[0]}: ${first[1]}` : codeLine }
      }
      case 409:
        return { title: err.message || "Conflict", description: codeLine }
      default:
        return { title: err.message || fallbackTitle, description: codeLine }
    }
  }
  if (err instanceof Error) return { title: err.message || fallbackTitle }
  return { title: fallbackTitle }
}

export function toastError(err: unknown, fallbackTitle?: string): void {
  const d = describeError(err, fallbackTitle)
  toast.error(d.title, { description: d.description })
}
