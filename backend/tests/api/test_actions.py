"""The actions layer: restore (undo of soft delete), full-text q on lists, users lookup."""

from __future__ import annotations

from .conftest import API


async def _create_contact(client, headers, **over):
    body = {"display_name": "Undo Testperson", "contact_type": "individual", "first_name": "Undo", "last_name": "Testperson", "status": "lead"}
    body.update(over)
    r = await client.post(f"{API}/contacts", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_restore_undoes_soft_delete_and_is_audited(client, broker, owner):
    c = await _create_contact(client, broker)
    cid = c["id"]
    assert (await client.delete(f"{API}/contacts/{cid}", headers=broker)).status_code == 204
    assert (await client.get(f"{API}/contacts/{cid}", headers=broker)).status_code == 404

    r = await client.post(f"{API}/contacts/{cid}/restore", headers=broker)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == cid
    assert (await client.get(f"{API}/contacts/{cid}", headers=broker)).status_code == 200

    hist = await client.get(f"{API}/admin/audit-log/contact/{cid}", headers=owner)
    assert hist.status_code == 200
    actions = [e["action"] for e in hist.json()]
    assert "soft_delete" in actions and "restore" in actions


async def test_restore_requires_delete_permission(client, ops, broker):
    c = await _create_contact(client, broker)
    # ops has no contacts.* at all
    r = await client.post(f"{API}/contacts/{c['id']}/restore", headers=ops)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "permission_denied"


async def test_list_q_full_text_filters_contacts(client, broker):
    await _create_contact(client, broker, display_name="Quokka Aviation Holdings", contact_type="company", company_name="Quokka Aviation Holdings", first_name=None, last_name=None)
    r = await client.get(f"{API}/contacts", params={"q": "quokka"}, headers=broker)
    assert r.status_code == 200, r.text
    names = [i["display_name"] for i in r.json()["items"]]
    assert names == ["Quokka Aviation Holdings"]
    assert r.json()["total"] == 1
    # prefix on the last word, combined with an equality filter
    r = await client.get(f"{API}/contacts", params={"q": "quok", "status": "lead"}, headers=broker)
    assert [i["display_name"] for i in r.json()["items"]] == ["Quokka Aviation Holdings"]
    r = await client.get(f"{API}/contacts", params={"q": "quok", "status": "churned"}, headers=broker)
    assert r.json()["items"] == []


async def test_list_q_on_non_searchable_resource_is_422(client, owner):
    r = await client.get(f"{API}/segments", params={"q": "x"}, headers=owner)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_users_lookup_available_without_users_view(client, broker, owner):
    # broker lacks users.view: the full admin list is forbidden ...
    assert (await client.get(f"{API}/admin/users", headers=broker)).status_code == 403
    # ... but the name lookup for pickers works, and carries no emails.
    r = await client.get(f"{API}/admin/users/lookup", headers=broker)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert {u["full_name"] for u in rows} >= {"Olivia Grant", "Ben Carter", "Nadia Osei"}
    assert set(rows[0]) == {"id", "full_name", "role"}
    assert rows == sorted(rows, key=lambda u: u["full_name"])
