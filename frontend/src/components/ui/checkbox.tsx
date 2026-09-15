import * as React from "react"
import { cn } from "@/lib/utils"

/** Native checkbox styled to match the other inputs (no Radix dependency needed). */
const Checkbox = React.forwardRef<HTMLInputElement, Omit<React.ComponentProps<"input">, "type">>(function Checkbox({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      type="checkbox"
      data-slot="checkbox"
      className={cn("size-4 shrink-0 cursor-pointer rounded-[4px] border border-input accent-primary shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50", className)}
      {...props}
    />
  )
})

export { Checkbox }
