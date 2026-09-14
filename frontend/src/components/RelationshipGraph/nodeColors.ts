/** One colour per entity type, grouped by domain so the legend reads as a system. */
export const NODE_COLORS: Record<string, string> = {
  client: "#1e293b",
  user: "#475569",
  segment: "#7c3aed",
  contact: "#2563eb",
  contact_channel: "#60a5fa",
  passenger: "#0891b2",
  travel_document: "#22d3ee",
  account_holder: "#0f766e",
  manufacturer: "#a16207",
  aircraft_model: "#ca8a04",
  aircraft: "#d97706",
  operator: "#ea580c",
  operator_safety_rating: "#fb923c",
  crew_member: "#9a3412",
  airport: "#65a30d",
  fbo: "#84cc16",
  trip: "#dc2626",
  leg: "#f87171",
  empty_leg: "#be123c",
  quote: "#db2777",
  quote_line_item: "#f472b6",
  booking: "#c026d3",
  invoice: "#059669",
  invoice_line_item: "#34d399",
  payment: "#10b981",
  document: "#6b7280",
  task: "#4f46e5",
  activity: "#818cf8",
}

export const DEFAULT_NODE_COLOR = "#94a3b8"

export function nodeColor(type: string): string {
  return NODE_COLORS[type] ?? DEFAULT_NODE_COLOR
}
