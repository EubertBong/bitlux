import { useNavigate, useParams } from "react-router"
import { Card, CardContent } from "@/components/ui/card"
import { PageHeader } from "@/components/common/PageHeader"
import { ErrorState, LoadingState } from "@/components/common/States"
import { RequirePermission } from "@/lib/auth"
import { ResourceForm } from "./ResourceForm"
import { getEntity } from "./registry"
import { useCreateEntity, useEntityRecord, useUpdateEntity } from "./useEntityActions"

/** Full-page create (`/<entity>/new`) and edit (`/<entity>/:id/edit`). Save → detail; Cancel → back. */
export function EntityFormPage({ entity, mode }: { entity: string; mode: "create" | "edit" }) {
  const cfg = getEntity(entity)
  const { id } = useParams()
  const navigate = useNavigate()
  const record = useEntityRecord<{ id: string }>(entity, mode === "edit" ? id : undefined)
  const create = useCreateEntity<{ id: string }>(entity)
  const update = useUpdateEntity<{ id: string }>(entity)
  const back = () => (window.history.length > 1 ? navigate(-1) : navigate(cfg.path))
  const permission = `${cfg.permissionPrefix}.${mode === "edit" ? "edit" : "create"}`

  const onSubmit = async (v: Record<string, unknown>) => {
    const row = mode === "edit" ? await update.mutateAsync({ id: id!, payload: cfg.form.toPayload(v, "edit") }) : await create.mutateAsync(cfg.form.toPayload(v, "create"))
    navigate(`${cfg.path}/${row.id}`)
  }

  const title = mode === "edit" ? (record.data ? `Edit ${cfg.nameOf(record.data)}` : `Edit ${cfg.label.toLowerCase()}`) : `New ${cfg.label.toLowerCase()}`
  return (
    <RequirePermission permission={permission}>
      <div className="mx-auto max-w-3xl">
        <PageHeader title={title} description={mode === "edit" ? "Changes are audited." : `Creates a ${cfg.label.toLowerCase()} in your tenant.`} />
        <Card>
          <CardContent>
            {mode === "edit" && record.isPending ? <LoadingState /> : mode === "edit" && record.isError ? <ErrorState error={record.error} onRetry={() => void record.refetch()} /> : (
              <ResourceForm
                key={mode === "edit" ? `${id}:${(record.data as { updated_at?: string } | undefined)?.updated_at ?? ""}` : "create"}
                schema={cfg.form.schema}
                fields={cfg.form.fields}
                defaultValues={mode === "edit" && record.data ? cfg.form.fromRecord(record.data) : cfg.form.defaults}
                onSubmit={onSubmit}
                onCancel={back}
                submitLabel={mode === "edit" ? "Save changes" : `Create ${cfg.label.toLowerCase()}`}
                footer="page"
              />
            )}
          </CardContent>
        </Card>
      </div>
    </RequirePermission>
  )
}
