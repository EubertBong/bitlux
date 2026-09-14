import { Filter, Maximize2, Minus, Plus, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { titleCase } from "@/lib/format"
import { nodeColor } from "./nodeColors"
import type { GraphDepth } from "./useGraphData"

export interface GraphControlsProps {
  depth: GraphDepth
  onDepthChange: (d: GraphDepth) => void
  types: string[]
  hiddenTypes: ReadonlySet<string>
  onToggleType: (type: string) => void
  onShowAllTypes: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  onFit: () => void
  disabled?: boolean
}

export function GraphControls(p: GraphControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="graph-controls">
      <Tabs value={String(p.depth)} onValueChange={(v) => p.onDepthChange(v === "2" ? 2 : 1)}>
        <TabsList aria-label="Graph depth">
          <TabsTrigger value="1" data-testid="depth-1">Depth 1</TabsTrigger>
          <TabsTrigger value="2" data-testid="depth-2">Depth 2</TabsTrigger>
        </TabsList>
      </Tabs>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" disabled={p.disabled} data-testid="type-filter">
            <Filter /> Types{p.hiddenTypes.size > 0 ? ` (${p.hiddenTypes.size} hidden)` : ""}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          <DropdownMenuLabel>Show entity types</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {p.types.map((t) => (
            <DropdownMenuCheckboxItem key={t} checked={!p.hiddenTypes.has(t)} onCheckedChange={() => p.onToggleType(t)} onSelect={(e) => e.preventDefault()} data-testid={`type-toggle-${t}`}>
              <span className="mr-2 inline-block size-2.5 rounded-full" style={{ background: nodeColor(t) }} />
              {titleCase(t)}
            </DropdownMenuCheckboxItem>
          ))}
          {p.hiddenTypes.size > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuCheckboxItem checked={false} onCheckedChange={p.onShowAllTypes} onSelect={(e) => e.preventDefault()}>
                Show all
              </DropdownMenuCheckboxItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="ml-auto flex items-center gap-1" role="group" aria-label="Zoom">
        <Button variant="outline" size="icon-sm" onClick={p.onZoomIn} aria-label="Zoom in" disabled={p.disabled}><Plus /></Button>
        <Button variant="outline" size="icon-sm" onClick={p.onZoomOut} aria-label="Zoom out" disabled={p.disabled}><Minus /></Button>
        <Button variant="outline" size="icon-sm" onClick={p.onFit} aria-label="Fit to view" disabled={p.disabled}><Maximize2 /></Button>
        <Button variant="outline" size="icon-sm" onClick={p.onReset} aria-label="Reset view" disabled={p.disabled}><RotateCcw /></Button>
      </div>
    </div>
  )
}
