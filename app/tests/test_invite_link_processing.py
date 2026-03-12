from types import SimpleNamespace
from unittest.mock import Mock

from app.api import public_routes
from app.services.invite_service import InviteService


class TestInviteLinkProcessing:
    def test_process_invite_link_returns_invalid_when_missing(self):
        service = InviteService.__new__(InviteService)
        service.repo = Mock()
        service.repo.get_invite_link_by_link_id.return_value = None

        result = service.process_invite_link("missing-token")

        assert result.success is False
        assert result.message == "Invalid invite link"

    def test_process_invite_link_checks_is_valid_property(self):
        service = InviteService.__new__(InviteService)
        service.repo = Mock()

        invite_link = SimpleNamespace(is_valid=False, user_id=3)
        service.repo.get_invite_link_by_link_id.return_value = invite_link

        result = service.process_invite_link("expired-token")

        assert result.success is False
        assert result.message == "Invite link is expired or has reached maximum uses"

    def test_process_invite_link_success_path(self):
        service = InviteService.__new__(InviteService)
        service.repo = Mock()

        invite_link = SimpleNamespace(is_valid=True, user_id=7)
        service.repo.get_invite_link_by_link_id.return_value = invite_link
        service.repo.use_invite_link.return_value = invite_link

        result = service.process_invite_link("valid-token", ip_address="127.0.0.1")

        assert result.success is True
        assert result.message == "Invite link processed successfully"
        assert result.creator_id == 7

    def test_process_invite_code_checks_is_valid_property(self):
        service = InviteService.__new__(InviteService)
        service.repo = Mock()

        invite_code = SimpleNamespace(is_valid=False, invite_type="app_general", user_id=2)
        service.repo.get_invite_code_by_code.return_value = invite_code

        result = service.process_invite_code("invalid-code")

        assert result.success is False
        assert result.message == "Invite code is expired or already used"

    def test_deep_link_base_strips_wrapping_characters(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "DEEP_LINK_BASE_URL", "`https://planetal.app`")
        monkeypatch.setattr(public_routes.settings, "FRONTEND_URL", "https://fallback.planetal.app")

        assert public_routes._deep_link_base() == "https://planetal.app"

    def test_invite_fallback_url_strips_wrapping_characters(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "INVITE_FALLBACK_URL", "'https://planetal.app'")
        monkeypatch.setattr(public_routes.settings, "FRONTEND_URL", "https://fallback.planetal.app")

        assert public_routes._invite_fallback_url() == "https://planetal.app"

    def test_normalize_url_for_compare_strips_quotes_and_trailing_slash(self):
        assert public_routes._normalize_url_for_compare("`https://planetal.app/invite/token/`") == "https://planetal.app/invite/token"

    def test_mobile_app_invite_url_uses_mobile_scheme(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "MOBILE_APP_SCHEME", "planetal://")

        assert public_routes._mobile_app_invite_url("pfz9aadgkmdz") == "planetal://invite/pfz9aadgkmdz"

    def test_preferred_store_url_ios(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "IOS_APP_STORE_URL", "https://apps.apple.com/app/id123")
        monkeypatch.setattr(public_routes.settings, "ANDROID_PLAY_STORE_URL", "https://play.google.com/store/apps/details?id=com.app.planetal")

        url = public_routes._preferred_store_url("Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X)")

        assert url == "https://apps.apple.com/app/id123"

    def test_preferred_store_url_android(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "IOS_APP_STORE_URL", "https://apps.apple.com/app/id123")
        monkeypatch.setattr(public_routes.settings, "ANDROID_PLAY_STORE_URL", "https://play.google.com/store/apps/details?id=com.app.planetal")

        url = public_routes._preferred_store_url("Mozilla/5.0 (Linux; Android 14; Pixel 8)")

        assert url == "https://play.google.com/store/apps/details?id=com.app.planetal"

    def test_simple_fallback_page_includes_mobile_link(self, monkeypatch):
        monkeypatch.setattr(public_routes.settings, "MOBILE_APP_SCHEME", "planetal://")
        monkeypatch.setattr(public_routes.settings, "INVITE_FALLBACK_URL", "https://planetal.app")
        monkeypatch.setattr(public_routes.settings, "FRONTEND_URL", "https://planetal.app")
        monkeypatch.setattr(public_routes.settings, "IOS_APP_STORE_URL", "https://apps.apple.com/app/id123")
        monkeypatch.setattr(public_routes.settings, "ANDROID_PLAY_STORE_URL", "https://play.google.com/store/apps/details?id=com.app.planetal")

        response = public_routes._simple_fallback_page("https://planetal.app/invite/pfz9aadgkmdz", token="pfz9aadgkmdz")
        page = response.body.decode()

        assert "Open in PlanEtAl app" in page
        assert "Download on the App Store" in page
        assert "Get it on Google Play" in page

    def test_simple_fallback_page_invalid_link_status_code(self):
        response = public_routes._simple_fallback_page(
            "https://planetal.app/invite/invalid-token",
            invalid_link=True,
            status_code=404
        )

        assert response.status_code == 404
