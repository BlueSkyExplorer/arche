from app.core.config import Settings


def test_config_defaults(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for name in ("DATABASE_URL", "APP_ENV", "AUTH_MODE", "STUB_AUTH_EMAIL"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("/arche_dev")
    assert settings.app_env == "development"
    assert settings.auth_mode == "stub"
    assert settings.stub_auth_email == "demo@example.com"
