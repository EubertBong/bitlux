import { Navigate, Route, Routes } from "react-router"
import { RequireAuth, RequirePermission } from "@/lib/auth"
import { AppShell } from "@/components/layout/AppShell"
import { LoginPage } from "@/pages/LoginPage"
import { AuthCallbackPage } from "@/pages/AuthCallbackPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { ClientListPage } from "@/pages/clients/ClientListPage"
import { ClientDetailPage } from "@/pages/clients/ClientDetailPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { ProfilePage } from "@/pages/settings/ProfilePage"
import { ContactListPage } from "@/pages/contacts/ContactListPage"
import { ContactDetailPage } from "@/pages/contacts/ContactDetailPage"
import { EntityFormPage } from "@/components/actions"
import { RESOURCES, ResourceDetailPage, ResourceListPage } from "@/pages/resources"
import "@/entities"

/** Routes with a real implementation; the skeleton fallback below skips these. */
const IMPLEMENTED = new Set(["contacts"])

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
        <Route path="contacts" element={gated("contacts.view", <ContactListPage />)} />
        <Route path="contacts/new" element={gated("contacts.create", <EntityFormPage entity="contact" mode="create" />)} />
        <Route path="contacts/:id" element={gated("contacts.view", <ContactDetailPage />)} />
        <Route path="contacts/:id/edit" element={gated("contacts.edit", <EntityFormPage entity="contact" mode="edit" />)} />
        {RESOURCES.filter((r) => !IMPLEMENTED.has(r.path)).map((r) => (
          <Route key={r.path} path={r.path} element={gated(r.permission, <ResourceListPage resource={r} />)} />
        ))}
        {RESOURCES.filter((r) => r.detail && !IMPLEMENTED.has(r.path)).map((r) => (
          <Route key={`${r.path}/:id`} path={`${r.path}/:id`} element={gated(r.permission, <ResourceDetailPage resource={r} />)} />
        ))}
        <Route path="settings" element={<Navigate to="/settings/profile" replace />} />
        <Route path="settings/profile" element={<ProfilePage />} />
        <Route path="admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
