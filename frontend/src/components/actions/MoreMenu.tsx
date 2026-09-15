/**
 * The detail page's "⋯ More" menu: the entity's own actions (Send, Complete, Publish …).
 * Implemented ones run; planned ones are visibly disabled with the reason.
 */

import * as React from "react"
import { useNavigate } from "react-router"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { MoreHorizontal } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { toastError } from "@/lib/errors"
import { ConfirmDialog } from "./ConfirmDialog"
import { QuickActionDialog } from "./QuickActionDialog"
import { getEntity, PLANNED, type AnyRow, type DialogAction, type MoreAction, type PatchAction } from "./registry"
import { invalidateEntity } from "./useEntityActions"

export function MoreMenu({ entity, row, label = "More" }: { entity: string; row: AnyRow; label?: string }) {
  const cfg = getEntity(entity)
  const { can } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [pending, setPending] = React.useState<MoreAction | null>(null)
  const actions = (cfg.moreActions ?? []).filter((a) => !a.hidden?.(row)).filter((a) => a.kind !== "patch" || a.body(row) !== null)
  const patchRun = useMutation({
    mutationFn: async (a: PatchAction & MoreAction) => {
      if (a.post) return api.post<unknown>(a.post(row), a.body(row) ?? {})
      return api.patch<unknown>(`${cfg.endpoint}/${row.id}`, a.body(row) ?? {})
    },
    onSuccess: (_d, a) => {
      toast.success(a.success, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
      setPending(null)
    },
    onError: (e) => toastError(e),
  })
  if (actions.length === 0) return null
  const visible = actions.filter((a) => can(a.permission))
  if (visible.length === 0) return null

  const onSelect = (a: MoreAction) => {
    switch (a.kind) {
      case "patch":
      case "dialog":
        setPending(a)
        return
      case "link": {
        const href = a.href?.(row)
        if (href) window.open(href, href.startsWith("http") ? "_blank" : "_self")
        else if (a.to) navigate(a.to(row))
        return
      }
      default:
        return
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" aria-label={`${label} actions for ${cfg.nameOf(row)}`} data-testid="more-menu"><MoreHorizontal /> {label}</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuLabel>{cfg.label} actions</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {visible.map((a) => {
            const planned = a.kind === "planned" || (a.kind === "link" && !a.href?.(row) && !a.to)
            const reason = a.kind === "planned" ? (a.reason ?? PLANNED) : "Not available for this record"
            return (
              <DropdownMenuItem key={a.key} disabled={planned} onSelect={() => onSelect(a)} title={planned ? reason : undefined} data-testid={`more-${a.key}`} data-planned={planned || undefined}>
                <a.icon /> {a.label}
                {planned && <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">Planned</span>}
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
      {pending?.kind === "patch" && (
        <ConfirmDialog open onOpenChange={(o) => !o && setPending(null)} title={pending.title(row)} message={pending.message(row)} destructive={pending.destructive} confirmLabel={pending.label} pending={patchRun.isPending} onConfirm={() => patchRun.mutate(pending)} />
      )}
      {pending?.kind === "dialog" && <QuickActionDialog entity={entity} row={row} action={pending as DialogAction & MoreAction} open onOpenChange={(o) => !o && setPending(null)} />}
    </>
  )
}
