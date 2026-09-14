"""Tenancy: the tenant root and its users (DATA_MODEL.md 3.1)."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, ForeignKey, Index, Text, text, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, IdMixin, TenantScopedMixin, TimestampMixin, pg_enum, tenant_indexes, utcnow
from .enums import ClientStatus, UserRole, UserStatus


class Client(BitluxBase, IdMixin, TimestampMixin, table=True):
    """Tenant root. DATA_MODEL.md 3.1."""
    __tablename__ = "clients"
    __table_args__ = (
        Index("uq_clients_slug", "slug", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_clients_status", "status", postgresql_where=text("deleted_at IS NULL")),
        {"comment": "Tenant root. DATA_MODEL.md 3.1."},
    )

    slug: str = Field(sa_column=Column("slug", CITEXT, nullable=False))
    name: str = Field(sa_column=Column("name", Text, nullable=False))
    legal_name: Optional[str] = Field(default=None, sa_column=Column("legal_name", Text))
    status: ClientStatus = Field(default=ClientStatus.TRIALING, sa_column=Column("status", pg_enum(ClientStatus), nullable=False, server_default="trialing"))
    default_currency: str = Field(default="USD", sa_column=Column("default_currency", CHAR(3), nullable=False, server_default="USD"))
    timezone: str = Field(default="UTC", sa_column=Column("timezone", Text, nullable=False, server_default="UTC"))
    locale: str = Field(default="en-US", sa_column=Column("locale", Text, nullable=False, server_default="en-US"))
    billing_email: Optional[str] = Field(default=None, sa_column=Column("billing_email", CITEXT))
    support_email: Optional[str] = Field(default=None, sa_column=Column("support_email", CITEXT))
    logo_url: Optional[str] = Field(default=None, sa_column=Column("logo_url", Text))
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column("settings", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    feature_flags: dict[str, Any] = Field(default_factory=dict, sa_column=Column("feature_flags", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    trip_number_prefix: Optional[str] = Field(default=None, sa_column=Column("trip_number_prefix", Text))

    users: list["User"] = Relationship(back_populates="client")


class User(BitluxBase, TenantScopedMixin, table=True):
    """Staff users of a tenant. DATA_MODEL.md 3.1."""
    __tablename__ = "users"
    __table_args__ = (
        *tenant_indexes("users"),
        Index("uq_users_client_email", "client_id", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_users_auth_subject", "auth_provider", "auth_subject", unique=True, postgresql_where=text("auth_subject IS NOT NULL")),
        Index("ix_users_client_role", "client_id", "role", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_users_client_status", "client_id", "status"),
        {"comment": "Staff users of a tenant. DATA_MODEL.md 3.1."},
    )

    email: str = Field(sa_column=Column("email", CITEXT, nullable=False))
    full_name: str = Field(sa_column=Column("full_name", Text, nullable=False))
    given_name: Optional[str] = Field(default=None, sa_column=Column("given_name", Text))
    family_name: Optional[str] = Field(default=None, sa_column=Column("family_name", Text))
    role: UserRole = Field(default=UserRole.BROKER, sa_column=Column("role", pg_enum(UserRole), nullable=False, server_default="broker"))
    status: UserStatus = Field(default=UserStatus.INVITED, sa_column=Column("status", pg_enum(UserStatus), nullable=False, server_default="invited"))
    phone: Optional[str] = Field(default=None, sa_column=Column("phone", Text))
    avatar_url: Optional[str] = Field(default=None, sa_column=Column("avatar_url", Text))
    timezone: Optional[str] = Field(default=None, sa_column=Column("timezone", Text))
    auth_provider: Optional[str] = Field(default=None, sa_column=Column("auth_provider", Text))
    auth_subject: Optional[str] = Field(default=None, sa_column=Column("auth_subject", Text))
    mfa_enabled: bool = Field(default=False, sa_column=Column("mfa_enabled", Boolean, nullable=False, server_default=text("false")))
    last_login_at: Optional[datetime] = Field(default=None, sa_column=Column("last_login_at", TIMESTAMP(timezone=True)))
    # Migration 016. argon2id hash; NULL = no password login. Never appears in a schema.
    password_hash: Optional[str] = Field(default=None, sa_column=Column("password_hash", Text))
    password_changed_at: Optional[datetime] = Field(default=None, sa_column=Column("password_changed_at", TIMESTAMP(timezone=True)))

    client: Optional["Client"] = Relationship(back_populates="users")


class RefreshToken(BitluxBase, TenantScopedMixin, table=True):
    """Refresh-token state for rotation and logout (migration 016). Holds a hash, never the token."""
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        *tenant_indexes("refresh_tokens"),
        Index("uq_refresh_tokens_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_user", "client_id", "user_id"),
        Index("ix_refresh_tokens_active", "expires_at", postgresql_where=text("revoked_at IS NULL")),
        CheckConstraint("expires_at > issued_at", name="ck_refresh_tokens_expiry"),
        {"comment": "Refresh-token state for rotation and logout. Stores a hash, never the token."},
    )

    user_id: uuid.UUID = Field(sa_column=Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    token_hash: str = Field(sa_column=Column("token_hash", Text, nullable=False))
    issued_at: datetime = Field(default_factory=utcnow, sa_column=Column("issued_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")))
    expires_at: datetime = Field(sa_column=Column("expires_at", TIMESTAMP(timezone=True), nullable=False))
    revoked_at: Optional[datetime] = Field(default=None, sa_column=Column("revoked_at", TIMESTAMP(timezone=True)))
    replaced_by_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("replaced_by_id", UUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL")))
    user_agent: Optional[str] = Field(default=None, sa_column=Column("user_agent", Text))
    ip_address: Optional[Any] = Field(default=None, sa_column=Column("ip_address", INET))

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > utcnow()
