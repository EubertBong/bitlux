"""013 - Triggers

Three concerns, all of them things the application must not be trusted to
remember:

1. ``updated_at`` maintenance on every table that has the column.
2. Polymorphic reference validation -- the integrity PostgreSQL cannot give us
   as a foreign key (DATA_MODEL 5, "Polymorphism").
3. ``audit_logs`` immutability, enforced even against the table owner.

Revision ID: 013
Revises: 012
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table with an updated_at column (i.e. everything except audit_logs).
TIMESTAMPED_TABLES: tuple[str, ...] = (
    # 003 reference catalog
    "manufacturers", "aircraft_models", "airports", "fbos",
    # 004 tenancy
    "clients", "users",
    # 005 CRM spine
    "segments", "contacts", "contact_channels", "addresses", "passengers",
    "account_holders", "account_holder_passengers", "travel_documents",
    # 006 fleet
    "operators", "operator_safety_ratings", "aircraft",
    "aircraft_operator_assignments",
    # 007 crew
    "crew_members",
    # 008 trips
    "trips", "legs", "leg_passengers", "leg_crew",
    # 009 empty legs
    "empty_legs",
    # 010 commerce
    "quotes", "quote_line_items", "bookings", "invoices", "invoice_line_items",
    "payments",
    # 011 cross-cutting
    "documents", "document_links", "tasks", "activities", "tags", "entity_tags",
)

# entity_type enum value -> table name.
ENTITY_TABLES: dict[str, str] = {
    "client": "clients",
    "user": "users",
    "segment": "segments",
    "contact": "contacts",
    "passenger": "passengers",
    "account_holder": "account_holders",
    "travel_document": "travel_documents",
    "manufacturer": "manufacturers",
    "aircraft_model": "aircraft_models",
    "aircraft": "aircraft",
    "operator": "operators",
    "operator_safety_rating": "operator_safety_ratings",
    "crew_member": "crew_members",
    "airport": "airports",
    "fbo": "fbos",
    "trip": "trips",
    "leg": "legs",
    "leg_passenger": "leg_passengers",
    "leg_crew": "leg_crew",
    "empty_leg": "empty_legs",
    "quote": "quotes",
    "booking": "bookings",
    "invoice": "invoices",
    "payment": "payments",
    "document": "documents",
    "task": "tasks",
    "activity": "activities",
}

# Tables whose client_id may be NULL (global reference rows) -- a tenant is
# allowed to point at those.
SHARED_CATALOG = {"manufacturers", "aircraft_models", "airports", "fbos"}

# (table, type column, id column) for every polymorphic association.
POLYMORPHIC_TABLES: tuple[tuple[str, str, str], ...] = (
    ("addresses", "owner_type", "owner_id"),
    ("document_links", "entity_type", "entity_id"),
    ("entity_tags", "entity_type", "entity_id"),
    ("tasks", "entity_type", "entity_id"),
    ("activities", "entity_type", "entity_id"),
)


def _entity_table_case() -> str:
    arms = "\n".join(
        f"            WHEN '{value}' THEN '{table}'"
        for value, table in ENTITY_TABLES.items()
    )
    return f"CASE p_entity_type\n{arms}\n        END"


def upgrade() -> None:
    # ------------------------------------------------------------- updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION trg_set_updated_at() IS "
        "'Maintains updated_at. DATA_MODEL.md 1.1 -- the column is trigger-maintained "
        "so a direct SQL fix cannot silently leave it stale.'"
    )
    for table in TIMESTAMPED_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER set_updated_at_{table}
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
            """
        )

    # ------------------------------------------- polymorphic reference validation
    # PostgreSQL cannot FK a column whose target table varies per row. This
    # resolves entity_type -> table and checks the row exists, is not
    # soft-deleted, and belongs to the same tenant.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION validate_polymorphic_ref(
            p_entity_type entity_type,
            p_entity_id   uuid,
            p_client_id   uuid
        ) RETURNS boolean
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
            v_table  text;
            v_exists boolean;
        BEGIN
            IF p_entity_id IS NULL OR p_entity_type IS NULL THEN
                RETURN true;
            END IF;

            v_table := {_entity_table_case()};

            IF v_table IS NULL THEN
                RETURN false;
            END IF;

            IF v_table = 'clients' THEN
                -- The tenant root has no client_id of its own.
                EXECUTE format(
                    'SELECT EXISTS(SELECT 1 FROM %I WHERE id = $1 AND deleted_at IS NULL)',
                    v_table
                ) INTO v_exists USING p_entity_id;
            ELSIF v_table IN ('manufacturers','aircraft_models','airports','fbos') THEN
                -- Shared reference catalog: a global row (client_id IS NULL) is
                -- a legitimate target for any tenant (DATA_MODEL 1.3).
                EXECUTE format(
                    'SELECT EXISTS(SELECT 1 FROM %I WHERE id = $1 '
                    'AND (client_id = $2 OR client_id IS NULL) AND deleted_at IS NULL)',
                    v_table
                ) INTO v_exists USING p_entity_id, p_client_id;
            ELSE
                EXECUTE format(
                    'SELECT EXISTS(SELECT 1 FROM %I WHERE id = $1 '
                    'AND client_id = $2 AND deleted_at IS NULL)',
                    v_table
                ) INTO v_exists USING p_entity_id, p_client_id;
            END IF;

            RETURN v_exists;
        END $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION validate_polymorphic_ref(entity_type, uuid, uuid) IS "
        "'Integrity check for polymorphic (entity_type, entity_id) pairs. "
        "DATA_MODEL.md 5 -- the trigger is the enforcement, a nightly orphan sweep "
        "is the backstop for rows soft-deleted after the fact.'"
    )

    # Column names arrive via TG_ARGV so one function serves both the
    # (entity_type, entity_id) tables and addresses' (owner_type, owner_id).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_validate_polymorphic_ref() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            v_type_col text := TG_ARGV[0];
            v_id_col   text := TG_ARGV[1];
            v_row      jsonb := to_jsonb(NEW);
            v_type     entity_type;
            v_id       uuid;
        BEGIN
            IF v_row ->> v_type_col IS NULL OR v_row ->> v_id_col IS NULL THEN
                RETURN NEW;
            END IF;

            v_type := (v_row ->> v_type_col)::entity_type;
            v_id   := (v_row ->> v_id_col)::uuid;

            IF NOT validate_polymorphic_ref(v_type, v_id, NEW.client_id) THEN
                RAISE EXCEPTION
                    '%.% -> % % not found, soft-deleted, or in another tenant',
                    TG_TABLE_NAME, v_id_col, v_type, v_id
                    USING ERRCODE = 'foreign_key_violation';
            END IF;

            RETURN NEW;
        END $$;
        """
    )
    for table, type_col, id_col in POLYMORPHIC_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER validate_polymorphic_{table}
            BEFORE INSERT OR UPDATE OF {type_col}, {id_col} ON {table}
            FOR EACH ROW EXECUTE FUNCTION
                trg_validate_polymorphic_ref('{type_col}', '{id_col}');
            """
        )

    # --------------------------------------------------- audit_logs immutability
    # Grants alone are not enough: in local dev the app connects as the table
    # owner, and an owner is exempt from its own REVOKEs on tables it owns.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_audit_logs_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only; % is not permitted', TG_OP
                USING ERRCODE = 'insufficient_privilege',
                      HINT = 'Correct a mistaken entry by appending a compensating row.';
        END $$;
        """
    )
    # Row-level triggers on a partitioned table propagate to every partition,
    # including partitions created later (PG13+).
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS trg_audit_logs_immutable()")

    for table, _type_col, _id_col in POLYMORPHIC_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS validate_polymorphic_{table} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS trg_validate_polymorphic_ref()")
    op.execute("DROP FUNCTION IF EXISTS validate_polymorphic_ref(entity_type, uuid, uuid)")

    for table in TIMESTAMPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS set_updated_at_{table} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS trg_set_updated_at()")
