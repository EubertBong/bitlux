import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { GraphResponse } from "@/lib/types"

export type GraphDepth = 1 | 2

export function graphQueryKey(entityType: string, entityId: string, depth: GraphDepth) {
  return ["graph", entityType, entityId, depth] as const
}

/** GET /graph/{entity}/{id}?depth= -- the neighbourhood the visualiser draws. */
export function useGraphData(entityType: string, entityId: string, depth: GraphDepth): UseQueryResult<GraphResponse> {
  return useQuery({
    queryKey: graphQueryKey(entityType, entityId, depth),
    queryFn: ({ signal }) => api.get<GraphResponse>(`/graph/${entityType}/${entityId}?depth=${depth}`, signal),
    staleTime: 30_000,
  })
}
