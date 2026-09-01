from app.models.user import User
from app.services.auth import link_google_identity


def test_link_google_identity_upgrades_a_legacy_user() -> None:
    user = User(
        full_name="Legacy Creator",
        email="creator@example.com",
        hashed_password="legacy-hash",
        auth_provider="password",
    )

    link_google_identity(
        user,
        {
            "sub": "google-account-123",
            "name": "Google Creator",
            "picture": "https://example.com/avatar.png",
        },
    )

    assert user.auth_provider == "google"
    assert user.provider_account_id == "google-account-123"
    assert user.avatar_url == "https://example.com/avatar.png"
    assert user.hashed_password is None


def test_link_google_identity_keeps_existing_name_when_google_name_is_missing() -> None:
    user = User(
        full_name="Existing Name",
        email="creator@example.com",
        hashed_password=None,
        auth_provider="google",
    )

    link_google_identity(user, {"sub": "google-account-123"})

    assert user.full_name == "Existing Name"
