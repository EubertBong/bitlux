import { Navigate } from "react-router"
import { useAuth } from "@/lib/auth"

/** Placeholder for a future OAuth/OIDC redirect target. Today it just lands you home. */
export function AuthCallbackPage() {
  const { status } = useAuth()
  if (status === "loading") return null
  return <Navigate to={status === "authenticated" ? "/" : "/login"} replace />
}
