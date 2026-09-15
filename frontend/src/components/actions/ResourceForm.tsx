/**
 * A form built from a Zod schema plus field metadata (labels, kinds, options).
 *
 * Client-side validation comes from the schema; server-side 422s are mapped back
 * onto the fields they name (FastAPI's ["body", "<field>"] locs). Anything the
 * server rejects that has no field on screen is toasted instead of swallowed.
 */

import * as React from "react"
import { Controller, useForm, type DefaultValues, type FieldValues, type Path, type Resolver } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import type { z, ZodTypeAny } from "zod"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { fieldErrorsFrom, toastError } from "@/lib/errors"
import { cn } from "@/lib/utils"
import type { FieldDef } from "./registry"

const NONE = "__none__"

export interface ResourceFormProps<V extends FieldValues> {
  /** A z.object(...) whose inferred type is V. Typed loosely so entity configs can be stored in one registry. */
  schema: ZodTypeAny
  fields: FieldDef[]
  defaultValues: V
  /** Edit: the current record's values (re-applied when they change). */
  values?: V
  onSubmit: (values: V) => Promise<unknown> | unknown
  onCancel?: () => void
  submitLabel?: string
  cancelLabel?: string
  /** "dialog" right-aligns the footer; "page" puts it under a rule. */
  footer?: "dialog" | "page"
  formId?: string
  className?: string
}

function SelectControl({ field, value, onChange, invalid, id }: { field: FieldDef; value: string; onChange: (v: string) => void; invalid: boolean; id: string }) {
  const dynamic = field.useOptions?.()
  const options = field.options ?? dynamic?.options ?? []
  if (dynamic?.unavailable) return <p className="text-xs text-muted-foreground">Not available for your role.</p>
  return (
    <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? "" : v)} disabled={dynamic?.isLoading}>
      <SelectTrigger id={id} aria-invalid={invalid || undefined} className="w-full" data-testid={`field-${field.name}`}>
        <SelectValue placeholder={dynamic?.isLoading ? "Loading…" : field.placeholder ?? "Select…"} />
      </SelectTrigger>
      <SelectContent>
        {(field.allowEmpty ?? true) && <SelectItem value={NONE}>{field.emptyLabel ?? "—"}</SelectItem>}
        {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

export function ResourceForm<V extends FieldValues>({ schema, fields, defaultValues, values, onSubmit, onCancel, submitLabel = "Save", cancelLabel = "Cancel", footer = "dialog", formId, className }: ResourceFormProps<V>) {
  // The registry erases the schema's generic; re-attach V here so handleSubmit hands back V.
  const resolver = zodResolver(schema as unknown as z.ZodType<V, z.ZodTypeDef, V>) as unknown as Resolver<V>
  const form = useForm<V>({ resolver, defaultValues: defaultValues as DefaultValues<V>, values })
  const { register, control, handleSubmit, formState, setError, watch } = form
  const current = watch()
  const names = React.useMemo(() => new Set(fields.map((f) => f.name)), [fields])

  const submit = handleSubmit(async (v) => {
    try {
      await onSubmit(v)
    } catch (err) {
      const serverErrors = fieldErrorsFrom(err)
      const unmapped: string[] = []
      for (const [name, message] of Object.entries(serverErrors)) {
        if (names.has(name)) setError(name as Path<V>, { type: "server", message })
        else unmapped.push(`${name}: ${message}`)
      }
      if (Object.keys(serverErrors).length === 0) toastError(err)
      else if (unmapped.length) toast.error("Some fields were rejected", { description: unmapped.join(" · ") })
    }
  })

  const errorOf = (name: string): string | undefined => {
    const e = (formState.errors as Record<string, { message?: unknown } | undefined>)[name]
    return typeof e?.message === "string" ? e.message : undefined
  }

  return (
    <form id={formId} onSubmit={(e) => void submit(e)} className={cn("flex flex-col gap-4", className)} noValidate data-testid="resource-form">
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((field) => {
          if (field.when && !field.when(current)) return null
          const id = `f-${field.name}`
          const error = errorOf(field.name)
          const type = field.type ?? "text"
          const wrap = (control: React.ReactNode, inline = false) => (
            <div key={field.name} className={cn("flex flex-col gap-1.5", (field.span ?? 1) === 2 && "sm:col-span-2", inline && "flex-row items-center gap-2 pt-6")}>
              {!inline && <Label htmlFor={id}>{field.label}</Label>}
              {control}
              {inline && <Label htmlFor={id} className="font-normal">{field.label}</Label>}
              {field.description && !error && <p className="text-xs text-muted-foreground">{field.description}</p>}
              {error && <p role="alert" className="text-xs text-destructive" data-testid={`error-${field.name}`}>{error}</p>}
            </div>
          )
          switch (type) {
            case "checkbox":
              return wrap(<Controller control={control} name={field.name as Path<V>} render={({ field: f }) => <Checkbox id={id} checked={Boolean(f.value)} onChange={(e) => f.onChange(e.target.checked)} onBlur={f.onBlur} ref={f.ref} />} />, true)
            case "select":
              return wrap(<Controller control={control} name={field.name as Path<V>} render={({ field: f }) => <SelectControl field={field} id={id} value={String(f.value ?? "")} onChange={f.onChange} invalid={Boolean(error)} />} />)
            case "textarea":
            case "json":
              return wrap(<Textarea id={id} placeholder={field.placeholder} aria-invalid={Boolean(error) || undefined} className={type === "json" ? "font-mono text-xs" : undefined} {...register(field.name as Path<V>)} />)
            case "datetime":
              return wrap(<Input id={id} type="datetime-local" aria-invalid={Boolean(error) || undefined} {...register(field.name as Path<V>)} />)
            default:
              return wrap(<Input id={id} type={type === "date" ? "date" : type} placeholder={field.placeholder} autoFocus={field.autoFocus} aria-invalid={Boolean(error) || undefined} {...register(field.name as Path<V>, type === "number" ? { valueAsNumber: true } : undefined)} />)
          }
        })}
      </div>
      <div className={cn("flex items-center gap-2", footer === "dialog" ? "justify-end" : "justify-end border-t pt-4")}>
        {onCancel && <Button type="button" variant="outline" onClick={onCancel} disabled={formState.isSubmitting}>{cancelLabel}</Button>}
        <Button type="submit" disabled={formState.isSubmitting} data-testid="submit-button">
          {formState.isSubmitting && <Loader2 className="animate-spin" />} {submitLabel}
        </Button>
      </div>
    </form>
  )
}
