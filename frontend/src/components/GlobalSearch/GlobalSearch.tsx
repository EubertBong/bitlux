import * as React from "react"
import { useNavigate } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { api, qs } from "@/lib/api"
import type { SearchHit, SearchResponse } from "@/lib/types"
import { nodeIcon } from "@/components/RelationshipGraph/nodeIcons"
import { nodeColor } from "@/components/RelationshipGraph/nodeColors"

/** Display order and labels; also the `types=` we ask the API for. */
export const SEARCH_GROUPS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "contacts", label: "Contacts" },
  { key: "passengers", label: "Passengers" },
  { key: "operators", label: "Operators" },
  { key: "aircraft", label: "Aircraft" },
  { key: "airports", label: "Airports" },
  { key: "trips", label: "Trips" },
  { key: "quotes", label: "Quotes" },
  { key: "documents", label: "Documents" },
  // Beyond the brief's eight: the catalog, so "gulf" finds Gulfstream.
  { key: "manufacturers", label: "Manufacturers" },
  { key: "aircraft_models", label: "Aircraft models" },
]

export const SEARCH_DEBOUNCE_MS = 200
const MIN_QUERY = 2

export function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = React.useState(value)
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

/** The API's hit.url uses table names; routes use dashes (aircraft_models -> aircraft-models). */
export function hitRoute(hit: SearchHit): string {
  return hit.url.replace(/_/g, "-")
}

export function GlobalSearch() {
  const [open, setOpen] = React.useState(false)
  const [q, setQ] = React.useState("")
  const debouncedQ = useDebounced(q.trim(), SEARCH_DEBOUNCE_MS)
  const navigate = useNavigate()

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const enabled = open && debouncedQ.length >= MIN_QUERY
  const { data, isFetching, isError } = useQuery({
    queryKey: ["search", debouncedQ],
    queryFn: ({ signal }) =>
      api.get<SearchResponse>(`/search${qs({ q: debouncedQ, types: SEARCH_GROUPS.map((g) => g.key).join(","), limit: 20 })}`, signal),
    enabled,
    staleTime: 30_000,
  })

  const go = (hit: SearchHit) => {
    setOpen(false)
    setQ("")
    navigate(hitRoute(hit))
  }

  const groups = SEARCH_GROUPS.map((g) => ({ ...g, hits: data?.results[g.key] ?? [] })).filter((g) => g.hits.length > 0)
  const total = groups.reduce((n, g) => n + g.hits.length, 0)

  return (
    <>
      <Button
        variant="outline"
        className="h-9 w-full max-w-md justify-start gap-2 text-muted-foreground sm:w-72"
        onClick={() => setOpen(true)}
        aria-label="Search (Ctrl+K)"
      >
        <Search className="size-4" aria-hidden />
        <span className="flex-1 text-left text-sm">Search…</span>
        <kbd className="pointer-events-none hidden rounded border bg-muted px-1.5 font-mono text-[10px] sm:inline">⌘K</kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Search contacts, passengers, operators, aircraft, airports, trips, quotes and documents">
        <CommandInput placeholder="Search everything…" value={q} onValueChange={setQ} aria-label="Search query" />
        <CommandList>
          <div role="status" aria-live="polite" className="sr-only">
            {enabled ? (isFetching ? "Searching" : `${total} results`) : ""}
          </div>
          {!enabled && <div className="py-6 text-center text-sm text-muted-foreground">Type at least {MIN_QUERY} characters</div>}
          {enabled && isError && <div className="py-6 text-center text-sm text-destructive">Search failed</div>}
          {enabled && !isError && !isFetching && total === 0 && <CommandEmpty>No results for “{debouncedQ}”</CommandEmpty>}
          {groups.map((g) => (
            <CommandGroup key={g.key} heading={g.label}>
              {g.hits.map((hit) => {
                const Icon = nodeIcon(hit.type.replace(/s$/, ""))
                return (
                  <CommandItem key={`${hit.type}:${hit.id}`} value={`${g.label} ${hit.label} ${hit.subtitle ?? ""} ${hit.id}`} onSelect={() => go(hit)} data-testid="search-hit">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-md text-white" style={{ background: nodeColor(hit.type.replace(/s$/, "")) }}>
                      <Icon className="size-3.5" aria-hidden />
                    </span>
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate">{hit.label}</span>
                      {hit.subtitle && <span className="truncate text-xs text-muted-foreground">{hit.subtitle}</span>}
                    </span>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          ))}
        </CommandList>
      </CommandDialog>
    </>
  )
}
