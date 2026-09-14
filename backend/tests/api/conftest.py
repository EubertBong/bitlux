"""API tests: the real app, over httpx, with get_session overridden to the test's
rolled-back connection. Every request's tenant_transaction() becomes a savepoint,
so nothing a test does survives it -- and everything still runs as bitlux_app
under RLS, because that is the role the connection belongs to.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.deps import get_session
from app.main import create_app
from app.repositories import ClientRepository, ContactRepository, UserRepository, tenant_transaction
from app.security.passwords import hash_password

from ..conftest import DEMO  # noqa: F401  (re-exported for convenience)

DEMO_PASSWORD = "Demo!2026"
API = "/api/v1"


@pytest.fixture
async def client(bare_session):
    app = create_app()

    async def _session_override():
        yield bare_session

    app.dependency_overrides[get_session] = _session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: AsyncClient, email: str, password: str = DEMO_PASSWORD) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def broker(client):
    return await login(client, "broker@demo.test")


@pytest.fixture
async def owner(client):
    return await login(client, "owner@demo.test")


@pytest.fixture
async def ops(client):
    return await login(client, "ops@demo.test")


@pytest.fixture
async def other_tenant(bare_session):
    """A second tenant with one user and one contact, created directly through the
    repositories inside the test's transaction. Returns (client_id, contact_id, email)."""
    other = uuid.uuid5(DEMO, "api-tests-tenant-b")
    email = "owner@tenant-b.test"
    async with tenant_transaction(bare_session, other, None):
        await ClientRepository(bare_session).create({"id": other, "slug": "tenant-b", "name": "Tenant B", "status": "active"})
        user = await UserRepository(bare_session).create({"email": email, "full_name": "B Owner", "role": "owner", "status": "active",
                                                          "password_hash": hash_password(DEMO_PASSWORD), "created_by": None, "updated_by": None})
        contact = await ContactRepository(bare_session).create({"display_name": "Zebrawood Holdings", "contact_type": "company",
                                                               "company_name": "Zebrawood Holdings", "created_by": user.id})
    return other, contact.id, email
