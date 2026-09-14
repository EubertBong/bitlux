import type { SimEdge } from "./simulation"

/** Edge label at the midpoint, rotated to follow the edge but never upside down. */
export function EdgeLabel({ edge, visible }: { edge: SimEdge; visible: boolean }) {
  if (!visible) return null
  const sx = edge.source.x ?? 0
  const sy = edge.source.y ?? 0
  const tx = edge.target.x ?? 0
  const ty = edge.target.y ?? 0
  const mx = (sx + tx) / 2
  const my = (sy + ty) / 2
  let angle = (Math.atan2(ty - sy, tx - sx) * 180) / Math.PI
  if (angle > 90 || angle < -90) angle += 180
  return (
    <text
      transform={`translate(${mx},${my}) rotate(${angle})`}
      dy={-4}
      textAnchor="middle"
      className="pointer-events-none fill-muted-foreground select-none"
      fontSize={9}
      data-edge-label={edge.type}
    >
      {edge.label}
    </text>
  )
}
