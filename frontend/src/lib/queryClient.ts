import { QueryClient } from "@tanstack/react-query"
import { ApiError } from "./api"

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => {
          // Never retry auth/permission/not-found; the answer will not change.
          if (err instanceof ApiError && [401, 403, 404, 422].includes(err.status)) return false
          return count < 2
        },
      },
    },
  })
}

export const queryClient = makeQueryClient()
