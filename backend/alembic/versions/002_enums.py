"""002 - Native ENUM types

Every enum in DATA_MODEL.md section 2, created as a native PostgreSQL ENUM.

Enums are append-only once shipped (DATA_MODEL 1.2): a later migration may
``ALTER TYPE ... ADD VALUE``, but a value is never renamed or removed, because
doing so would rewrite history in audit_logs.

Alembic autogenerate cannot express these, so they are raw ``op.execute``.
Table columns reference them via ``postgresql.ENUM(name=..., create_type=False)``.

Revision ID: 002
Revises: 001
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Ordered as DATA_MODEL.md section 2 lists them.
ENUMS: dict[str, tuple[str, ...]] = {
    # --- Tenancy & people ---------------------------------------------------
    "client_status": ("active", "trialing", "past_due", "suspended", "cancelled"),
    "user_role": ("owner", "admin", "broker", "ops", "finance", "read_only"),
    "user_status": ("invited", "active", "disabled", "locked"),
    "segment_type": (
        "uhnw", "corporate", "family_office", "government", "sports",
        "entertainment", "medical", "group_charter", "cargo", "broker_partner",
        "other",
    ),
    "contact_type": ("individual", "company"),
    "contact_status": ("lead", "prospect", "active", "dormant", "churned", "blocked"),
    "lead_source": (
        "referral", "website", "inbound_call", "outbound", "broker_network",
        "event", "advertising", "partner", "empty_leg_alert", "import", "other",
    ),
    "channel_type": (
        "email", "phone", "mobile", "whatsapp", "telegram", "signal", "fax",
        "website", "linkedin", "other",
    ),
    "address_type": ("billing", "home", "office", "shipping", "other"),
    "passenger_status": ("active", "inactive", "deceased"),
    "pax_relationship": (
        "self", "spouse", "partner", "child", "family", "employee", "assistant",
        "colleague", "guest", "other",
    ),
    "travel_document_type": (
        "passport", "visa", "national_id", "drivers_license", "residence_permit",
        "global_entry", "known_traveler", "crew_license", "crew_medical", "other",
    ),
    # --- Accounts & money ---------------------------------------------------
    "account_type": (
        "individual", "corporate", "family_office", "jet_card", "fractional",
        "government", "broker_partner",
    ),
    "account_status": ("pending", "active", "on_hold", "suspended", "closed"),
    "payment_terms": (
        "prepaid", "due_on_receipt", "net_7", "net_15", "net_30", "net_45",
        "net_60", "on_account",
    ),
    "payment_method": (
        "wire", "ach", "sepa", "credit_card", "check", "jet_card_debit",
        "escrow", "crypto", "other",
    ),
    "payment_status": ("pending", "cleared", "failed", "refunded", "chargeback"),
    "invoice_type": ("deposit", "balance", "full", "credit_note", "adjustment"),
    "invoice_status": (
        "draft", "issued", "sent", "partially_paid", "paid", "overdue", "void",
        "refunded", "written_off",
    ),
    "line_item_type": (
        "flight_hours", "positioning", "fuel_surcharge", "federal_excise_tax",
        "segment_fee", "international_fee", "landing_fee", "ramp_fee",
        "handling", "overflight", "customs", "catering", "ground_transport",
        "deicing", "overnight", "crew_expense", "wifi", "pet_fee",
        "peak_day_surcharge", "short_notice", "discount", "commission",
        "credit_card_fee", "other",
    ),
    # --- Fleet --------------------------------------------------------------
    "aircraft_category": (
        "piston", "turboprop", "very_light_jet", "light_jet", "midsize_jet",
        "super_midsize_jet", "heavy_jet", "ultra_long_range", "vip_airliner",
        "helicopter",
    ),
    "aircraft_status": (
        "active", "maintenance", "aog", "stored", "for_sale", "sold", "retired",
    ),
    "operator_status": (
        "prospect", "under_review", "approved", "conditional", "suspended",
        "blacklisted",
    ),
    "regulatory_part": (
        "part_91", "part_91k", "part_121", "part_135", "easa_cat", "easa_nco",
        "easa_spo", "other",
    ),
    "safety_program": (
        "argus", "wyvern", "isbao", "isbah", "acsf", "tsa_twelve_five",
        "easa_sms", "other",
    ),
    "safety_rating_level": (
        "not_rated", "argus_gold", "argus_gold_plus", "argus_platinum",
        "wyvern_registered", "wyvern_wingman", "wyvern_wingman_plus",
        "isbao_stage_1", "isbao_stage_2", "isbao_stage_3", "acsf_registered",
        "other",
    ),
    "crew_role": (
        "pic", "sic", "relief_pilot", "flight_engineer", "flight_attendant",
        "flight_nurse", "flight_physician", "ground_ops", "observer",
    ),
    "crew_status": (
        "active", "inactive", "training", "on_leave", "suspended", "terminated",
    ),
    # --- Trips --------------------------------------------------------------
    "trip_type": (
        "charter", "owner_flight", "empty_reposition", "demo",
        "maintenance_ferry", "air_ambulance", "cargo", "group",
    ),
    "trip_status": (
        "draft", "sourcing", "quoted", "confirmed", "in_progress", "completed",
        "cancelled", "archived",
    ),
    "leg_status": (
        "scheduled", "released", "boarding", "departed", "enroute", "arrived",
        "delayed", "diverted", "cancelled",
    ),
    "leg_purpose": ("revenue", "positioning", "ferry", "maintenance", "training"),
    "empty_leg_status": (
        "draft", "available", "on_hold", "booked", "expired", "cancelled",
    ),
    "empty_leg_source": (
        "manual", "operator_feed", "avinode", "email_parse", "api_partner",
    ),
    # --- Commerce -----------------------------------------------------------
    "quote_status": (
        "draft", "sent", "viewed", "negotiating", "accepted", "declined",
        "expired", "withdrawn", "superseded",
    ),
    "booking_status": (
        "pending", "confirmed", "contract_sent", "contract_signed",
        "funds_pending", "funds_received", "flown", "completed", "cancelled",
        "disputed",
    ),
    # --- Cross-cutting ------------------------------------------------------
    "document_type": (
        "contract", "charter_agreement", "quote_pdf", "invoice_pdf", "receipt",
        "passport_scan", "visa_scan", "id_scan", "insurance_certificate",
        "aoc_certificate", "ops_specification", "safety_audit_report", "w9",
        "tax_form", "catering_order", "handling_confirmation", "flight_release",
        "gendec", "weight_balance", "apis_manifest", "trip_sheet", "photo",
        "other",
    ),
    "document_status": (
        "pending", "under_review", "approved", "rejected", "expired", "superseded",
    ),
    "storage_provider": ("s3", "gcs", "azure_blob", "local"),
    "task_status": ("open", "in_progress", "blocked", "completed", "cancelled"),
    "task_priority": ("low", "normal", "high", "urgent"),
    "task_type": (
        "call", "email", "follow_up", "document_request", "document_expiry",
        "payment_chase", "quote_prep", "ops_check", "compliance_review", "other",
    ),
    "activity_type": (
        "call", "email", "meeting", "note", "sms", "whatsapp", "site_visit",
        "system",
    ),
    "activity_direction": ("inbound", "outbound", "internal"),
    "audit_action": (
        "insert", "update", "delete", "soft_delete", "restore", "login",
        "login_failed", "logout", "export", "download", "permission_change",
        "impersonate_start", "impersonate_end",
    ),
    "actor_type": (
        "user", "system", "api_key", "integration", "impersonation", "anonymous",
    ),
    # The single discriminator shared by every polymorphic association:
    # document_links, entity_tags, tasks, activities, addresses, audit_logs.
    # Adding a newly attachable entity is one ALTER TYPE ... ADD VALUE.
    "entity_type": (
        "client", "user", "segment", "contact", "passenger", "account_holder",
        "travel_document", "manufacturer", "aircraft_model", "aircraft",
        "operator", "operator_safety_rating", "crew_member", "airport", "fbo",
        "trip", "leg", "leg_passenger", "leg_crew", "empty_leg", "quote",
        "booking", "invoice", "payment", "document", "task", "activity",
    ),
}


def upgrade() -> None:
    for name, values in ENUMS.items():
        rendered = ", ".join("'%s'" % v for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({rendered})")


def downgrade() -> None:
    for name in reversed(list(ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name}")
