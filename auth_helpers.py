import streamlit as st

from config import get_auth_settings, get_oidc_settings


def is_logged_in():
    return bool(getattr(st.user, "is_logged_in", False))


def get_user_claim(claim_name, default=""):
    try:
        value = st.user.get(claim_name, default)
    except Exception:
        value = getattr(st.user, claim_name, default)
    return value if value is not None else default


def get_user_email():
    for claim_name in ("email", "preferred_username", "upn", "unique_name"):
        value = str(get_user_claim(claim_name, "")).strip().lower()
        if value:
            return value
    return ""


def get_user_display_name():
    for claim_name in ("name", "given_name", "preferred_username", "email"):
        value = str(get_user_claim(claim_name, "")).strip()
        if value:
            return value
    return "Unbekannter Benutzer"


def get_role_for_email(email, settings=None):
    normalized_email = str(email or "").strip().lower()
    settings = settings or get_auth_settings()
    if normalized_email and normalized_email in settings.admin_emails:
        return "admin"
    return "user"


def is_email_authorized(email, settings=None):
    normalized_email = str(email or "").strip().lower()
    settings = settings or get_auth_settings()

    if not normalized_email:
        return False

    # Regel 1: Eine explizite Allowlist hat Vorrang.
    if settings.allowed_emails and normalized_email in settings.allowed_emails:
        return True

    if "@" not in normalized_email:
        return False

    # Regel 2: Danach gilt optional der Domain-Check.
    # Wenn keine passende Domain konfiguriert ist, bleibt deny by default aktiv.
    domain = normalized_email.split("@", 1)[1]
    return domain in settings.allowed_domains


def get_user_role():
    return get_role_for_email(get_user_email())


def is_user_authorized():
    if not is_logged_in():
        return False
    return is_email_authorized(get_user_email())


def login_button_label():
    settings = get_auth_settings()
    provider = settings.provider_label.strip() or "Microsoft Entra ID"
    return f"Mit {provider} anmelden"


def format_oidc_configuration_error(oidc_settings):
    if oidc_settings.is_configured:
        return ""

    missing_keys = ", ".join(oidc_settings.missing_fields)
    return (
        "OIDC-Anmeldung ist noch nicht vollstaendig konfiguriert. "
        "Bitte pruefen Sie die Streamlit-Secrets fuer Redirect URI, Cookie Secret, "
        f"Client ID, Client Secret und Tenant-/Metadata-URL. Fehlende Eintraege: {missing_keys}"
    )


def get_oidc_configuration_error():
    oidc_settings = get_oidc_settings()
    return format_oidc_configuration_error(oidc_settings)


def render_access_denied():
    email = get_user_email()
    st.error("Zugriff verweigert. Dieses Konto ist fuer die interne Preisrechner-App nicht freigeschaltet.")
    if email:
        st.caption(f"Angemeldetes Konto: {email}")
    if st.button("Abmelden", key="auth_logout_denied"):
        st.logout()
