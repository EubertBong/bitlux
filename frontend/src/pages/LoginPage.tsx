import * as React from "react"
import { Navigate, useLocation, useNavigate } from "react-router"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plane } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { FullPageSpinner, useAuth } from "@/lib/auth"

const schema = z.object({
  email: z.string().trim().min(3, "Enter your email").email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
  clientSlug: z.string().trim().optional(),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? "/"
  const [serverError, setServerError] = React.useState<string | null>(null)
  const [needsSlug, setNeedsSlug] = React.useState(false)
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "", clientSlug: "" } })

  if (status === "loading") return <FullPageSpinner />
  if (status === "authenticated") return <Navigate to="/" replace />

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null)
    try {
      await login(values.email, values.password, values.clientSlug || undefined)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setNeedsSlug(true)
        setServerError(err.message)
      } else if (err instanceof ApiError) {
        setServerError(err.message)
      } else {
        setServerError("Could not reach the server")
      }
    }
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-sidebar p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <span className="mb-2 flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Plane className="size-5" aria-hidden /></span>
          <CardTitle asChild className="text-xl"><h1>Sign in to Bitlux CRM</h1></CardTitle>
          <CardDescription>Use your brokerage account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" {...form.register("email")} aria-invalid={!!form.formState.errors.email} />
              {form.formState.errors.email && <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} aria-invalid={!!form.formState.errors.password} />
              {form.formState.errors.password && <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>}
            </div>
            {needsSlug && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="clientSlug">Organisation</Label>
                <Input id="clientSlug" placeholder="e.g. demo" {...form.register("clientSlug")} />
              </div>
            )}
            {serverError && <p role="alert" className="text-sm text-destructive">{serverError}</p>}
            <Button type="submit" disabled={form.formState.isSubmitting} className="mt-1">
              {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
