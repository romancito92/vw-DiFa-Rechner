import os
import tomllib
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

    candidate_maps = []

    try:
        if hasattr(st.secrets, "to_dict"):
            candidate_maps.append(("st.secrets", st.secrets.to_dict()))
    except Exception:
        pass

    for secrets_path in (
        Path(__file__).with_name(".streamlit").joinpath("secrets.toml"),
        Path.home().joinpath(".streamlit", "secrets.toml"),
    ):
        try:
            if secrets_path.exists():
                with secrets_path.open("rb") as fh:
                    candidate_maps.append((str(secrets_path), tomllib.load(fh)))
        except Exception:
            continue

    for _, secret_map in candidate_maps:
        node = secret_map
        found = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                found = False
                break
        if found:
            return node

    return default


def _read_from_sources(secret_paths, env_names, default="", allow_blank=False):
    for path in secret_paths:
        raw = _safe_get_secret(path, "")
        value = _normalize_text(raw)
        if value or allow_blank:
            if value:
                return value, "st.secrets[" + ".".join(path) + "]"

    for env_name in env_names:
        value = _normalize_text(os.getenv(env_name, ""))
        if value:
            return value, f"env[{env_name}]"

    return default, "missing"


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
    return SecretValue(
        *_read_from_sources(
            secret_paths=(
                ("ORS_API_KEY",),
                ("ors_api_key",),
                ("OPENROUTESERVICE_API_KEY",),
                ("openrouteservice_api_key",),
                ("openrouteservice", "api_key"),
                ("openrouteservice", "apiKey"),
            ),
            env_names=("ORS_API_KEY", "ors_api_key", "OPENROUTESERVICE_API_KEY"),
        )
    )


def get_tankerkoenig_api_key():
    value, source = _read_from_sources(
        secret_paths=(
            ("TANKERKOENIG_API_KEY",),
            ("tankerkoenig_api_key",),
            ("tankerkoenig", "api_key"),
            ("tankerkoenig", "apiKey"),
        ),
        env_names=("TANKERKOENIG_API_KEY", "tankerkoenig_api_key"),
        default=TANKERKOENIG_DEMO_API_KEY,
    )
    if source == "missing":
        source = "demo key"
    return SecretValue(value=value, source=source)


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

    client_id, _ = _read_from_sources(
        secret_paths=(
            ("auth", provider_key, "client_id"),
            ("auth", "client_id"),
        ),
        env_names=("STREAMLIT_AUTH_CLIENT_ID",),
    )
    client_secret, _ = _read_from_sources(
        secret_paths=(
            ("auth", provider_key, "client_secret"),
            ("auth", "client_secret"),
        ),
        env_names=("STREAMLIT_AUTH_CLIENT_SECRET",),
    )
    tenant_id, _ = _read_from_sources(
        secret_paths=(
            ("auth", provider_key, "tenant_id"),
            ("auth", "tenant_id"),
        ),
        env_names=("STREAMLIT_AUTH_TENANT_ID",),
    )
    server_metadata_url, _ = _read_from_sources(
        secret_paths=(
            ("auth", provider_key, "server_metadata_url"),
            ("auth", "server_metadata_url"),
        ),
        env_names=("STREAMLIT_AUTH_SERVER_METADATA_URL",),
        default=build_microsoft_metadata_url(tenant_id),
    )

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
