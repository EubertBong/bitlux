"""003 - Shared reference catalog

DATA_MODEL.md 1.3 and 3.3 / 3.4: manufacturers, aircraft_models, airports, fbos.

These four tables are shared reference data with tenant overrides, so
``client_id`` is NULLABLE:

    client_id IS NULL   -> global catalog row, readable by every tenant,
                           written only by the platform (seeded in 015).
    client_id = <tenant> -> tenant-private row (a bespoke type, a private
                           strip, a custom FBO).

Uniqueness therefore uses ``UNIQUE NULLS NOT DISTINCT`` (PG15+) so that a tenant
adding its own 'KJFK' does not collide with the global one -- with the default
NULLS DISTINCT the global rows would never conflict with each other either, and
duplicate global airports could be inserted freely.

FK ordering note
----------------
``clients`` and ``users`` are created in migration 004, so ``client_id``,
``created_by`` and ``updated_by`` are created here as bare uuid columns and
their FK constraints are attached at the end of 004. The build order
(reference catalog before tenancy) is fixed by the project plan; this is the
only clean way to honour it.

Revision ID: 003
Revises: 002
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import (
    CITEXT,
    grant_app_dml,
    JSONB,
    money,
    pgenum,
    std_cols,
    std_indexes,
    tsv,
    UUID,
)

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared-catalog tables predate clients/users: no FKs on the standard columns yet.
CATALOG = dict(client_nullable=True, with_client_fk=False, with_user_fks=False)


def upgrade() -> None:
    # ---------------------------------------------------------------- manufacturers
    op.create_table(
        "manufacturers",
        *std_cols(**CATALOG),
        sa.Column("name", sa.Text(), nullable=False),           # 'Gulfstream Aerospace'
        sa.Column("short_name", sa.Text(), nullable=True),      # 'Gulfstream'
        sa.Column("code", CITEXT(), nullable=True),             # 'GLF'
        sa.Column("country_code", sa.CHAR(2), nullable=True),   # ISO 3166-1 alpha-2
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("founded_year", sa.SmallInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        comment="Aircraft manufacturers. DATA_MODEL.md 3.3.",
    )
    std_indexes("manufacturers")
    op.create_index(
        "uq_manufacturers_client_name",
        "manufacturers",
        ["client_id", sa.text("lower(name)")],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_manufacturers_name", "manufacturers", [sa.text("lower(name)")])

    # -------------------------------------------------------------- aircraft_models
    op.create_table(
        "aircraft_models",
        *std_cols(**CATALOG),
        sa.Column(
            "manufacturer_id",
            UUID,
            sa.ForeignKey("manufacturers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),            # 'G650ER'
        sa.Column("family", sa.Text(), nullable=True),           # 'G650'
        sa.Column("icao_type_code", sa.Text(), nullable=True),   # 'GLF6'
        sa.Column("category", pgenum("aircraft_category"), nullable=False),
        sa.Column("max_passengers", sa.SmallInteger(), nullable=True),
        sa.Column("typical_passengers", sa.SmallInteger(), nullable=True),
        sa.Column("range_nm", sa.Integer(), nullable=True),
        sa.Column("cruise_speed_kt", sa.Integer(), nullable=True),
        sa.Column("max_altitude_ft", sa.Integer(), nullable=True),
        sa.Column("baggage_capacity_cuft", sa.Integer(), nullable=True),
        sa.Column("cabin_length_in", sa.Numeric(6, 1), nullable=True),
        sa.Column("cabin_width_in", sa.Numeric(6, 1), nullable=True),
        sa.Column("cabin_height_in", sa.Numeric(6, 1), nullable=True),
        sa.Column("has_lavatory", sa.Boolean(), nullable=True),
        sa.Column("has_enclosed_lavatory", sa.Boolean(), nullable=True),
        sa.Column("wifi_available", sa.Boolean(), nullable=True),
        sa.Column(
            "cabin_crew_standard", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        # Market reference band, not a quotable price.
        sa.Column("hourly_rate_low_cents", money(), nullable=True),
        sa.Column("hourly_rate_high_cents", money(), nullable=True),
        sa.Column("production_start_year", sa.SmallInteger(), nullable=True),
        sa.Column("production_end_year", sa.SmallInteger(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "hourly_rate_low_cents IS NULL OR hourly_rate_high_cents IS NULL "
            "OR hourly_rate_high_cents >= hourly_rate_low_cents",
            name="ck_aircraft_models_rate_band",
        ),
        comment="Aircraft types. DATA_MODEL.md 3.3.",
    )
    std_indexes("aircraft_models")
    op.create_index(
        "uq_aircraft_models_client_mfr_name",
        "aircraft_models",
        ["client_id", "manufacturer_id", sa.text("lower(name)")],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_aircraft_models_cat_pax", "aircraft_models", ["category", "max_passengers"])
    op.create_index("ix_aircraft_models_icao", "aircraft_models", ["icao_type_code"])
    op.create_index("ix_aircraft_models_mfr", "aircraft_models", ["manufacturer_id"])
    # "can it fly KTEB->EGGW nonstop?"
    op.create_index("ix_aircraft_models_cat_range", "aircraft_models", ["category", "range_nm"])

    # -------------------------------------------------------------------- airports
    op.create_table(
        "airports",
        *std_cols(**CATALOG),
        sa.Column("icao_code", sa.CHAR(4), nullable=True),
        sa.Column("iata_code", sa.CHAR(3), nullable=True),
        sa.Column("local_code", sa.Text(), nullable=True),       # FAA LID etc.
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("country_code", sa.CHAR(2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        # `location` is added below -- see the ALTER, it is a generated `point`.
        sa.Column("elevation_ft", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=False),        # IANA
        sa.Column("longest_runway_ft", sa.Integer(), nullable=True),
        sa.Column("has_customs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_towered", sa.Boolean(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("slot_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("curfew", JSONB(), nullable=True),             # { start, end, exceptions }
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "search_tsv",
            sa.dialects.postgresql.TSVECTOR(),
            sa.Computed(tsv("name", "city", "icao_code", "iata_code"), persisted=True),
            nullable=True,
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_airports_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_airports_longitude"),
        comment="Airports. DATA_MODEL.md 3.4.",
    )
    # Core PostgreSQL `point`, NOT PostGIS geography -- PostGIS is unavailable in
    # local dev (DATA_MODEL 1.6). SQLAlchemy has no POINT type, so this is raw DDL.
    # `point(float8, float8)` and the numeric->float8 cast are both IMMUTABLE,
    # which a STORED generated column requires.
    op.execute(
        "ALTER TABLE airports ADD COLUMN location point "
        "GENERATED ALWAYS AS (point(longitude::float8, latitude::float8)) STORED"
    )
    std_indexes("airports")
    op.create_index(
        "uq_airports_client_icao",
        "airports",
        ["client_id", "icao_code"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("icao_code IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_airports_iata",
        "airports",
        ["iata_code"],
        postgresql_where=sa.text("iata_code IS NOT NULL"),
    )
    # Planar prefilter only -- exact great-circle distance is computed in the
    # application. See DATA_MODEL 1.6 for why `<->` must never be shown to a user.
    op.execute("CREATE INDEX ix_airports_location ON airports USING GIST (location)")
    op.create_index(
        "ix_airports_search", "airports", ["search_tsv"], postgresql_using="gin"
    )
    op.create_index("ix_airports_country_active", "airports", ["country_code", "is_active"])

    # ------------------------------------------------------------------------ fbos
    op.create_table(
        "fbos",
        *std_cols(**CATALOG),
        sa.Column(
            "airport_id", UUID, sa.ForeignKey("airports.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),  # 'Signature', 'Atlantic'
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("unicom_frequency", sa.Text(), nullable=True),
        sa.Column("address_line", sa.Text(), nullable=True),
        sa.Column("fuel_brand", sa.Text(), nullable=True),
        sa.Column("has_customs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hours_of_operation", sa.Text(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        comment="Fixed-base operators (ground handling). DATA_MODEL.md 3.4.",
    )
    std_indexes("fbos")
    op.create_index(
        "uq_fbos_client_airport_name",
        "fbos",
        ["client_id", "airport_id", sa.text("lower(name)")],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_fbos_airport", "fbos", ["airport_id"])
    op.create_index(
        "ix_fbos_preferred",
        "fbos",
        ["client_id"],
        postgresql_where=sa.text("is_preferred AND deleted_at IS NULL"),
    )

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml("manufacturers", "aircraft_models", "airports", "fbos")


def downgrade() -> None:
    # Reverse FK dependency order: fbos -> airports, aircraft_models -> manufacturers.
    op.drop_table("fbos")
    op.drop_table("airports")
    op.drop_table("aircraft_models")
    op.drop_table("manufacturers")
