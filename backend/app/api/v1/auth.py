"""/auth -- login, refresh (with rotation), logout, me.

Login is the one step that runs before a tenant is known; it uses
auth_lookup_user() (migration 016) and then enters the tenant's transaction
for everything else. Refresh tokens are stateful: hashed in refresh_tokens,
rotated on every use, revoked on logout.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import RequestContext, get_context, get_session
from app.errors import Conflict, Unauthorized
from app.models.enums import ActorType, AuditAction, ClientStatus, EntityType, UserStatus
from app.repositories import AuditEvent, AuditLogRepository, RefreshTokenRepository, UserRepository, tenant_transaction
from app.schemas.auth import LoginRequest, LogoutRequest, MeResponse, RefreshRequest, TokenPair
from app.security.passwords import needs_rehash, verify_password, hash_password
from app.security.tokens import TokenError, decode, fingerprint, issue

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_pair(session: AsyncSession, user_id: uuid.UUID, client_id: uuid.UUID, role: str, request: Request) -> TokenPair:
    """Inside a tenant transaction: mint access + refresh, persist the refresh hash."""
    access, _ = issue(user_id, client_id, role, "access")
    refresh_jti = uuid.uuid4()
    refresh, claims = issue(user_id, client_id, role, "refresh", jti=refresh_jti)
    await RefreshTokenRepository(session).create({
        "id": refresh_jti, "user_id": user_id, "token_hash": fingerprint(refresh), "expires_at": claims.expires_at,
        "user_agent": request.headers.get("user-agent", "")[:512], "ip_address": request.client.host if request.client else None,
    })
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=get_settings().access_token_ttl_minutes * 60)


@router.post("/login", response_model=TokenPair, summary="Email + password -> access and refresh tokens")
async def login(body: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)) -> TokenPair:
    candidates = await UserRepository(session).login_candidates(str(body.email), body.client_slug)
    if len(candidates) > 1:
        raise Conflict("This email exists in more than one tenant; supply client_slug", details={"tenants": sorted(c.client_slug for c in candidates)})
    cand = candidates[0] if candidates else None
    # Verify even when there is no such user, so timing does not reveal existence.
    ok = verify_password(body.password, cand.password_hash if cand else None)
    if not cand or not ok:
        raise Unauthorized("Invalid email or password")
    if cand.status != UserStatus.ACTIVE or cand.client_status not in (ClientStatus.ACTIVE, ClientStatus.TRIALING):
        raise Unauthorized("Account is not active")

    async with tenant_transaction(session, cand.client_id, cand.user_id):
        request.state.user_id, request.state.client_id = str(cand.user_id), str(cand.client_id)
        users = UserRepository(session)
        updates = {"last_login_at": __import__("app.models.base", fromlist=["utcnow"]).utcnow()}
        if needs_rehash(cand.password_hash):
            updates["password_hash"] = hash_password(body.password)
        await users.update(cand.user_id, updates)
        pair = await _issue_pair(session, cand.user_id, cand.client_id, cand.role.value, request)
        await AuditLogRepository(session).append(AuditEvent(
            action=AuditAction.LOGIN, entity_type=EntityType.USER, entity_id=cand.user_id,
            actor_label=str(body.email), actor_type=ActorType.USER, ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ))
        return pair


@router.post("/refresh", response_model=TokenPair, summary="Refresh token -> new access token (refresh is rotated)")
async def refresh(body: RefreshRequest, request: Request, session: AsyncSession = Depends(get_session)) -> TokenPair:
    try:
        claims = decode(body.refresh_token, "refresh")
    except TokenError as e:
        raise Unauthorized(str(e)) from e
    async with tenant_transaction(session, claims.client_id, claims.user_id):
        request.state.user_id, request.state.client_id = str(claims.user_id), str(claims.client_id)
        tokens = RefreshTokenRepository(session)
        row = await tokens.by_hash(fingerprint(body.refresh_token))
        if row is None or not row.is_active or row.user_id != claims.user_id:
            # A replayed (already rotated) token is a red flag: revoke the whole family.
            if row is not None and row.revoked_at is not None:
                await tokens.revoke_all_for_user(claims.user_id)
            raise Unauthorized("Refresh token is invalid or has been revoked")
        user = await UserRepository(session).get(claims.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise Unauthorized("Account is not active")
        pair = await _issue_pair(session, user.id, claims.client_id, user.role.value, request)
        await tokens.revoke(row.id, replaced_by=decode(pair.refresh_token, "refresh").jti)
        return pair


@router.post("/logout", status_code=204, summary="Revoke a refresh token")
async def logout(body: LogoutRequest, request: Request, session: AsyncSession = Depends(get_session)) -> None:
    try:
        claims = decode(body.refresh_token, "refresh")
    except TokenError:
        return None  # already unusable; logout is idempotent
    async with tenant_transaction(session, claims.client_id, claims.user_id):
        request.state.user_id, request.state.client_id = str(claims.user_id), str(claims.client_id)
        tokens = RefreshTokenRepository(session)
        row = await tokens.by_hash(fingerprint(body.refresh_token))
        if row is not None and row.revoked_at is None:
            await tokens.revoke(row.id)
            await AuditLogRepository(session).append(AuditEvent(
                action=AuditAction.LOGOUT, entity_type=EntityType.USER, entity_id=claims.user_id, actor_label=str(claims.user_id)))
    return None


@router.get("/me", response_model=MeResponse, summary="Current user and effective permissions")
async def me(ctx: RequestContext = Depends(get_context)) -> MeResponse:
    u = ctx.user
    return MeResponse(id=u.id, client_id=u.client_id, email=u.email, full_name=u.full_name, role=u.role, status=u.status,
                      timezone=u.timezone, permissions=sorted(ctx.permissions))
