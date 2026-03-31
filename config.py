import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st


RATE_TABLE = {
    "Transporter / Sprinter": {
        "kurz": {"min": 1.10, "mittel": 1.30, "max": 1.50},
        "mittel": {"min": 0.80, "mittel": 1.10, "max": 1.40},
        "lang": {"min": 0.80, "mittel": 1.00, "max": 1.20},
    },
    "XXL / Planensprinter": {
        "kurz": {"min": 1.30, "mittel": 1.50, "max": 1.70},
        "mittel": {"min": 1.00, "mittel": 1.30, "max": 1.60},
        "lang": {"min": 1.10, "mittel": 1.20, "max": 1.40},
    },
    "7,5 to": {
        "kurz": {"min": 3.00, "mittel": 3.50, "max": 4.00},
        "mittel": {"min": 2.75, "mittel": 3.00, "max": 3.75},
        "lang": {"min": 2.00, "mittel": 2.50, "max": 3.00},
    },
    "12 to": {
        "kurz": {"min": 3.80, "mittel": 4.50, "max": 5.00},
        "mittel": {"min": 3.50, "mittel": 4.00, "max": 4.50},
        "lang": {"min": 2.80, "mittel": 3.20, "max": 3.80},
    },
}

PARCEL_CONFIG_PATH = Path(__file__).with_name("parcel_tariffs_de.json")

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_DIRECTIONS_URL_TEMPLATE = "https://api.openrouteservice.org/v2/directions/{profile}"
TANKERKOENIG_LIST_URL = "https://creativecommons.tankerkoenig.de/json/list.php"
TANKERKOENIG_DEMO_API_KEY = "00000000-0000-0000-0000-000000000002"
TANKERKOENIG_DEFAULT_LOCATION = {
    "label": "Hauptstandort 57072 Siegen",
    "lat": 50.8804,
    "lng": 7.9845,
}
TANKERKOENIG_DEFAULT_RADIUS_KM = 5.0
DEFAULT_ALLOWED_EMAIL_DOMAINS = ("versandwerk.net",)


@dataclass(frozen=True)
class SecretValue:
    value: str
    source: str


@dataclass(frozen=True)
class AuthSettings:
    provider_key: str
    provider_label: str
    allowed_domains: tuple[str, ...]
    allowed_emails: tuple[str, ...]
    admin_emails: tuple[str, ...]


@dataclass(frozen=True)
class OidcSettings:
    provider_key: str
    provider_label: str
    redirect_uri: str
    cookie_secret: str
    client_id: str
    client_secret: str
    tenant_id: str
    server_metadata_url: str
    missing_fields: tuple[str, ...]

    @property
    def is_configured(self):
        return len(self.missing_fields) == 0


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _safe_get_secret(path, default=""):
    try:
        node = st.secrets
        for key in path:
            next_node = None
            if hasattr(node, "get"):
                try:
                    next_node = node.get(key)
                except Exception:
                    next_node = None
            if next_node is None:
                try:
                    next_node = node[key]
                except Exception:
                    return default
            node = next_node
        if node is not None:
            return node
    except Exception:
        pass

    return default


def get_secret(secret_name, section_paths=(), env_names=(), default=None):
    """Read a secret with Streamlit Community Cloud-friendly precedence."""
    root_value = _normalize_text(_safe_get_secret((secret_name,), ""))
    if root_value:
        return SecretValue(root_value, f"st.secrets[{secret_name}]")

    for section_path in section_paths:
        if not section_path:
            continue
        if isinstance(section_path, str):
            path = tuple(part for part in section_path.split(".") if part)
        else:
            path = tuple(section_path)
        value = _normalize_text(_safe_get_secret(path, ""))
        if value:
            return SecretValue(value, "st.secrets[" + ".".join(path) + "]")

    for env_name in env_names:
        value = _normalize_text(os.getenv(env_name, ""))
        if value:
            return SecretValue(value, f"env[{env_name}]")

    return SecretValue("" if default is None else str(default), "missing")


def _read_list(secret_paths, env_names, default=()):
    for path in secret_paths:
        raw = _safe_get_secret(path, None)
        if isinstance(raw, (list, tuple, set)):
            values = tuple(_normalize_text(item).lower() for item in raw if _normalize_text(item))
            if values:
                return values
        if isinstance(raw, str):
            values = tuple(
                item.strip().lower()
                for item in raw.split(",")
                if item and item.strip()
            )
            if values:
                return values

    for env_name in env_names:
        raw = _normalize_text(os.getenv(env_name, ""))
        if raw:
            return tuple(item.strip().lower() for item in raw.split(",") if item.strip())

    return tuple(item.lower() for item in default)


def get_ors_api_key():
    return get_secret(
        "ORS_API_KEY",
        section_paths=(
            ("openrouteservice", "api_key"),
            ("openrouteservice", "apiKey"),
            ("api", "ORS_API_KEY"),
        ),
        env_names=("ORS_API_KEY", "OPENROUTESERVICE_API_KEY"),
    )


def get_tankerkoenig_api_key():
    secret = get_secret(
        "TANKERKOENIG_API_KEY",
        section_paths=(
            ("tankerkoenig", "api_key"),
            ("tankerkoenig", "apiKey"),
            ("api", "TANKERKOENIG_API_KEY"),
        ),
        env_names=("TANKERKOENIG_API_KEY",),
        default=TANKERKOENIG_DEMO_API_KEY,
    )
    if secret.source == "missing":
        return SecretValue(value=TANKERKOENIG_DEMO_API_KEY, source="demo key")
    return secret


def get_auth_settings():
    provider_key = _normalize_text(
        _safe_get_secret(("app_auth", "provider_key"), "")
    ) or _normalize_text(os.getenv("VW_AUTH_PROVIDER_KEY", "")) or "microsoft"
    provider_label = _normalize_text(
        _safe_get_secret(("app_auth", "provider_label"), "")
    ) or _normalize_text(os.getenv("VW_AUTH_PROVIDER_LABEL", "")) or "Microsoft Entra ID"

    allowed_domains = _read_list(
        secret_paths=(
            ("app_auth", "allowed_domains"),
            ("allowed_domains",),
        ),
        env_names=("VW_ALLOWED_DOMAINS",),
        default=DEFAULT_ALLOWED_EMAIL_DOMAINS,
    )
    allowed_emails = _read_list(
        secret_paths=(
            ("app_auth", "allowed_emails"),
            ("allowed_emails",),
        ),
        env_names=("VW_ALLOWED_EMAILS",),
    )
    admin_emails = _read_list(
        secret_paths=(
            ("app_auth", "admin_emails"),
            ("admin_emails",),
        ),
        env_names=("VW_ADMIN_EMAILS",),
    )

    return AuthSettings(
        provider_key=provider_key,
        provider_label=provider_label,
        allowed_domains=allowed_domains,
        allowed_emails=allowed_emails,
        admin_emails=admin_emails,
    )


def build_microsoft_metadata_url(tenant_id):
    normalized_tenant_id = _normalize_text(tenant_id)
    if not normalized_tenant_id:
        return ""
    return (
        f"https://login.microsoftonline.com/{normalized_tenant_id}"
        "/v2.0/.well-known/openid-configuration"
    )


def get_oidc_settings():
    auth_settings = get_auth_settings()
    provider_key = auth_settings.provider_key or "microsoft"

    redirect_uri = _normalize_text(_safe_get_secret(("auth", "redirect_uri"), "")) or _normalize_text(
        os.getenv("STREAMLIT_AUTH_REDIRECT_URI", "")
    )
    cookie_secret = _normalize_text(_safe_get_secret(("auth", "cookie_secret"), "")) or _normalize_text(
        os.getenv("STREAMLIT_AUTH_COOKIE_SECRET", "")
    )

    client_id = get_secret(
        "client_id",
        section_paths=(("auth", provider_key, "client_id"), ("auth", "client_id")),
        env_names=("STREAMLIT_AUTH_CLIENT_ID",),
    ).value
    client_secret = get_secret(
        "client_secret",
        section_paths=(("auth", provider_key, "client_secret"), ("auth", "client_secret")),
        env_names=("STREAMLIT_AUTH_CLIENT_SECRET",),
    ).value
    tenant_id = get_secret(
        "tenant_id",
        section_paths=(("auth", provider_key, "tenant_id"), ("auth", "tenant_id")),
        env_names=("STREAMLIT_AUTH_TENANT_ID",),
    ).value
    server_metadata_secret = get_secret(
        "server_metadata_url",
        section_paths=(("auth", provider_key, "server_metadata_url"), ("auth", "server_metadata_url")),
        env_names=("STREAMLIT_AUTH_SERVER_METADATA_URL",),
        default=build_microsoft_metadata_url(tenant_id),
    )
    server_metadata_url = server_metadata_secret.value

    missing_fields = []
    if not redirect_uri:
        missing_fields.append("auth.redirect_uri")
    if not cookie_secret:
        missing_fields.append("auth.cookie_secret")
    if not client_id:
        missing_fields.append(f"auth.{provider_key}.client_id")
    if not client_secret:
        missing_fields.append(f"auth.{provider_key}.client_secret")
    if not tenant_id and "login.microsoftonline.com" in server_metadata_url:
        missing_fields.append(f"auth.{provider_key}.tenant_id")
    if not server_metadata_url:
        missing_fields.append(f"auth.{provider_key}.server_metadata_url")

    return OidcSettings(
        provider_key=provider_key,
        provider_label=auth_settings.provider_label,
        redirect_uri=redirect_uri,
        cookie_secret=cookie_secret,
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        server_metadata_url=server_metadata_url,
        missing_fields=tuple(missing_fields),
    )


ORS_PROFILE_LABELS = {
    "driving-car": "PKW (driving-car)",
    "driving-hgv": "LKW (driving-hgv)",
    "cycling-regular": "Fahrrad (cycling-regular)",
    "foot-walking": "Zu Fuss (foot-walking)",
}

VEHICLE_TO_ORS_PROFILE = {
    "Transporter / Sprinter": "driving-car",
    "XXL / Planensprinter": "driving-car",
    "7,5 to": "driving-hgv",
    "12 to": "driving-hgv",
}

ORS_PROFILE_TO_VEHICLE = {
    "driving-car": "Transporter / Sprinter",
    "driving-hgv": "7,5 to",
    "cycling-regular": "Transporter / Sprinter",
    "foot-walking": "Transporter / Sprinter",
}
