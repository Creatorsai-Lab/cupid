"""
Admin Overview — a custom SQLAdmin page with at-a-glance analytics and a few
live health signals. Read-only; everything is computed per request from the DB
(cheap COUNT/GROUP BY) plus a Redis ping. Extend with charts/time-series later.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqladmin import BaseView, expose
from sqlalchemy import func, select
from starlette.requests import Request

from app.core.db import async_session
from app.models.audit_log import AuditLog
from app.models.creation_history import CreationHistory
from app.models.social_connection import SocialConnection
from app.models.user import User
from app.subscriptions.models import Subscription


async def _gather_metrics() -> dict:
    now = datetime.now(UTC)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    async with async_session() as s:
        total_users = await s.scalar(select(func.count()).select_from(User))
        new_7d = await s.scalar(
            select(func.count()).select_from(User).where(User.created_at >= cutoff_7d)
        )
        new_30d = await s.scalar(
            select(func.count()).select_from(User).where(User.created_at >= cutoff_30d)
        )
        admins = await s.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        providers = dict(
            (
                await s.execute(
                    select(User.auth_provider, func.count()).group_by(
                        User.auth_provider
                    )
                )
            ).all()
        )
        tiers = dict(
            (
                await s.execute(
                    select(Subscription.tier, func.count()).group_by(Subscription.tier)
                )
            ).all()
        )
        content_total = await s.scalar(
            select(func.count()).select_from(CreationHistory)
        )
        content_7d = await s.scalar(
            select(func.count())
            .select_from(CreationHistory)
            .where(CreationHistory.created_at >= cutoff_7d)
        )
        connections = await s.scalar(select(func.count()).select_from(SocialConnection))
        recent_audit = (
            (
                await s.execute(
                    select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
                )
            )
            .scalars()
            .all()
        )

    return {
        "total_users": total_users or 0,
        "new_7d": new_7d or 0,
        "new_30d": new_30d or 0,
        "admins": admins or 0,
        "providers": providers,
        "tiers": tiers,
        "content_total": content_total or 0,
        "content_7d": content_7d or 0,
        "connections": connections or 0,
        "recent_audit": recent_audit,
    }


async def _health() -> dict:
    """Lightweight liveness signals for the monitoring strip."""
    from app.config import settings

    redis_ok = False
    try:
        from app.core.redis import redis_client

        redis_ok = bool(await redis_client.ping())
    except Exception:
        redis_ok = False

    # If this view ran at all, the DB session/query path is healthy.
    return {"env": settings.app_env, "redis_ok": redis_ok, "db_ok": True}


class DashboardView(BaseView):
    name = "Overview"
    icon = "fa-solid fa-gauge-high"

    @expose("/dashboard", methods=["GET"])
    async def dashboard(self, request: Request):
        metrics = await _gather_metrics()
        health = await _health()
        return await self.templates.TemplateResponse(
            request,
            "dashboard.html",
            {"metrics": metrics, "health": health},
        )
