"""End-to-end API behaviour against the seeded demo tenant, as bitlux_app under RLS."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert

from app.models import Contact
from app.models.base import uuid7
from app.models.enums import EntityType
from app.repositories import AuditLogRepository, tenant_transaction

from ..conftest import BROKER, DEMO, u
from .conftest import API, DEMO_PASSWORD, login


async def test_auth_login_and_me(client):
    r = await client.post(f"{API}/auth/login", json={"email": "broker@demo.test", "password": DEMO_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "broker@demo.test" and me.json()["role"] == "broker"
    assert "contacts.create" in me.json()["permissions"] and "invoices.create" not in me.json()["permissions"]

    bad = await client.post(f"{API}/auth/login", json={"email": "broker@demo.test", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "unauthorized"
    assert (await client.get(f"{API}/auth/me")).status_code == 401


async def test_auth_refresh(client):
    pair = (await client.post(f"{API}/auth/login", json={"email": "ops@demo.test", "password": DEMO_PASSWORD})).json()
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"] != pair["access_token"] and new["refresh_token"] != pair["refresh_token"]
    assert (await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"})).status_code == 200
    # Rotation: the old refresh token is dead.
    replay = await client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert replay.status_code == 401
    # Logout kills the new one too.
    assert (await client.post(f"{API}/auth/logout", json={"refresh_token": new["refresh_token"]})).status_code == 204
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": new["refresh_token"]})).status_code == 401


async def test_permission_denied_on_create_without_permission(client, ops):
    r = await client.post(f"{API}/contacts", headers=ops, json={"display_name": "Nope", "last_name": "Nope"})
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "permission_denied" and "contacts.create" in err["message"] and err["details"]["role"] == "ops"
    # ...but ops can read trips
    assert (await client.get(f"{API}/trips", headers=ops)).status_code == 200


async def test_tenant_isolation_via_api(client, broker, other_tenant):
    _other, b_contact_id, b_email = other_tenant
    r = await client.get(f"{API}/contacts/{b_contact_id}", headers=broker)
    assert r.status_code == 404, "another tenant's row must be indistinguishable from a missing one"
    assert r.json()["error"]["code"] == "not_found"
    # and the graph / relationships path agrees
    assert (await client.get(f"{API}/graph/contact/{b_contact_id}", headers=broker)).status_code == 404
    # tenant B's own user can see it
    b_headers = await login(client, b_email)
    assert (await client.get(f"{API}/contacts/{b_contact_id}", headers=b_headers)).status_code == 200
    assert (await client.get(f"{API}/contacts", headers=b_headers)).json()["total"] == 1


async def test_search_returns_grouped_results(client, owner):
    r = await client.get(f"{API}/search", params={"q": "halcyon"}, headers=owner)
    assert r.status_code == 200
    results = r.json()["results"]
    assert "contacts" in results and any("Halcyon" in h["label"] for h in results["contacts"])
    hit = results["contacts"][0]
    assert set(hit) >= {"id", "type", "label", "subtitle", "url", "rank"} and hit["url"].startswith("/contacts/")

    r = await client.get(f"{API}/search", params={"q": "gulf"}, headers=owner)  # prefix match
    assert "manufacturers" in r.json()["results"]
    r = await client.get(f"{API}/search", params={"q": "skyline", "types": "operators,contacts"}, headers=owner)
    assert set(r.json()["results"]) == {"operators"}
    r = await client.get(f"{API}/search", params={"q": "BLX-2026-001"}, headers=owner)
    assert [h["label"] for h in r.json()["results"]["trips"]] == ["BLX-2026-001"]


async def test_search_respects_tenant(client, broker, other_tenant):
    r = await client.get(f"{API}/search", params={"q": "zebrawood"}, headers=broker)
    assert r.status_code == 200 and "contacts" not in r.json()["results"]
    # ops has no contacts.view, so contacts never appear for ops even when they match
    ops = await login(client, "ops@demo.test")
    assert "contacts" not in (await client.get(f"{API}/search", params={"q": "halcyon"}, headers=ops)).json()["results"]


async def test_graph_depth_1_on_contact_returns_expected_nodes(client, owner):
    halcyon = u("contact:halcyon")
    r = await client.get(f"{API}/graph/contact/{halcyon}", headers=owner)
    assert r.status_code == 200
    g = r.json()
    types = {n["type"] for n in g["nodes"]}
    assert {"contact", "segment", "contact_channel", "account_holder", "activity"} <= types
    root = next(n for n in g["nodes"] if n["id"] == str(halcyon))
    assert root["label"] == "Halcyon Capital Partners" and root["url"] == f"/contacts/{halcyon}"
    assert all(set(e) == {"from", "to", "type", "label"} for e in g["edges"])
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"]), "every edge endpoint is a node"
    assert any(e["type"] == "in_segment" for e in g["edges"])
    # the /relationships alias returns the same neighbourhood
    rel = await client.get(f"{API}/contacts/{halcyon}/relationships", headers=owner)
    assert rel.status_code == 200 and {n["id"] for n in rel.json()["nodes"]} == ids


async def test_graph_depth_2_caps_at_200_nodes(client, owner, bare_session):
    ok = await client.get(f"{API}/graph/client/{DEMO}", params={"depth": 2}, headers=owner)
    assert ok.status_code == 200 and 20 < len(ok.json()["nodes"]) < 200

    # Add 250 contacts to the tenant; the client's neighbourhood now blows the cap.
    async with tenant_transaction(bare_session, DEMO, BROKER):
        await bare_session.execute(insert(Contact.__table__), [
            {"id": uuid7(), "client_id": DEMO, "display_name": f"Bulk {i}", "last_name": f"Bulk{i}", "contact_type": "individual"} for i in range(250)
        ])
    r = await client.get(f"{API}/graph/client/{DEMO}", params={"depth": 2}, headers=owner)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "graph_too_large" and r.json()["error"]["details"]["max_nodes"] == 200
    assert (await client.get(f"{API}/graph/client/{DEMO}", params={"depth": 3}, headers=owner)).status_code == 422


async def test_soft_deleted_record_not_returned_in_list(client, broker):
    created = await client.post(f"{API}/contacts", headers=broker, json={"display_name": "Temp Person", "last_name": "Person"})
    assert created.status_code == 201
    cid = created.json()["id"]
    assert (await client.delete(f"{API}/contacts/{cid}", headers=broker)).status_code == 204
    ids = {c["id"] for c in (await client.get(f"{API}/contacts", params={"page_size": 500}, headers=broker)).json()["items"]}
    assert cid not in ids
    assert (await client.get(f"{API}/contacts/{cid}", headers=broker)).status_code == 404


async def test_audit_log_written_on_create(client, broker, owner, bare_session):
    created = await client.post(f"{API}/contacts", headers=broker, json={"display_name": "Audited Person", "last_name": "Person", "status": "prospect"})
    cid = uuid.UUID(created.json()["id"])
    async with tenant_transaction(bare_session, DEMO, BROKER):
        rows = await AuditLogRepository(bare_session).history_of(EntityType.CONTACT, cid)
    assert [r.action.value for r in rows] == ["insert"]
    assert rows[0].actor_user_id == BROKER and "broker@demo.test" in rows[0].actor_label
    assert rows[0].after["display_name"] == "Audited Person"
    # and via the admin endpoint
    r = await client.get(f"{API}/admin/audit-log/contact/{cid}", headers=owner)
    assert r.status_code == 200 and r.json()[0]["action"] == "insert"
    assert (await client.get(f"{API}/admin/audit-log/contact/{cid}", headers=broker)).status_code == 403


async def test_encrypted_fields_not_in_response(client, broker):
    r = await client.post(f"{API}/passengers", headers=broker, json={
        "first_name": "Secret", "last_name": "Traveller", "known_traveler_number": "TT1234567", "redress_number": "RR7654321"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ktn_last4"] == "4567" and "known_traveler_number" not in body and "redress_number" not in body
    pid = body["id"]
    d = await client.post(f"{API}/passengers/{pid}/travel-documents", headers=broker, json={
        "document_type": "passport", "number": "P98765432", "full_name_on_document": "TRAVELLER, SECRET",
        "issuing_country": "US", "expiry_date": "2031-01-01"})
    assert d.status_code == 201, d.text
    assert d.json()["number_last4"] == "5432" and "P98765432" not in d.text and "number" not in d.json()
    for path in (f"/passengers/{pid}", f"/passengers/{pid}/travel-documents", f"/passengers?page_size=500", f"/graph/passenger/{pid}"):
        text = (await client.get(f"{API}{path}", headers=broker)).text
        assert "P98765432" not in text and "TT1234567" not in text and "RR7654321" not in text, path


async def test_pagination_works(client, broker):
    p1 = (await client.get(f"{API}/contacts", params={"page": 1, "page_size": 3, "order_by": "display_name"}, headers=broker)).json()
    assert p1["total"] == 8 and len(p1["items"]) == 3 and (p1["page"], p1["page_size"]) == (1, 3)
    p3 = (await client.get(f"{API}/contacts", params={"page": 3, "page_size": 3, "order_by": "display_name"}, headers=broker)).json()
    assert len(p3["items"]) == 2
    names = [c["display_name"] for c in p1["items"]] + [c["display_name"] for c in p3["items"]]
    assert names == sorted(names) and len(set(names)) == 5
    assert (await client.get(f"{API}/contacts", params={"page_size": 0}, headers=broker)).status_code == 422
    assert (await client.get(f"{API}/contacts", params={"order_by": "password"}, headers=broker)).status_code == 422


async def test_filtering_by_related_entity(client, broker):
    corporate = u("segment:corporate")
    r = await client.get(f"{API}/contacts", params={"segment_id": str(corporate)}, headers=broker)
    assert r.status_code == 200
    assert {c["display_name"] for c in r.json()["items"]} == {"Halcyon Capital Partners", "Northwind Logistics Inc", "Daniel Okafor"}
    assert r.json()["total"] == 3
    r = await client.get(f"{API}/contacts", params={"segment_id": str(corporate), "contact_type": "company"}, headers=broker)
    assert r.json()["total"] == 2
    assert (await client.get(f"{API}/contacts", params={"segment_id": "not-a-uuid"}, headers=broker)).status_code == 422
    # a filter on a related entity for trips
    r = await client.get(f"{API}/trips", params={"account_holder_id": str(u("account_holder:halcyon"))}, headers=broker)
    assert [t["trip_number"] for t in r.json()["items"]] == ["BLX-2026-001"]


async def test_error_shape_and_domain_routes(client, owner):
    r = await client.get(f"{API}/contacts/{uuid.uuid4()}", headers=owner)
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "details"}
    assert "X-Request-ID" in r.headers
    aging = (await client.get(f"{API}/invoices/ar-aging", headers=owner)).json()
    assert aging["buckets"]["current"]["balance_cents"] == 1_459_500
    queue = (await client.get(f"{API}/tasks/my-queue", headers=await login(client, "broker@demo.test"))).json()
    assert queue[0]["title"].startswith("Chase balance payment")
    el = (await client.get(f"{API}/empty_legs/search", params={"origin": "KTEB", "destination": "KOPF", "date_from": "2026-09-01", "date_to": "2027-09-01"}, headers=owner)).json()
    assert len(el) == 1
