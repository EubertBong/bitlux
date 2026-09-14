import type { SimNode } from "./simulation"
import { nodeColor } from "./nodeColors"
import { titleCase } from "@/lib/format"

/** HTML tooltip positioned over the graph container (SVG cannot host rich tooltips). */
export function NodeTooltip({ node, x, y }: { node: SimNode; x: number; y: number }) {
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-20 max-w-xs -translate-x-1/2 -translate-y-full rounded-md border bg-popover px-3 py-2 text-xs shadow-md"
      style={{ left: x, top: y - 14 }}
    >
      <div className="flex items-center gap-1.5">
        <span className="inline-block size-2 rounded-full" style={{ background: nodeColor(node.type) }} />
        <span className="font-medium text-foreground">{node.label}</span>
      </div>
      {node.subtitle && <div className="mt-0.5 text-muted-foreground">{node.subtitle}</div>}
      <div className="mt-1 text-[10px] text-muted-foreground uppercase tracking-wide">
        {titleCase(node.type)} · {node.degree} connection{node.degree === 1 ? "" : "s"}
      </div>
    </div>
  )
}
