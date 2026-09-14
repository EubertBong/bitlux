"""Domain queries against the seeded demo tenant."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.enums import AircraftCategory, EntityType, LegPurpose, QuoteStatus, TaskStatus
from app.repositories import (
    AircraftRepository,
    AirportRepository,
    DocumentRepository,
    EmptyLegRepository,
    EntityNotFound,
    InvoiceRepository,
    LegRepository,
    OperatorRepository,
    OperatorSafetyRatingRepository,
    PassengerRepository,
    QuoteLineItemRepository,
    QuoteRepository,
    TaskRepository,
    TripRepository,
    ensure_entity_exists,
    resolve_entity,
)


async def test_quote_supersede_creates_new_revision(session, seed_id):
    quotes = QuoteRepository(session)
    old = await quotes.get_or_raise(seed_id("quote:q3"))
    assert old.revision == 1 and old.is_current and old.status == QuoteStatus.DRAFT
    old_items = await QuoteLineItemRepository(session).for_quote(old.id)

    new = await quotes.supersede(old.id, {"total_cents": old.total_cents + 100_000, "internal_notes": "r2: +$1,000"})

    assert new.revision == 2 and new.is_current and new.parent_quote_id == old.id
    assert new.quote_number == old.quote_number and new.trip_id == old.trip_id
    assert new.total_cents == old.total_cents + 100_000
    assert not old.is_current and old.status == QuoteStatus.SUPERSEDED
    assert len(await QuoteLineItemRepository(session).for_quote(new.id)) == len(old_items) == 5
    assert [q.id for q in await quotes.current_for_trip(old.trip_id)] == [new.id]
    assert [q.revision for q in await quotes.revisions(old.quote_number)] == [1, 2]


async def test_aircraft_double_booked_detects_conflict(session, seed_id):
    aircraft, legs, trips, airports = AircraftRepository(session), LegRepository(session), TripRepository(session), AirportRepository(session)
    tail = await aircraft.by_tail("N650BX")
    (existing,) = [l for l in await legs.list(aircraft_id=tail.id)]
    at = existing.scheduled_departure_at + timedelta(hours=1)

    assert await aircraft.double_booked(tail.id, at) == [], "one leg is not a conflict"

    trip = await trips.create({"trip_number": "TEST-DB-001", "primary_contact_id": seed_id("contact:jaylen")})
    ksfo, kjfk = await airports.by_code("KSFO"), await airports.by_code("JFK")
    await legs.create({
        "trip_id": trip.id, "leg_number": 1, "purpose": LegPurpose.REVENUE,
        "departure_airport_id": ksfo.id, "arrival_airport_id": kjfk.id,
        "scheduled_departure_at": existing.scheduled_departure_at + timedelta(minutes=30),
        "scheduled_arrival_at": existing.scheduled_arrival_at + timedelta(minutes=30),
        "departure_timezone": ksfo.timezone, "arrival_timezone": kjfk.timezone,
        "aircraft_id": tail.id, "operator_id": tail.operator_id,
    })

    conflict = await aircraft.double_booked(tail.id, at)
    assert len(conflict) == 2 and existing.id in {l.id for l in conflict}
    assert len(await aircraft.conflicting_legs(tail.id, existing.scheduled_departure_at, existing.scheduled_arrival_at, exclude_leg_id=existing.id)) == 1
    assert tail.id not in {a.id for a in await aircraft.available_between(tail.aircraft_model_id, at, at + timedelta(hours=1))}


async def test_operator_lapsed_rating_finds_expired(session, seed_id):
    operators = OperatorRepository(session)
    assert await operators.with_lapsed_rating() == [], "the seed ships every rating current"

    await OperatorSafetyRatingRepository(session).update(seed_id("rating:crown:isbao"), {"expiry_date": date.today() - timedelta(days=1)})

    lapsed = await operators.with_lapsed_rating()
    assert [o.legal_name for o in lapsed] == ["Atlantic Crown Aviation Ltd"]
    # still exactly one operator even though Crown has two current ratings
    assert len(lapsed) == 1


async def test_empty_leg_search_by_route(session):
    empty = EmptyLegRepository(session)
    window = (date.today(), date.today() + timedelta(days=30))

    hits = await empty.search("KTEB", "KOPF", *window)
    assert len(hits) == 1 and hits[0].asking_price_cents == 1_450_000
    assert len(await empty.search("TEB", "OPF", *window)) == 1, "IATA codes work too"
    assert await empty.search("KOPF", "KTEB", *window) == [], "direction matters"
    assert len(await empty.search("KTEB", "KOPF", *window, cabin_class=AircraftCategory.SUPER_MIDSIZE_JET)) == 1, "G280"
    assert await empty.search("KTEB", "KOPF", *window, cabin_class=AircraftCategory.LIGHT_JET) == []
    assert await empty.search("KTEB", "KOPF", date.today() + timedelta(days=200), date.today() + timedelta(days=230)) == []


async def test_ar_aging_buckets_correctly(session, seed_id):
    invoices = InvoiceRepository(session)
    report = await invoices.ar_aging()
    # Seed: INV-0001 paid (excluded); INV-0002 due in 8 days, 2,209,500 billed, 750,000 net paid.
    assert report.buckets["current"].count == 1
    assert report.buckets["current"].balance_cents == 2_209_500 - 750_000
    assert all(report.buckets[b].count == 0 for b in ("1-30", "31-60", "61-90", "90+"))
    assert report.overdue_cents == 0

    await invoices.create({
        "invoice_number": "TEST-AGE-045", "status": "issued", "account_holder_id": seed_id("account_holder:halcyon"),
        "issue_date": date.today() - timedelta(days=60), "due_date": date.today() - timedelta(days=45),
        "subtotal_cents": 100_000, "total_cents": 100_000,
    })
    report = await invoices.ar_aging()
    assert (report.buckets["31-60"].count, report.buckets["31-60"].balance_cents) == (1, 100_000)
    assert report.overdue_cents == 100_000 and report.total_cents == 1_459_500 + 100_000
    assert [i.invoice_number for i in await invoices.overdue()] == ["TEST-AGE-045"]


async def test_task_my_queue_ordering(session, broker_id):
    tasks = TaskRepository(session)
    queue = await tasks.my_queue(broker_id)
    assert [t.title[:32] for t in queue] == [
        "Chase balance payment on INV-202",      # high, overdue 3d, open
        "Follow up with Lindqvist Family ",      # high, overdue 1d, in_progress
        "Prepare quote for BLX-2026-004 (",      # normal, due in 3d
    ], "urgent/high first, then soonest due; completed, blocked and cancelled excluded"
    assert all(t.status in (TaskStatus.OPEN, TaskStatus.IN_PROGRESS) for t in queue)

    overdue = {t.title[:20] for t in await tasks.overdue()}
    assert "Call Jaylen Brooks a" in overdue, "blocked tasks are still late"
    assert "Send charter agreeme" not in overdue, "completed tasks are not"


async def test_document_for_entity_polymorphic(session, seed_id):
    docs = DocumentRepository(session)
    found = await docs.for_entity(EntityType.AIRCRAFT, seed_id("aircraft:N650BX"))
    assert {d.document_type.value for d in found} == {"insurance_certificate", "aoc_certificate"}
    assert await docs.for_entity(EntityType.AIRCRAFT, uuid.uuid4()) == []

    # resolution mirrors the DB trigger: in-tenant rows, global catalog rows, nothing else
    assert (await resolve_entity(session, EntityType.AIRCRAFT, seed_id("aircraft:N650BX"))).tail_number == "N650BX"
    kteb = await AirportRepository(session).by_code("KTEB")
    assert (await resolve_entity(session, EntityType.AIRPORT, kteb.id)).client_id is None, "global catalog rows resolve"
    with pytest.raises(EntityNotFound):
        await ensure_entity_exists(session, EntityType.CONTACT, uuid.uuid4())
    with pytest.raises(EntityNotFound):
        await docs.attach(found[0].id, EntityType.TRIP, uuid.uuid4())


async def test_passenger_manifest_and_history(session, seed_id):
    passengers = PassengerRepository(session)
    trip = await TripRepository(session).with_legs(seed_id("trip:t1"))
    assert [l.leg_number for l in trip.legs] == [1, 2]
    names = {f"{p.first_name} {p.last_name}" for p in await passengers.flown_on_leg(trip.legs[0].id)}
    assert names == {"Priya Raman", "Rafael Mendes"}
    history = await passengers.flight_history(seed_id("passenger:priya"))
    assert len(history) == 2 and history[0].scheduled_departure_at >= history[1].scheduled_departure_at


async def test_trip_queries(session):
    trips = TripRepository(session)
    assert {t.trip_number for t in await trips.by_status("confirmed")} == {"BLX-2026-001"}
    upcoming = await trips.by_date_range(date.today(), date.today() + timedelta(days=30))
    assert {t.trip_number for t in upcoming} == {"BLX-2026-001", "BLX-2026-002"}
    thin = await trips.with_margin_below(600_000)
    assert [(t.trip_number, t.margin_cents) for t in thin] == [("BLX-2026-002", 442_000), ("BLX-2026-003", 490_000)], "thinnest first"
    assert [t.trip_number for t in await trips.with_margin_below(450_000)] == ["BLX-2026-002"]
