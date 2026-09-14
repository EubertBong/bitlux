import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type Simulation, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force"
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types"

export interface SimNode extends SimulationNodeDatum, GraphNode {
  degree: number
  isRoot: boolean
}

export interface SimEdge extends SimulationLinkDatum<SimNode> {
  source: SimNode
  target: SimNode
  type: string
  label: string
  key: string
}

export const NODE_MIN_RADIUS = 12
export const NODE_MAX_RADIUS = 26

/** Radius grows with connections (sub-linearly), the root gets a floor of its own. */
export function nodeRadius(n: Pick<SimNode, "degree" | "isRoot">): number {
  const r = NODE_MIN_RADIUS + Math.min(NODE_MAX_RADIUS - NODE_MIN_RADIUS, Math.sqrt(n.degree) * 3)
  return n.isRoot ? Math.max(r, 22) : r
}

export interface PreparedGraph {
  nodes: SimNode[]
  edges: SimEdge[]
  types: string[]
  hiddenCount: number
}

/** Apply the type filter, compute degrees, and build mutable simulation copies. */
export function prepareGraph(data: GraphResponse, rootId: string, hiddenTypes: ReadonlySet<string>, previous?: Map<string, SimNode>): PreparedGraph {
  const visible = data.nodes.filter((n) => !hiddenTypes.has(n.type) || n.id === rootId)
  const visibleIds = new Set(visible.map((n) => n.id))
  const degree = new Map<string, number>()
  const edges: GraphEdge[] = []
  const seen = new Set<string>()
  for (const e of data.edges) {
    if (!visibleIds.has(e.from) || !visibleIds.has(e.to)) continue
    const key = `${e.from}>${e.to}:${e.type}`
    if (seen.has(key)) continue
    seen.add(key)
    edges.push(e)
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1)
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1)
  }
  const nodes: SimNode[] = visible.map((n) => {
    const prev = previous?.get(n.id)
    return { ...n, degree: degree.get(n.id) ?? 0, isRoot: n.id === rootId, x: prev?.x, y: prev?.y, vx: 0, vy: 0 }
  })
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const simEdges: SimEdge[] = edges.map((e) => ({
    source: byId.get(e.from) as SimNode,
    target: byId.get(e.to) as SimNode,
    type: e.type,
    label: e.label,
    key: `${e.from}>${e.to}:${e.type}`,
  }))
  const types = Array.from(new Set(data.nodes.map((n) => n.type))).sort()
  return { nodes, edges: simEdges, types, hiddenCount: data.nodes.length - visible.length }
}

export function createSimulation(nodes: SimNode[], edges: SimEdge[], width: number, height: number): Simulation<SimNode, SimEdge> {
  const root = nodes.find((n) => n.isRoot)
  if (root && root.x === undefined) {
    root.x = width / 2
    root.y = height / 2
  }
  return forceSimulation<SimNode>(nodes)
    .force("link", forceLink<SimNode, SimEdge>(edges).id((d) => d.id).distance((l) => 70 + nodeRadius(l.source) + nodeRadius(l.target)).strength(0.6))
    .force("charge", forceManyBody<SimNode>().strength((d) => -220 - d.degree * 12).distanceMax(600))
    .force("center", forceCenter(width / 2, height / 2).strength(0.05))
    .force("collide", forceCollide<SimNode>((d) => nodeRadius(d) + 10).iterations(2))
    .alpha(1)
    .alphaDecay(0.035)
}

export function boundingBox(nodes: SimNode[]): { x0: number; y0: number; x1: number; y1: number } | null {
  if (nodes.length === 0) return null
  let x0 = Infinity
  let y0 = Infinity
  let x1 = -Infinity
  let y1 = -Infinity
  for (const n of nodes) {
    const r = nodeRadius(n) + 24
    x0 = Math.min(x0, (n.x ?? 0) - r)
    y0 = Math.min(y0, (n.y ?? 0) - r)
    x1 = Math.max(x1, (n.x ?? 0) + r)
    y1 = Math.max(y1, (n.y ?? 0) + r)
  }
  return { x0, y0, x1, y1 }
}
