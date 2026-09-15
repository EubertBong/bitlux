import { useNavigate } from "react-router"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"

/** "← Back": history when there is some, otherwise the given list route. */
export function BackLink({ to, label = "Back" }: { to: string; label?: string }) {
  const navigate = useNavigate()
  return (
    <Button variant="ghost" size="sm" className="-ml-2 text-muted-foreground" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(to))} data-testid="back-link">
      <ArrowLeft /> {label}
    </Button>
  )
}
