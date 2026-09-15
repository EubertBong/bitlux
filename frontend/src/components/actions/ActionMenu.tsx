import * as React from "react"
import { Archive, Copy, MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth"
import { ConfirmDialog } from "./ConfirmDialog"
import { EntityFormDialog } from "./EntityFormDialog"
import { getEntity } from "./registry"
import { useArchiveEntity, useDeleteEntity, useDuplicateEntity } from "./useEntityActions"

export interface ActionMenuProps {
  entity: string
  id: string
  /** The row, when the caller has it: used for the name and the archive state. */
  row?: { id: string; status?: string }
  onDeleted?: () => void
  onSaved?: (row: { id: string }) => void
  align?: "start" | "end"
}

/** The ⋯ menu: Edit / Duplicate / Archive / Delete, each gated on its permission. */
export function ActionMenu({ entity, id, row, onDeleted, onSaved, align = "end" }: ActionMenuProps) {
  const cfg = getEntity(entity)
  const { can } = useAuth()
  const name = row ? cfg.nameOf(row) : cfg.label.toLowerCase()
  const [editOpen, setEditOpen] = React.useState(false)
  const [archiveOpen, setArchiveOpen] = React.useState(false)
  const [deleteOpen, setDeleteOpen] = React.useState(false)
  const del = useDeleteEntity(entity)
  const archive = useArchiveEntity(entity)
  const duplicate = useDuplicateEntity(entity)
  const canEdit = can(`${cfg.permissionPrefix}.edit`)
  const canCreate = can(`${cfg.permissionPrefix}.create`)
  const canDelete = can(`${cfg.permissionPrefix}.delete`)
  const canArchive = canEdit && Boolean(cfg.archive) && row?.status !== cfg.archive?.status
  if (!canEdit && !canCreate && !canDelete) return null

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${name}`} data-testid={`actions-${id}`}><MoreHorizontal /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align} className="w-44">
          {canEdit && <DropdownMenuItem onSelect={() => setEditOpen(true)}><Pencil /> Edit</DropdownMenuItem>}
          {canCreate && <DropdownMenuItem onSelect={() => duplicate.mutate({ id })}><Copy /> Duplicate</DropdownMenuItem>}
          {canArchive && <DropdownMenuItem onSelect={() => setArchiveOpen(true)}><Archive /> {cfg.archive?.label ?? "Archive"}</DropdownMenuItem>}
          {canDelete && (canEdit || canCreate || canArchive) && <DropdownMenuSeparator />}
          {canDelete && <DropdownMenuItem variant="destructive" onSelect={() => setDeleteOpen(true)}><Trash2 /> Delete</DropdownMenuItem>}
        </DropdownMenuContent>
      </DropdownMenu>
      {canEdit && <EntityFormDialog entity={entity} id={id} open={editOpen} onOpenChange={setEditOpen} onSaved={onSaved} />}
      {cfg.archive && (
        <ConfirmDialog
          open={archiveOpen}
          onOpenChange={setArchiveOpen}
          title={`Archive ${name}?`}
          message={cfg.archive.describe && row ? cfg.archive.describe(row) : <span>Status becomes <b>{cfg.archive.status}</b>. Nothing is deleted; change the status back to unarchive.</span>}
          confirmLabel="Archive"
          pending={archive.isPending}
          onConfirm={() => archive.mutate({ id, name }, { onSuccess: () => setArchiveOpen(false) })}
        />
      )}
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        destructive
        title={`Delete ${name}?`}
        message={<span>It disappears from every list and report immediately. You can <b>Undo</b> from the notification for a few seconds; the audit trail keeps the record either way.</span>}
        pending={del.isPending}
        onConfirm={() => del.mutate({ id, name }, { onSuccess: () => { setDeleteOpen(false); onDeleted?.() } })}
      />
    </>
  )
}
