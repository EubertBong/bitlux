import { Link } from "react-router"
import { ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * "← Back to Contacts". Always an explicit route, never history.back(): a detail
 * page reached by a deep link or a refresh has no history to go back to, and
 * history.back() there lands outside the app.
 */
export function BackLink({ to, label, className }: { to: string; label: string; className?: string }) {
  return (
    <Link
      to={to}
      className={cn("-ml-1 inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground", className)}
      data-testid="back-link"
    >
      <ArrowLeft className="size-4" aria-hidden /> Back to {label}
    </Link>
  )
}
