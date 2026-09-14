#!/usr/bin/env python
"""Provision audit_logs monthly partitions and police the default partition.

Run monthly (``make partition-maintenance``), or from cron/CI. Idempotent.

What it does
------------
1. Lists the existing partitions of ``audit_logs`` and their bounds.
2. Ensures a partition exists for every month from the current one through
   ``--months`` ahead (default 12, so there is always >= 12 months of runway).
   Existing months are skipped; the DEFAULT partition is left alone.
3. Counts rows in ``audit_logs_default``. Anything there is a row that arrived
   for a month nobody provisioned -- and while such rows exist, creating the
   partition they belong to fails ("would be violated by some row"). So:
   **>0 rows => WARNING, exit 1**, for cron/CI to alert on.

Exit codes: 0 healthy, 1 default partition non-empty, 2 could not create a
partition (usually because of 1 -- the error will say so).

Must run as the schema owner (creating partitions needs CREATE on the parent).
New partitions inherit the parent's row triggers (immutability, PG13+) and are
reachable only through the parent -- direct privileges are revoked, matching
migration 012, because partitions carry no RLS of their own.

See DATA_MODEL.md 3.9 (audit_logs) and the README's Operational Runbook.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import date

from _db import APP_ROLE, connect

PARENT = "audit_logs"
BOUND_RE = re.compile(r"FOR VALUES FROM \('(\d{4}-\d{2}-\d{2})[^']*'\) TO \('(\d{4}-\d{2}-\d{2})[^']*'\)")


@dataclass(frozen=True)
class Partition:
    name: str
    lo: date | None  # None => DEFAULT partition
    hi: date | None

    @property
    def is_default(self) -> bool:
        return self.lo is None

    def covers(self, lo: date, hi: date) -> bool:
        return not self.is_default and self.lo <= lo and hi <= self.hi  # type: ignore[operator]


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def months_ahead(start: date, count: int) -> list[tuple[date, date]]:
    """[month_start, next_month_start) for the current month plus `count` more."""
    out: list[tuple[date, date]] = []
    lo = month_start(start)
    for _ in range(count + 1):
        hi = next_month(lo)
        out.append((lo, hi))
        lo = hi
    return out


async def list_partitions(conn) -> list[Partition]:
    rows = await conn.fetch(
        """
        SELECT c.relname AS name, pg_get_expr(c.relpartbound, c.oid) AS bound
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = $1::regclass
        ORDER BY c.relname
        """,
        PARENT,
    )
    out: list[Partition] = []
    for r in rows:
        if r["bound"] == "DEFAULT":
            out.append(Partition(r["name"], None, None))
            continue
        m = BOUND_RE.search(r["bound"])
        if not m:
            print(f"  ! cannot parse bound for {r['name']}: {r['bound']}", file=sys.stderr)
            continue
        out.append(Partition(r["name"], date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))))
    return out


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--months", type=int, default=12, help="months of runway beyond the current month (default 12)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be created, change nothing")
    args = ap.parse_args()

    conn = await connect()
    try:
        existing = await list_partitions(conn)
        default = next((p for p in existing if p.is_default), None)
        monthly = [p for p in existing if not p.is_default]

        print(f"audit_logs partitions: {len(monthly)} monthly"
              + (f", default = {default.name}" if default else ", NO DEFAULT PARTITION"))
        if monthly:
            print(f"  range covered : {monthly[0].lo:%Y-%m} .. {monthly[-1].hi:%Y-%m} (exclusive)")

        created: list[str] = []
        skipped = 0
        failures: list[tuple[str, str]] = []
        wanted = months_ahead(date.today(), args.months)
        print(f"  ensuring      : {wanted[0][0]:%Y-%m} .. {wanted[-1][0]:%Y-%m} ({len(wanted)} months)")

        for lo, hi in wanted:
            if any(p.covers(lo, hi) for p in existing):
                skipped += 1
                continue
            name = f"{PARENT}_{lo:%Y_%m}"
            if args.dry_run:
                print(f"  would create  : {name}  [{lo} .. {hi})")
                created.append(name)
                continue
            try:
                async with conn.transaction():
                    await conn.execute(
                        f"CREATE TABLE {name} PARTITION OF {PARENT} "
                        f"FOR VALUES FROM ('{lo:%Y-%m-%d}') TO ('{hi:%Y-%m-%d}')"
                    )
                    # Reachable only through the parent (see module docstring).
                    await conn.execute(f"REVOKE ALL ON {name} FROM {APP_ROLE}")
                created.append(name)
                print(f"  created       : {name}  [{lo} .. {hi})")
            except asyncpg.PostgresError as exc:  # noqa: F821 - imported below for type only
                failures.append((name, str(exc).splitlines()[0]))
                print(f"  FAILED        : {name}: {failures[-1][1]}")

        print(f"  summary       : created {len(created)}, already present {skipped}, failed {len(failures)}")

        # Sanity: new partitions must carry the immutability trigger.
        if created and not args.dry_run:
            missing_trg = await conn.fetch(
                """
                SELECT c.relname
                FROM pg_class c
                WHERE c.relname = ANY($1::text[])
                  AND NOT EXISTS (SELECT 1 FROM pg_trigger t
                                  WHERE t.tgrelid = c.oid AND t.tgname = 'audit_logs_immutable')
                """,
                created,
            )
            if missing_trg:
                print(f"  ! immutability trigger missing on: {[r['relname'] for r in missing_trg]}")
                return 2
            print("  triggers      : audit_logs_immutable present on every new partition")

        # Default partition health.
        if default is None:
            print("WARNING: no DEFAULT partition -- an insert for an unprovisioned month will fail outright")
            return 1
        n = await conn.fetchval(f"SELECT count(*) FROM {default.name}")
        if n:
            oldest, newest = await conn.fetchrow(
                f"SELECT min(occurred_at), max(occurred_at) FROM {default.name}"
            )
            print(f"WARNING: {default.name} holds {n} row(s) ({oldest:%Y-%m-%d} .. {newest:%Y-%m-%d}).")
            print("         These landed in months with no partition. Provision those months (they may")
            print("         be in the past), move the rows out, and re-run. Partition creation for")
            print("         any month with rows here will fail until then.")
            return 1
        print(f"  default       : {default.name} is empty  (OK)")
        return 2 if failures else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncpg  # for the exception class used above

    sys.exit(asyncio.run(main()))
