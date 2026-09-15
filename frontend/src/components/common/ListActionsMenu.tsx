/**
 * The list page's "⋯ Actions": Export CSV (of the rows on screen), Column chooser,
 * Refresh. All three work; nothing here is a stub.
 */

import { Columns3, Download, MoreHorizontal, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

export interface ColumnToggle {
  id: string
  label: string
  visible: boolean
  onToggle: (visible: boolean) => void
}

export function toCsv(rows: Record<string, unknown>[], columns: { id: string; label: string }[]): string {
  const esc = (v: unknown) => {
    const str = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v)
    return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str
  }
  return [columns.map((c) => esc(c.label)).join(","), ...rows.map((r) => columns.map((c) => esc(r[c.id])).join(","))].join("\n")
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function ListActionsMenu({ title, rows, columns, onRefresh }: { title: string; rows: Record<string, unknown>[]; columns: ColumnToggle[]; onRefresh?: () => void }) {
  const exportable = columns.filter((c) => c.visible)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" aria-label={`${title} list actions`} data-testid="list-actions"><MoreHorizontal /> Actions</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem
          disabled={rows.length === 0}
          onSelect={() => {
            downloadCsv(`${title.toLowerCase().replace(/\s+/g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows, exportable))
            toast.success(`Exported ${rows.length} row${rows.length === 1 ? "" : "s"}`, { description: "The rows on this page, visible columns only." })
          }}
          data-testid="export-csv"
        >
          <Download /> Export CSV ({rows.length})
        </DropdownMenuItem>
        {onRefresh && <DropdownMenuItem onSelect={onRefresh}><RefreshCw /> Refresh</DropdownMenuItem>}
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="flex items-center gap-2"><Columns3 className="size-4" /> Columns</DropdownMenuLabel>
        {columns.map((c) => (
          <DropdownMenuCheckboxItem key={c.id} checked={c.visible} onCheckedChange={(v) => c.onToggle(Boolean(v))} onSelect={(e) => e.preventDefault()} data-testid={`column-${c.id}`}>{c.label}</DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function SelectionBar({ count, onClear, children }: { count: number; onClear: () => void; children?: React.ReactNode }) {
  if (count === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 px-3 py-2 text-sm" data-testid="selection-bar" role="status">
      <span className="font-medium">{count} selected</span>
      {children}
      <Button variant="ghost" size="sm" className="ml-auto" onClick={onClear}>Clear selection</Button>
    </div>
  )
}
