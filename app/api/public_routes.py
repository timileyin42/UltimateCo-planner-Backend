from typing import List, Optional
from html import escape
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logger import get_logger
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


def _simple_fallback_page(target_url: str, token: Optional[str] = None, invalid_link: bool = False) -> HTMLResponse:
    safe_target_url = escape(_normalize_url_for_compare(target_url))
    safe_web_url = escape(_invite_fallback_url())
    mobile_url = _mobile_app_invite_url(token)
    safe_mobile_url = escape(mobile_url) if mobile_url else ""
    heading = "This invite link is no longer valid" if invalid_link else "Open in PlanEtAl"
    description = (
        "Use the options below to continue."
        if invalid_link
        else "Use the options below to continue in the app or on web."
    )
    primary_label = "Open app link"
    fallback_label = "Open web page"
    open_script = ""
    if mobile_url and not invalid_link:
        open_script = f"""
        <script>
            setTimeout(function () {{
                window.location.href = "{safe_mobile_url}";
            }}, 150);
        </script>
        """

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
                max-width: 520px;
                margin: 40px auto;
                padding: 0 16px;
                line-height: 1.5;
            }}
            .actions {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-top: 20px;
            }}
            .btn {{
                display: inline-block;
                text-decoration: none;
                padding: 10px 14px;
                border-radius: 8px;
                border: 1px solid #d0d7de;
                color: #111827;
            }}
            .btn-primary {{
                background: #111827;
                color: #ffffff;
                border-color: #111827;
            }}
            .muted {{
                margin-top: 16px;
                font-size: 14px;
                color: #6b7280;
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <h2>{heading}</h2>
        <p>{description}</p>
        <div class="actions">
            {"<a class='btn btn-primary' href='" + safe_mobile_url + "'>" + primary_label + "</a>" if mobile_url else ""}
            <a class="btn" href="{safe_target_url if not invalid_link else safe_web_url}">{fallback_label if invalid_link else "Open invite URL"}</a>
            {"<a class='btn' href='" + safe_web_url + "'>" + fallback_label + "</a>" if mobile_url and not invalid_link else ""}
        </div>
        <p class="muted">{safe_target_url if not invalid_link else safe_web_url}</p>
        {open_script}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


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

    is_valid = False
    if invite_code and invite_code.is_valid:
        is_valid = True
    if invite_link and invite_link.is_valid:
        is_valid = True

    target_base = _deep_link_base()
    target_url = f"{target_base}/invite/{token}"
    normalized_request_url = _normalize_url_for_compare(str(request.url))

    if not is_valid:
        fallback_url = _invite_fallback_url()
        if normalized_request_url == _normalize_url_for_compare(fallback_url):
            return _simple_fallback_page(fallback_url, invalid_link=True)
        return RedirectResponse(url=fallback_url, status_code=302)

    if normalized_request_url == _normalize_url_for_compare(target_url):
        return _simple_fallback_page(target_url, token=token)

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
