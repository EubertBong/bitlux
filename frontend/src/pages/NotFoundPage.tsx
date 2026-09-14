import { Link } from "react-router"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted-foreground">Nothing lives at this address.</p>
      <Button asChild className="mt-6"><Link to="/">Back to dashboard</Link></Button>
    </div>
  )
}
