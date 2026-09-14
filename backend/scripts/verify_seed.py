#!/usr/bin/env python
"""Assert the "Demo Brokerage" seed looks the way seed.py says it should.

Runs through the application path (``SET LOCAL ROLE bitlux_app`` + tenant set),
so every query below is also a live test that RLS lets the tenant see its own
rows. Prints PASS/FAIL per check; exits 1 on any FAIL.

Usage:  make verify-seed   (or)  backend/.venv/bin/python backend/scripts/verify_seed.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from _db import connect, enter_tenant
from seed import AIRPORTS, DEMO, FBOS, MANUFACTURERS, MODELS, ORDER, expected_counts, tenant_filter

FAILS: list[str] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


async def main() -> int:
    conn = await connect()
    try:
        async with conn.transaction():
            info = await enter_tenant(conn, DEMO)
            print(f"verifying as {info.current_user} (RLS enforced), tenant {DEMO}\n")

            # 1. row counts ----------------------------------------------------
            print("1. row counts per table")
            expected = expected_counts()
            mismatches = []
            for table in ORDER:
                got = await conn.fetchval(f"SELECT count(*) FROM {table} WHERE {tenant_filter(table)} = $1", DEMO)
                if got != expected[table]:
                    mismatches.append(f"{table}: expected {expected[table]}, got {got}")
            report("tenant tables match seed.expected_counts()",
                   not mismatches, f"{len(ORDER)} tables, {sum(expected.values())} rows" if not mismatches else "; ".join(mismatches))
            cat_missing = []
            for name, *_ in MANUFACTURERS:
                if not await conn.fetchval("SELECT 1 FROM manufacturers WHERE client_id IS NULL AND lower(name)=lower($1)", name):
                    cat_missing.append(f"manufacturer {name}")
            for _m, name, *_ in MODELS:
                if not await conn.fetchval("SELECT 1 FROM aircraft_models WHERE client_id IS NULL AND lower(name)=lower($1)", name):
                    cat_missing.append(f"model {name}")
            for icao, *_ in AIRPORTS:
                if not await conn.fetchval("SELECT 1 FROM airports WHERE client_id IS NULL AND icao_code=$1", icao):
                    cat_missing.append(f"airport {icao}")
            for _apt, name, _b in FBOS:
                if not await conn.fetchval("SELECT 1 FROM fbos WHERE client_id IS NULL AND lower(name)=lower($1)", name):
                    cat_missing.append(f"fbo {name}")
            report("global catalog rows visible to the tenant",
                   not cat_missing, f"{len(MANUFACTURERS)} manufacturers, {len(MODELS)} models, {len(AIRPORTS)} airports, {len(FBOS)} FBOs"
                   if not cat_missing else ", ".join(cat_missing))

            # 2. manifest for one trip ----------------------------------------
            print("\n2. all passengers on trip BLX-2026-001")
            rows = await conn.fetch(
                """
                SELECT DISTINCT p.first_name || ' ' || p.last_name AS name
                FROM leg_passengers lp
                JOIN legs l ON l.id = lp.leg_id AND l.deleted_at IS NULL
                JOIN trips t ON t.id = l.trip_id AND t.deleted_at IS NULL
                JOIN passengers p ON p.id = lp.passenger_id
                WHERE t.trip_number = 'BLX-2026-001' AND lp.deleted_at IS NULL
                ORDER BY 1
                """)
            got = {r["name"] for r in rows}
            want = {"Priya Raman", "Rafael Mendes"}
            report("manifest matches", got == want, ", ".join(sorted(got)) or "(none)")

            # 3. documents for one tail --------------------------------------
            print("\n3. all documents for aircraft N650BX")
            rows = await conn.fetch(
                """
                SELECT d.document_type::text AS t, d.title
                FROM document_links dl
                JOIN aircraft a ON a.id = dl.entity_id AND dl.entity_type = 'aircraft'
                JOIN documents d ON d.id = dl.document_id AND d.deleted_at IS NULL
                WHERE a.tail_number = 'N650BX' AND dl.deleted_at IS NULL
                ORDER BY 1
                """)
            got = {r["t"] for r in rows}
            want = {"insurance_certificate", "aoc_certificate"}
            report("document set matches", got == want, ", ".join(sorted(got)) or "(none)")

            # 4. passports expiring soon --------------------------------------
            print("\n4. passports expiring in the next 180 days")
            rows = await conn.fetch(
                """
                SELECT p.first_name || ' ' || p.last_name AS name, td.expiry_date
                FROM travel_documents td
                JOIN passengers p ON p.id = td.passenger_id
                WHERE td.document_type = 'passport' AND td.deleted_at IS NULL
                  AND td.expiry_date BETWEEN current_date AND current_date + 180
                ORDER BY td.expiry_date
                """)
            got = {r["name"] for r in rows}
            want = {"Tomas Lindqvist", "Priya Raman"}
            report("expiring passports match", got == want,
                   ", ".join(f"{r['name']} ({r['expiry_date']})" for r in rows) or "(none)")

            # 5. lapsed operator ratings --------------------------------------
            print("\n5. operators with a lapsed safety rating")
            n = await conn.fetchval(
                """
                SELECT count(DISTINCT operator_id) FROM operator_safety_ratings
                WHERE is_current AND deleted_at IS NULL AND expiry_date < current_date
                """)
            report("no lapsed ratings", n == 0, f"{n} operator(s) lapsed")

            # 6. double-booking check ---------------------------------------
            print("\n6. is N650BX double-booked?")
            n = await conn.fetchval(
                """
                SELECT count(*)
                FROM legs a
                JOIN legs b ON b.aircraft_id = a.aircraft_id AND b.id > a.id
                JOIN aircraft ac ON ac.id = a.aircraft_id
                WHERE ac.tail_number = 'N650BX'
                  AND a.deleted_at IS NULL AND b.deleted_at IS NULL
                  AND tstzrange(a.scheduled_departure_at, a.scheduled_arrival_at)
                   && tstzrange(b.scheduled_departure_at, b.scheduled_arrival_at)
                """)
            legs = await conn.fetchval(
                "SELECT count(*) FROM legs l JOIN aircraft a ON a.id = l.aircraft_id WHERE a.tail_number = 'N650BX' AND l.deleted_at IS NULL")
            report("no overlapping legs", n == 0, f"{legs} leg(s) on the tail, {n} overlap(s)")

            # 7. tenant isolation, from inside the app path --------------------
            print("\n7. tenant isolation (bonus)")
            other = uuid.uuid5(DEMO, "some-other-tenant")
            await conn.fetchval("SELECT set_config('app.client_id', $1, true)", str(other))
            leak = sum([await conn.fetchval(f"SELECT count(*) FROM {t}") for t in ("clients", "contacts", "trips", "audit_logs")])
            await conn.fetchval("SELECT set_config('app.client_id', $1, true)", str(DEMO))
            report("another tenant sees none of the demo rows", leak == 0, f"{leak} row(s) visible")

        print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}")
        return 0 if not FAILS else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
