from auth_helpers import format_oidc_configuration_error, get_role_for_email, is_email_authorized
from config import AuthSettings, OidcSettings


def run_tests():
    settings = AuthSettings(
        provider_key="microsoft",
        provider_label="Microsoft Entra ID",
        allowed_domains=("versandwerk.net",),
        allowed_emails=("sonderfall@partner.example",),
        admin_emails=("admin@versandwerk.net",),
    )

    assert is_email_authorized("max@versandwerk.net", settings) is True
    assert is_email_authorized("Max@Versandwerk.net", settings) is True
    assert is_email_authorized("sonderfall@partner.example", settings) is True
    assert is_email_authorized("extern@example.com", settings) is False
    assert is_email_authorized("", settings) is False

    assert get_role_for_email("admin@versandwerk.net", settings) == "admin"
    assert get_role_for_email("mitarbeiter@versandwerk.net", settings) == "user"

    deny_by_default_settings = AuthSettings(
        provider_key="microsoft",
        provider_label="Microsoft Entra ID",
        allowed_domains=(),
        allowed_emails=(),
        admin_emails=(),
    )
    assert is_email_authorized("max@versandwerk.net", deny_by_default_settings) is False

    configured_oidc = OidcSettings(
        provider_key="microsoft",
        provider_label="Microsoft Entra ID",
        redirect_uri="https://example.streamlit.app/oauth2callback",
        cookie_secret="cookie-secret",
        client_id="client-id",
        client_secret="client-secret",
        tenant_id="tenant-id",
        server_metadata_url="https://login.microsoftonline.com/tenant-id/v2.0/.well-known/openid-configuration",
        missing_fields=(),
    )
    assert format_oidc_configuration_error(configured_oidc) == ""

    missing_oidc = OidcSettings(
        provider_key="microsoft",
        provider_label="Microsoft Entra ID",
        redirect_uri="",
        cookie_secret="",
        client_id="",
        client_secret="",
        tenant_id="",
        server_metadata_url="",
        missing_fields=(
            "auth.redirect_uri",
            "auth.cookie_secret",
            "auth.microsoft.client_id",
            "auth.microsoft.client_secret",
            "auth.microsoft.server_metadata_url",
        ),
    )
    oidc_error = format_oidc_configuration_error(missing_oidc)
    assert "OIDC-Anmeldung" in oidc_error
    assert "auth.redirect_uri" in oidc_error

    print("OK: Auth- und Autorisierungsregeln bestehen den Smoke-Test.")


if __name__ == "__main__":
    run_tests()
