import re
from itertools import product
from urllib.parse import urlencode

import pycountry
import requests
import streamlit as st

from config import ORS_DIRECTIONS_URL_TEMPLATE, ORS_GEOCODE_URL, ORS_REVERSE_GEOCODE_URL


ORS_GEOCODE_LANGUAGE = "de"
ORS_GEOCODE_CANDIDATE_LIMIT = 5
ORS_RETRY_SNAP_RADIUS_METERS = 1000
ORS_MAX_ROUTING_ATTEMPTS = 6
ORS_FALLBACK_USER_MESSAGE = (
    "ORS-Abruf fehlgeschlagen. Bitte Adresse prüfen oder Route in Google Maps öffnen."
)
GERMAN_COUNTRY_CODES = {"DE", "DEU"}
GERMAN_POSTAL_CODE_PATTERN = re.compile(r"(?<!\d)(\d{5})(?!\d)")

GERMAN_CITY_TRANSLATIONS = {
    "Cologne": "Köln",
    "Munich": "München",
    "Nuremberg": "Nürnberg",
}

COUNTRY_TRANSLATIONS = {
    "Germany": "Deutschland",
    "Austria": "Österreich",
    "Switzerland": "Schweiz",
}

ISO3_TO_ISO2_OVERRIDES = {
    "XKX": "XK",
}


class ORSError(ValueError):
    """Structured ORS error that keeps the response payload inspectable."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.error_code = None
        if isinstance(payload, dict):
            error_payload = payload.get("error", {})
            if isinstance(error_payload, dict):
                self.error_code = error_payload.get("code")
        super().__init__(f"ORS HTTP {status_code}: {payload}")


def _raise_ors_error(response):
    """Build a readable ORS error with HTTP status and payload."""
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    raise ORSError(response.status_code, payload)


def _build_geocode_params(search_text, api_key, size):
    return {
        "api_key": api_key,
        "text": search_text,
        "size": size,
        "lang": ORS_GEOCODE_LANGUAGE,
    }


def geocode_with_ors(address, api_key):
    """Liefert [lon, lat] für eine Adresse via ORS Geocoder."""
    candidates = geocode_candidates_with_ors(address, api_key, size=1)
    return candidates[0]["coordinates"]


def geocode_candidates_with_ors(address, api_key, size=ORS_GEOCODE_CANDIDATE_LIMIT):
    """Liefert mehrere ORS-Geocoding-Kandidaten inkl. Label und Koordinaten."""
    response = requests.get(
        ORS_GEOCODE_URL,
        params=_build_geocode_params(address, api_key, size),
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Adresse nicht gefunden: {address}")
    candidates = []
    seen = set()
    for feature in features:
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates")
        if not coordinates or len(coordinates) < 2:
            continue
        props = feature.get("properties", {})
        label = (
            _format_address_suggestion(
                props,
                fallback_postal_code=_extract_german_postal_code(address),
            )
            or props.get("label")
            or address
        )
        key = (round(float(coordinates[0]), 6), round(float(coordinates[1]), 6), label)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "coordinates": coordinates,
                "label": label,
                "properties": props,
            }
        )
    if not candidates:
        raise ValueError(f"Adresse nicht gefunden: {address}")
    return candidates


def _join_non_empty(parts, separator=", "):
    return separator.join(str(part).strip() for part in parts if str(part).strip())


def _translate_locality_name(locality, country_code):
    cleaned_locality = (locality or "").strip()
    if not cleaned_locality:
        return ""
    if country_code in GERMAN_COUNTRY_CODES:
        return GERMAN_CITY_TRANSLATIONS.get(cleaned_locality, cleaned_locality)
    return cleaned_locality


def _format_country(country, country_code):
    if country_code:
        return _to_iso2_country_code(country_code)
    cleaned_country = (country or "").strip()
    if not cleaned_country:
        return ""
    return COUNTRY_TRANSLATIONS.get(cleaned_country, cleaned_country)


def _to_iso2_country_code(country_code):
    """Normalize ORS alpha-2/alpha-3 country codes to ISO alpha-2."""
    cleaned_code = str(country_code or "").strip().upper()
    if len(cleaned_code) == 2:
        return cleaned_code
    if cleaned_code in ISO3_TO_ISO2_OVERRIDES:
        return ISO3_TO_ISO2_OVERRIDES[cleaned_code]
    if len(cleaned_code) == 3:
        country = pycountry.countries.get(alpha_3=cleaned_code)
        if country is not None:
            return country.alpha_2
    return cleaned_code


def _looks_like_same_place(first, second):
    return (first or "").strip().casefold() == (second or "").strip().casefold()


def _extract_german_postal_code(search_text):
    match = GERMAN_POSTAL_CODE_PATTERN.search(str(search_text or ""))
    return match.group(1) if match else ""


def _format_address_suggestion(props, fallback_postal_code=""):
    name = props.get("name") or ""
    street = props.get("street") or ""
    house_number = props.get("housenumber") or ""
    postal_code = props.get("postalcode") or props.get("postal_code") or ""
    country_code = (props.get("country_a") or "").upper()
    country_name = (props.get("country") or "").strip()
    is_german_result = (
        country_code in GERMAN_COUNTRY_CODES
        or country_name.casefold() in {"germany", "deutschland"}
    )
    if not postal_code and fallback_postal_code and is_german_result:
        postal_code = fallback_postal_code
    locality = (
        props.get("locality")
        or props.get("borough")
        or props.get("municipality")
        or props.get("localadmin")
        or props.get("county")
        or ""
    )
    if not locality and name and not street:
        locality = name
    locality = _translate_locality_name(locality, country_code)
    country = _format_country(country_name, country_code)

    layer = props.get("layer") or ""
    if not street and name and not _looks_like_same_place(name, locality):
        if house_number or layer in {"address", "street", "venue"}:
            street = name

    street_line = _join_non_empty([street, house_number], separator=" ")
    city_line = _join_non_empty([postal_code, locality], separator=" ")

    return _join_non_empty([street_line, city_line, country])


@st.cache_data(ttl=86400, show_spinner=False)
def _reverse_lookup_postal_code(longitude, latitude, api_key, country_code=""):
    """Resolve a missing postal code from a candidate coordinate via ORS address data."""
    response = requests.get(
        ORS_REVERSE_GEOCODE_URL,
        params={
            "api_key": api_key,
            "point.lon": float(longitude),
            "point.lat": float(latitude),
            "size": 5,
            "layers": "address",
            "lang": ORS_GEOCODE_LANGUAGE,
        },
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    expected_country = str(country_code or "").upper()
    for feature in response.json().get("features", []):
        props = feature.get("properties", {})
        feature_country = str(props.get("country_a") or "").upper()
        if expected_country and feature_country and feature_country != expected_country:
            continue
        postal_code = props.get("postalcode") or props.get("postal_code")
        if postal_code:
            return str(postal_code).strip()
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def get_ors_address_suggestions(query, api_key):
    """Liefert bis zu 5 Adressvorschläge für Autocomplete."""
    if not query or len(query.strip()) < 3:
        return []
    response = requests.get(
        ORS_GEOCODE_URL,
        params=_build_geocode_params(query.strip(), api_key, 5),
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    suggestions = []
    fallback_postal_code = _extract_german_postal_code(query)
    for feature in features:
        props = feature.get("properties", {})
        postal_code = props.get("postalcode") or props.get("postal_code")
        country_code = str(props.get("country_a") or "").upper()
        country_name = str(props.get("country") or "").strip().casefold()
        uses_query_postal_code = bool(fallback_postal_code) and (
            country_code in GERMAN_COUNTRY_CODES
            or country_name in {"germany", "deutschland"}
        )
        formatted_props = props
        if not postal_code and not uses_query_postal_code:
            coordinates = feature.get("geometry", {}).get("coordinates") or []
            if len(coordinates) >= 2:
                try:
                    reverse_postal_code = _reverse_lookup_postal_code(
                        coordinates[0],
                        coordinates[1],
                        api_key,
                        props.get("country_a") or "",
                    )
                    if reverse_postal_code:
                        formatted_props = {**props, "postalcode": reverse_postal_code}
                except Exception:
                    pass
        label = (
            _format_address_suggestion(
                formatted_props,
                fallback_postal_code=fallback_postal_code,
            )
            or props.get("label")
        )
        if label:
            suggestions.append(label)
    seen = set()
    deduped = []
    for item in suggestions:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def _fetch_ors_route_summary(start_coords, target_coords, api_key, profile, radiuses=None):
    payload = {"coordinates": [start_coords, target_coords]}
    if radiuses:
        payload["radiuses"] = radiuses
    response = requests.post(
        ORS_DIRECTIONS_URL_TEMPLATE.format(profile=profile),
        json=payload,
        headers={"Authorization": api_key},
        timeout=25,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    routes = data.get("routes", [])
    if not routes:
        raise ValueError("Keine Route von ORS erhalten.")

    summary = routes[0]["summary"]
    distance_km = summary["distance"] / 1000
    duration_minutes = summary["duration"] / 60
    return distance_km, duration_minutes


def get_ors_distance_and_duration(start_address, target_address, api_key, profile):
    """Berechnet Distanz (km) und Dauer (Minuten) via ORS Directions."""
    start_coords = geocode_with_ors(start_address, api_key)
    target_coords = geocode_with_ors(target_address, api_key)
    return _fetch_ors_route_summary(start_coords, target_coords, api_key, profile)


def _is_routable_point_error(exc):
    if isinstance(exc, ORSError) and exc.error_code == 2010:
        return True
    return "Could not find routable point within a radius" in str(exc)


def _build_routing_attempts(start_candidates, target_candidates):
    attempts = [
        {
            "start": start_candidates[0],
            "target": target_candidates[0],
            "radiuses": None,
        },
        {
            "start": start_candidates[0],
            "target": target_candidates[0],
            "radiuses": [ORS_RETRY_SNAP_RADIUS_METERS, ORS_RETRY_SNAP_RADIUS_METERS],
        },
    ]
    for start_index, target_index in product(
        range(min(3, len(start_candidates))),
        range(min(3, len(target_candidates))),
    ):
        if start_index == 0 and target_index == 0:
            continue
        attempts.append(
            {
                "start": start_candidates[start_index],
                "target": target_candidates[target_index],
                "radiuses": [ORS_RETRY_SNAP_RADIUS_METERS, ORS_RETRY_SNAP_RADIUS_METERS],
            }
        )
        if len(attempts) >= ORS_MAX_ROUTING_ATTEMPTS:
            break
    return attempts[:ORS_MAX_ROUTING_ATTEMPTS]


def get_ors_distance_and_duration_robust(start_address, target_address, api_key, profile):
    """Berechnet ORS-Daten mit wenigen, nachvollziehbaren Snapping-/Kandidaten-Retries."""
    start_candidates = geocode_candidates_with_ors(start_address, api_key)
    target_candidates = geocode_candidates_with_ors(target_address, api_key)
    last_error = None

    for attempt in _build_routing_attempts(start_candidates, target_candidates):
        try:
            return _fetch_ors_route_summary(
                attempt["start"]["coordinates"],
                attempt["target"]["coordinates"],
                api_key,
                profile,
                radiuses=attempt["radiuses"],
            )
        except Exception as exc:
            last_error = exc
            if not _is_routable_point_error(exc):
                raise

    raise last_error


def build_google_maps_directions_url(start_address, target_address):
    """Erzeugt einen Google-Maps-Fallback-Link ohne API-Key."""
    start = (start_address or "").strip()
    target = (target_address or "").strip()
    if not start or not target:
        return None
    return "https://www.google.com/maps/dir/?" + urlencode(
        {
            "api": "1",
            "origin": start,
            "destination": target,
            "travelmode": "driving",
        }
    )


def _sanitize_error_detail(detail):
    cleaned = str(detail or "")
    patterns = (
        r"(?i)(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[^'\",\s}&]+",
        r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)[^'\",\s}&]+",
    )
    for pattern in patterns:
        cleaned = re.sub(pattern, r"\1<redacted>", cleaned)
    return cleaned


def build_ors_failure_feedback(exc, start_address="", target_address=""):
    """Bereitet eine ruhige Nutzerfehlermeldung plus technische Details auf."""
    return {
        "state": "error",
        "message": ORS_FALLBACK_USER_MESSAGE,
        "details": _sanitize_error_detail(exc),
        "maps_url": build_google_maps_directions_url(start_address, target_address),
    }
