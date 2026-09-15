/**
 * The entity registry the action primitives read from.
 *
 * `<CreateButton entity="contact" />` needs to know the endpoint, the label, the
 * permission prefix, the query key to invalidate and how to build the form. Each
 * entity module (src/entities/*.tsx) describes itself once with registerEntity();
 * the primitives never special-case an entity.
 */

import type { ZodTypeAny } from "zod"
import type { FieldValues } from "react-hook-form"
import type { LucideIcon } from "lucide-react"

/** Why a control is disabled. The wording on every disabled action button/menu item. */
export const PLANNED = "Coming in a future sprint"

export type AnyRow = { id: string; status?: string } & Record<string, unknown>

/** A confirm-then-PATCH transition, e.g. "Mark inactive". */
export interface PatchAction {
  kind: "patch"
  /** PATCH body; return null when the action does not apply to this row (item hidden). */
  body: (row: AnyRow) => Record<string, unknown> | null
  /** Alternative to a PATCH: POST to a resource-specific route (e.g. /tasks/{id}/complete). */
  post?: (row: AnyRow) => string
  title: (row: AnyRow) => string
  message: (row: AnyRow) => string
  destructive?: boolean
  success: string
}

/** A small form (ResourceForm) whose submit PATCHes the row or POSTs somewhere. */
export interface DialogAction {
  kind: "dialog"
  title: string
  description?: string
  schema: ZodTypeAny
  fields: FieldDef[]
  defaults: (row: AnyRow) => FieldValues
  submit: (values: FieldValues, row: AnyRow) => { method: "patch" | "post"; path: string; body: Record<string, unknown> }
  success: string
  /** Query keys to refresh besides the entity's own (e.g. ["payments"]). */
  refresh?: string[]
}

/** An external link (mailto:, tel:) or an internal route. */
export interface LinkAction {
  kind: "link"
  href?: (row: AnyRow) => string | null
  to?: (row: AnyRow) => string
}

/** Not implemented: rendered disabled with the PLANNED hint. */
export interface PlannedAction {
  kind: "planned"
  reason?: string
}

export type MoreAction = { key: string; label: string; icon: LucideIcon; permission: string; hidden?: (row: AnyRow) => boolean } & (PatchAction | DialogAction | LinkAction | PlannedAction)

/** A related collection shown as a section on the detail page, with an optional "+ Add" form. */
export interface SectionSpec {
  key: string
  title: string
  icon?: LucideIcon
  /** GET path returning an array (or a Page). */
  list: (id: string) => string
  permission: string
  columns: { key: string; label: string; kind?: "text" | "date" | "datetime" | "money" | "status" | "link"; to?: (row: AnyRow) => string }[]
  empty: string
  add?: {
    label: string
    permission: string
    schema: ZodTypeAny
    fields: FieldDef[]
    defaults: FieldValues
    /** Build the POST body; the parent id is available. */
    body: (values: FieldValues, parentId: string) => Record<string, unknown>
    post: (parentId: string) => string
    success: string
  } | { label: string; permission: string; planned: true }
}

export interface FieldOption {
  value: string
  label: string
}

export interface OptionsState {
  options: FieldOption[]
  isLoading?: boolean
  /** The current user may not list the source (e.g. no segments.view): hide the field. */
  unavailable?: boolean
}

export type FieldType = "text" | "email" | "tel" | "number" | "textarea" | "select" | "checkbox" | "date" | "datetime" | "json"

export interface FieldDef {
  name: string
  label: string
  type?: FieldType
  placeholder?: string
  description?: string
  /** Static options for a select. */
  options?: FieldOption[]
  /** Dynamic options for a select. Must be a stable hook (called inside a component per field). */
  useOptions?: () => OptionsState
  /** Allow clearing a select back to "none". */
  allowEmpty?: boolean
  emptyLabel?: string
  /** Grid columns the field spans (of 2). */
  span?: 1 | 2
  /** Only show when this predicate holds for the current values. */
  when?: (values: FieldValues) => boolean
  autoFocus?: boolean
}

export interface EntityForm<TRow, TValues extends FieldValues> {
  schema: ZodTypeAny
  fields: FieldDef[]
  defaults: TValues
  /** Row from the API → form values (edit). */
  fromRecord: (row: TRow) => TValues
  /** Form values → API payload (create: full body; edit: PATCH body). */
  toPayload: (values: TValues, mode: "create" | "edit") => Record<string, unknown>
  /** Row → form values for a copy (defaults to fromRecord with " (copy)" appended by the caller). */
  duplicate?: (row: TRow) => TValues
}

export interface EntityConfig<TRow extends { id: string } = { id: string }, TValues extends FieldValues = FieldValues> {
  /** "contact" */
  kind: string
  /** "Contact" / "Contacts" */
  label: string
  plural: string
  /** API collection, e.g. "/contacts". */
  endpoint: string
  /** Route base, e.g. "/contacts". */
  path: string
  /** Root TanStack Query key for this collection, e.g. "contacts". */
  queryKey: string
  /** RBAC prefix: `${prefix}.create|edit|delete|view`. */
  permissionPrefix: string
  /** Graph node type, so graph caches can be refreshed after a write. */
  graphType?: string
  nameOf: (row: TRow) => string
  icon?: LucideIcon
  /** Status enum values, when the entity has a `status` column (filters, badges). */
  statuses?: readonly string[]
  /** A reversible "archive" status transition, when the entity has one. */
  archive?: { status: string; label?: string; describe?: (row: TRow) => string }
  /** Create/edit form. Absent = create/edit/duplicate are disabled with the PLANNED hint. */
  form?: EntityForm<TRow, TValues>
  /** The API has no writes for this resource (audit log, roles): delete is disabled too. */
  readOnly?: boolean
  /** Entity-specific "⋯ More" actions on the detail page. */
  moreActions?: MoreAction[]
  /** Related collections on the detail page. */
  sections?: SectionSpec[]
  /** Fields to hide from the generic details card. */
  hideFields?: string[]
}

const REGISTRY = new Map<string, EntityConfig>()

export function registerEntity<TRow extends { id: string }, TValues extends FieldValues>(cfg: EntityConfig<TRow, TValues>): EntityConfig<TRow, TValues> {
  REGISTRY.set(cfg.kind, cfg as unknown as EntityConfig)
  return cfg
}

export function getEntity(kind: string): EntityConfig {
  const cfg = REGISTRY.get(kind)
  if (!cfg) throw new Error(`Unknown entity "${kind}". Did you import "@/entities"?`)
  return cfg
}

export function listEntities(): EntityConfig[] {
  return [...REGISTRY.values()]
}
