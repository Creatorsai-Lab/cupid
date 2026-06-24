"""
app/admin/setup.py
═══════════════════════════════════════════════════════════════════════════

Mounts the SQLAdmin dashboard — a prebuilt web admin UI over the existing
SQLAlchemy models. Zero hand-written frontend: register a ModelView per table
and SQLAdmin renders list/detail/edit pages.

SAFETY POSTURE
──────────────
  • Mounted at settings.admin_panel_path (non-obvious; cosmetic).
  • Behind AdminAuth (username/password credential wall).
  • Only mounted if dashboard credentials are configured — no creds means no
    panel, never an open one.
  • audit_log is read-only here (append-only by design); users can't be deleted.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqladmin import Admin, ModelView

from app.admin.security import AdminAuth
from app.config import settings
from app.core.db import engine
from app.models.audit_log import AuditLog
from app.models.user import User
from app.subscriptions.models import Subscription

logger = logging.getLogger("app.admin")


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [
        User.email,
        User.full_name,
        User.is_admin,
        User.is_active,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.created_at, User.email]
    can_delete = False  # deleting a user cascades a lot — do it deliberately, not here
    can_create = False


class SubscriptionAdmin(ModelView, model=Subscription):
    name = "Subscription"
    name_plural = "Subscriptions"
    icon = "fa-solid fa-id-card"
    column_list = [
        Subscription.user_id,
        Subscription.tier,
        Subscription.status,
        Subscription.cancel_at_period_end,
        Subscription.grandfathered_until,
        Subscription.updated_at,
    ]
    column_sortable_list = [Subscription.updated_at, Subscription.tier]
    # Editable so you can flip a tier from the UI for testing. NOTE: edits here
    # write the row directly — they bypass service.set_user_tier, so they are
    # NOT validated and NOT audited. For an audited change use the API endpoint.
    can_create = False
    can_delete = False


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Audit Log"
    name_plural = "Audit Log"
    icon = "fa-solid fa-clipboard-list"
    column_list = [
        AuditLog.created_at,
        AuditLog.actor_email,
        AuditLog.action,
        AuditLog.target_id,
        AuditLog.detail,
    ]
    column_sortable_list = [AuditLog.created_at]
    column_default_sort = ("created_at", True)  # newest first
    # Append-only: never created, edited, or deleted through the UI.
    can_create = False
    can_edit = False
    can_delete = False


def setup_admin(app: FastAPI) -> None:
    """Mount the dashboard — only if dashboard credentials are configured."""
    if not (settings.admin_panel_user and settings.admin_panel_password):
        logger.info(
            "[admin] dashboard NOT mounted — set ADMIN_PANEL_USER/ADMIN_PANEL_PASSWORD to enable"
        )
        return

    secret = settings.admin_session_secret or settings.secret_key
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminAuth(secret_key=secret),
        base_url=settings.admin_panel_path,
        title="Cupid Admin",
    )
    admin.add_view(UserAdmin)
    admin.add_view(SubscriptionAdmin)
    admin.add_view(AuditLogAdmin)
    logger.info("[admin] dashboard mounted at %s", settings.admin_panel_path)
