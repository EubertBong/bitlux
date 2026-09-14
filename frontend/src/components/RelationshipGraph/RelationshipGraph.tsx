/**
 * The relationship visualiser: nodes and edges from /graph/{entity}/{id}, laid
 * out by a d3-force simulation and rendered as SVG by React.
 *
 * Division of labour: d3 owns the numbers (simulation, zoom transform, drag),
 * React owns the DOM. Each simulation tick bumps a counter (throttled to one
 * per animation frame) so React re-reads node positions; zoom is applied as a
 * transform on the inner <g>; drag behaviours are bound to the node groups
 * React rendered, keyed by node id, so re-renders do not lose them.
 *
 * SVG is used up to the backend's 200-node cap; that is comfortably within
 * SVG's budget for this many elements, so there is no second renderer to keep
 * in step. Canvas can be added behind the same data preparation if the cap
 * ever rises.
 */

import * as React from "react"
import { useNavigate } from "react-router"
import { drag as d3drag, type D3DragEvent } from "d3-drag"
import { select } from "d3-selection"
import "d3-transition" // augments Selection with .transition()
import { zoom as d3zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior, type ZoomTransform } from "d3-zoom"
import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api"
import { titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"
import { EdgeLabel } from "./EdgeLabel"
import { GraphControls } from "./GraphControls"
import { NodeTooltip } from "./NodeTooltip"
import { nodeColor } from "./nodeColors"
import { nodeIcon } from "./nodeIcons"
import { boundingBox, createSimulation, nodeRadius, prepareGraph, type SimEdge, type SimNode } from "./simulation"
import { useGraphData, type GraphDepth } from "./useGraphData"

export interface RelationshipGraphProps {
  entityType: string
  entityId: string
  initialDepth?: GraphDepth
  /** Minimum height in px (defaults to 600, per the brief). */
  minHeight?: number
  className?: string
  /** Override navigation on node click (tests, embeds). */
  onNavigate?: (url: string) => void
}

const LABEL_MAX = 18
function truncate(s: string, n = LABEL_MAX): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}

/** Route path for a node: the API's url uses table names, routes use dashes. */
export function nodeRoute(url: string): string {
  return url.replace(/_/g, "-")
}

function useContainerWidth<T extends HTMLElement>(fallback = 800): [React.RefObject<T | null>, number] {
  const ref = React.useRef<T | null>(null)
  const [width, setWidth] = React.useState(fallback)
  React.useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      const w = el.clientWidth
      if (w > 0) setWidth(w)
    }
    measure()
    if (typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width]
}

export function RelationshipGraph({ entityType, entityId, initialDepth = 1, minHeight = 600, className, onNavigate }: RelationshipGraphProps) {
  const navigate = useNavigate()
  const [depth, setDepth] = React.useState<GraphDepth>(initialDepth)
  const [hiddenTypes, setHiddenTypes] = React.useState<ReadonlySet<string>>(() => new Set())
  const query = useGraphData(entityType, entityId, depth)
  const [containerRef, width] = useContainerWidth<HTMLDivElement>()
  const height = minHeight
  const svgRef = React.useRef<SVGSVGElement | null>(null)
  const layerRef = React.useRef<SVGGElement | null>(null)
  const zoomRef = React.useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [transform, setTransform] = React.useState<ZoomTransform>(zoomIdentity)
  const [, setTick] = React.useState(0)
  const [hovered, setHovered] = React.useState<SimNode | null>(null)
  const [focusedId, setFocusedId] = React.useState<string | null>(null)
  const positionsRef = React.useRef<Map<string, SimNode>>(new Map())
  // Simulation ticks and drag events arrive from d3's timers; never let one
  // schedule a React update after this component has unmounted.
  const mountedRef = React.useRef(true)
  React.useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])
  const bump = React.useCallback(() => {
    if (mountedRef.current) setTick((t) => t + 1)
  }, [])

  // ---- data -> simulation nodes (memoised on data + filter)
  const prepared = React.useMemo(() => {
    if (!query.data) return null
    return prepareGraph(query.data, entityId, hiddenTypes, positionsRef.current)
  }, [query.data, entityId, hiddenTypes])

  // ---- simulation lifecycle
  React.useEffect(() => {
    if (!prepared) return
    const positions = positionsRef.current
    const sim = createSimulation(prepared.nodes, prepared.edges, width, height)
    let raf: number | null = null
    sim.on("tick", () => {
      if (raf !== null) return
      raf = requestAnimationFrame(() => {
        raf = null
        bump()
      })
    })
    sim.on("end", () => {
      for (const n of prepared.nodes) positions.set(n.id, n)
    })
    return () => {
      sim.stop()
      if (raf !== null) cancelAnimationFrame(raf)
      for (const n of prepared.nodes) positions.set(n.id, n)
    }
  }, [prepared, width, height, bump])

  // ---- zoom / pan
  React.useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const behaviour = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .filter((event: Event) => {
        // Let plain wheel scroll the page; zoom with ctrl/cmd+wheel, drag, and buttons.
        if (event.type === "wheel") return (event as WheelEvent).ctrlKey || (event as WheelEvent).metaKey
        return !(event as MouseEvent).button
      })
      .on("zoom", (event: D3ZoomEvent<SVGSVGElement, unknown>) => setTransform(event.transform))
    select(svg).call(behaviour)
    zoomRef.current = behaviour
    return () => {
      select(svg).on(".zoom", null)
      zoomRef.current = null
    }
  }, [])

  // ---- drag, bound to the node groups React rendered (keyed by id)
  React.useEffect(() => {
    const layer = layerRef.current
    if (!layer || !prepared) return
    const behaviour = d3drag<SVGGElement, SimNode>()
      // d3's default filter plus "the event came from a window": d3-drag reads
      // event.view.document to suppress text selection, and synthetic events
      // (test environments) carry view === null.
      .filter((event: MouseEvent | TouchEvent) => !("button" in event && event.button) && !event.ctrlKey && event.view !== null)
      .on("start", (event: D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        if (!event.active) event.sourceEvent?.stopPropagation?.()
        d.fx = d.x
        d.fy = d.y
      })
      .on("drag", (event: D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        d.fx = event.x
        d.fy = event.y
        bump()
      })
      .on("end", (_event, d) => {
        d.fx = null
        d.fy = null
      })
    // Bind each node's datum to the <g> React rendered for it. Not a d3 data join:
    // React owns element creation, and a keyed join would evaluate the key on
    // elements that have no datum yet.
    const byId = new Map(prepared.nodes.map((n) => [n.id, n]))
    layer.querySelectorAll<SVGGElement>("g[data-node]").forEach((el) => {
      const node = byId.get(el.dataset.node ?? "")
      if (node) select<SVGGElement, SimNode>(el).datum(node).call(behaviour)
    })
  }, [prepared, bump])

  // ---- controls
  const zoomBy = (k: number) => {
    if (svgRef.current && zoomRef.current) select(svgRef.current).transition().duration(200).call(zoomRef.current.scaleBy, k)
  }
  const resetView = () => {
    if (svgRef.current && zoomRef.current) select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, zoomIdentity)
  }
  const fitView = () => {
    if (!prepared || !svgRef.current || !zoomRef.current) return
    const bb = boundingBox(prepared.nodes)
    if (!bb) return
    const w = bb.x1 - bb.x0
    const h = bb.y1 - bb.y0
    const legendRoom = 44 // keep the bottom row of nodes clear of the legend overlay
    const usable = height - legendRoom
    const k = Math.max(0.2, Math.min(4, 0.92 / Math.max(w / width, h / usable)))
    const t = zoomIdentity.translate(width / 2 - (k * (bb.x0 + bb.x1)) / 2, usable / 2 - (k * (bb.y0 + bb.y1)) / 2).scale(k)
    select(svgRef.current).transition().duration(400).call(zoomRef.current.transform, t)
  }
  const toggleType = (t: string) =>
    setHiddenTypes((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })

  const go = (n: SimNode) => (onNavigate ?? navigate)(nodeRoute(n.url))

  // ---- render states
  const ariaLabel = `Relationship graph for ${titleCase(entityType)} ${entityId}`
  const showEdgeLabels = (prepared?.edges.length ?? 0) <= 60 && transform.k >= 0.6

  if (query.isPending) {
    return (
      <div className={cn("w-full", className)} style={{ minHeight }} data-testid="graph-loading" role="status" aria-label="Loading relationship graph">
        <div className="mb-3 flex gap-2">
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-9 w-24" />
          <Skeleton className="ml-auto h-9 w-36" />
        </div>
        <Skeleton className="w-full rounded-xl" style={{ height: minHeight - 48 }} />
      </div>
    )
  }

  if (query.isError) {
    const err = query.error
    const tooLarge = err instanceof ApiError && err.code === "graph_too_large"
    return (
      <div className={cn("flex w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed text-center", className)} style={{ minHeight }} role="alert" data-testid="graph-error">
        <p className="font-medium">Graph unavailable</p>
        <p className="max-w-md text-sm text-muted-foreground">{err instanceof Error ? err.message : "Unknown error"}</p>
        <div className="flex gap-2">
          {tooLarge && depth === 2 && (
            <Button variant="outline" onClick={() => setDepth(1)}>Back to depth 1</Button>
          )}
          <Button onClick={() => void query.refetch()} data-testid="graph-retry"><RefreshCw /> Retry</Button>
        </div>
      </div>
    )
  }

  const nodes = prepared?.nodes ?? []
  const edges = prepared?.edges ?? []
  const hoveredPos = hovered ? transform.apply([hovered.x ?? 0, hovered.y ?? 0]) : null

  return (
    <div className={cn("flex w-full flex-col gap-3", className)} data-testid="relationship-graph">
      <GraphControls
        depth={depth}
        onDepthChange={setDepth}
        types={prepared?.types ?? []}
        hiddenTypes={hiddenTypes}
        onToggleType={toggleType}
        onShowAllTypes={() => setHiddenTypes(new Set())}
        onZoomIn={() => zoomBy(1.4)}
        onZoomOut={() => zoomBy(1 / 1.4)}
        onReset={resetView}
        onFit={fitView}
        disabled={query.isFetching}
      />
      <div role="status" aria-live="polite" className="sr-only" data-testid="graph-status">
        Showing {nodes.length} nodes and {edges.length} edges at depth {depth}
        {prepared && prepared.hiddenCount > 0 ? `; ${prepared.hiddenCount} nodes hidden by type filter` : ""}
      </div>
      <div ref={containerRef} className={cn("relative w-full overflow-hidden rounded-xl border bg-card", query.isFetching && "opacity-70")} style={{ minHeight }}>
        <svg
          ref={svgRef}
          role="img"
          aria-label={ariaLabel}
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="block touch-none select-none"
          data-testid="graph-svg"
        >
          <defs>
            <marker id="rg-arrow" viewBox="0 -5 10 10" refX={10} refY={0} markerWidth={7} markerHeight={7} orient="auto">
              <path d="M0,-5L10,0L0,5" className="fill-muted-foreground/70" />
            </marker>
          </defs>
          <g ref={layerRef} transform={transform.toString()}>
            <g className="edges">
              {edges.map((e) => (
                <EdgeLine key={e.key} edge={e} emphasised={hovered !== null && (e.source.id === hovered.id || e.target.id === hovered.id)} />
              ))}
            </g>
            <g className="edge-labels">
              {edges.map((e) => (
                <EdgeLabel key={`${e.key}:label`} edge={e} visible={showEdgeLabels || (hovered !== null && (e.source.id === hovered.id || e.target.id === hovered.id))} />
              ))}
            </g>
            <g className="nodes">
              {nodes.map((n) => {
                const r = nodeRadius(n)
                const Icon = nodeIcon(n.type)
                const focused = focusedId === n.id
                return (
                  <g
                    key={n.id}
                    data-node={n.id}
                    data-node-type={n.type}
                    transform={`translate(${n.x ?? 0},${n.y ?? 0})`}
                    tabIndex={0}
                    role="button"
                    aria-label={`${titleCase(n.type)}: ${n.label}${n.subtitle ? `, ${n.subtitle}` : ""}. ${n.degree} connections. Press Enter to open.`}
                    className="cursor-pointer outline-none"
                    onClick={() => go(n)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        go(n)
                      }
                    }}
                    onMouseEnter={() => setHovered(n)}
                    onMouseLeave={() => setHovered((h) => (h?.id === n.id ? null : h))}
                    onFocus={() => setFocusedId(n.id)}
                    onBlur={() => setFocusedId((f) => (f === n.id ? null : f))}
                  >
                    {(focused || n.isRoot) && <circle r={r + 5} fill="none" stroke={focused ? "var(--ring)" : nodeColor(n.type)} strokeWidth={focused ? 3 : 1.5} strokeDasharray={focused ? undefined : "3 3"} opacity={0.9} />}
                    <circle r={r} fill={nodeColor(n.type)} stroke="white" strokeWidth={2} />
                    <Icon x={-r * 0.55} y={-r * 0.55} width={r * 1.1} height={r * 1.1} color="white" strokeWidth={2} aria-hidden />
                    <text y={r + 13} textAnchor="middle" fontSize={11} className="fill-foreground pointer-events-none select-none" fontWeight={n.isRoot ? 600 : 400}>
                      {truncate(n.label)}
                    </text>
                  </g>
                )
              })}
            </g>
          </g>
        </svg>
        {hovered && hoveredPos && <NodeTooltip node={hovered} x={hoveredPos[0]} y={hoveredPos[1] - nodeRadius(hovered) * transform.k} />}
        <Legend types={prepared?.types ?? []} hiddenTypes={hiddenTypes} onToggle={toggleType} />
      </div>
    </div>
  )
}

function EdgeLine({ edge, emphasised }: { edge: SimEdge; emphasised: boolean }) {
  const sx = edge.source.x ?? 0
  const sy = edge.source.y ?? 0
  const tx = edge.target.x ?? 0
  const ty = edge.target.y ?? 0
  // Stop the line at the target's radius so the arrowhead is visible.
  const dx = tx - sx
  const dy = ty - sy
  const len = Math.max(1, Math.hypot(dx, dy))
  const rT = nodeRadius(edge.target) + 3
  const ex = tx - (dx / len) * rT
  const ey = ty - (dy / len) * rT
  return (
    <line
      x1={sx}
      y1={sy}
      x2={ex}
      y2={ey}
      data-edge={edge.key}
      data-edge-type={edge.type}
      stroke={emphasised ? "var(--foreground)" : "var(--border)"}
      strokeOpacity={emphasised ? 0.9 : 1}
      strokeWidth={emphasised ? 2 : 1.4}
      markerEnd="url(#rg-arrow)"
    />
  )
}

function Legend({ types, hiddenTypes, onToggle }: { types: string[]; hiddenTypes: ReadonlySet<string>; onToggle: (t: string) => void }) {
  if (types.length === 0) return null
  return (
    <div className="absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] flex-wrap gap-1 rounded-md border bg-background/90 p-1.5 text-[11px] backdrop-blur" aria-label="Legend" data-testid="graph-legend">
      {types.map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onToggle(t)}
          aria-pressed={!hiddenTypes.has(t)}
          className={cn("flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-accent", hiddenTypes.has(t) && "opacity-40 line-through")}
        >
          <span className="inline-block size-2.5 rounded-full" style={{ background: nodeColor(t) }} />
          {titleCase(t)}
        </button>
      ))}
    </div>
  )
}
