import { Navigate, Route, Routes } from "react-router"
import { RequireAuth, RequirePermission } from "@/lib/auth"
import { AppShell } from "@/components/layout/AppShell"
import { LoginPage } from "@/pages/LoginPage"
import { AuthCallbackPage } from "@/pages/AuthCallbackPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { ClientListPage } from "@/pages/clients/ClientListPage"
import { ClientDetailPage } from "@/pages/clients/ClientDetailPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { RESOURCES, ResourceDetailPage, ResourceListPage } from "@/pages/resources"

function gated(permission: string | null, element: React.ReactNode): React.ReactNode {
  return permission ? <RequirePermission permission={permission}>{element}</RequirePermission> : element
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="clients" element={gated("clients.view", <ClientListPage />)} />
        <Route path="clients/:id" element={gated("clients.view", <ClientDetailPage />)} />
        {RESOURCES.map((r) => (
          <Route key={r.path} path={r.path} element={gated(r.permission, <ResourceListPage resource={r} />)} />
        ))}
        {RESOURCES.filter((r) => r.detail).map((r) => (
          <Route key={`${r.path}/:id`} path={`${r.path}/:id`} element={gated(r.permission, <ResourceDetailPage resource={r} />)} />
        ))}
        <Route path="admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
