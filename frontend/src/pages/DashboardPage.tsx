import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { Bar, BarChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/common/PageHeader"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { api, qs } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { ago, fmtDate, money, titleCase } from "@/lib/format"
import type { Activity, AgingReport, Page, Task, Trip } from "@/lib/types"

function Kpi({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4"><CardDescription>{label}</CardDescription></CardHeader>
      <CardContent className="px-4">
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { user, can } = useAuth()
  const contacts = useQuery({ queryKey: ["contacts", "count"], queryFn: () => api.get<Page<unknown>>(`/contacts${qs({ page_size: 1 })}`), enabled: can("contacts.view") })
  const upcoming = useQuery({ queryKey: ["trips", "upcoming"], queryFn: () => api.get<Page<Trip>>(`/trips/upcoming${qs({ page_size: 5 })}`), enabled: can("trips.view") })
  const queue = useQuery({ queryKey: ["tasks", "my-queue"], queryFn: () => api.get<Task[]>("/tasks/my-queue"), enabled: can("tasks.view") })
  const aging = useQuery({ queryKey: ["invoices", "ar-aging"], queryFn: () => api.get<AgingReport>("/invoices/ar-aging"), enabled: can("invoices.view") })
  const activity = useQuery({ queryKey: ["activities", "recent"], queryFn: () => api.get<Page<Activity>>(`/activities${qs({ page_size: 8, order_by: "-occurred_at" })}`), enabled: can("activities.view") })

  const agingData = aging.data ? Object.values(aging.data.buckets).map((b) => ({ bucket: b.bucket, amount: b.balance_cents / 100 })) : []
  const arTotal = aging.data ? Object.values(aging.data.buckets).reduce((n, b) => n + b.balance_cents, 0) : null

  return (
    <div>
      <PageHeader title={`Good day, ${user?.full_name.split(" ")[0] ?? ""}`} description="What needs your attention." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {can("contacts.view") && <Kpi label="Contacts" value={contacts.data?.total ?? "—"} />}
        {can("trips.view") && <Kpi label="Upcoming trips" value={upcoming.data?.total ?? "—"} hint="confirmed or in progress" />}
        {can("tasks.view") && <Kpi label="My open tasks" value={queue.data?.length ?? "—"} hint={queue.data?.some((t) => t.due_at && new Date(t.due_at) < new Date()) ? "some overdue" : undefined} />}
        {can("invoices.view") && <Kpi label="AR outstanding" value={arTotal === null ? "—" : money(arTotal)} hint={aging.data ? `as of ${fmtDate(aging.data.as_of)}` : undefined} />}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {can("tasks.view") && (
          <Card>
            <CardHeader><CardTitle>My tasks</CardTitle><CardDescription>Most urgent first</CardDescription></CardHeader>
            <CardContent>
              {queue.isPending ? <LoadingState rows={4} /> : queue.isError ? <ErrorState error={queue.error} onRetry={() => void queue.refetch()} /> : queue.data.length === 0 ? <EmptyState>Nothing in your queue</EmptyState> : (
                <ul className="flex flex-col divide-y">
                  {queue.data.slice(0, 6).map((t) => (
                    <li key={t.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                      <span className="min-w-0 truncate">{t.title}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        <Badge variant={t.priority === "urgent" || t.priority === "high" ? "warning" : "secondary"}>{t.priority}</Badge>
                        <span className="text-xs text-muted-foreground">{t.due_at ? ago(t.due_at) : "no due date"}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        )}
        {can("activities.view") && (
          <Card>
            <CardHeader><CardTitle>Recent activity</CardTitle><CardDescription>Across the brokerage</CardDescription></CardHeader>
            <CardContent>
              {activity.isPending ? <LoadingState rows={4} /> : activity.isError ? <ErrorState error={activity.error} onRetry={() => void activity.refetch()} /> : activity.data.items.length === 0 ? <EmptyState>No activity yet</EmptyState> : (
                <ul className="flex flex-col divide-y">
                  {activity.data.items.map((a) => (
                    <li key={a.id} className="py-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate">{a.subject ?? titleCase(a.activity_type)}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">{ago(a.occurred_at)}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">{titleCase(a.activity_type)} · {a.direction}</div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        )}
        {can("invoices.view") && (
          <Card>
            <CardHeader><CardTitle>AR aging</CardTitle><CardDescription>Outstanding by days past due</CardDescription></CardHeader>
            <CardContent>
              {aging.isPending ? <LoadingState rows={4} /> : aging.isError ? <ErrorState error={aging.error} onRetry={() => void aging.refetch()} /> : (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={agingData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                      <XAxis dataKey="bucket" fontSize={11} tickLine={false} axisLine={false} />
                      <YAxis fontSize={11} tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} />
                      <ChartTooltip formatter={(v) => money(Math.round(Number(v) * 100))} cursor={{ fill: "var(--accent)" }} />
                      <Bar dataKey="amount" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {can("trips.view") && (
        <Card className="mt-4">
          <CardHeader><CardTitle>Upcoming trips</CardTitle></CardHeader>
          <CardContent>
            {upcoming.isPending ? <LoadingState rows={3} /> : upcoming.isError ? <ErrorState error={upcoming.error} onRetry={() => void upcoming.refetch()} /> : upcoming.data.items.length === 0 ? <EmptyState>No upcoming trips</EmptyState> : (
              <ul className="divide-y text-sm">
                {upcoming.data.items.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-2">
                    <Link to={`/trips/${t.id}`} className="font-medium hover:underline">{t.trip_number}</Link>
                    <span className="text-muted-foreground">{fmtDate(t.departure_date)} · {t.leg_count} leg{t.leg_count === 1 ? "" : "s"} · {t.pax_count} pax</span>
                    <Badge variant="secondary">{titleCase(t.status)}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
