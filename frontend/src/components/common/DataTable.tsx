import { flexRender, getCoreRowModel, useReactTable, type ColumnDef, type OnChangeFn, type RowSelectionState, type SortingState, type VisibilityState } from "@tanstack/react-table"
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { LoadingState } from "./States"

export interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[]
  data: T[]
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  sorting?: SortingState
  onSortingChange?: OnChangeFn<SortingState>
  isLoading?: boolean
  emptyMessage?: string
  getRowId?: (row: T) => string
  columnVisibility?: VisibilityState
  onColumnVisibilityChange?: OnChangeFn<VisibilityState>
  rowSelection?: RowSelectionState
  onRowSelectionChange?: OnChangeFn<RowSelectionState>
}

/** Server-driven TanStack table: sorting and pagination are reported up, not computed here. */
export function DataTable<T>({ columns, data, total, page, pageSize, onPageChange, sorting = [], onSortingChange, isLoading, emptyMessage = "Nothing to show", getRowId, columnVisibility, onColumnVisibilityChange, rowSelection, onRowSelectionChange }: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility: columnVisibility ?? {}, rowSelection: rowSelection ?? {} },
    onSortingChange,
    onColumnVisibilityChange,
    onRowSelectionChange,
    enableRowSelection: Boolean(onRowSelectionChange),
    manualSorting: true,
    manualPagination: true,
    getCoreRowModel: getCoreRowModel(),
    getRowId,
  })
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)

  if (isLoading && data.length === 0) return <LoadingState />

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => {
                  const sortable = h.column.getCanSort() && onSortingChange
                  const dir = h.column.getIsSorted()
                  const cls = (h.column.columnDef.meta as { className?: string } | undefined)?.className
                  return (
                    <TableHead key={h.id} className={cn(cls)}>
                      {h.isPlaceholder ? null : sortable ? (
                        <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={h.column.getToggleSortingHandler()} aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}>
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {dir === "asc" ? <ArrowUp className="size-3.5" /> : dir === "desc" ? <ArrowDown className="size-3.5" /> : <ArrowUpDown className="size-3.5 opacity-40" />}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">{emptyMessage}</TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} data-testid="table-row" data-state={row.getIsSelected() ? "selected" : undefined}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className={cn((cell.column.columnDef.meta as { className?: string } | undefined)?.className)}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-sm text-muted-foreground" data-testid="pagination">
        <span>
          {from}–{to} of {total}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page"><ChevronLeft /></Button>
          <span aria-live="polite">Page {page} of {pageCount}</span>
          <Button variant="outline" size="icon-sm" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount} aria-label="Next page"><ChevronRight /></Button>
        </div>
      </div>
    </div>
  )
}
