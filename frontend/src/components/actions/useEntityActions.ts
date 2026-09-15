/**
 * The mutations behind every action button. Success → toast (with the entity's
 * name) + cache refresh. Errors are left to the caller: forms map 422s onto
 * fields, buttons toast (see toastError). The API writes the audit trail.
 */

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/lib/api"
import { toastError } from "@/lib/errors"
import { getEntity, type EntityConfig } from "./registry"

const UNDO_MS = 5000

/** Everything a write to this entity can have changed: its lists, its detail, graphs, search. */
export function invalidateEntity(qc: QueryClient, cfg: EntityConfig): void {
  void qc.invalidateQueries({ queryKey: [cfg.queryKey] })
  void qc.invalidateQueries({ queryKey: [cfg.endpoint] })
  void qc.invalidateQueries({ queryKey: ["graph"] })
  void qc.invalidateQueries({ queryKey: ["search"] })
  void qc.invalidateQueries({ queryKey: ["activities"] })
}

export function useEntityRecord<T extends { id: string }>(kind: string, id: string | undefined) {
  const cfg = getEntity(kind)
  return useQuery({ queryKey: [cfg.queryKey, id], queryFn: () => api.get<T>(`${cfg.endpoint}/${id}`), enabled: Boolean(id) })
}

export function useCreateEntity<T extends { id: string }>(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.post<T>(cfg.endpoint, payload),
    onSuccess: (row) => {
      toast.success(`${cfg.label} created`, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
    },
  })
}

export function useUpdateEntity<T extends { id: string }>(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => api.patch<T>(`${cfg.endpoint}/${id}`, payload),
    onSuccess: (row) => {
      toast.success(`${cfg.label} updated`, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
    },
  })
}

export function useRestoreEntity<T extends { id: string }>(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<T>(`${cfg.endpoint}/${id}/restore`),
    onSuccess: (row) => {
      toast.success(`${cfg.label} restored`, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
    },
    onError: (err) => toastError(err, `Could not restore ${cfg.label.toLowerCase()}`),
  })
}

/** Soft delete. The success toast carries an Undo action for 5 seconds (POST .../restore). */
export function useDeleteEntity(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  const restore = useRestoreEntity(kind)
  return useMutation({
    mutationFn: async ({ id }: { id: string; name?: string }) => {
      await api.delete(`${cfg.endpoint}/${id}`)
      return id
    },
    onSuccess: (id, vars) => {
      // Drop the deleted record's own queries first: refetching them would just 404.
      qc.removeQueries({ queryKey: [cfg.queryKey, id] })
      qc.removeQueries({ queryKey: [cfg.endpoint, id] })
      invalidateEntity(qc, cfg)
      toast.success(`${cfg.label} deleted`, {
        description: vars.name,
        duration: UNDO_MS,
        action: { label: "Undo", onClick: () => restore.mutate(id) },
      })
    },
    onError: (err) => toastError(err, `Could not delete ${cfg.label.toLowerCase()}`),
  })
}

/** Archive = the entity's reversible archival status (a PATCH), never a delete. */
export function useArchiveEntity<T extends { id: string }>(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string; name?: string }) => {
      if (!cfg.archive) throw new Error(`${cfg.label} has no archive status`)
      return api.patch<T>(`${cfg.endpoint}/${id}`, { status: cfg.archive.status })
    },
    onSuccess: (row) => {
      toast.success(`${cfg.label} archived`, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
    },
    onError: (err) => toastError(err, `Could not archive ${cfg.label.toLowerCase()}`),
  })
}

/** Duplicate = GET the row, run it through the form's copy transform, POST it. */
export function useDuplicateEntity<T extends { id: string }>(kind: string) {
  const cfg = getEntity(kind)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string }) => {
      const row = await api.get<T>(`${cfg.endpoint}/${id}`)
      const values = cfg.form.duplicate ? cfg.form.duplicate(row) : cfg.form.fromRecord(row)
      return api.post<T>(cfg.endpoint, cfg.form.toPayload(values, "create"))
    },
    onSuccess: (row) => {
      toast.success(`${cfg.label} duplicated`, { description: cfg.nameOf(row) })
      invalidateEntity(qc, cfg)
    },
    onError: (err) => toastError(err, `Could not duplicate ${cfg.label.toLowerCase()}`),
  })
}
