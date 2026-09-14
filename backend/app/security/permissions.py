"""RBAC: string permission keys, a role -> permission map, and the check.

Keys are ``<resource>.<action>``. The map below is the one from the sprint brief,
implemented literally; wildcards are expanded once at import into concrete sets
so ``has_permission`` is a set lookup. A permissions table is future work.
"""

from __future__ import annotations

from app.models.enums import UserRole

RESOURCES: tuple[str, ...] = (
    "clients", "segments", "contacts", "passengers", "account_holders",
    "manufacturers", "aircraft_models", "operators", "aircraft", "airports", "crew",
    "trips", "legs", "empty_legs", "quotes", "bookings", "invoices", "payments",
    "documents", "tasks", "activities",
    "users", "audit", "billing",
)
ACTIONS: tuple[str, ...] = ("view", "create", "edit", "delete", "manage")
EXTRA: dict[str, tuple[str, ...]] = {"documents": ("upload",), "billing": ("transfer",)}

ALL_PERMISSIONS: frozenset[str] = frozenset(
    {f"{r}.{a}" for r in RESOURCES for a in ACTIONS} | {f"{r}.{a}" for r, acts in EXTRA.items() for a in acts}
)

# The brief's map, verbatim.
ROLE_GRANTS: dict[UserRole, tuple[str, ...]] = {
    UserRole.OWNER: ("*",),
    UserRole.ADMIN: ("*", "-billing.transfer"),
    UserRole.BROKER: ("clients.*", "contacts.*", "passengers.*", "trips.*", "quotes.*", "bookings.*",
                      "documents.view", "documents.upload", "tasks.*", "activities.*", "empty_legs.view"),
    UserRole.OPS: ("trips.*", "legs.*", "aircraft.view", "operators.view", "crew.*",
                   "documents.view", "documents.upload", "tasks.*"),
    UserRole.FINANCE: ("invoices.*", "payments.*", "quotes.view", "bookings.view", "billing.*", "documents.view"),
    UserRole.READ_ONLY: ("*.view",),
}


def expand(pattern: str) -> frozenset[str]:
    if pattern == "*":
        return ALL_PERMISSIONS
    resource, action = pattern.split(".", 1)
    if resource == "*":
        return frozenset(p for p in ALL_PERMISSIONS if p.endswith("." + action))
    if action == "*":
        return frozenset(p for p in ALL_PERMISSIONS if p.startswith(resource + "."))
    if pattern not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {pattern!r}")
    return frozenset({pattern})


def _build() -> dict[UserRole, frozenset[str]]:
    out: dict[UserRole, frozenset[str]] = {}
    for role, grants in ROLE_GRANTS.items():
        perms: set[str] = set()
        for g in grants:
            if g.startswith("-"):
                perms -= expand(g[1:])
            else:
                perms |= expand(g)
        out[role] = frozenset(perms)
    return out


ROLE_PERMISSIONS: dict[UserRole, frozenset[str]] = _build()


def permissions_for(role: UserRole | str) -> frozenset[str]:
    return ROLE_PERMISSIONS[UserRole(role)]


def has_permission(role: UserRole | str, key: str) -> bool:
    """``x.manage`` implies every action on x; otherwise an exact match."""
    perms = permissions_for(role)
    if key in perms:
        return True
    resource = key.split(".", 1)[0]
    return f"{resource}.manage" in perms and key != f"{resource}.transfer"
