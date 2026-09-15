import * as React from "react"
import { useNavigate } from "react-router"
import { Archive, Copy, Eye, MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth"
import { ConfirmDialog } from "./ConfirmDialog"
import { EntityFormDialog } from "./EntityFormDialog"
import { getEntity, PLANNED, type AnyRow } from "./registry"
import { useArchiveEntity, useDeleteEntity, useDuplicateEntity } from "./useEntityActions"

export interface ActionMenuProps {
  entity: string
  id: string
  /** The row, when the caller has it: used for the name and the archive state. */
  row?: AnyRow
  onDeleted?: () => void
  onSaved?: (row: { id: string }) => void
  align?: "start" | "end"
  /** Hide "View" (e.g. on the detail page itself). */
  hideView?: boolean
}

function PlannedHint() {
  return <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">Planned</span>
}

/**
 * The row ⋯ menu: View / Edit / Duplicate / Archive / Delete, in that order.
 * Items the API or the UI cannot do yet stay visible but disabled, with the reason.
 */
export function ActionMenu({ entity, id, row, onDeleted, onSaved, align = "end", hideView = false }: ActionMenuProps) {
  const cfg = getEntity(entity)
  const { can } = useAuth()
  const navigate = useNavigate()
  const name = row ? cfg.nameOf(row) : cfg.label.toLowerCase()
  const [editOpen, setEditOpen] = React.useState(false)
  const [archiveOpen, setArchiveOpen] = React.useState(false)
  const [deleteOpen, setDeleteOpen] = React.useState(false)
  const del = useDeleteEntity(entity)
  const archive = useArchiveEntity(entity)
  const duplicate = useDuplicateEntity(entity)
  const hasForm = Boolean(cfg.form)
  const canEdit = can(`${cfg.permissionPrefix}.edit`)
  const canCreate = can(`${cfg.permissionPrefix}.create`)
  const canDelete = can(`${cfg.permissionPrefix}.delete`)
  const archivable = Boolean(cfg.archive) && row?.status !== cfg.archive?.status
  const anyWrite = canEdit || canCreate || canDelete

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${name}`} data-testid={`actions-${id}`}><MoreHorizontal /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align} className="w-48">
          {!hideView && <DropdownMenuItem onSelect={() => navigate(`${cfg.path}/${id}`)} data-testid="menu-view"><Eye /> View</DropdownMenuItem>}
          {canEdit && (
            <DropdownMenuItem disabled={!hasForm || cfg.readOnly} title={!hasForm || cfg.readOnly ? PLANNED : undefined} onSelect={() => setEditOpen(true)} data-testid="menu-edit"><Pencil /> Edit{(!hasForm || cfg.readOnly) && <PlannedHint />}</DropdownMenuItem>
          )}
          {canCreate && (
            <DropdownMenuItem disabled={!hasForm || cfg.readOnly} title={!hasForm || cfg.readOnly ? PLANNED : undefined} onSelect={() => duplicate.mutate({ id })} data-testid="menu-duplicate"><Copy /> Duplicate{(!hasForm || cfg.readOnly) && <PlannedHint />}</DropdownMenuItem>
          )}
          {canEdit && (
            <DropdownMenuItem disabled={!archivable || cfg.readOnly} title={!cfg.archive ? PLANNED : !archivable ? "Already archived" : undefined} onSelect={() => setArchiveOpen(true)} data-testid="menu-archive"><Archive /> {cfg.archive?.label ?? "Archive"}{!cfg.archive && <PlannedHint />}</DropdownMenuItem>
          )}
          {canDelete && anyWrite && <DropdownMenuSeparator />}
          {canDelete && (
            <DropdownMenuItem variant="destructive" disabled={cfg.readOnly} title={cfg.readOnly ? PLANNED : undefined} onSelect={() => setDeleteOpen(true)} data-testid="menu-delete"><Trash2 /> Delete{cfg.readOnly && <PlannedHint />}</DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {canEdit && hasForm && <EntityFormDialog entity={entity} id={id} open={editOpen} onOpenChange={setEditOpen} onSaved={onSaved} />}
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
