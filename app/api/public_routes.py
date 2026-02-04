from typing import List
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
    return base.rstrip("/")


def _invite_fallback_url() -> str:
    fallback = settings.INVITE_FALLBACK_URL or settings.FRONTEND_URL
    return fallback.rstrip("/")


def _simple_fallback_page(target_url: str) -> HTMLResponse:
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>PlanEtAl Invite</title>
    </head>
    <body>
        <h2>Open in PlanEtAl</h2>
        <p>If you are not redirected automatically, use the link below:</p>
        <p><a href="{target_url}">{target_url}</a></p>
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

    if not is_valid:
        fallback_url = _invite_fallback_url()
        if str(request.url).rstrip("/") == fallback_url:
            return _simple_fallback_page(fallback_url)
        return RedirectResponse(url=fallback_url, status_code=302)

    if str(request.url) == target_url:
        return _simple_fallback_page(target_url)

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