/** API shapes the frontend relies on. Mirrors backend/app/schemas (subset). */

export type UUID = string
export type ISODate = string

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> }
}

export type UserRole = "owner" | "admin" | "broker" | "ops" | "finance" | "read_only"

export interface TokenPair {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

export interface Me {
  id: UUID
  client_id: UUID
  email: string
  full_name: string
  role: UserRole
  status: string
  timezone: string | null
  permissions: string[]
}

interface Stamped {
  id: UUID
  created_at: ISODate
  updated_at: ISODate
  created_by?: UUID | null
  updated_by?: UUID | null
}

export interface Client extends Stamped {
  slug: string
  name: string
  legal_name: string | null
  status: "active" | "trialing" | "past_due" | "suspended" | "cancelled"
  default_currency: string
  timezone: string
  locale: string
  billing_email: string | null
  support_email: string | null
  trip_number_prefix: string | null
}

export interface Segment extends Stamped {
  name: string
  code: string | null
  segment_type: string
  description: string | null
  parent_segment_id: UUID | null
}

export type ContactStatus = "lead" | "prospect" | "active" | "dormant" | "churned" | "blocked"

export interface Contact extends Stamped {
  client_id?: UUID | null
  segment_id: UUID | null
  contact_type: "individual" | "company"
  status: ContactStatus
  salutation?: string | null
  first_name: string | null
  middle_name?: string | null
  last_name: string | null
  suffix?: string | null
  display_name: string
  company_name: string | null
  job_title: string | null
  parent_contact_id?: UUID | null
  referred_by_contact_id?: UUID | null
  owner_user_id: UUID | null
  source?: string
  primary_email: string | null
  primary_phone: string | null
  preferred_language?: string | null
  lifetime_value_cents: number
  trip_count: number
  last_activity_at: ISODate | null
  do_not_contact?: boolean
  vip_notes?: string | null
  preferences?: Record<string, unknown>
}

export interface ContactChannel extends Stamped {
  contact_id: UUID
  channel_type: string
  value: string
  label: string | null
  is_primary: boolean
}

export interface UserLookup {
  id: UUID
  full_name: string
  role: UserRole
}

export interface Passenger extends Stamped {
  contact_id: UUID | null
  status: string
  first_name: string
  last_name: string
  nationality_code: string | null
  date_of_birth: ISODate | null
  ktn_last4: string | null
}

export interface AccountHolder extends Stamped {
  account_number: string
  name: string
  account_type: string
  status: string
  primary_contact_id: UUID
  currency: string
  payment_terms: string
  balance_cents: number
  credit_limit_cents: number
}

export interface Trip extends Stamped {
  trip_number: string
  trip_type: string
  status: string
  account_holder_id: UUID | null
  primary_contact_id: UUID | null
  pax_count: number
  leg_count: number
  departure_date: ISODate | null
  return_date: ISODate | null
  currency: string
  total_sell_cents: number
  total_cost_cents: number
  margin_cents: number | null
}

export interface Activity extends Stamped {
  activity_type: string
  direction: string
  subject: string | null
  body: string | null
  user_id: UUID | null
  contact_id: UUID | null
  occurred_at: ISODate
}

export interface Task extends Stamped {
  title: string
  task_type: string
  status: string
  priority: "low" | "normal" | "high" | "urgent"
  assigned_to_user_id: UUID | null
  due_at: ISODate | null
  entity_type: string | null
  entity_id: UUID | null
}

export interface Document extends Stamped {
  document_type: string
  status: string
  title: string
  filename: string
  mime_type: string
  byte_size: number
  expires_at: ISODate | null
}

export interface AgingBucket {
  bucket: string
  count: number
  balance_cents: number
}

export interface AgingReport {
  as_of: ISODate
  buckets: Record<string, AgingBucket>
  total_cents?: number
  overdue_cents?: number
}

export interface User extends Stamped {
  email: string
  full_name: string
  role: UserRole
  status: string
}

export interface SearchHit {
  id: UUID
  type: string
  label: string
  subtitle: string | null
  url: string
  rank: number
}

export interface SearchResponse {
  query: string
  results: Record<string, SearchHit[]>
}

export interface GraphNode {
  id: UUID
  type: string
  label: string
  subtitle: string | null
  url: string
}

export interface GraphEdge {
  from: UUID
  to: UUID
  type: string
  label: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/** A record we only know as "an object with an id and some fields" (skeleton pages). */
export type AnyRecord = Stamped & Record<string, unknown>
