import * as React from "react"
import { RefreshCw, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function LoadingState({ rows = 6, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2" data-testid="loading-state">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }: { error: unknown; onRetry?: () => void; title?: string }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div role="alert" className="flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4" data-testid="error-state">
      <div className="font-medium">{title}</div>
      <div className="text-sm text-muted-foreground">{message}</div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      )}
    </div>
  )
}

export interface EmptyStateProps {
  children?: React.ReactNode
  icon?: LucideIcon
  title?: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

/** Dashed panel. Bare children = the old one-liner; icon/title/description/action = the first-run layout. */
export function EmptyState({ children, icon: Icon, title, description, action, className }: EmptyStateProps) {
  if (!title && !Icon && !action) return <div className={cn("rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground", className)} data-testid="empty-state">{children}</div>
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-14 text-center", className)} data-testid="empty-state">
      {Icon && <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground"><Icon className="size-6" aria-hidden /></div>}
      {title && <h2 className="text-lg font-semibold">{title}</h2>}
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {children}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
