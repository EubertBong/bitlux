import type { LucideIcon } from "lucide-react"
import {
  Building,
  Building2,
  CalendarCheck,
  CheckSquare,
  FileText,
  FolderOpen,
  IdCard,
  LayoutDashboard,
  MapPin,
  Plane,
  PlaneTakeoff,
  Receipt,
  Route,
  ScrollText,
  Shield,
  UserCog,
  UserRound,
  Users,
} from "lucide-react"

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Permission key required to see the item; null = everyone. */
  permission: string | null
  /** Show in the mobile bottom tab bar. */
  mobile?: boolean
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "CRM",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, permission: null, mobile: true },
      { to: "/clients", label: "Clients", icon: Building2, permission: "clients.view", mobile: true },
      { to: "/contacts", label: "Contacts", icon: Users, permission: "contacts.view", mobile: true },
      { to: "/passengers", label: "Passengers", icon: UserRound, permission: "passengers.view" },
    ],
  },
  {
    label: "Fleet",
    items: [
      { to: "/aircraft", label: "Aircraft", icon: Plane, permission: "aircraft.view" },
      { to: "/operators", label: "Operators", icon: Building, permission: "operators.view" },
      { to: "/airports", label: "Airports", icon: MapPin, permission: "airports.view" },
      { to: "/crew", label: "Crew", icon: IdCard, permission: "crew.view" },
    ],
  },
  {
    label: "Trips",
    items: [
      { to: "/trips", label: "Trips", icon: Route, permission: "trips.view", mobile: true },
      { to: "/empty-legs", label: "Empty legs", icon: PlaneTakeoff, permission: "empty_legs.view" },
    ],
  },
  {
    label: "Commerce",
    items: [
      { to: "/quotes", label: "Quotes", icon: FileText, permission: "quotes.view" },
      { to: "/bookings", label: "Bookings", icon: CalendarCheck, permission: "bookings.view" },
      { to: "/invoices", label: "Invoices", icon: Receipt, permission: "invoices.view" },
      { to: "/documents", label: "Documents", icon: FolderOpen, permission: "documents.view" },
      { to: "/tasks", label: "Tasks", icon: CheckSquare, permission: "tasks.view", mobile: true },
    ],
  },
  {
    label: "Admin",
    items: [
      { to: "/admin/users", label: "Users", icon: UserCog, permission: "users.view" },
      { to: "/admin/roles", label: "Roles", icon: Shield, permission: "users.view" },
      { to: "/admin/audit-log", label: "Audit log", icon: ScrollText, permission: "audit.view" },
    ],
  },
]

export function visibleGroups(can: (permission: string) => boolean): NavGroup[] {
  return NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => i.permission === null || can(i.permission)) })).filter(
    (g) => g.items.length > 0,
  )
}
