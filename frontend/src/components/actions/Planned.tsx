import * as React from "react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { PLANNED } from "./registry"

/**
 * Wrap a disabled control so the reason is discoverable: a tooltip on hover/focus
 * (the wrapper span receives the pointer events a disabled button drops) and the
 * same text as a `title` for assistive tech and touch.
 */
export function Planned({ reason = PLANNED, children, className }: { reason?: string; children: React.ReactNode; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={className ?? "inline-flex"} tabIndex={0} title={reason} aria-label={reason} data-testid="planned">{children}</span>
      </TooltipTrigger>
      <TooltipContent>{reason}</TooltipContent>
    </Tooltip>
  )
}
