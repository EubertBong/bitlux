/** /settings/profile -- who you are signed in as, and exactly what that lets you do. */

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { PageHeader } from "@/components/common/PageHeader"
import { useAuth } from "@/lib/auth"
import { initials, titleCase } from "@/lib/format"
import { useTheme, type Theme } from "@/lib/theme"

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2.5 last:border-b-0 sm:flex-row sm:gap-4">
      <dt className="w-40 shrink-0 text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  )
}

const THEME_LABEL: Record<Theme, string> = { light: "Light", dark: "Dark", system: "System" }

export function ProfilePage() {
  const { user } = useAuth()
  const { theme, resolvedTheme } = useTheme()
  if (!user) return null
  const byResource = new Map<string, string[]>()
  for (const p of [...user.permissions].sort()) {
    const [resource = "other", action = p] = p.split(".")
    byResource.set(resource, [...(byResource.get(resource) ?? []), action])
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Profile" description="Your account, as the API sees it." />
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center gap-3">
            <Avatar className="size-12"><AvatarFallback className="text-base">{initials(user.full_name)}</AvatarFallback></Avatar>
            <div>
              <CardTitle>{user.full_name}</CardTitle>
              <CardDescription>{user.email}</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <dl data-testid="profile-details">
              <Row label="Role"><Badge variant="secondary">{titleCase(user.role)}</Badge></Row>
              <Row label="Status">{titleCase(user.status)}</Row>
              <Row label="Timezone">{user.timezone ?? "Not set"}</Row>
              <Row label="Theme">{THEME_LABEL[theme]}{theme === "system" ? ` (currently ${resolvedTheme})` : ""}</Row>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Permissions</CardTitle>
            <CardDescription>{user.permissions.length} granted by your role. The API enforces these; the UI only hides what they forbid.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {[...byResource.entries()].map(([resource, actions]) => (
                <div key={resource} className="flex flex-wrap items-baseline gap-2 border-b py-1.5 last:border-b-0">
                  <span className="w-44 shrink-0 text-sm font-medium">{titleCase(resource)}</span>
                  <span className="flex flex-wrap gap-1">
                    {actions.map((a) => <Badge key={a} variant="outline" className="font-mono text-[10px]">{a}</Badge>)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
