import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { api } from "@/lib/api"
import { ResourceForm } from "./ResourceForm"
import { getEntity, type AnyRow, type DialogAction, type MoreAction } from "./registry"
import { invalidateEntity } from "./useEntityActions"

/** Hosts a DialogAction (a small ResourceForm that PATCHes the row or POSTs a related record). */
export function QuickActionDialog({ entity, row, action, open, onOpenChange }: { entity: string; row: AnyRow; action: DialogAction & Pick<MoreAction, "key">; open: boolean; onOpenChange: (o: boolean) => void }) {
  const cfg = getEntity(entity)
  const qc = useQueryClient()
  const run = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      const req = action.submit(values, row)
      return req.method === "patch" ? api.patch<unknown>(req.path, req.body) : api.post<unknown>(req.path, req.body)
    },
    onSuccess: () => {
      toast.success(action.success, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
      for (const key of action.refresh ?? []) void qc.invalidateQueries({ queryKey: [key] })
      onOpenChange(false)
    },
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="quick-action-dialog">
        <DialogHeader>
          <DialogTitle>{action.title}</DialogTitle>
          <DialogDescription>{action.description ?? cfg.nameOf(row)}</DialogDescription>
        </DialogHeader>
        <ResourceForm key={`${action.key}-${row.id}`} schema={action.schema} fields={action.fields} defaultValues={action.defaults(row)} onSubmit={(v) => run.mutateAsync(v)} onCancel={() => onOpenChange(false)} submitLabel={action.title} />
      </DialogContent>
    </Dialog>
  )
}
