#!/usr/bin/env python
"""Seed one realistic demo tenant -- "Demo Brokerage" -- into the CRM.

Idempotent: every row id is ``uuid5(NAMESPACE, natural key)``, and every write is
``INSERT ... ON CONFLICT (id) DO UPDATE`` (``DO NOTHING`` for the immutable
``audit_logs``). Re-running refreshes the demo data in place; it never
duplicates. (Production rows are UUIDv7 per DATA_MODEL.md 1.5; v5 is used here
precisely because it is *not* random.)

Two phases, deliberately run as two different roles:

  A. **Global reference catalog** (manufacturers, aircraft models, airports,
     FBOs) -- resolved by natural key against the rows migration 015 seeded;
     anything missing (Heathrow, the Citation X+) is inserted as a *global*
     row (``client_id IS NULL``, DATA_MODEL.md 1.3). That requires the schema
     owner and ``row_security = off`` for the transaction.

  B. **Everything belonging to the demo tenant** -- written through the exact
     path the application uses: ``SET LOCAL ROLE bitlux_app`` and
     ``app.client_id`` set for the transaction, so Row-Level Security is
     genuinely enforced on every insert. The script refuses to run phase B
     if the effective role would bypass RLS.

Dates are relative to today so the demo stays "live" (upcoming trips, an
overdue task, a passport expiring soon); ids do not depend on dates.

Usage:  make seed      (or)  backend/.venv/bin/python backend/scripts/seed.py
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import math
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from _db import connect, enter_tenant, role_info

# --------------------------------------------------------------------------- ids
NS = uuid.uuid5(uuid.NAMESPACE_DNS, "seed.bitlux-crm.local")


def u(key: str) -> uuid.UUID:
    """Deterministic id for a natural key. Same key => same id, every run."""
    return uuid.uuid5(NS, key)


DEMO = u("client:demo")

# ------------------------------------------------------------------------- time
UTC = timezone.utc
TODAY = date.today()
NOW = datetime.now(UTC).replace(microsecond=0)


def d(days: int) -> date:
    return TODAY + timedelta(days=days)


def ago(days: int, hours: int = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


def local(days: int, hh: int, mm: int, tz: str) -> datetime:
    """A wall-clock time at an airport, `days` from today, as an aware datetime."""
    return datetime.combine(d(days), datetime.min.time(), ZoneInfo(tz)).replace(hour=hh, minute=mm)


# audit_logs rows are immutable and keyed (id, occurred_at), so their timestamps
# must be as deterministic as their ids -- a NOW-relative value would insert a
# *new* row under the same id on every run (and nothing could ever update it).
# Anchored inside 2026-09, the first partition migration 012 creates
# unconditionally, so the rows never fall into the DEFAULT partition.
AUDIT_EPOCH = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def audit_at(step: int, hours: int = 0) -> datetime:
    return AUDIT_EPOCH + timedelta(hours=6 * step + hours)


def enc(plain: str) -> bytes:
    """Placeholder for the application's envelope encryption ([enc] columns).

    NOT encryption. The demo has no key hierarchy; production must never write
    bytes like these. The *_last4 columns beside them hold the real display value.
    """
    return b"demo-plaintext:" + plain.encode()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Great-circle distance -- computed in the application, per DATA_MODEL 1.6."""
    r = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))


# =========================================================================== A. catalog
# (name, short, code, country, founded) -- names match migration 015's rows.
MANUFACTURERS = [
    ("Gulfstream Aerospace", "Gulfstream", "GLF", "US", 1958),
    ("Bombardier Aviation", "Bombardier", "BBD", "CA", 1942),
    ("Dassault Aviation", "Dassault", "DAS", "FR", 1929),
    ("Embraer Executive Jets", "Embraer", "EMB", "BR", 1969),
    ("Textron Aviation", "Cessna", "TXT", "US", 1927),
    ("Pilatus Aircraft", "Pilatus", "PIL", "CH", 1939),
]
# (mfr, name, family, icao, category, max_pax, typ_pax, range_nm, cruise_kt, alt_ft, bag_cuft)
MODELS = [
    ("Gulfstream Aerospace", "G650ER", "G650", "GLF6", "ultra_long_range", 19, 13, 7500, 516, 51000, 195),
    ("Gulfstream Aerospace", "G550", "G550", "GLF5", "ultra_long_range", 19, 14, 6750, 488, 51000, 170),
    ("Gulfstream Aerospace", "G280", "G280", "G280", "super_midsize_jet", 10, 8, 3600, 482, 45000, 154),
    ("Bombardier Aviation", "Global 7500", "Global", "GL7T", "ultra_long_range", 19, 14, 7700, 516, 51000, 195),
    ("Bombardier Aviation", "Challenger 350", "Challenger", "CL35", "super_midsize_jet", 10, 9, 3200, 470, 45000, 106),
    ("Dassault Aviation", "Falcon 8X", "Falcon", "FA8X", "ultra_long_range", 16, 12, 6450, 460, 41000, 140),
    ("Dassault Aviation", "Falcon 2000LXS", "Falcon", "F2TH", "heavy_jet", 10, 8, 4000, 470, 47000, 131),
    ("Embraer Executive Jets", "Praetor 600", "Praetor", "E550", "super_midsize_jet", 12, 9, 4018, 466, 45000, 155),
    ("Embraer Executive Jets", "Phenom 300E", "Phenom", "E55P", "light_jet", 10, 7, 2010, 464, 45000, 76),
    ("Textron Aviation", "Citation X+", "Citation", "C750", "super_midsize_jet", 12, 9, 3460, 527, 51000, 82),
    ("Textron Aviation", "Citation Longitude", "Citation", "C700", "super_midsize_jet", 12, 9, 3500, 483, 45000, 112),
    ("Pilatus Aircraft", "PC-24", "PC-24", "PC24", "light_jet", 10, 8, 2000, 440, 45000, 90),
]
CRUISE = {m[1]: m[8] for m in MODELS}
# (icao, iata, name, city, country, lat, lon, elev_ft, tz, customs, runway_ft)
AIRPORTS = [
    ("KTEB", "TEB", "Teterboro Airport", "Teterboro", "US", 40.850100, -74.060837, 9, "America/New_York", True, 7000),
    ("KJFK", "JFK", "John F. Kennedy International Airport", "New York", "US", 40.639801, -73.778900, 13, "America/New_York", True, 14511),
    ("KLAX", "LAX", "Los Angeles International Airport", "Los Angeles", "US", 33.942501, -118.407997, 125, "America/Los_Angeles", True, 12091),
    ("EGLL", "LHR", "London Heathrow Airport", "London", "GB", 51.470600, -0.461941, 83, "Europe/London", True, 12802),
    ("EGGW", "LTN", "London Luton Airport", "London", "GB", 51.874699, -0.368333, 526, "Europe/London", True, 7087),
    ("LFPB", "LBG", "Paris-Le Bourget Airport", "Paris", "FR", 48.969398, 2.441390, 218, "Europe/Paris", True, 9843),
    ("LSGG", "GVA", "Geneva Airport", "Geneva", "CH", 46.238098, 6.109000, 1411, "Europe/Zurich", True, 12795),
    ("KSFO", "SFO", "San Francisco International Airport", "San Francisco", "US", 37.618999, -122.375000, 13, "America/Los_Angeles", True, 11870),
    ("KOPF", "OPF", "Miami-Opa Locka Executive Airport", "Opa-locka", "US", 25.907000, -80.278397, 8, "America/New_York", True, 8002),
    ("KASE", "ASE", "Aspen-Pitkin County Airport", "Aspen", "US", 39.223202, -106.868698, 7820, "America/Denver", False, 8006),
]
APT = {a[0]: a for a in AIRPORTS}
# (airport, name, brand)
FBOS = [
    ("KTEB", "Signature Flight Support TEB", "Signature"),
    ("KOPF", "Signature Flight Support OPF", "Signature"),
    ("KASE", "Atlantic Aviation ASE", "Atlantic"),
    ("EGGW", "Signature Flight Support Luton", "Signature"),
    ("LSGG", "Jet Aviation Geneva", "Jet Aviation"),
]


class Catalog:
    """Resolved ids for the global reference rows the tenant data points at."""

    def __init__(self) -> None:
        self.mfr: dict[str, uuid.UUID] = {}
        self.model: dict[str, uuid.UUID] = {}
        self.apt: dict[str, uuid.UUID] = {}
        self.fbo: dict[str, uuid.UUID] = {}
        self.inserted: dict[str, list[str]] = {"manufacturers": [], "aircraft_models": [], "airports": [], "fbos": []}

    @classmethod
    def placeholder(cls) -> "Catalog":
        """Ids that never touch the DB -- for counting rows without connecting."""
        c = cls()
        c.mfr = {m[0]: u(f"ph:mfr:{m[0]}") for m in MANUFACTURERS}
        c.model = {m[1]: u(f"ph:model:{m[1]}") for m in MODELS}
        c.apt = {a[0]: u(f"ph:apt:{a[0]}") for a in AIRPORTS}
        c.fbo = {f[1]: u(f"ph:fbo:{f[1]}") for f in FBOS}
        return c


async def ensure_catalog(conn) -> Catalog:
    cat = Catalog()
    async with conn.transaction():
        # Owner-only escape hatch: global rows have client_id NULL, which no
        # tenant policy permits (DATA_MODEL 1.7 / migration 015).
        await conn.execute("SET LOCAL row_security = off")

        for name, short, code, cc, founded in MANUFACTURERS:
            mid = await conn.fetchval(
                "SELECT id FROM manufacturers WHERE client_id IS NULL AND lower(name)=lower($1) AND deleted_at IS NULL", name)
            if mid is None:
                mid = u(f"manufacturer:{name}")
                await conn.execute(
                    "INSERT INTO manufacturers (id, client_id, name, short_name, code, country_code, founded_year) "
                    "VALUES ($1, NULL, $2, $3, $4, $5, $6)", mid, name, short, code, cc, founded)
                cat.inserted["manufacturers"].append(name)
            cat.mfr[name] = mid

        for mfr, name, fam, icao, cat_, mx, typ, rng, spd, alt, bag in MODELS:
            mid = await conn.fetchval(
                "SELECT id FROM aircraft_models WHERE client_id IS NULL AND manufacturer_id=$1 AND lower(name)=lower($2) AND deleted_at IS NULL",
                cat.mfr[mfr], name)
            if mid is None:
                mid = u(f"aircraft_model:{name}")
                await conn.execute(
                    "INSERT INTO aircraft_models (id, client_id, manufacturer_id, name, family, icao_type_code, category, "
                    "max_passengers, typical_passengers, range_nm, cruise_speed_kt, max_altitude_ft, baggage_capacity_cuft, "
                    "has_lavatory, wifi_available) VALUES ($1, NULL, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, true, true)",
                    mid, cat.mfr[mfr], name, fam, icao, cat_, mx, typ, rng, spd, alt, bag)
                cat.inserted["aircraft_models"].append(name)
            cat.model[name] = mid

        for icao, iata, name, city, cc, lat, lon, elev, tz, customs, rwy in AIRPORTS:
            aid = await conn.fetchval(
                "SELECT id FROM airports WHERE client_id IS NULL AND icao_code=$1 AND deleted_at IS NULL", icao)
            if aid is None:
                aid = u(f"airport:{icao}")
                await conn.execute(
                    "INSERT INTO airports (id, client_id, icao_code, iata_code, name, city, country_code, latitude, longitude, "
                    "elevation_ft, timezone, has_customs, longest_runway_ft) VALUES ($1, NULL, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
                    aid, icao, iata, name, city, cc, Decimal(str(lat)), Decimal(str(lon)), elev, tz, customs, rwy)
                cat.inserted["airports"].append(icao)
            cat.apt[icao] = aid

        for icao, name, brand in FBOS:
            fid = await conn.fetchval(
                "SELECT id FROM fbos WHERE client_id IS NULL AND airport_id=$1 AND lower(name)=lower($2) AND deleted_at IS NULL",
                cat.apt[icao], name)
            if fid is None:
                fid = u(f"fbo:{icao}:{name}")
                await conn.execute(
                    "INSERT INTO fbos (id, client_id, airport_id, name, brand, has_customs) VALUES ($1, NULL, $2, $3, $4, true)",
                    fid, cat.apt[icao], name, brand)
                cat.inserted["fbos"].append(name)
            cat.fbo[name] = fid
    return cat


# =========================================================================== B. tenant
# Insert order matters: FK targets first, polymorphic targets before the rows
# that point at them (the validation trigger checks existence in-tenant).
ORDER = [
    "clients", "users", "documents", "segments", "contacts", "contact_channels",
    "passengers", "travel_documents", "account_holders", "addresses",
    "account_holder_passengers", "operators", "operator_safety_ratings", "aircraft",
    "aircraft_operator_assignments", "crew_members", "trips", "legs", "leg_passengers",
    "leg_crew", "quotes", "quote_line_items", "bookings", "invoices",
    "invoice_line_items", "payments", "empty_legs", "tasks", "activities", "tags",
    "entity_tags", "document_links", "audit_logs",
]

# Every demo user logs in with this password (argon2id-hashed at seed time). Demo only.
DEMO_PASSWORD = "Demo!2026"

USERS = {  # key -> (email, name, role)
    "owner": ("owner@demo.test", "Olivia Grant", "owner"),
    "broker": ("broker@demo.test", "Ben Carter", "broker"),
    "ops": ("ops@demo.test", "Nadia Osei", "ops"),
}
SEGMENTS = [  # (key, name, type)
    ("uhnw", "UHNW", "uhnw"), ("corporate", "Corporate", "corporate"),
    ("family_office", "Family Office", "family_office"), ("sports", "Sports", "sports"),
    ("entertainment", "Entertainment", "entertainment"),
]
# key: (segment, type, first, last, company, title, email, phone, status, source, parent)
CONTACTS = {
    "victoria": ("uhnw", "individual", "Victoria", "Ashworth", "Ashworth Holdings", "Principal",
                 "victoria.ashworth@ashworthholdings.example", "+1 212 555 0142", "active", "referral", None),
    "marcus": ("uhnw", "individual", "Marcus", "Chen", None, None,
               "marcus.chen@chenfamily.example", "+1 415 555 0177", "prospect", "website", None),
    "halcyon": ("corporate", "company", None, None, "Halcyon Capital Partners", None,
                "ops@halcyoncp.example", "+1 212 555 0199", "active", "broker_network", None),
    "northwind": ("corporate", "company", None, None, "Northwind Logistics Inc", None,
                  "travel@northwindlogistics.example", "+1 312 555 0123", "active", "referral", None),
    "daniel": ("corporate", "individual", "Daniel", "Okafor", "Halcyon Capital Partners", "Executive Assistant",
               "daniel.okafor@halcyoncp.example", "+1 212 555 0188", "active", "broker_network", "halcyon"),
    "lindqvist": ("family_office", "company", None, None, "The Lindqvist Family Office", None,
                  "office@lindqvistfo.example", "+41 22 555 01 44", "active", "event", None),
    "jaylen": ("sports", "individual", "Jaylen", "Brooks", "Brooks Management", "Athlete",
               "jb@brooksmgmt.example", "+1 310 555 0155", "lead", "partner", None),
    "sofia": ("entertainment", "individual", "Sofia", "Marchetti", "Marchetti Talent", "Actor",
              "sofia@marchettitalent.example", "+33 1 55 55 01 66", "active", "referral", None),
}
# key: (contact_key|None, first, last, dob, nationality, weight_kg, passport_country, passport_expiry_days, prefs)
PASSENGERS = {
    "victoria": ("victoria", "Victoria", "Ashworth", date(1971, 4, 12), "US", 61.0, "US", 1460, {"seat": "forward club", "beverage": "sparkling water", "temperature_c": 21}),
    "jaylen": ("jaylen", "Jaylen", "Brooks", date(1998, 11, 3), "US", 98.5, "US", 900, {"seat": "divan", "beverage": "electrolyte"}),
    "sofia": ("sofia", "Sofia", "Marchetti", date(1989, 7, 22), "IT", 57.0, "IT", 1200, {"beverage": "espresso", "press": "none"}),
    "priya": (None, "Priya", "Raman", date(1980, 2, 9), "IN", 64.0, "IN", 140, {"seat": "aft", "wifi": "required"}),
    "rafael": (None, "Rafael", "Mendes", date(1986, 9, 30), "BR", 82.0, "BR", 720, {}),
    "tomas": (None, "Tomas", "Lindqvist", date(1965, 1, 18), "SE", 88.0, "SE", 60, {"seat": "forward", "beverage": "still water"}),
}
# key: (legal, dba, code, cc, part, aoc, aoc_days, status, ins_days, ins_limit, preferred, commission, terms)
OPERATORS = {
    "skyline": ("Skyline Jet Charter LLC", "Skyline Jets", "SKY", "US", "part_135", "SKYA135X", 400, "approved", 200, 30_000_000_00, True, "0.0750", "net_15"),
    "meridian": ("Meridian Air Partners LLC", None, "MAP", "US", "part_135", "MAPA135Y", 320, "approved", 150, 25_000_000_00, False, "0.0700", "prepaid"),
    "alpine": ("Alpine Executive Aviation AG", None, "ALP", "CH", "easa_cat", "CH.AOC.1042", 500, "approved", 260, 50_000_000_00, True, "0.0650", "net_30"),
    "crown": ("Atlantic Crown Aviation Ltd", "Atlantic Crown", "ACA", "GB", "easa_cat", "GB.AOC.2211", 210, "conditional", 95, 20_000_000_00, False, "0.0800", "prepaid"),
}
# (operator, program, level, label, issued_days_ago, expiry_days)
RATINGS = [
    ("skyline", "argus", "argus_platinum", "ARGUS Platinum", 60, 300),
    ("skyline", "wyvern", "wyvern_wingman", "Wyvern Wingman", 100, 250),
    ("meridian", "argus", "argus_gold", "ARGUS Gold", 180, 180),
    ("alpine", "isbao", "isbao_stage_3", "IS-BAO Stage 3", 200, 500),
    ("crown", "isbao", "isbao_stage_2", "IS-BAO Stage 2", 240, 120),
    ("crown", "wyvern", "wyvern_registered", "Wyvern Registered", 270, 90),
]
# tail: (model, operator, year, home, hourly_cents, seats)
AIRCRAFT = {
    "N650BX": ("G650ER", "skyline", 2019, "KTEB", 950_000, 16),
    "N7500G": ("Global 7500", "skyline", 2021, "KTEB", 1_050_000, 17),
    "N280SJ": ("G280", "skyline", 2018, "KTEB", 680_000, 9),
    "N350MA": ("Challenger 350", "meridian", 2020, "KLAX", 620_000, 9),
    "N600PR": ("Praetor 600", "meridian", 2022, "KLAX", 650_000, 10),
    "N750CX": ("Citation X+", "meridian", 2016, "KSFO", 590_000, 9),
    "HB-JEA": ("Falcon 8X", "alpine", 2020, "LSGG", 920_000, 14),
    "HB-VPC": ("PC-24", "alpine", 2021, "LSGG", 440_000, 8),
    "G-CRWN": ("Falcon 2000LXS", "crown", 2017, "EGGW", 690_000, 10),
    "G-LNGT": ("Citation Longitude", "crown", 2021, "EGGW", 560_000, 9),
}
# key: (first, last, role, operator, nationality, license_type, ratings, medical_days, base, hours)
CREW = {
    "whitaker": ("James", "Whitaker", "pic", "skyline", "US", "ATP", ["GLF6", "GL7T", "G280"], 200, "KTEB", 9800),
    "vasquez": ("Elena", "Vasquez", "sic", "skyline", "US", "ATP", ["G280", "GLF6", "CL35", "E550", "FA8X", "C700"], 45, "KTEB", 4200),
    "brandt": ("Lukas", "Brandt", "pic", "alpine", "DE", "ATPL", ["FA8X", "PC24", "C700"], 320, "LSGG", 7600),
}
# key: (number, type, status, contact, lead_pax, pax, segment_source, currency, legs)
#   leg: (dep, arr, day_offset, hh, mm, tail, dep_fbo, arr_fbo, customs, pax_keys, crew(pic, sic))
TRIPS = {
    "t1": ("BLX-2026-001", "charter", "confirmed", "daniel", "priya", "broker_network", "USD", [
        ("KTEB", "KOPF", 10, 8, 0, "N280SJ", "Signature Flight Support TEB", "Signature Flight Support OPF", False, ["priya", "rafael"], ("whitaker", "vasquez")),
        ("KOPF", "KTEB", 10, 17, 30, "N280SJ", "Signature Flight Support OPF", "Signature Flight Support TEB", False, ["priya", "rafael"], ("whitaker", "vasquez")),
    ]),
    "t2": ("BLX-2026-002", "charter", "sourcing", "victoria", "victoria", "referral", "USD", [
        ("KLAX", "KASE", 24, 14, 0, "N350MA", None, "Atlantic Aviation ASE", False, ["victoria"], ("whitaker", "vasquez")),
        ("KASE", "KLAX", 26, 15, 0, "N350MA", "Atlantic Aviation ASE", None, False, ["victoria"], ("whitaker", "vasquez")),
    ]),
    "t3": ("BLX-2026-003", "charter", "quoted", "lindqvist", "tomas", "event", "EUR", [
        ("EGLL", "LSGG", 38, 9, 0, "HB-JEA", None, "Jet Aviation Geneva", True, ["tomas"], ("brandt", "vasquez")),
        ("LSGG", "EGLL", 41, 16, 0, "HB-JEA", "Jet Aviation Geneva", None, True, ["tomas"], ("brandt", "vasquez")),
    ]),
    "t4": ("BLX-2026-004", "charter", "sourcing", "jaylen", "jaylen", "partner", "USD", [
        ("KSFO", "KJFK", 45, 7, 30, "N650BX", None, None, False, ["jaylen"], ("whitaker", "vasquez")),
    ]),
    "t5": ("BLX-2026-005", "charter", "draft", "sofia", "sofia", "referral", "EUR", [
        ("LFPB", "EGGW", 60, 11, 0, "G-LNGT", None, "Signature Flight Support Luton", True, ["sofia"], ("brandt", "vasquez")),
    ]),
}
TRIP_ACCOUNT = {"t1": "halcyon"}  # only the booked trip is attached to a paying account
# quote key: (number, status, trip, account, contact, operator, tail, currency, sent_ago, valid_days, lines)
#   line: (type, description, qty, unit, unit_price, sell, cost, taxable, pass_through, leg_index|None)
QUOTES = {
    "q1": ("Q-2026-0001", "accepted", "t1", "halcyon", "daniel", "skyline", "N280SJ", "USD", 6, 1, [
        ("flight_hours", "G280 flight time, KTEB-KOPF-KTEB", "5.500", "hour", 720_000, 3_960_000, 3_300_000, False, False, None),
        ("federal_excise_tax", "Federal excise tax 7.5%", "1", "each", 297_000, 297_000, 297_000, False, True, None),
        ("segment_fee", "Domestic segment fees (2 pax x 2 legs)", "4", "pax", 500, 2_000, 2_000, False, True, None),
        ("handling", "FBO handling, TEB + OPF", "2", "leg", 45_000, 90_000, 90_000, False, True, None),
        ("catering", "Catering, both legs", "2", "leg", 35_000, 70_000, 60_000, False, False, None),
    ]),
    "q2": ("Q-2026-0002", "sent", "t3", None, "lindqvist", "alpine", "HB-JEA", "EUR", 2, 5, [
        ("flight_hours", "Falcon 8X flight time, EGLL-LSGG-EGLL", "3.400", "hour", 950_000, 3_230_000, 2_750_000, False, False, None),
        ("handling", "Handling, LHR + GVA", "2", "leg", 85_000, 170_000, 170_000, False, True, None),
        ("catering", "Catering, both legs", "2", "leg", 45_000, 90_000, 80_000, False, False, None),
        ("customs", "Customs and GAR filings", "2", "leg", 25_000, 50_000, 50_000, False, True, None),
    ]),
    "q3": ("Q-2026-0003", "draft", "t2", None, "victoria", "meridian", "N350MA", "USD", None, 7, [
        ("flight_hours", "Challenger 350 flight time, KLAX-KASE-KLAX", "3.600", "hour", 620_000, 2_232_000, 1_850_000, False, False, None),
        ("federal_excise_tax", "Federal excise tax 7.5%", "1", "each", 167_400, 167_400, 167_400, False, True, None),
        ("landing_fee", "Landing and ramp, ASE + LAX", "2", "leg", 65_000, 130_000, 130_000, False, True, None),
        ("catering", "Catering, both legs", "2", "leg", 30_000, 60_000, 50_000, False, False, None),
        ("pet_fee", "Pet on board", "1", "each", 50_000, 50_000, 0, False, False, None),
    ]),
}
DOCUMENTS = {  # key: (type, title, mime, confidential, expires_days|None, links[(entity_type, entity_key, role)])
    "contract": ("charter_agreement", "Charter Agreement - BLX-2026-001", "application/pdf", False, None,
                 [("booking", "bk1", "contract"), ("trip", "t1", "contract"), ("account_holder", "halcyon", "contract")]),
    "passport_victoria": ("passport_scan", "Passport - Victoria Ashworth", "image/jpeg", True, 1460,
                          [("passenger", "victoria", "passport_scan")]),
    "insurance_skyline": ("insurance_certificate", "Certificate of Insurance - Skyline Jet Charter", "application/pdf", False, 200,
                          [("operator", "skyline", "insurance"), ("aircraft", "N650BX", "insurance")]),
    "aoc_skyline": ("aoc_certificate", "Part 135 Certificate - Skyline Jet Charter", "application/pdf", False, 400,
                    [("operator", "skyline", "aoc"), ("aircraft", "N650BX", "aoc")]),
    "audit_skyline": ("safety_audit_report", "ARGUS Platinum Audit Report - Skyline Jet Charter", "application/pdf", True, None,
                      [("operator", "skyline", "safety_audit"), ("operator_safety_rating", "skyline:argus", "safety_audit")]),
}
# (dep, arr, operator, tail, day, hh_from, hh_to, asking, floor, seats, currency, source, ext_ref, flex)
EMPTY_LEGS = [
    ("KTEB", "KOPF", "skyline", "N280SJ", 11, 9, 15, 1_450_000, 1_200_000, 8, "USD", "manual", None, False),
    ("KLAX", "KASE", "meridian", "N350MA", 23, 8, 18, 985_000, 800_000, 8, "USD", "avinode", "AVN-771203", True),
    ("EGLL", "LSGG", "alpine", "HB-JEA", 37, 7, 12, 1_150_000, 950_000, 12, "EUR", "operator_feed", "ALP-EL-2026-118", False),
    ("KSFO", "KJFK", "skyline", "N650BX", 44, 6, 20, 2_950_000, 2_500_000, 14, "USD", "manual", None, False),
    ("LFPB", "EGGW", "crown", "G-CRWN", 59, 10, 16, 620_000, 500_000, 8, "EUR", "email_parse", "mail-8f2a", False),
]
# (key, title, type, status, priority, assignee, due_days, entity(type,key)|None, dedupe, extra)
TASKS = [
    ("contract", "Send charter agreement to Halcyon for signature", "document_request", "completed", "high", "broker", -4, ("booking", "bk1"), None),
    ("chase_inv2", "Chase balance payment on INV-2026-0002", "payment_chase", "open", "high", "broker", -3, ("invoice", "inv2"), None),
    ("tomas_passport", "Tomas Lindqvist passport expires in 60 days - request renewal", "document_expiry", "open", "urgent", "ops", 7, ("passenger", "tomas"), "travel_document:tomas:expiry"),
    ("priya_passport", "Priya Raman passport expiring - confirm renewal before next travel", "document_expiry", "open", "normal", "ops", 30, ("passenger", "priya"), "travel_document:priya:expiry"),
    ("catering_t1", "Confirm catering order for BLX-2026-001 with Signature TEB", "ops_check", "open", "normal", "ops", 8, ("trip", "t1"), None),
    ("followup_q2", "Follow up with Lindqvist Family Office on Q-2026-0002", "follow_up", "in_progress", "high", "broker", -1, ("quote", "q2"), None),
    ("quote_t4", "Prepare quote for BLX-2026-004 (KSFO-KJFK, Jaylen Brooks)", "quote_prep", "open", "normal", "broker", 3, ("trip", "t4"), None),
    ("skyline_ins", "Review Skyline insurance certificate renewal", "compliance_review", "open", "low", "ops", 90, ("operator", "skyline"), "operator:skyline:insurance"),
    ("call_jaylen", "Call Jaylen Brooks about schedule change", "call", "blocked", "normal", "broker", -5, ("contact", "jaylen"), None),
    ("northwind_w9", "Collect W-9 from Northwind Logistics", "document_request", "cancelled", "normal", "ops", -10, ("contact", "northwind"), None),
]
# (days_ago, type, direction, subject, contact_key, entity(type,key)|None, user)
ACTIVITIES = [
    (58, "email", "inbound", "Introduction via Meridian Air Partners", "halcyon", None, "broker"),
    (55, "call", "outbound", "Discovery call - travel patterns and preferred cabin", "halcyon", None, "broker"),
    (52, "meeting", "internal", "Onboarding review: Halcyon Capital Partners", "halcyon", ("account_holder", "halcyon"), "owner"),
    (47, "email", "outbound", "Sent credit application and terms", "daniel", ("account_holder", "halcyon"), "broker"),
    (40, "note", "internal", "Victoria prefers forward club seat; travels with a small dog", "victoria", ("passenger", "victoria"), "broker"),
    (35, "call", "inbound", "Aspen ski weekend enquiry", "victoria", ("trip", "t2"), "broker"),
    (30, "email", "outbound", "Preliminary options for KLAX-KASE", "victoria", ("trip", "t2"), "broker"),
    (28, "email", "inbound", "Request for Geneva round trip in November", "lindqvist", ("trip", "t3"), "broker"),
    (21, "whatsapp", "inbound", "Jaylen's agent asking about a transcon after the game", "jaylen", ("trip", "t4"), "broker"),
    (18, "meeting", "outbound", "Site visit - Skyline hangar and N280SJ cabin", "halcyon", ("operator", "skyline"), "ops"),
    (14, "email", "outbound", "Quote Q-2026-0001 sent for KTEB-KOPF-KTEB", "daniel", ("quote", "q1"), "broker"),
    (12, "call", "inbound", "Questions on FET and catering line items", "daniel", ("quote", "q1"), "broker"),
    (9, "email", "inbound", "Q-2026-0001 accepted - proceed to contract", "daniel", ("quote", "q1"), "broker"),
    (7, "email", "outbound", "Charter agreement sent for e-signature", "daniel", ("booking", "bk1"), "broker"),
    (6, "system", "internal", "Deposit invoice INV-2026-0001 issued", "halcyon", ("invoice", "inv1"), "ops"),
    (5, "email", "inbound", "Wire confirmation for deposit", "daniel", ("invoice", "inv1"), "ops"),
    (4, "email", "outbound", "Q-2026-0002 sent (Falcon 8X, Alpine)", "lindqvist", ("quote", "q2"), "broker"),
    (3, "sms", "outbound", "Confirming Priya and Rafael passport details for manifest", "daniel", ("trip", "t1"), "ops"),
    (2, "call", "outbound", "Sofia's team - Paris to Luton in November, timing flexible", "sofia", ("trip", "t5"), "broker"),
    (1, "note", "internal", "Marcus Chen still evaluating; revisit after Q4", "marcus", None, "broker"),
]
TAGS = [("vip", "VIP", "priority", "#C9A227"), ("repeat", "Repeat Client", "relationship", "#2E7D32"),
        ("pets", "Pets Onboard", "preference", "#8E44AD"), ("ski", "Ski Season", "campaign", "#1565C0"),
        ("net30", "Net-30 Approved", "finance", "#00838F")]
ENTITY_TAGS = [
    ("vip", "contact", "victoria"), ("vip", "passenger", "victoria"), ("vip", "contact", "sofia"), ("vip", "contact", "jaylen"), ("vip", "trip", "t2"),
    ("repeat", "contact", "halcyon"), ("repeat", "contact", "victoria"), ("repeat", "contact", "lindqvist"), ("repeat", "account_holder", "halcyon"),
    ("pets", "passenger", "victoria"), ("pets", "trip", "t2"), ("pets", "aircraft", "N7500G"),
    ("ski", "trip", "t2"), ("ski", "airport", "KASE"), ("ski", "empty_leg", "el:KLAX-KASE"),
    ("net30", "account_holder", "halcyon"), ("net30", "account_holder", "northwind"), ("net30", "contact", "halcyon"), ("net30", "contact", "northwind"), ("net30", "operator", "skyline"),
]


def build(cat: Catalog) -> dict[str, list[dict]]:
    """Every tenant row, keyed by table, in insert order."""
    R: dict[str, list[dict]] = {t: [] for t in ORDER}
    ids: dict[str, uuid.UUID] = {}  # "kind:key" -> id, for polymorphic refs

    def reg(kind: str, key: str, id_: uuid.UUID) -> uuid.UUID:
        ids[f"{kind}:{key}"] = id_
        return id_

    def ref(kind: str, key: str) -> uuid.UUID:
        if kind == "airport":
            return cat.apt[key]
        return ids[f"{kind}:{key}"]

    uid = {k: reg("user", k, u(f"user:{v[0]}")) for k, v in USERS.items()}
    base = lambda **kw: {"client_id": DEMO, "created_by": uid["broker"], "updated_by": uid["broker"], **kw}  # noqa: E731

    # ---- client + users
    R["clients"].append({"id": DEMO, "slug": "demo", "name": "Demo Brokerage", "legal_name": "Demo Brokerage LLC",
                         "status": "active", "default_currency": "USD", "timezone": "America/New_York",
                         "billing_email": "billing@demo.test", "trip_number_prefix": "BLX",
                         "settings": {"quote_validity_days": 7, "deposit_percent": 50}})
    from app.security.passwords import hash_password  # argon2id; app package is installed in the venv

    for k, (email, name, role) in USERS.items():
        given, family = name.split(" ", 1)
        # users is self-referential (created_by -> users): the bootstrap rows are
        # authored by nobody, which is also the truth.
        R["users"].append(base(id=uid[k], email=email, full_name=name, given_name=given, family_name=family,
                               role=role, status="active", timezone="America/New_York", auth_provider="password",
                               mfa_enabled=(role == "owner"), last_login_at=ago(0, 3),
                               password_hash=hash_password(DEMO_PASSWORD), password_changed_at=ago(30),
                               created_by=None, updated_by=None))

    # ---- documents (early: several FK columns point at them)
    for k, (dtype, title, mime, conf, exp_days, _links) in DOCUMENTS.items():
        key = f"demo/{dtype}/{k}.{ 'jpg' if mime.endswith('jpeg') else 'pdf'}"
        R["documents"].append(base(id=reg("document", k, u(f"document:{k}")), document_type=dtype, status="approved",
                                   title=title, storage_provider="s3", bucket="bitlux-demo", storage_key=key,
                                   filename=key.rsplit("/", 1)[-1], mime_type=mime, byte_size=180_000 + len(key) * 991,
                                   checksum_sha256=sha(key), is_confidential=conf, effective_date=d(-3),
                                   expires_at=d(exp_days) if exp_days else None, uploaded_by_user_id=uid["broker"],
                                   metadata={"demo": True}))

    # ---- segments / contacts / channels
    for i, (k, name, stype) in enumerate(SEGMENTS):
        R["segments"].append(base(id=reg("segment", k, u(f"segment:{k}")), name=name, code=k.upper(), segment_type=stype,
                                  path=k, sort_order=i))
    for k, (seg, ctype, first, last, company, title, email, phone, status, source, parent) in CONTACTS.items():
        cid = reg("contact", k, u(f"contact:{k}"))
        display = f"{first} {last}" if ctype == "individual" else company
        R["contacts"].append(base(id=cid, segment_id=ref("segment", seg), contact_type=ctype, status=status,
                                  first_name=first, last_name=last, display_name=display, company_name=company,
                                  job_title=title, parent_contact_id=ref("contact", parent) if parent else None,
                                  owner_user_id=uid["broker"], source=source, primary_email=email, primary_phone=phone,
                                  preferred_language="en", last_activity_at=ago(1)))
        for ctype_, value in (("email", email), ("phone", phone)):
            R["contact_channels"].append(base(id=u(f"channel:{k}:{ctype_}"), contact_id=cid, channel_type=ctype_,
                                              value=value, label="work", is_primary=True, verified_at=ago(30)))

    # ---- passengers + passports
    for k, (ck, first, last, dob, nat, kg, pp_cc, pp_days, prefs) in PASSENGERS.items():
        pid = reg("passenger", k, u(f"passenger:{k}"))
        R["passengers"].append(base(id=pid, contact_id=ref("contact", ck) if ck else None, status="active",
                                    first_name=first, last_name=last, date_of_birth=dob, nationality_code=nat,
                                    weight_kg=Decimal(str(kg)), preferences=prefs,
                                    travels_with_pet=(k == "victoria"), pet_details={"type": "dog", "breed": "Cavalier", "weight_kg": 8} if k == "victoria" else None,
                                    dietary_restrictions=["vegetarian"] if k == "priya" else [], allergies=["shellfish"] if k == "tomas" else []))
        num = f"P{abs(hash(k)) % 10**7:07d}X"
        R["travel_documents"].append(base(id=reg("travel_document", k, u(f"travel_document:{k}:passport")), passenger_id=pid,
                                          document_type="passport", number=enc(num), number_last4=num[-4:],
                                          full_name_on_document=f"{last.upper()}, {first.upper()}", issuing_country=pp_cc,
                                          nationality_code=nat, issue_date=d(pp_days - 3650), expiry_date=d(pp_days),
                                          scan_document_id=ref("document", "passport_victoria") if k == "victoria" else None,
                                          verified_at=ago(20), verified_by_user_id=uid["ops"], is_primary=True))

    # ---- account holders, addresses, passenger links
    for k, (num, name, pc, bc, terms, credit, balance) in {
        "halcyon": ("ACC-00001", "Halcyon Capital Partners", "halcyon", "daniel", "net_30", 25_000_000_00, 1_459_500),
        "northwind": ("ACC-00002", "Northwind Logistics Inc", "northwind", "northwind", "prepaid", 0, 0),
    }.items():
        ahid = reg("account_holder", k, u(f"account_holder:{k}"))
        R["account_holders"].append(base(id=ahid, account_number=num, name=name, account_type="corporate", status="active",
                                         primary_contact_id=ref("contact", pc), billing_contact_id=ref("contact", bc),
                                         owner_user_id=uid["broker"], currency="USD", payment_terms=terms,
                                         credit_limit_cents=credit, balance_cents=balance, tax_id=enc("12-3456789"),
                                         tax_id_last4="6789", contract_signed_at=ago(50), credit_reviewed_at=ago(48)))
    for k, (line1, line2, city, region, postal) in {
        "halcyon": ("200 Park Avenue", "Suite 4500", "New York", "NY", "10166"),
        "northwind": ("233 S Wacker Dr", "Floor 60", "Chicago", "IL", "60606"),
    }.items():
        R["addresses"].append(base(id=reg("address", k, u(f"address:{k}:billing")), owner_type="account_holder",
                                   owner_id=ref("account_holder", k), address_type="billing", line1=line1, line2=line2,
                                   city=city, region=region, postal_code=postal, country_code="US", is_primary=True))
    for pk, rel, booker in (("priya", "employee", True), ("rafael", "employee", False)):
        R["account_holder_passengers"].append(base(id=u(f"ahp:halcyon:{pk}"), account_holder_id=ref("account_holder", "halcyon"),
                                                   passenger_id=ref("passenger", pk), relationship=rel, is_authorized_booker=booker,
                                                   valid_from=d(-50)))

    # ---- operators, ratings, aircraft, assignments, crew
    for k, (legal, dba, code, cc, part, aoc, aoc_days, status, ins_days, ins_limit, pref, comm, terms) in OPERATORS.items():
        R["operators"].append(base(id=reg("operator", k, u(f"operator:{k}")), legal_name=legal, dba_name=dba, operator_code=code,
                                   status=status, country_code=cc, regulatory_part=part, aoc_number=aoc, aoc_expiry=d(aoc_days),
                                   fleet_size=sum(1 for a in AIRCRAFT.values() if a[1] == k), ops_email=f"ops@{code.lower()}.example",
                                   ops_phone="+1 800 555 0100", ops_24h_phone="+1 800 555 0101", insurance_expiry=d(ins_days),
                                   insurance_limit_cents=ins_limit, w9_on_file=(cc == "US"), is_preferred=pref,
                                   commission_rate=Decimal(comm), payment_terms=terms))
    for opk, prog, level, label, issued_ago, exp in RATINGS:
        R["operator_safety_ratings"].append(base(id=reg("operator_safety_rating", f"{opk}:{prog}", u(f"rating:{opk}:{prog}")),
                                                 operator_id=ref("operator", opk), program=prog, rating_level=level, rating_label=label,
                                                 issued_date=d(-issued_ago), expiry_date=d(exp), auditor_name=label.split()[0],
                                                 is_current=True, report_document_id=ref("document", "audit_skyline") if (opk, prog) == ("skyline", "argus") else None,
                                                 verified_at=ago(issued_ago - 2), verified_by_user_id=uid["ops"]))
    for tail, (model, opk, year, home, rate, seats) in AIRCRAFT.items():
        aid = reg("aircraft", tail, u(f"aircraft:{tail}"))
        R["aircraft"].append(base(id=aid, tail_number=tail, serial_number=f"SN-{abs(hash(tail)) % 9000 + 1000}",
                                  aircraft_model_id=cat.model[model], operator_id=ref("operator", opk), status="active",
                                  year_of_manufacture=year, registration_country=tail[:1] if tail[0] in "NG" else "CH",
                                  home_base_airport_id=cat.apt[home], configured_seats=seats, wifi_provider="Starlink" if year >= 2020 else "Gogo Avance",
                                  amenities={"wifi": True, "galley": "full", "berthing": seats >= 12}, pets_allowed=True,
                                  hourly_rate_cents=rate, is_available_for_charter=True, last_verified_at=ago(15)))
        R["aircraft_operator_assignments"].append(base(id=u(f"aoa:{tail}"), aircraft_id=aid, operator_id=ref("operator", opk),
                                                       effective_from=date(year + 1, 3, 1), effective_to=None, is_current=True))
    for k, (first, last, role, opk, nat, lic, ratings, med_days, home, hours) in CREW.items():
        R["crew_members"].append(base(id=reg("crew_member", k, u(f"crew:{k}")), operator_id=ref("operator", opk), first_name=first,
                                      last_name=last, primary_role=role, status="active", nationality_code=nat,
                                      email=f"{first.lower()}.{last.lower()}@crew.example", license_number=enc(f"LIC-{k}"),
                                      license_last4=k[-4:].upper(), license_type=lic, license_country=nat, medical_class="Class 1",
                                      medical_expiry=d(med_days), type_ratings=ratings, total_hours=hours,
                                      hours_on_type={r: 300 + 90 * i for i, r in enumerate(ratings)}, base_airport_id=cat.apt[home],
                                      last_recurrent_at=d(-120), next_recurrent_due=d(245)))

    # ---- trips, legs, manifests, crew
    trip_total = {"t1": (4_419_000, 3_749_000), "t2": (2_639_400, 2_197_400), "t3": (3_540_000, 3_050_000)}
    for tk, (num, ttype, status, contact, lead, source, cur, legs) in TRIPS.items():
        tid = reg("trip", tk, u(f"trip:{tk}"))
        pax = len({p for lg in legs for p in lg[9]})
        sell, cost = trip_total.get(tk, (0, 0))
        R["trips"].append(base(id=tid, trip_number=num, trip_type=ttype, status=status,
                               account_holder_id=ref("account_holder", TRIP_ACCOUNT[tk]) if tk in TRIP_ACCOUNT else None,
                               primary_contact_id=ref("contact", contact), lead_passenger_id=ref("passenger", lead),
                               owner_user_id=uid["broker"], ops_user_id=uid["ops"], source=source, pax_count=pax,
                               leg_count=len(legs), departure_date=d(legs[0][2]), return_date=d(legs[-1][2]), currency=cur,
                               total_sell_cents=sell, total_cost_cents=cost,
                               special_requests="Dog on board (8kg Cavalier)" if tk == "t2" else None))
        for n, (dep, arr, day, hh, mm, tail, dfbo, afbo, customs, pax_keys, (pic, sic)) in enumerate(legs, start=1):
            lid = reg("leg", f"{tk}:{n}", u(f"leg:{tk}:{n}"))
            dist = haversine_nm(APT[dep][5], APT[dep][6], APT[arr][5], APT[arr][6])
            flight_min = round(dist / CRUISE[AIRCRAFT[tail][0]] * 60) + 25
            block_min = flight_min + 15
            dep_at = local(day, hh, mm, APT[dep][8])
            arr_at = dep_at + timedelta(minutes=block_min)
            R["legs"].append(base(id=lid, trip_id=tid, leg_number=n, status="scheduled", purpose="revenue",
                                  departure_airport_id=cat.apt[dep], arrival_airport_id=cat.apt[arr],
                                  departure_fbo_id=cat.fbo[dfbo] if dfbo else None, arrival_fbo_id=cat.fbo[afbo] if afbo else None,
                                  scheduled_departure_at=dep_at, scheduled_arrival_at=arr_at, departure_timezone=APT[dep][8],
                                  arrival_timezone=APT[arr][8], block_time_minutes=block_min, flight_time_minutes=flight_min,
                                  distance_nm=dist, aircraft_id=ref("aircraft", tail), operator_id=ref("operator", AIRCRAFT[tail][1]),
                                  pax_count=len(pax_keys), customs_required=customs, catering_notes="Light catering" if n == 1 else None,
                                  cost_cents=cost // len(legs), sell_cents=sell // len(legs)))
            for i, pk in enumerate(pax_keys):
                R["leg_passengers"].append(base(id=u(f"leg_pax:{tk}:{n}:{pk}"), leg_id=lid, passenger_id=ref("passenger", pk),
                                                is_lead_passenger=(pk == lead), seat_assignment=f"{i + 1}A",
                                                travel_document_id=ref("travel_document", pk),
                                                catering_selection={"meal": "vegetarian"} if pk == "priya" else {}))
            for ck, role in ((pic, "pic"), (sic, "sic")):
                R["leg_crew"].append(base(id=u(f"leg_crew:{tk}:{n}:{ck}"), leg_id=lid, crew_member_id=ref("crew_member", ck),
                                          crew_role=role, duty_start_at=dep_at - timedelta(minutes=90), duty_end_at=arr_at + timedelta(minutes=45)))

    # ---- quotes and line items
    for qk, (num, status, tk, ahk, ck, opk, tail, cur, sent_ago, valid_days, lines) in QUOTES.items():
        qid = reg("quote", qk, u(f"quote:{qk}"))
        subtotal = sum(l[5] for l in lines if l[0] != "federal_excise_tax")
        tax = sum(l[5] for l in lines if l[0] == "federal_excise_tax")
        cost = sum(l[6] for l in lines)
        R["quotes"].append(base(id=qid, quote_number=num, revision=1, is_current=True, status=status, trip_id=ref("trip", tk),
                                account_holder_id=ref("account_holder", ahk) if ahk else None, contact_id=ref("contact", ck),
                                prepared_by_user_id=uid["broker"], operator_id=ref("operator", opk),
                                aircraft_model_id=cat.model[AIRCRAFT[tail][0]], aircraft_id=ref("aircraft", tail), currency=cur,
                                subtotal_cents=subtotal, tax_cents=tax, total_cents=subtotal + tax, cost_total_cents=cost,
                                valid_until=ago(-valid_days), sent_at=ago(sent_ago) if sent_ago is not None else None,
                                first_viewed_at=ago(sent_ago, -2) if sent_ago is not None else None,
                                view_count=3 if sent_ago is not None else 0,
                                accepted_at=ago(4) if status == "accepted" else None,
                                terms="50% deposit on signature, balance 48h before departure. Cancellation per charter agreement.",
                                customer_notes="Pricing includes FET and standard catering." if cur == "USD" else "Pricing in EUR, VAT exempt (international)."))
        for i, (ltype, desc, qty, unit, price, sell, lcost, taxable, pt, leg_idx) in enumerate(lines):
            R["quote_line_items"].append(base(id=reg("quote_line_item", f"{qk}:{i}", u(f"qli:{qk}:{i}")), quote_id=qid, leg_id=None,
                                              line_type=ltype, description=desc, quantity=Decimal(qty), unit=unit,
                                              unit_price_cents=price, sell_cents=sell, cost_cents=lcost, is_taxable=taxable,
                                              tax_rate=Decimal("0"), is_pass_through=pt, sort_order=i))

    # ---- booking, invoices, payments (all against Q1 / Halcyon)
    q1_total, q1_cost = 4_419_000, 3_749_000
    deposit = q1_total // 2
    bid = reg("booking", "bk1", u("booking:bk1"))
    R["bookings"].append(base(id=bid, booking_number="BK-2026-0001", trip_id=ref("trip", "t1"), quote_id=ref("quote", "q1"),
                              account_holder_id=ref("account_holder", "halcyon"), status="funds_pending", operator_id=ref("operator", "skyline"),
                              operator_confirmation_ref="SKY-88412", contract_document_id=ref("document", "contract"),
                              signed_by_contact_id=ref("contact", "daniel"), esign_envelope_id="env_demo_bk1", currency="USD",
                              total_cents=q1_total, cost_cents=q1_cost, deposit_required_cents=deposit, deposit_due_at=ago(3),
                              deposit_received_at=ago(3), confirmed_at=ago(4), contract_sent_at=ago(4), contract_signed_at=ago(3),
                              cancellation_policy="100% refundable until 72h before departure; 50% thereafter; non-refundable inside 24h."))
    inv = {
        "inv1": ("INV-2026-0001", "deposit", "paid", -4, -2, deposit, 0, deposit, deposit, ago(3)),
        "inv2": ("INV-2026-0002", "balance", "partially_paid", -1, 8, deposit, 148_500, deposit - 148_500, 750_000, None),
    }
    for k, (num, itype, status, issue, due, total, tax, subtotal, paid, paid_at) in inv.items():
        R["invoices"].append(base(id=reg("invoice", k, u(f"invoice:{k}")), invoice_number=num, invoice_type=itype, status=status,
                                  account_holder_id=ref("account_holder", "halcyon"), booking_id=bid, trip_id=ref("trip", "t1"),
                                  issue_date=d(issue), due_date=d(due), payment_terms="due_on_receipt", currency="USD",
                                  subtotal_cents=subtotal, tax_cents=tax, total_cents=total, amount_paid_cents=paid,
                                  billing_address_id=ref("address", "halcyon"), sent_at=ago(-issue), paid_at=paid_at))
    R["invoice_line_items"].append(base(id=u("ili:inv1:0"), invoice_id=ref("invoice", "inv1"), quote_line_item_id=None, line_type="other",
                                        description="Deposit - 50% of quote Q-2026-0001", quantity=Decimal("1"), unit="each",
                                        unit_price_cents=deposit, amount_cents=deposit, is_taxable=False, tax_rate=Decimal("0"), sort_order=0))
    for i, (ltype, desc, qty, unit, price, sell, lcost, taxable, pt, _) in enumerate(QUOTES["q1"][10]):
        R["invoice_line_items"].append(base(id=u(f"ili:inv2:{i}"), invoice_id=ref("invoice", "inv2"),
                                            quote_line_item_id=ref("quote_line_item", f"q1:{i}"), line_type=ltype,
                                            description=f"Balance - {desc}", quantity=Decimal(qty), unit=unit, unit_price_cents=price // 2,
                                            amount_cents=sell // 2, is_taxable=False, tax_rate=Decimal("0"), sort_order=i))
    pay = [
        ("p1", "inv1", "wire", "cleared", deposit, 0, 3, "WIRE-HALCYON-0001", None, None, None),
        ("p2", "inv2", "credit_card", "cleared", 1_000_000, 29_300, 1, None, "stripe", "ch_demo_0002", None),
        ("p3", "inv2", "credit_card", "cleared", -250_000, 0, 0, None, "stripe", "re_demo_0003", "p2"),
    ]
    for k, ik, method, status, amount, fee, days_ago, refn, proc, txn, refund_of in pay:
        R["payments"].append(base(id=reg("payment", k, u(f"payment:{k}")), account_holder_id=ref("account_holder", "halcyon"),
                                  invoice_id=ref("invoice", ik), method=method, status=status, amount_cents=amount, currency="USD",
                                  fee_cents=fee, received_at=ago(days_ago), cleared_at=ago(days_ago), reference=refn, processor=proc,
                                  processor_txn_id=txn, refund_of_payment_id=ref("payment", refund_of) if refund_of else None,
                                  notes="Partial refund - duplicate surcharge" if amount < 0 else None))

    # ---- empty legs
    for dep, arr, opk, tail, day, h1, h2, ask, floor, seats, cur, source, ext, flex in EMPTY_LEGS:
        R["empty_legs"].append(base(id=reg("empty_leg", f"el:{dep}-{arr}", u(f"empty_leg:{dep}-{arr}")), operator_id=ref("operator", opk),
                                    aircraft_id=ref("aircraft", tail), aircraft_model_id=cat.model[AIRCRAFT[tail][0]], status="available",
                                    source=source, departure_airport_id=cat.apt[dep], arrival_airport_id=cat.apt[arr],
                                    earliest_departure_at=local(day, h1, 0, APT[dep][8]), latest_departure_at=local(day, h2, 0, APT[dep][8]),
                                    seats_available=seats, asking_price_cents=ask, floor_price_cents=floor, currency=cur,
                                    is_flexible_routing=flex, routing_radius_nm=100 if flex else None, published_at=ago(1),
                                    expires_at=local(day - 1, 18, 0, APT[dep][8]), external_ref=ext))

    # ---- tasks, activities, tags
    for k, title, ttype, status, prio, who, due, ent, dedupe in TASKS:
        R["tasks"].append(base(id=u(f"task:{k}"), title=title, task_type=ttype, status=status, priority=prio,
                               assigned_to_user_id=uid[who], entity_type=ent[0] if ent else None, entity_id=ref(*ent) if ent else None,
                               due_at=ago(-due), started_at=ago(2) if status == "in_progress" else None,
                               completed_at=ago(3) if status == "completed" else None,
                               completed_by_user_id=uid[who] if status == "completed" else None,
                               blocked_reason="Agent unreachable until after the road trip" if status == "blocked" else None,
                               source_system="expiry_sweep" if dedupe else "manual", dedupe_key=dedupe))
    for i, (days_ago, atype, direction, subject, ck, ent, who) in enumerate(ACTIVITIES):
        R["activities"].append(base(id=u(f"activity:{i}"), activity_type=atype, direction=direction, subject=subject,
                                    body=f"{subject}. Logged by {USERS[who][1]}.", user_id=uid[who], contact_id=ref("contact", ck),
                                    entity_type=ent[0] if ent else None, entity_id=ref(*ent) if ent else None,
                                    occurred_at=ago(days_ago, 2), duration_minutes=20 if atype in ("call", "meeting") else None))
    for k, name, category, color in TAGS:
        R["tags"].append(base(id=reg("tag", k, u(f"tag:{k}")), name=name, category=category, color=color))
    for tk, etype, ekey in ENTITY_TAGS:
        R["entity_tags"].append(base(id=u(f"entity_tag:{tk}:{etype}:{ekey}"), tag_id=ref("tag", tk), entity_type=etype, entity_id=ref(etype, ekey)))

    # ---- document links
    for dk, (_t, _title, _m, _c, _e, links) in DOCUMENTS.items():
        for etype, ekey, role in links:
            R["document_links"].append(base(id=u(f"doclink:{dk}:{etype}:{ekey}"), document_id=ref("document", dk), entity_type=etype,
                                            entity_id=ref(etype, ekey), link_role=role, is_primary=(role == "contract")))

    # ---- audit trail, as the application would have written it
    actor = f"{USERS['broker'][1]} <{USERS['broker'][0]}>"
    events = [
        (12, "insert", "client", DEMO, "Demo Brokerage", "owner", None, None),
        (11, "insert", "contact", ref("contact", "halcyon"), "Halcyon Capital Partners", "broker", None, None),
        (11, "insert", "contact", ref("contact", "victoria"), "Victoria Ashworth", "broker", None, None),
        (10, "insert", "trip", ref("trip", "t1"), "BLX-2026-001", "broker", None, None),
        (9, "insert", "quote", ref("quote", "q1"), "Q-2026-0001 r1", "broker", None, None),
        (8, "update", "quote", ref("quote", "q1"), "Q-2026-0001 r1", "broker", {"status": "sent"}, {"status": "accepted"}),
        (7, "insert", "booking", bid, "BK-2026-0001", "broker", None, None),
        (6, "insert", "invoice", ref("invoice", "inv1"), "INV-2026-0001", "ops", None, None),
        (5, "insert", "payment", ref("payment", "p1"), "WIRE-HALCYON-0001", "ops", None, None),
        (4, "soft_delete", "contact", u("contact:marcus-duplicate"), "Marcus Chen (duplicate)", "broker", {"deleted_at": None}, {"deleted_at": "now"}),
    ]
    for i, (_days_ago, action, etype, eid, label, who, before, after) in enumerate(events):
        R["audit_logs"].append({"id": u(f"audit:{i}"), "client_id": DEMO, "occurred_at": audit_at(i), "action": action,
                                "entity_type": etype, "entity_id": eid, "entity_label": label, "actor_type": "user",
                                "actor_user_id": uid[who], "actor_label": f"{USERS[who][1]} <{USERS[who][0]}>",
                                "changed_fields": list(after) if after else None, "before": before, "after": after,
                                "request_id": u(f"request:{i}"), "ip_address": ipaddress.ip_address("203.0.113.10"),
                                "user_agent": "bitlux-web/0.1 (demo seed)"})
    del actor
    return R


def tenant_filter(table: str) -> str:
    """Column that scopes a table to a tenant. The tenant root has no client_id."""
    return "id" if table == "clients" else "client_id"


def expected_counts() -> dict[str, int]:
    """Rows per tenant table the seed produces -- computed, never hand-maintained."""
    return {t: len(rows) for t, rows in build(Catalog.placeholder()).items()}


# ------------------------------------------------------------------ writing
UPDATE_ONLY = {"clients": ("id",), "audit_logs": ("id", "occurred_at")}
CASTS = {"path": "::text::ltree"}
IMMUTABLE = {"audit_logs"}


async def upsert(conn, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols: list[str] = []
    for r in rows:
        cols.extend(c for c in r if c not in cols)
    rows = [{c: r.get(c) for c in cols} for r in rows]
    conflict = UPDATE_ONLY.get(table, ("id",))
    values = ", ".join(f"${i + 1}{CASTS.get(c, '')}" for i, c in enumerate(cols))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({values}) ON CONFLICT ({', '.join(conflict)}) "
    if table in IMMUTABLE:
        sql += "DO NOTHING"
    else:
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict and c != "created_by")
        sql += f"DO UPDATE SET {sets}"
    await conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])


async def main() -> int:
    conn = await connect()
    try:
        who = await role_info(conn)
        print(f"connected as {who.current_user} (superuser={who.is_superuser})")

        # A. global catalog, as the owner
        print("\nA. global reference catalog (client_id IS NULL)")
        cat = await ensure_catalog(conn)
        for table, names in cat.inserted.items():
            total = {"manufacturers": len(MANUFACTURERS), "aircraft_models": len(MODELS), "airports": len(AIRPORTS), "fbos": len(FBOS)}[table]
            print(f"   {table:<18} {total:>3} ensured  ({len(names)} inserted{': ' + ', '.join(names) if names else ''})")

        # B. tenant data, through the application path
        print("\nB. demo tenant, written as the application role under RLS")
        rows = build(cat)
        async with conn.transaction():
            info = await enter_tenant(conn, DEMO)
            print(f"   role={info.current_user} superuser={info.is_superuser} bypassrls={info.bypass_rls} app.client_id={DEMO}")
            for table in ORDER:
                await upsert(conn, table, rows[table])
            # Late-bound references (targets did not exist yet at insert time).
            await conn.execute("UPDATE account_holders SET billing_address_id = a.id FROM addresses a "
                               "WHERE a.owner_type = 'account_holder' AND a.owner_id = account_holders.id AND a.is_primary")
            await conn.execute("UPDATE trips SET accepted_quote_id = $1, booking_id = $2 WHERE id = $3",
                               u("quote:q1"), u("booking:bk1"), u("trip:t1"))

            print(f"\n   {'table':<30} {'rows':>5}")
            total = 0
            for table in ORDER:
                n = await conn.fetchval(f"SELECT count(*) FROM {table} WHERE {tenant_filter(table)} = $1", DEMO)
                total += n
                print(f"   {table:<30} {n:>5}")
            print(f"   {'total':<30} {total:>5}")

            stray = await conn.fetchval(
                "SELECT count(*) FROM audit_logs WHERE client_id = $1 AND tableoid = 'audit_logs_default'::regclass", DEMO)
            if stray:
                print(f"\n   WARNING: {stray} audit row(s) landed in audit_logs_default -- run `make partition-maintenance`.")
        print("\nseed complete.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
