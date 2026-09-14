/** Base URL of the API, no trailing slash. Same-site with the SPA in local dev. */
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1"

/** The demo tenant's id, used only for docs/screenshots; never assumed by app code. */
export const APP_NAME = "Bitlux CRM"
