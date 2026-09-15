import { Badge } from "@/components/ui/badge"
import { titleCase } from "@/lib/format"
import type { ContactStatus } from "@/lib/types"

const VARIANT: Record<ContactStatus, "success" | "secondary" | "warning" | "destructive" | "outline"> = {
  lead: "secondary",
  prospect: "warning",
  active: "success",
  dormant: "outline",
  churned: "outline",
  blocked: "destructive",
}

export function ContactStatusBadge({ status }: { status: ContactStatus | string }) {
  return <Badge variant={VARIANT[status as ContactStatus] ?? "secondary"}>{titleCase(status)}</Badge>
}
