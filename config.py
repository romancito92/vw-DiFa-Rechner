import os
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

def _load_ors_api_key():
    """Load ORS key from Streamlit secrets first, then environment."""
    try:
        direct_secret = st.secrets.get("ORS_API_KEY", "")
        if isinstance(direct_secret, str) and direct_secret.strip():
            return direct_secret.strip(), "st.secrets[ORS_API_KEY]"

        alt_secret = st.secrets.get("OPENROUTESERVICE_API_KEY", "")
        if isinstance(alt_secret, str) and alt_secret.strip():
            return alt_secret.strip(), "st.secrets[OPENROUTESERVICE_API_KEY]"

        scoped = st.secrets.get("openrouteservice", {})
        if isinstance(scoped, dict):
            scoped_key = scoped.get("api_key", "")
            if isinstance(scoped_key, str) and scoped_key.strip():
                return scoped_key.strip(), "st.secrets[openrouteservice.api_key]"
    except Exception:
        pass

    env_key = os.getenv("ORS_API_KEY", "").strip()
    if env_key:
        return env_key, "env[ORS_API_KEY]"

    env_alt = os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
    if env_alt:
        return env_alt, "env[OPENROUTESERVICE_API_KEY]"

    return "", "missing"


DEFAULT_ORS_API_KEY, ORS_API_KEY_SOURCE = _load_ors_api_key()


def _load_tankerkoenig_api_key():
    """Load Tankerkoenig key from Streamlit secrets first, then environment, else demo."""
    try:
        direct_secret = st.secrets.get("TANKERKOENIG_API_KEY", "")
        if isinstance(direct_secret, str) and direct_secret.strip():
            return direct_secret.strip(), "st.secrets[TANKERKOENIG_API_KEY]"

        scoped = st.secrets.get("tankerkoenig", {})
        if isinstance(scoped, dict):
            scoped_key = scoped.get("api_key", "")
            if isinstance(scoped_key, str) and scoped_key.strip():
                return scoped_key.strip(), "st.secrets[tankerkoenig.api_key]"
    except Exception:
        pass

    env_key = os.getenv("TANKERKOENIG_API_KEY", "").strip()
    if env_key:
        return env_key, "env[TANKERKOENIG_API_KEY]"

    return TANKERKOENIG_DEMO_API_KEY, "demo key"


DEFAULT_TANKERKOENIG_API_KEY, TANKERKOENIG_API_KEY_SOURCE = _load_tankerkoenig_api_key()

ORS_PROFILE_LABELS = {
    "driving-car": "PKW (driving-car)",
    "driving-hgv": "LKW (driving-hgv)",
    "cycling-regular": "Fahrrad (cycling-regular)",
    "foot-walking": "Zu Fuß (foot-walking)",
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
