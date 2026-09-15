import * as React from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ErrorState, LoadingState } from "@/components/common/States"
import { ResourceForm } from "./ResourceForm"
import { getEntity } from "./registry"
import { useCreateEntity, useEntityRecord, useUpdateEntity } from "./useEntityActions"

export interface EntityFormDialogProps {
  entity: string
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Editing an existing record. */
  id?: string
  /** Pre-filled values for a create (e.g. a duplicate, or a passenger for a known contact). */
  initialValues?: Record<string, unknown>
  onSaved?: (row: { id: string }) => void
}

/** Create or edit any registered entity in a dialog. */
export function EntityFormDialog({ entity, open, onOpenChange, id, initialValues, onSaved }: EntityFormDialogProps) {
  const cfg = getEntity(entity)
  const record = useEntityRecord<{ id: string }>(entity, open && id ? id : undefined)
  const create = useCreateEntity<{ id: string }>(entity)
  const update = useUpdateEntity<{ id: string }>(entity)
  const editing = Boolean(id)
  // The record becomes the form's defaultValues and the form is keyed on the record, so a
  // (re)load remounts it. react-hook-form's `values` prop resets registered inputs but left
  // Controller-driven selects empty in tests; a fresh mount is unambiguous.
  const initial = React.useMemo(() => (editing ? (record.data ? cfg.form.fromRecord(record.data) : undefined) : { ...cfg.form.defaults, ...initialValues }), [editing, record.data, cfg, initialValues])
  const formKey = editing ? `${id}:${(record.data as { updated_at?: string } | undefined)?.updated_at ?? ""}` : "create"

  const onSubmit = async (v: Record<string, unknown>) => {
    const row = editing ? await update.mutateAsync({ id: id!, payload: cfg.form.toPayload(v, "edit") }) : await create.mutateAsync(cfg.form.toPayload(v, "create"))
    onOpenChange(false)
    onSaved?.(row)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid={`${entity}-form-dialog`}>
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${cfg.label.toLowerCase()}` : `New ${cfg.label.toLowerCase()}`}</DialogTitle>
          <DialogDescription>{editing ? "Changes are audited." : `Creates a ${cfg.label.toLowerCase()} in your tenant.`}</DialogDescription>
        </DialogHeader>
        {editing && record.isPending ? <LoadingState rows={4} /> : editing && record.isError ? <ErrorState error={record.error} onRetry={() => void record.refetch()} /> : (
          <ResourceForm
            key={formKey}
            schema={cfg.form.schema}
            fields={cfg.form.fields}
            defaultValues={initial ?? cfg.form.defaults}
            onSubmit={onSubmit}
            onCancel={() => onOpenChange(false)}
            submitLabel={editing ? "Save changes" : `Create ${cfg.label.toLowerCase()}`}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
