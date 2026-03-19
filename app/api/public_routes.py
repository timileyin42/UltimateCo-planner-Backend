from typing import List, Optional
from html import escape
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.contact_models import ContactInvitation, ContactInviteStatus
from app.repositories.invite_repo import InviteRepository

router = APIRouter()
logger = get_logger(__name__)


def _deep_link_base() -> str:
    base = settings.DEEP_LINK_BASE_URL or settings.FRONTEND_URL
    return base.strip("`'\" ").rstrip("/")


def _invite_fallback_url() -> str:
    fallback = settings.INVITE_FALLBACK_URL or settings.FRONTEND_URL
    return fallback.strip("`'\" ").rstrip("/")


def _normalize_url_for_compare(url: str) -> str:
    return url.strip("`'\" ").rstrip("/")


def _mobile_app_invite_url(token: Optional[str]) -> Optional[str]:
    if not token or not settings.MOBILE_APP_SCHEME:
        return None
    scheme_base = settings.MOBILE_APP_SCHEME.strip("`'\" ")
    if scheme_base.endswith("://") or scheme_base.endswith("/"):
        return f"{scheme_base}invite/{token}"
    return f"{scheme_base.rstrip('/')}/invite/{token}"


def _is_contact_invitation_valid(invitation: Optional[ContactInvitation]) -> bool:
    if not invitation:
        return False
    is_expired = invitation.expires_at is not None and invitation.expires_at < datetime.utcnow()
    invalid_statuses = {
        ContactInviteStatus.EXPIRED,
        ContactInviteStatus.FAILED
    }
    return not is_expired and invitation.status not in invalid_statuses


def _preferred_store_url(user_agent: str) -> Optional[str]:
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua or "ipod" in ua or "ios" in ua:
        return settings.IOS_APP_STORE_URL
    if "android" in ua:
        return settings.ANDROID_PLAY_STORE_URL
    return settings.IOS_APP_STORE_URL or settings.ANDROID_PLAY_STORE_URL


def _simple_fallback_page(
    target_url: str,
    token: Optional[str] = None,
    invalid_link: bool = False,
    user_agent: str = "",
    status_code: int = 200
) -> HTMLResponse:
    safe_target_url = escape(_normalize_url_for_compare(target_url))
    mobile_url = _mobile_app_invite_url(token)
    safe_mobile_url = escape(mobile_url) if mobile_url else ""
    ios_store_url = settings.IOS_APP_STORE_URL
    android_store_url = settings.ANDROID_PLAY_STORE_URL
    preferred_store_url = _preferred_store_url(user_agent)
    safe_ios_store_url = escape(ios_store_url) if ios_store_url else ""
    safe_android_store_url = escape(android_store_url) if android_store_url else ""
    safe_preferred_store_url = escape(preferred_store_url) if preferred_store_url else ""
    heading = "Invite link unavailable" if invalid_link else "PlanEtAl"
    description = (
        "This invite may be expired, disabled, or already used."
        if invalid_link
        else "Plan beautifully together. Tap below to open your invite in the app."
    )
    primary_label = "Open in PlanEtAl app"
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>PlanEtAl Invite</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                margin: 0;
                min-height: 100vh;
                line-height: 1.55;
                background: radial-gradient(1200px 500px at 10% 10%, #fff3ee 0%, #fff 55%),
                            radial-gradient(900px 500px at 90% 20%, #f7edff 0%, rgba(255,255,255,0) 50%);
                color: #14161a;
            }}
            .wrap {{
                max-width: 560px;
                margin: 0 auto;
                padding: 32px 18px 44px;
            }}
            .logo {{
                width: 42px;
                height: 42px;
                border-radius: 12px;
                background: linear-gradient(135deg, #ff7a59 0%, #7a5cff 100%);
                color: #fff;
                display: grid;
                place-items: center;
                font-weight: 700;
                margin-bottom: 16px;
            }}
            .card {{
                background: rgba(255, 255, 255, 0.88);
                border: 1px solid #eee;
                border-radius: 18px;
                box-shadow: 0 10px 30px rgba(20, 22, 26, 0.06);
                padding: 24px;
            }}
            h1 {{
                font-size: 28px;
                margin: 0 0 10px;
                letter-spacing: -0.02em;
            }}
            p {{
                margin: 0;
                color: #4b5563;
            }}
            .cta {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                margin-top: 20px;
                text-decoration: none;
                padding: 12px 16px;
                border-radius: 10px;
                background: #14161a;
                color: #fff;
                font-weight: 600;
                min-width: 210px;
            }}
            .cta:hover {{
                opacity: 0.92;
            }}
            .muted {{
                margin-top: 16px;
                font-size: 12px;
                color: #6b7280;
                word-break: break-all;
            }}
            .section-title {{
                margin-top: 18px;
                font-size: 14px;
                color: #6b7280;
            }}
            .feature-list {{
                margin: 8px 0 0;
                padding-left: 18px;
                color: #374151;
                font-size: 14px;
            }}
            .feature-list li {{
                margin: 4px 0;
            }}
            .store-links {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 14px;
            }}
            .store-link {{
                text-decoration: none;
                padding: 8px 11px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #374151;
                font-size: 13px;
            }}
        </style>
        <script>
            function openPlanEtAl() {{
                var appUrl = "{safe_mobile_url}";
                var storeUrl = "{safe_preferred_store_url}";
                if (!appUrl) {{
                    if (storeUrl) {{
                        window.location.href = storeUrl;
                    }}
                    return false;
                }}
                window.location.href = appUrl;
                if (storeUrl) {{
                    setTimeout(function () {{
                        window.location.href = storeUrl;
                    }}, 1300);
                }}
                return false;
            }}
        </script>
    </head>
    <body>
        <div class="wrap">
            <div class="logo">P</div>
            <div class="card">
                <h1>{heading}</h1>
                <p>{description}</p>
                {"<a class='cta' href='" + (safe_mobile_url or safe_preferred_store_url or safe_target_url) + "' onclick='return openPlanEtAl();'>" + primary_label + "</a>" if not invalid_link else "<a class='cta' href='" + (safe_preferred_store_url or safe_target_url) + "'>Download PlanEtAl</a>"}
                {"<div class='store-links'>" if (ios_store_url or android_store_url) else ""}
                {"<a class='store-link' href='" + safe_ios_store_url + "'>Download on the App Store</a>" if ios_store_url else ""}
                {"<a class='store-link' href='" + safe_android_store_url + "'>Get it on Google Play</a>" if android_store_url else ""}
                {"</div>" if (ios_store_url or android_store_url) else ""}
                <div class="section-title">Why PlanEtAl</div>
                <ul class="feature-list">
                    <li>Collaborative event planning in one place</li>
                    <li>Invites, reminders, RSVP, and timelines together</li>
                    <li>Built for both hosts and guests</li>
                </ul>
            </div>
            <p class="muted">{safe_target_url}</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=status_code)


@router.get("/invite/{token}")
def handle_invite_link(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Public invite handler for deep links.

    Validates the token and redirects to the deep link base URL.
    """
    repo = InviteRepository(db)

    invite_code = repo.get_invite_code_by_code(token)
    invite_link = repo.get_invite_link_by_link_id(token) if not invite_code else None
    contact_invitation = (
        db.query(ContactInvitation).filter(ContactInvitation.invitation_token == token).first()
        if not invite_code and not invite_link
        else None
    )

    is_valid = False
    if invite_code and invite_code.is_valid:
        is_valid = True
    if invite_link and invite_link.is_valid:
        is_valid = True
    if _is_contact_invitation_valid(contact_invitation):
        is_valid = True

    target_base = _deep_link_base()
    target_url = f"{target_base}/invite/{token}"
    normalized_request_url = _normalize_url_for_compare(str(request.url))

    if not is_valid:
        return _simple_fallback_page(
            str(request.url),
            invalid_link=True,
            user_agent=request.headers.get("user-agent", ""),
            status_code=404
        )

    if normalized_request_url == _normalize_url_for_compare(target_url):
        return _simple_fallback_page(target_url, token=token, user_agent=request.headers.get("user-agent", ""))

    return RedirectResponse(url=target_url, status_code=302)


@router.get("/.well-known/assetlinks.json")
def android_assetlinks():
    """Serve Android App Links verification file."""
    fingerprints: List[str] = settings.ANDROID_SHA256_CERT_FINGERPRINTS
    if settings.ANDROID_PACKAGE_NAME and fingerprints:
        data = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.ANDROID_PACKAGE_NAME,
                    "sha256_cert_fingerprints": fingerprints,
                },
            }
        ]
    else:
        data = []

    return JSONResponse(content=data)


@router.get("/.well-known/apple-app-site-association")
def apple_app_site_association():
    """Serve iOS Universal Links verification file."""
    paths = settings.IOS_APP_PATHS or ["/invite/*"]
    details = (
        [{"appID": settings.IOS_APP_ID, "paths": paths}]
        if settings.IOS_APP_ID
        else []
    )

    data = {
        "applinks": {
            "apps": [],
            "details": details,
        }
    }
    return JSONResponse(content=data)
