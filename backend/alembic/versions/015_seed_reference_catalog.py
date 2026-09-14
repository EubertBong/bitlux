"""015 - Seed the global reference catalog

DATA_MODEL.md 1.3: rows with ``client_id = NULL`` are the global catalog --
readable by every tenant, writable only by the platform. Tenants add their own
private rows alongside these (a bespoke interior, a private strip, a local FBO).

Identifiers are literal UUIDv7 values rather than generated at run time, for two
reasons: there is no database-side default to fall back on (DATA_MODEL 1.5), and
a fixed id means fixtures, tests and downgrade can all reference a known row.

RLS note: migration 014 applied FORCE ROW LEVEL SECURITY, which binds the table
owner too. These INSERTs write ``client_id = NULL``, which no tenant policy
permits, so the migration turns row security off for its own transaction --
the owner-only escape hatch documented in DATA_MODEL.md 1.7.

Revision ID: 015
Revises: 014
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from migration_helpers import APP_ROLE

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- Seeded row ids (see downgrade) ------------------------------------------
MANUFACTURER_IDS = [
    "01a0a008-12f4-73f1-b5af-8c64fd13b8cf",
    "01a0a008-12f4-73f1-b5af-8c78f0c7741a",
    "01a0a008-12f4-73f1-b5af-8c873bc6e5f1",
    "01a0a008-12f4-73f1-b5af-8c990d64fd7d",
    "01a0a008-12f4-73f1-b5af-8cad517949a0",
    "01a0a008-12f4-73f1-b5af-8cb29f702199",
    "01a0a008-12f4-73f1-b5af-8cce4cda25e8",
    "01a0a008-12f4-73f1-b5af-8cdec01609fc",
    "01a0a008-12f4-73f1-b5af-8ce6b0ea256b",
    "01a0a008-12f4-73f1-b5af-8cfe77361528",
]
MODEL_IDS = [
    "01a0a008-12f4-73f1-b5af-8d056b758e6b",
    "01a0a008-12f4-73f1-b5af-8d1708b142b5",
    "01a0a008-12f4-73f1-b5af-8d2e4cdf5d82",
    "01a0a008-12f4-73f1-b5af-8d3741267f60",
    "01a0a008-12f4-73f1-b5af-8d48bbcc183f",
    "01a0a008-12f4-73f1-b5af-8d569e2bbeee",
    "01a0a008-12f4-73f1-b5af-8d66bbf76674",
    "01a0a008-12f4-73f1-b5af-8d784cdb28c0",
    "01a0a008-12f4-73f1-b5af-8d846d5f71b5",
    "01a0a008-12f4-73f1-b5af-8d9b8db9a5ee",
    "01a0a008-12f4-73f1-b5af-8dab67b9d6f2",
    "01a0a008-12f4-73f1-b5af-8db07f2287da",
    "01a0a008-12f4-73f1-b5af-8dc13139a49d",
    "01a0a008-12f4-73f1-b5af-8dded984f1a0",
    "01a0a008-12f4-73f1-b5af-8de07fda251f",
    "01a0a008-12f4-73f1-b5af-8df840ba3e8a",
    "01a0a008-12f4-73f1-b5af-8e09f1118954",
    "01a0a008-12f4-73f1-b5af-8e1a51a47605",
    "01a0a008-12f4-73f1-b5af-8e2816b5f5cb",
    "01a0a008-12f4-73f1-b5af-8e3ad661f764",
    "01a0a008-12f4-73f1-b5af-8e4eb86a6252",
    "01a0a008-12f4-73f1-b5af-8e536ca30d54",
    "01a0a008-12f4-73f1-b5af-8e6dc0f4bbbe",
    "01a0a008-12f4-73f1-b5af-8e70f93ddfe8",
    "01a0a008-12f4-73f1-b5af-8e80f54f6521",
    "01a0a008-12f4-73f1-b5af-8e9231724a85",
    "01a0a008-12f4-73f1-b5af-8eaccf37235d",
]
AIRPORT_IDS = [
    "01a0a008-12f4-73f1-b5af-8eb75a388dd9",
    "01a0a008-12f4-73f1-b5af-8ecf03bb02e6",
    "01a0a008-12f4-73f1-b5af-8edd5d5f5965",
    "01a0a008-12f4-73f1-b5af-8ee3f468f8cf",
    "01a0a008-12f4-73f1-b5af-8ef3425b9ca2",
    "01a0a008-12f4-73f1-b5af-8f0034ea746d",
    "01a0a008-12f4-73f1-b5af-8f1d424fdf66",
    "01a0a008-12f4-73f1-b5af-8f2c1199cb2b",
    "01a0a008-12f4-73f1-b5af-8f38a2c5ce28",
    "01a0a008-12f4-73f1-b5af-8f406d9cda2a",
    "01a0a008-12f4-73f1-b5af-8f53bda960ba",
    "01a0a008-12f4-73f1-b5af-8f6fe91e958d",
    "01a0a008-12f4-73f1-b5af-8f77c2c7b368",
    "01a0a008-12f4-73f1-b5af-8f8c382ab208",
    "01a0a008-12f4-73f1-b5af-8f9f86df1668",
    "01a0a008-12f4-73f1-b5af-8fa46f73f34e",
    "01a0a008-12f4-73f1-b5af-8fbb9482075b",
    "01a0a008-12f4-73f1-b5af-8fc12f82be1b",
    "01a0a008-12f4-73f1-b5af-8fd2a0afddbc",
    "01a0a008-12f4-73f1-b5af-8fe594e1a2c2",
    "01a0a008-12f4-73f1-b5af-8ff3f9888c76",
    "01a0a008-12f4-73f1-b5af-900b7b4db3da",
    "01a0a008-12f4-73f1-b5af-901f63861635",
    "01a0a008-12f4-73f1-b5af-9026f83d67f2",
    "01a0a008-12f4-73f1-b5af-90394ce3116c",
    "01a0a008-12f4-73f1-b5af-904f2182e947",
    "01a0a008-12f4-73f1-b5af-9054266cb7ba",
    "01a0a008-12f4-73f1-b5af-9061cef84d48",
    "01a0a008-12f4-73f1-b5af-907d3e41cbf9",
    "01a0a008-12f4-73f1-b5af-908d34339f25",
    "01a0a008-12f4-73f1-b5af-909379110dbb",
    "01a0a008-12f4-73f1-b5af-90a6a0dc7a6c",
    "01a0a008-12f4-73f1-b5af-90be4047bca7",
    "01a0a008-12f4-73f1-b5af-90ce026fd537",
]
FBO_IDS = [
    "01a0a008-12f4-73f1-b5af-90de98aa151e",
    "01a0a008-12f4-73f1-b5af-90e4950027d4",
    "01a0a008-12f4-73f1-b5af-90fce85ac914",
    "01a0a008-12f4-73f1-b5af-9106adc3b378",
    "01a0a008-12f4-73f1-b5af-911cc7fcef76",
    "01a0a008-12f4-73f1-b5af-9125d2ec362c",
    "01a0a008-12f4-73f1-b5af-91379d9c6b68",
    "01a0a008-12f4-73f1-b5af-9145026c22a1",
    "01a0a008-12f4-73f1-b5af-915d464e5b7a",
    "01a0a008-12f4-73f1-b5af-916819228144",
    "01a0a008-12f4-73f1-b5af-9170fc90b33f",
    "01a0a008-12f4-73f1-b5af-918f20d4ea14",
    "01a0a008-12f4-73f1-b5af-919b033f3a64",
    "01a0a008-12f4-73f1-b5af-91a143065d9c",
    "01a0a008-12f4-73f1-b5af-91b07d8b7bdb",
    "01a0a008-12f4-73f1-b5af-91c7fa60e96a",
]


def _ids(values: list[str]) -> str:
    """Render a python list of uuids as a SQL IN-list."""
    return ", ".join("'%s'" % v for v in values)


def upgrade() -> None:
    # Owner-only bypass so client_id = NULL rows can be written past the
    # tenant-isolation policies. Scoped to this transaction only.
    op.execute("SET LOCAL row_security = off")

    # ------------------------------------------------------------ manufacturers
    op.execute(
        """
        INSERT INTO manufacturers
            (id, client_id, name, short_name, code, country_code, founded_year, is_active)
        VALUES
            ('01a0a008-12f4-73f1-b5af-8c64fd13b8cf', NULL, 'Gulfstream Aerospace', 'Gulfstream', 'GLF', 'US', 1958, true),
            ('01a0a008-12f4-73f1-b5af-8c78f0c7741a', NULL, 'Bombardier Aviation', 'Bombardier', 'BBD', 'CA', 1942, true),
            ('01a0a008-12f4-73f1-b5af-8c873bc6e5f1', NULL, 'Dassault Aviation', 'Dassault', 'DAS', 'FR', 1929, true),
            ('01a0a008-12f4-73f1-b5af-8c990d64fd7d', NULL, 'Textron Aviation', 'Cessna', 'TXT', 'US', 1927, true),
            ('01a0a008-12f4-73f1-b5af-8cad517949a0', NULL, 'Embraer Executive Jets', 'Embraer', 'EMB', 'BR', 1969, true),
            ('01a0a008-12f4-73f1-b5af-8cb29f702199', NULL, 'Pilatus Aircraft', 'Pilatus', 'PIL', 'CH', 1939, true),
            ('01a0a008-12f4-73f1-b5af-8cce4cda25e8', NULL, 'Airbus Corporate Jets', 'ACJ', 'ACJ', 'FR', 1970, true),
            ('01a0a008-12f4-73f1-b5af-8cdec01609fc', NULL, 'Boeing Business Jets', 'BBJ', 'BBJ', 'US', 1916, true),
            ('01a0a008-12f4-73f1-b5af-8ce6b0ea256b', NULL, 'Honda Aircraft Company', 'HondaJet', 'HDA', 'US', 2006, true),
            ('01a0a008-12f4-73f1-b5af-8cfe77361528', NULL, 'Beechcraft', 'Beechcraft', 'BEE', 'US', 1932, true)
        """
    )

    # ---------------------------------------------------------- aircraft_models
    op.execute(
        """
        INSERT INTO aircraft_models
            (id, client_id, manufacturer_id, name, family, icao_type_code, category,
             max_passengers, typical_passengers, range_nm, cruise_speed_kt,
             max_altitude_ft, baggage_capacity_cuft, has_lavatory, wifi_available,
             cabin_crew_standard)
        VALUES
            ('01a0a008-12f4-73f1-b5af-8d056b758e6b', NULL, '01a0a008-12f4-73f1-b5af-8c64fd13b8cf', 'G650ER', 'G650', 'GLF6', 'ultra_long_range', 19, 13, 7500, 516, 51000, 195, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d1708b142b5', NULL, '01a0a008-12f4-73f1-b5af-8c64fd13b8cf', 'G700', 'G700', 'G700', 'ultra_long_range', 19, 13, 7750, 516, 51000, 195, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d2e4cdf5d82', NULL, '01a0a008-12f4-73f1-b5af-8c64fd13b8cf', 'G550', 'G550', 'GLF5', 'ultra_long_range', 19, 14, 6750, 488, 51000, 170, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d3741267f60', NULL, '01a0a008-12f4-73f1-b5af-8c64fd13b8cf', 'G280', 'G280', 'G280', 'super_midsize_jet', 10, 8, 3600, 482, 45000, 154, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8d48bbcc183f', NULL, '01a0a008-12f4-73f1-b5af-8c78f0c7741a', 'Global 7500', 'Global', 'GL7T', 'ultra_long_range', 19, 14, 7700, 516, 51000, 195, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d569e2bbeee', NULL, '01a0a008-12f4-73f1-b5af-8c78f0c7741a', 'Global 6000', 'Global', 'GL6T', 'ultra_long_range', 17, 13, 6000, 513, 51000, 195, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d66bbf76674', NULL, '01a0a008-12f4-73f1-b5af-8c78f0c7741a', 'Challenger 350', 'Challenger', 'CL35', 'super_midsize_jet', 10, 9, 3200, 470, 45000, 106, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8d784cdb28c0', NULL, '01a0a008-12f4-73f1-b5af-8c78f0c7741a', 'Challenger 650', 'Challenger', 'CL60', 'heavy_jet', 12, 10, 4000, 470, 41000, 115, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8d846d5f71b5', NULL, '01a0a008-12f4-73f1-b5af-8c78f0c7741a', 'Learjet 75 Liberty', 'Learjet', 'LJ75', 'light_jet', 9, 6, 2040, 465, 51000, 50, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8d9b8db9a5ee', NULL, '01a0a008-12f4-73f1-b5af-8c873bc6e5f1', 'Falcon 8X', 'Falcon', 'FA8X', 'ultra_long_range', 16, 12, 6450, 460, 41000, 140, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8dab67b9d6f2', NULL, '01a0a008-12f4-73f1-b5af-8c873bc6e5f1', 'Falcon 7X', 'Falcon', 'FA7X', 'ultra_long_range', 16, 12, 5950, 459, 51000, 140, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8db07f2287da', NULL, '01a0a008-12f4-73f1-b5af-8c873bc6e5f1', 'Falcon 2000LXS', 'Falcon', 'F2TH', 'heavy_jet', 10, 8, 4000, 470, 47000, 131, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8dc13139a49d', NULL, '01a0a008-12f4-73f1-b5af-8c873bc6e5f1', 'Falcon 900LX', 'Falcon', 'F900', 'heavy_jet', 14, 12, 4750, 459, 51000, 127, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8dded984f1a0', NULL, '01a0a008-12f4-73f1-b5af-8c990d64fd7d', 'Citation Longitude', 'Citation', 'C700', 'super_midsize_jet', 12, 9, 3500, 483, 45000, 112, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8de07fda251f', NULL, '01a0a008-12f4-73f1-b5af-8c990d64fd7d', 'Citation Latitude', 'Citation', 'C68A', 'midsize_jet', 9, 7, 2700, 446, 45000, 100, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8df840ba3e8a', NULL, '01a0a008-12f4-73f1-b5af-8c990d64fd7d', 'Citation XLS+', 'Citation', 'C56X', 'midsize_jet', 9, 8, 2100, 441, 45000, 90, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e09f1118954', NULL, '01a0a008-12f4-73f1-b5af-8c990d64fd7d', 'Citation CJ3+', 'Citation', 'C25B', 'light_jet', 8, 6, 2040, 416, 45000, 65, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e1a51a47605', NULL, '01a0a008-12f4-73f1-b5af-8c990d64fd7d', 'Citation M2 Gen2', 'Citation', 'C25M', 'very_light_jet', 7, 5, 1550, 404, 41000, 46, true, false, false),
            ('01a0a008-12f4-73f1-b5af-8e2816b5f5cb', NULL, '01a0a008-12f4-73f1-b5af-8cad517949a0', 'Praetor 600', 'Praetor', 'E550', 'super_midsize_jet', 12, 9, 4018, 466, 45000, 155, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e3ad661f764', NULL, '01a0a008-12f4-73f1-b5af-8cad517949a0', 'Praetor 500', 'Praetor', 'E545', 'midsize_jet', 9, 7, 3340, 466, 45000, 150, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e4eb86a6252', NULL, '01a0a008-12f4-73f1-b5af-8cad517949a0', 'Phenom 300E', 'Phenom', 'E55P', 'light_jet', 10, 7, 2010, 464, 45000, 76, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e536ca30d54', NULL, '01a0a008-12f4-73f1-b5af-8cb29f702199', 'PC-24', 'PC-24', 'PC24', 'light_jet', 10, 8, 2000, 440, 45000, 90, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e6dc0f4bbbe', NULL, '01a0a008-12f4-73f1-b5af-8cb29f702199', 'PC-12 NGX', 'PC-12', 'PC12', 'turboprop', 9, 8, 1803, 290, 30000, 40, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8e70f93ddfe8', NULL, '01a0a008-12f4-73f1-b5af-8cce4cda25e8', 'ACJ320neo', 'ACJ320', 'A20N', 'vip_airliner', 25, 19, 6000, 470, 39000, 900, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8e80f54f6521', NULL, '01a0a008-12f4-73f1-b5af-8cdec01609fc', 'BBJ 737-7', 'BBJ', 'B37M', 'vip_airliner', 25, 18, 7000, 470, 41000, 900, true, true, true),
            ('01a0a008-12f4-73f1-b5af-8e9231724a85', NULL, '01a0a008-12f4-73f1-b5af-8ce6b0ea256b', 'HondaJet Elite II', 'HondaJet', 'HDJT', 'very_light_jet', 6, 5, 1547, 422, 43000, 66, true, true, false),
            ('01a0a008-12f4-73f1-b5af-8eaccf37235d', NULL, '01a0a008-12f4-73f1-b5af-8cfe77361528', 'King Air 350i', 'King Air', 'B350', 'turboprop', 11, 9, 1806, 312, 35000, 71, true, true, false)
        """
    )

    # ------------------------------------------------------------------ airports
    op.execute(
        """
        INSERT INTO airports
            (id, client_id, icao_code, iata_code, name, city, country_code,
             latitude, longitude, elevation_ft, timezone, has_customs,
             longest_runway_ft, is_active)
        VALUES
            ('01a0a008-12f4-73f1-b5af-8eb75a388dd9', NULL, 'KTEB', 'TEB', 'Teterboro Airport', 'Teterboro', 'US', 40.8501, -74.060837, 9, 'America/New_York', true, 7000, true),
            ('01a0a008-12f4-73f1-b5af-8ecf03bb02e6', NULL, 'KJFK', 'JFK', 'John F. Kennedy International Airport', 'New York', 'US', 40.639801, -73.7789, 13, 'America/New_York', true, 14511, true),
            ('01a0a008-12f4-73f1-b5af-8edd5d5f5965', NULL, 'KLGA', 'LGA', 'LaGuardia Airport', 'New York', 'US', 40.777199, -73.872597, 21, 'America/New_York', true, 7003, true),
            ('01a0a008-12f4-73f1-b5af-8ee3f468f8cf', NULL, 'KHPN', 'HPN', 'Westchester County Airport', 'White Plains', 'US', 41.066999, -73.707603, 439, 'America/New_York', true, 6549, true),
            ('01a0a008-12f4-73f1-b5af-8ef3425b9ca2', NULL, 'KVNY', 'VNY', 'Van Nuys Airport', 'Van Nuys', 'US', 34.209801, -118.489998, 802, 'America/Los_Angeles', true, 8001, true),
            ('01a0a008-12f4-73f1-b5af-8f0034ea746d', NULL, 'KLAX', 'LAX', 'Los Angeles International Airport', 'Los Angeles', 'US', 33.942501, -118.407997, 125, 'America/Los_Angeles', true, 12091, true),
            ('01a0a008-12f4-73f1-b5af-8f1d424fdf66', NULL, 'KSNA', 'SNA', 'John Wayne Airport', 'Santa Ana', 'US', 33.675701, -117.868004, 56, 'America/Los_Angeles', true, 5701, true),
            ('01a0a008-12f4-73f1-b5af-8f2c1199cb2b', NULL, 'KPBI', 'PBI', 'Palm Beach International Airport', 'West Palm Beach', 'US', 26.683201, -80.095596, 19, 'America/New_York', true, 10008, true),
            ('01a0a008-12f4-73f1-b5af-8f38a2c5ce28', NULL, 'KOPF', 'OPF', 'Miami-Opa Locka Executive Airport', 'Opa-locka', 'US', 25.907, -80.278397, 8, 'America/New_York', true, 8002, true),
            ('01a0a008-12f4-73f1-b5af-8f406d9cda2a', NULL, 'KMIA', 'MIA', 'Miami International Airport', 'Miami', 'US', 25.7932, -80.290604, 8, 'America/New_York', true, 13016, true),
            ('01a0a008-12f4-73f1-b5af-8f53bda960ba', NULL, 'KFLL', 'FLL', 'Fort Lauderdale-Hollywood International Airport', 'Fort Lauderdale', 'US', 26.072599, -80.152702, 9, 'America/New_York', true, 9000, true),
            ('01a0a008-12f4-73f1-b5af-8f6fe91e958d', NULL, 'KLAS', 'LAS', 'Harry Reid International Airport', 'Las Vegas', 'US', 36.083999, -115.153702, 2181, 'America/Los_Angeles', true, 14515, true),
            ('01a0a008-12f4-73f1-b5af-8f77c2c7b368', NULL, 'KASE', 'ASE', 'Aspen-Pitkin County Airport', 'Aspen', 'US', 39.223202, -106.868698, 7820, 'America/Denver', false, 8006, true),
            ('01a0a008-12f4-73f1-b5af-8f8c382ab208', NULL, 'KSFO', 'SFO', 'San Francisco International Airport', 'San Francisco', 'US', 37.618999, -122.375, 13, 'America/Los_Angeles', true, 11870, true),
            ('01a0a008-12f4-73f1-b5af-8f9f86df1668', NULL, 'KBOS', 'BOS', 'Boston Logan International Airport', 'Boston', 'US', 42.362999, -71.006401, 20, 'America/New_York', true, 10083, true),
            ('01a0a008-12f4-73f1-b5af-8fa46f73f34e', NULL, 'KDAL', 'DAL', 'Dallas Love Field', 'Dallas', 'US', 32.847099, -96.851799, 487, 'America/Chicago', true, 8800, true),
            ('01a0a008-12f4-73f1-b5af-8fbb9482075b', NULL, 'KIAD', 'IAD', 'Washington Dulles International Airport', 'Washington', 'US', 38.9445, -77.455803, 313, 'America/New_York', true, 11500, true),
            ('01a0a008-12f4-73f1-b5af-8fc12f82be1b', NULL, 'KMDW', 'MDW', 'Chicago Midway International Airport', 'Chicago', 'US', 41.785999, -87.752403, 620, 'America/Chicago', true, 6522, true),
            ('01a0a008-12f4-73f1-b5af-8fd2a0afddbc', NULL, 'KSDL', 'SCF', 'Scottsdale Airport', 'Scottsdale', 'US', 33.622898, -111.910004, 1510, 'America/Phoenix', true, 8249, true),
            ('01a0a008-12f4-73f1-b5af-8fe594e1a2c2', NULL, 'KAPA', 'APA', 'Centennial Airport', 'Denver', 'US', 39.570099, -104.849197, 5885, 'America/Denver', true, 10002, true),
            ('01a0a008-12f4-73f1-b5af-8ff3f9888c76', NULL, 'EGGW', 'LTN', 'London Luton Airport', 'London', 'GB', 51.874699, -0.368333, 526, 'Europe/London', true, 7087, true),
            ('01a0a008-12f4-73f1-b5af-900b7b4db3da', NULL, 'EGLF', 'FAB', 'Farnborough Airport', 'Farnborough', 'GB', 51.275799, -0.776333, 238, 'Europe/London', true, 8005, true),
            ('01a0a008-12f4-73f1-b5af-901f63861635', NULL, 'EGKB', 'BQH', 'London Biggin Hill Airport', 'London', 'GB', 51.3308, 0.0325, 598, 'Europe/London', true, 5988, true),
            ('01a0a008-12f4-73f1-b5af-9026f83d67f2', NULL, 'LFPB', 'LBG', 'Paris-Le Bourget Airport', 'Paris', 'FR', 48.969398, 2.44139, 218, 'Europe/Paris', true, 9843, true),
            ('01a0a008-12f4-73f1-b5af-90394ce3116c', NULL, 'LSGG', 'GVA', 'Geneva Airport', 'Geneva', 'CH', 46.238098, 6.109, 1411, 'Europe/Zurich', true, 12795, true),
            ('01a0a008-12f4-73f1-b5af-904f2182e947', NULL, 'LSZH', 'ZRH', 'Zurich Airport', 'Zurich', 'CH', 47.464699, 8.54917, 1416, 'Europe/Zurich', true, 12139, true),
            ('01a0a008-12f4-73f1-b5af-9054266cb7ba', NULL, 'EDDM', 'MUC', 'Munich Airport', 'Munich', 'DE', 48.353802, 11.7861, 1487, 'Europe/Berlin', true, 13123, true),
            ('01a0a008-12f4-73f1-b5af-9061cef84d48', NULL, 'LEPA', 'PMI', 'Palma de Mallorca Airport', 'Palma', 'ES', 39.551701, 2.73881, 27, 'Europe/Madrid', true, 10741, true),
            ('01a0a008-12f4-73f1-b5af-907d3e41cbf9', NULL, 'LIRA', 'CIA', 'Rome-Ciampino Airport', 'Rome', 'IT', 41.7994, 12.5949, 427, 'Europe/Rome', true, 7188, true),
            ('01a0a008-12f4-73f1-b5af-908d34339f25', NULL, 'LEIB', 'IBZ', 'Ibiza Airport', 'Ibiza', 'ES', 38.872898, 1.37312, 24, 'Europe/Madrid', true, 9186, true),
            ('01a0a008-12f4-73f1-b5af-909379110dbb', NULL, 'OMDW', 'DWC', 'Al Maktoum International Airport', 'Dubai', 'AE', 24.8964, 55.1614, 172, 'Asia/Dubai', true, 14764, true),
            ('01a0a008-12f4-73f1-b5af-90a6a0dc7a6c', NULL, 'VHHH', 'HKG', 'Hong Kong International Airport', 'Hong Kong', 'HK', 22.308001, 113.918503, 28, 'Asia/Hong_Kong', true, 12467, true),
            ('01a0a008-12f4-73f1-b5af-90be4047bca7', NULL, 'RJTT', 'HND', 'Tokyo Haneda Airport', 'Tokyo', 'JP', 35.553299, 139.781006, 21, 'Asia/Tokyo', true, 9843, true),
            ('01a0a008-12f4-73f1-b5af-90ce026fd537', NULL, 'WSSL', 'XSP', 'Seletar Airport', 'Singapore', 'SG', 1.41695, 103.867996, 36, 'Asia/Singapore', true, 6017, true)
        """
    )

    # ---------------------------------------------------------------------- fbos
    _fbos_insert = """
        INSERT INTO fbos
            (id, client_id, airport_id, name, brand, has_customs, is_preferred)
        VALUES
            ('01a0a008-12f4-73f1-b5af-90de98aa151e', NULL, '01a0a008-12f4-73f1-b5af-8eb75a388dd9', 'Signature Flight Support TEB', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-90e4950027d4', NULL, '01a0a008-12f4-73f1-b5af-8eb75a388dd9', 'Meridian Teterboro', 'Meridian', true, false),
            ('01a0a008-12f4-73f1-b5af-90fce85ac914', NULL, '01a0a008-12f4-73f1-b5af-8eb75a388dd9', 'Atlantic Aviation TEB', 'Atlantic', true, false),
            ('01a0a008-12f4-73f1-b5af-9106adc3b378', NULL, '01a0a008-12f4-73f1-b5af-8eb75a388dd9', 'Jet Aviation Teterboro', 'Jet Aviation', true, false),
            ('01a0a008-12f4-73f1-b5af-911cc7fcef76', NULL, '01a0a008-12f4-73f1-b5af-8ef3425b9ca2', 'Clay Lacy Aviation', 'Clay Lacy', true, false),
            ('01a0a008-12f4-73f1-b5af-9125d2ec362c', NULL, '01a0a008-12f4-73f1-b5af-8ef3425b9ca2', 'Signature Flight Support VNY', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-91379d9c6b68', NULL, '01a0a008-12f4-73f1-b5af-8f2c1199cb2b', 'Signature Flight Support PBI', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-9145026c22a1', NULL, '01a0a008-12f4-73f1-b5af-8f2c1199cb2b', 'Atlantic Aviation PBI', 'Atlantic', true, false),
            ('01a0a008-12f4-73f1-b5af-915d464e5b7a', NULL, '01a0a008-12f4-73f1-b5af-8f6fe91e958d', 'Signature Flight Support LAS', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-916819228144', NULL, '01a0a008-12f4-73f1-b5af-8f38a2c5ce28', 'Signature Flight Support OPF', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-9170fc90b33f', NULL, '01a0a008-12f4-73f1-b5af-8ff3f9888c76', 'Signature Flight Support Luton', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-918f20d4ea14', NULL, '01a0a008-12f4-73f1-b5af-8ff3f9888c76', 'Harrods Aviation Luton', 'Harrods Aviation', true, false),
            ('01a0a008-12f4-73f1-b5af-919b033f3a64', NULL, '01a0a008-12f4-73f1-b5af-900b7b4db3da', 'Signature Flight Support Farnborough', 'Signature', true, false),
            ('01a0a008-12f4-73f1-b5af-91a143065d9c', NULL, '01a0a008-12f4-73f1-b5af-9026f83d67f2', 'Universal Aviation Paris', 'Universal', true, false),
            ('01a0a008-12f4-73f1-b5af-91b07d8b7bdb', NULL, '01a0a008-12f4-73f1-b5af-90394ce3116c', 'Jet Aviation Geneva', 'Jet Aviation', true, false),
            ('01a0a008-12f4-73f1-b5af-91c7fa60e96a', NULL, '01a0a008-12f4-73f1-b5af-8f77c2c7b368', 'Atlantic Aviation ASE', 'Atlantic', false, false)
        """
    op.execute(_fbos_insert)

    # --- Invariant: audit_logs is append-only for the application role ---------
    # This is the last migration in the chain, so it is the right place to assert
    # what 012 established still holds. has_table_privilege() is used rather than
    # information_schema.role_table_grants because it also sees privileges that
    # arrive indirectly -- via PUBLIC or via membership in another role -- which is
    # exactly how an accidental grant would sneak in.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF has_table_privilege('{APP_ROLE}', 'audit_logs', 'UPDATE')
               OR has_table_privilege('{APP_ROLE}', 'audit_logs', 'DELETE') THEN
                RAISE EXCEPTION
                    'audit_logs must be append-only but {APP_ROLE} has UPDATE or DELETE';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("SET LOCAL row_security = off")
    # Delete only the seeded global rows, by id, in reverse FK dependency order.
    # A tenant row that references a seeded manufacturer or airport will block
    # this via RESTRICT -- the correct outcome: investigate rather than cascade.
    op.execute("DELETE FROM fbos WHERE client_id IS NULL AND id IN (" + _ids(FBO_IDS) + ")")
    op.execute("DELETE FROM airports WHERE client_id IS NULL AND id IN (" + _ids(AIRPORT_IDS) + ")")
    op.execute(
        "DELETE FROM aircraft_models WHERE client_id IS NULL AND id IN ("
        + _ids(MODEL_IDS)
        + ")"
    )
    op.execute(
        "DELETE FROM manufacturers WHERE client_id IS NULL AND id IN ("
        + _ids(MANUFACTURER_IDS)
        + ")"
    )
