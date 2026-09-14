"""Aggregates every v1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    account_holders, activities, admin, aircraft, aircraft_models, airports, auth, bookings, clients, contacts, crew,
    documents, empty_legs, graph, invoices, legs, manufacturers, operators, passengers, payments, quotes, search,
    segments, tasks, trips,
)

api_router = APIRouter()
for module in (
    auth, admin, search, graph,
    clients, segments, contacts, passengers, account_holders,
    manufacturers, aircraft_models, operators, aircraft, airports, crew,
    trips, legs, empty_legs, quotes, bookings, invoices, payments,
    documents, tasks, activities,
):
    api_router.include_router(module.router)
