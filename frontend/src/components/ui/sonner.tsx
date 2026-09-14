import { Toaster as Sonner, type ToasterProps } from "sonner"
import { useTheme } from "@/lib/theme"

function Toaster(props: ToasterProps) {
  return <Sonner position="bottom-right" richColors closeButton className="toaster group" {...props} />
}

/** Toaster that follows the app theme (must render inside <ThemeProvider>). */
function ThemedToaster(props: ToasterProps) {
  const { resolvedTheme } = useTheme()
  return <Toaster theme={resolvedTheme} {...props} />
}

export { Toaster, ThemedToaster }
