import * as React from "react"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  message: React.ReactNode
  onConfirm: () => void | Promise<unknown>
  destructive?: boolean
  confirmLabel?: string
  cancelLabel?: string
  pending?: boolean
}

/** One question, two buttons. Destructive confirms are red; the dialog stays open while pending. */
export function ConfirmDialog({ open, onOpenChange, title, message, onConfirm, destructive = false, confirmLabel = destructive ? "Delete" : "Confirm", cancelLabel = "Cancel", pending = false }: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !pending && onOpenChange(o)}>
      <DialogContent data-testid="confirm-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription asChild><div>{message}</div></DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>{cancelLabel}</Button>
          <Button type="button" variant={destructive ? "destructive" : "default"} onClick={() => void onConfirm()} disabled={pending} data-testid="confirm-button">
            {pending && <Loader2 className="animate-spin" />} {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
