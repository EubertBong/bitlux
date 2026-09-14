import * as React from "react"
import { Check, Monitor, Moon, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useTheme, type Theme } from "@/lib/theme"

const OPTIONS: ReadonlyArray<{ value: Theme; label: string; icon: typeof Sun }> = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
]

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const current = OPTIONS.find((o) => o.value === theme) ?? OPTIONS[2]!
  const Icon = current.icon
  const [announcement, setAnnouncement] = React.useState("")

  const choose = (t: Theme) => {
    setTheme(t)
    setAnnouncement(`Theme set to ${OPTIONS.find((o) => o.value === t)?.label ?? t}`)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Theme: ${current.label}${theme === "system" ? ` (${resolvedTheme})` : ""}. Change theme`} data-testid="theme-toggle">
            <Icon aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {OPTIONS.map((o) => (
            <DropdownMenuItem key={o.value} onSelect={() => choose(o.value)} data-testid={`theme-${o.value}`} aria-current={theme === o.value ? "true" : undefined}>
              <o.icon aria-hidden /> {o.label}
              {theme === o.value && <Check className="ml-auto" aria-hidden />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <span role="status" aria-live="polite" className="sr-only">{announcement}</span>
    </>
  )
}
