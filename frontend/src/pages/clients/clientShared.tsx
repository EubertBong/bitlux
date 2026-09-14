import { Badge } from "@/components/ui/badge"
import type { Client } from "@/lib/types"
import { titleCase } from "@/lib/format"

const STATUS_VARIANT: Record<Client["status"], "success" | "secondary" | "warning" | "destructive" | "outline"> = {
  active: "success",
  trialing: "secondary",
  past_due: "warning",
  suspended: "destructive",
  cancelled: "outline",
}

export function ClientStatusBadge({ status }: { status: Client["status"] }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{titleCase(status)}</Badge>
}

export const CLIENT_STATUSES: Client["status"][] = ["active", "trialing", "past_due", "suspended", "cancelled"]
