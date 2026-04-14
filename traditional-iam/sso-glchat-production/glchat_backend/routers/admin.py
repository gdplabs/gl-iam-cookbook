"""Admin endpoints — partner CRUD + audit-log query. All require PLATFORM_ADMIN."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from gl_iam import User
from gl_iam.core.types.audit import AuditEventType
from gl_iam.core.types.sso import SSOMode, SSOPartnerCreate, SSOUserProvisioning
from gl_iam.fastapi import get_current_user, get_iam_gateway, require_platform_admin

from glchat_backend import audit
from glchat_backend.config import get_settings


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_platform_admin())])


class PartnerCreateRequest(BaseModel):
    partner_name: str
    allowed_origins: list[str] = []
    sso_mode: str = "idp_initiated"
    user_provisioning: str = "jit"
    metadata: dict | None = None
    allowed_email_domains: list[str] | None = None
    allowed_source_ips: list[str] | None = None
    max_users: int | None = None
    allowed_roles: list[str] | None = None


class PartnerCreateResponse(BaseModel):
    id: str
    partner_name: str
    consumer_key: str
    consumer_secret: str
    is_active: bool
    allowed_email_domains: list[str] | None = None
    allowed_origins: list[str] = []
    max_users: int | None = None
    allowed_roles: list[str] | None = None


class PartnerListItem(BaseModel):
    id: str
    partner_name: str
    consumer_key: str
    is_active: bool
    sso_mode: str
    allowed_email_domains: list[str] | None = None
    allowed_origins: list[str] = []
    max_users: int | None = None
    allowed_roles: list[str] | None = None
    created_at: str | None


class RotateRequest(BaseModel):
    grace_period_seconds: int | None = None


@router.post("/partners", response_model=PartnerCreateResponse)
async def register_partner(body: PartnerCreateRequest, user: User = Depends(get_current_user)):
    gateway = get_iam_gateway()
    settings = get_settings()

    result = await gateway.partner_registry.register_partner(
        SSOPartnerCreate(
            org_id=settings.default_org_id,
            partner_name=body.partner_name,
            allowed_origins=body.allowed_origins,
            sso_mode=SSOMode(body.sso_mode),
            user_provisioning=SSOUserProvisioning(body.user_provisioning),
            metadata=body.metadata,
            allowed_email_domains=body.allowed_email_domains,
            allowed_source_ips=body.allowed_source_ips,
            max_users=body.max_users,
            allowed_roles=body.allowed_roles,
        )
    )
    if result.is_err:
        raise HTTPException(400, result.error.message)

    reg = result.value
    audit.emit(
        event_type=AuditEventType.USER_CREATED,  # nearest existing "creation" event
        sso_event="partner_registered",
        message=f"Partner {reg.partner.partner_name} registered",
        user_id=user.id,
        organization_id=settings.default_org_id,
        resource_id=reg.partner.id,
    )
    return PartnerCreateResponse(
        id=reg.partner.id,
        partner_name=reg.partner.partner_name,
        consumer_key=reg.consumer_key,
        consumer_secret=reg.consumer_secret,
        is_active=reg.partner.is_active,
        allowed_email_domains=reg.partner.allowed_email_domains,
        allowed_origins=reg.partner.allowed_origins or [],
        max_users=reg.partner.max_users,
        allowed_roles=reg.partner.allowed_roles,
    )


@router.get("/partners", response_model=list[PartnerListItem])
async def list_partners():
    gateway = get_iam_gateway()
    result = await gateway.partner_registry.list_partners(organization_id=get_settings().default_org_id)
    if result.is_err:
        raise HTTPException(500, result.error.message)
    return [
        PartnerListItem(
            id=p.id,
            partner_name=p.partner_name,
            consumer_key=p.consumer_key,
            is_active=p.is_active,
            sso_mode=p.sso_mode.value if hasattr(p.sso_mode, "value") else p.sso_mode,
            allowed_email_domains=p.allowed_email_domains,
            allowed_origins=p.allowed_origins or [],
            max_users=p.max_users,
            allowed_roles=p.allowed_roles,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in result.value
    ]


@router.post("/partners/{partner_id}/rotate", response_model=PartnerCreateResponse)
async def rotate(partner_id: str, body: RotateRequest | None = None, user: User = Depends(get_current_user)):
    gateway = get_iam_gateway()
    grace = body.grace_period_seconds if body else None
    result = await gateway.partner_registry.rotate_consumer_secret(
        partner_id, grace_period_seconds=grace
    )
    if result.is_err:
        raise HTTPException(404, result.error.message)

    reg = result.value
    audit.emit(
        event_type=AuditEventType.API_KEY_ROTATED,
        sso_event="partner_secret_rotated",
        message=f"Consumer secret rotated (grace={grace}s)",
        user_id=user.id,
        resource_id=partner_id,
        grace_period_seconds=grace,
    )
    return PartnerCreateResponse(
        id=reg.partner.id,
        partner_name=reg.partner.partner_name,
        consumer_key=reg.consumer_key,
        consumer_secret=reg.consumer_secret,
        is_active=reg.partner.is_active,
        allowed_email_domains=reg.partner.allowed_email_domains,
        allowed_origins=reg.partner.allowed_origins or [],
        max_users=reg.partner.max_users,
        allowed_roles=reg.partner.allowed_roles,
    )


@router.post("/partners/{partner_id}/deactivate")
async def deactivate(partner_id: str, user: User = Depends(get_current_user)):
    gateway = get_iam_gateway()
    result = await gateway.partner_registry.deactivate_partner(partner_id)
    if result.is_err:
        raise HTTPException(404, result.error.message)
    audit.emit(
        event_type=AuditEventType.API_KEY_REVOKED,
        sso_event="partner_deactivated",
        message="Partner deactivated",
        user_id=user.id,
        resource_id=partner_id,
    )
    return {"status": "deactivated"}


@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    event_type: str | None = Query(None),
    sso_event: str | None = Query(None),
    resource_id: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
):
    import json as _json

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from gl_iam.providers.postgresql import AuditEventModel

    async with AsyncSession(request.app.state.provider.engine) as session:
        q = select(AuditEventModel).order_by(AuditEventModel.timestamp.desc())
        cq = select(func.count()).select_from(AuditEventModel)
        if event_type:
            q = q.where(AuditEventModel.event_type == event_type)
            cq = cq.where(AuditEventModel.event_type == event_type)
        if sso_event:
            like = f'%"sso.event": "{sso_event}"%'
            q = q.where(AuditEventModel.details_json.like(like))
            cq = cq.where(AuditEventModel.details_json.like(like))
        if resource_id:
            q = q.where(AuditEventModel.resource_id == resource_id)
            cq = cq.where(AuditEventModel.resource_id == resource_id)
        if from_date:
            q = q.where(AuditEventModel.timestamp >= from_date)
            cq = cq.where(AuditEventModel.timestamp >= from_date)
        if to_date:
            q = q.where(AuditEventModel.timestamp <= to_date)
            cq = cq.where(AuditEventModel.timestamp <= to_date)

        total = (await session.execute(cq)).scalar() or 0
        rows = (await session.execute(q.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "user_id": e.user_id,
                "resource_id": e.resource_id,
                "ip_address": e.ip_address,
                "error_code": e.error_code,
                "message": e.message,
                "details": _json.loads(e.details_json) if e.details_json else {},
            }
            for e in rows
        ],
    }
