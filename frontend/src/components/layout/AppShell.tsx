import * as React from "react"
import { Link, NavLink, Outlet, useNavigate } from "react-router"
import { LogOut, Menu, Plane, Shield, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { GlobalSearch } from "@/components/GlobalSearch/GlobalSearch"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { useAuth } from "@/lib/auth"
import { initials, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"
import { visibleGroups, type NavGroup } from "./nav"

function NavList({ groups, onNavigate }: { groups: NavGroup[]; onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary" className="flex flex-col gap-5 px-3">
      {groups.map((g) => (
        <div key={g.label}>
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-sidebar-muted uppercase">{g.label}</div>
          <ul className="flex flex-col gap-0.5">
            {g.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-sidebar-foreground/85 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                      isActive && "bg-sidebar-accent text-sidebar-foreground font-medium",
                    )
                  }
                >
                  <item.icon className="size-4 shrink-0" aria-hidden />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 px-6 py-5 text-sidebar-foreground">
      <span className="flex size-8 items-center justify-center rounded-lg bg-white/10">
        <Plane className="size-4" aria-hidden />
      </span>
      <span className="text-base font-semibold tracking-tight">Bitlux CRM</span>
    </Link>
  )
}

function UserMenu() {
  const { user, logout, can } = useAuth()
  const navigate = useNavigate()
  if (!user) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 px-2" aria-label="User menu">
          <Avatar className="size-7">
            <AvatarFallback>{initials(user.full_name)}</AvatarFallback>
          </Avatar>
          <span className="hidden text-sm sm:inline">{user.full_name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <div className="text-sm font-medium">{user.full_name}</div>
          <div className="text-xs text-muted-foreground">{user.email}</div>
          <div className="mt-1 text-xs text-muted-foreground">Role: {titleCase(user.role)}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/settings/profile")} data-testid="menu-profile">
          <UserRound /> Profile
        </DropdownMenuItem>
        {can("users.view") && (
          <DropdownMenuItem onSelect={() => navigate("/admin/users")} data-testid="menu-admin">
            <Shield /> Admin
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout().then(() => navigate("/login"))} data-testid="menu-signout">
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function AppShell() {
  const { can } = useAuth()
  const groups = React.useMemo(() => visibleGroups(can), [can])
  const mobileItems = React.useMemo(() => groups.flatMap((g) => g.items).filter((i) => i.mobile).slice(0, 5), [groups])
  const [sheetOpen, setSheetOpen] = React.useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="hidden h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground lg:flex" data-testid="sidebar">
        <Brand />
        {/* Issue 1: the only scroller in the sidebar, with the hover-only thin scrollbar. */}
        <div className="sidebar-scroll min-h-0 flex-1 pb-6" data-testid="sidebar-scroll">
          <NavList groups={groups} />
        </div>
      </aside>

      <div className="flex h-screen min-w-0 flex-1 flex-col">
        {/* Issue 3: real vertical padding and a separator; not sticky any more because <main> is the scroller. */}
        <header className="z-30 flex shrink-0 items-center gap-3 border-b bg-background/95 px-4 py-3 shadow-xs backdrop-blur sm:px-6" data-testid="topbar">
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 bg-sidebar p-0 text-sidebar-foreground">
              <SheetHeader className="p-0">
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <Brand />
              </SheetHeader>
              <div className="sidebar-scroll min-h-0 flex-1 pb-6">
                <NavList groups={groups} onNavigate={() => setSheetOpen(false)} />
              </div>
            </SheetContent>
          </Sheet>
          <div className="min-w-0 flex-1">
            <GlobalSearch />
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>

        {/* Issue 2: main scrolls on its own; the sidebar background is never revealed. */}
        <main className="min-h-0 flex-1 overflow-y-auto px-4 pt-6 pb-24 sm:px-6 lg:pb-8" data-testid="main">
          <Outlet />
        </main>

        <nav aria-label="Mobile" className="fixed inset-x-0 bottom-0 z-30 flex border-t bg-background lg:hidden">
          {mobileItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn("flex flex-1 flex-col items-center gap-1 py-2 text-[11px] text-muted-foreground", isActive && "text-primary")
              }
            >
              <item.icon className="size-5" aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
