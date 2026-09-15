import * as React from "react"
import { useNavigate } from "react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RequirePermission } from "@/lib/auth"
import { ConfirmDialog } from "./ConfirmDialog"
import { EntityFormDialog } from "./EntityFormDialog"
import { getEntity } from "./registry"
import { useDeleteEntity } from "./useEntityActions"

type ButtonProps = React.ComponentProps<typeof Button>

export interface CreateButtonProps extends Omit<ButtonProps, "onClick"> {
  entity: string
  /** "dialog" (default) opens the form in place; "page" navigates to `/<entity>/new`. */
  mode?: "dialog" | "page"
  label?: React.ReactNode
  initialValues?: Record<string, unknown>
  onCreated?: (row: { id: string }) => void
}

export function CreateButton({ entity, mode = "dialog", label, initialValues, onCreated, ...props }: CreateButtonProps) {
  const cfg = getEntity(entity)
  const navigate = useNavigate()
  const [open, setOpen] = React.useState(false)
  return (
    <RequirePermission permission={`${cfg.permissionPrefix}.create`} fallback={null}>
      <Button onClick={() => (mode === "page" ? navigate(`${cfg.path}/new`) : setOpen(true))} data-testid={`create-${entity}`} {...props}>
        <Plus /> {label ?? `New ${cfg.label}`}
      </Button>
      {mode === "dialog" && <EntityFormDialog entity={entity} open={open} onOpenChange={setOpen} initialValues={initialValues} onSaved={onCreated} />}
    </RequirePermission>
  )
}

export interface EditButtonProps extends Omit<ButtonProps, "onClick"> {
  entity: string
  id: string
  mode?: "dialog" | "page"
  label?: React.ReactNode
  onSaved?: (row: { id: string }) => void
}

export function EditButton({ entity, id, mode = "dialog", label = "Edit", variant = "outline", onSaved, ...props }: EditButtonProps) {
  const cfg = getEntity(entity)
  const navigate = useNavigate()
  const [open, setOpen] = React.useState(false)
  return (
    <RequirePermission permission={`${cfg.permissionPrefix}.edit`} fallback={null}>
      <Button variant={variant} onClick={() => (mode === "page" ? navigate(`${cfg.path}/${id}/edit`) : setOpen(true))} data-testid={`edit-${entity}`} {...props}>
        <Pencil /> {label}
      </Button>
      {mode === "dialog" && <EntityFormDialog entity={entity} id={id} open={open} onOpenChange={setOpen} onSaved={onSaved} />}
    </RequirePermission>
  )
}

export interface DeleteButtonProps extends Omit<ButtonProps, "onClick"> {
  entity: string
  id: string
  /** Shown in the confirmation and the toast. */
  name?: string
  label?: React.ReactNode
  onDeleted?: () => void
}

/** Soft delete behind a confirmation; the success toast offers Undo for 5 seconds. */
export function DeleteButton({ entity, id, name, label = "Delete", variant = "outline", onDeleted, ...props }: DeleteButtonProps) {
  const cfg = getEntity(entity)
  const [open, setOpen] = React.useState(false)
  const del = useDeleteEntity(entity)
  return (
    <RequirePermission permission={`${cfg.permissionPrefix}.delete`} fallback={null}>
      <Button variant={variant} onClick={() => setOpen(true)} data-testid={`delete-${entity}`} {...props}>
        <Trash2 /> {label}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        destructive
        title={`Delete ${name ?? cfg.label.toLowerCase()}?`}
        message={<span>It disappears from every list and report immediately. You can <b>Undo</b> from the notification for a few seconds; the audit trail keeps the record either way.</span>}
        pending={del.isPending}
        onConfirm={() => del.mutate({ id, name }, { onSuccess: () => { setOpen(false); onDeleted?.() } })}
      />
    </RequirePermission>
  )
}
