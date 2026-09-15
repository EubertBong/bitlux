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
  /** A reversible "archive" status transition, when the entity has one. */
  archive?: { status: string; label?: string; describe?: (row: TRow) => string }
  form: EntityForm<TRow, TValues>
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
