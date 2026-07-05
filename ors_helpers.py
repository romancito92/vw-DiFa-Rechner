import re
from itertools import product
from urllib.parse import urlencode

import pycountry
import requests
import streamlit as st

from config import ORS_DIRECTIONS_URL_TEMPLATE, ORS_GEOCODE_URL, ORS_REVERSE_GEOCODE_URL
from location_candidates import (
    LocationCandidate,
    LocationResolutionError,
    extract_german_postal_code,
    get_de_postal_code_candidates,
)


ORS_GEOCODE_LANGUAGE = "de"
ORS_GEOCODE_CANDIDATE_LIMIT = 5
ORS_RETRY_SNAP_RADIUS_METERS = 1000
ORS_MAX_ROUTING_ATTEMPTS = 6
ORS_FALLBACK_USER_MESSAGE = (
    "ORS-Abruf fehlgeschlagen. Bitte Adresse prüfen oder Route in Google Maps öffnen."
)
GERMAN_COUNTRY_CODES = {"DE", "DEU"}

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
    candidates = _routing_candidates(address, api_key, size=1)
    return list(candidates[0].coordinates)


def geocode_candidates_with_ors(address, api_key, size=ORS_GEOCODE_CANDIDATE_LIMIT):
    """Liefert mehrere ORS-Geocoding-Kandidaten inkl. Label und Koordinaten."""
    query = _location_query(address)
    response = requests.get(
        ORS_GEOCODE_URL,
        params=_build_geocode_params(query, api_key, size),
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Adresse nicht gefunden: {query}")
    candidates = []
    seen = set()
    for feature in features:
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates")
        if not coordinates or len(coordinates) < 2:
            continue
        props = feature.get("properties", {})
        candidate = _build_ors_candidate(
            query,
            props,
            coordinates,
        )
        key = (
            round(float(coordinates[0]), 6),
            round(float(coordinates[1]), 6),
            candidate.display_label,
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    if not candidates:
        raise ValueError(f"Adresse nicht gefunden: {query}")
    return _sort_candidates_for_postal_code(candidates, extract_german_postal_code(query))


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
    return extract_german_postal_code(search_text)


def _format_address_suggestion(props):
    name = props.get("name") or ""
    street = props.get("street") or ""
    house_number = props.get("housenumber") or ""
    postal_code = props.get("postalcode") or props.get("postal_code") or ""
    country_code = (props.get("country_a") or "").upper()
    country_name = (props.get("country") or "").strip()
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


def _location_query(location):
    if isinstance(location, LocationCandidate):
        return (location.query or location.display_label or location.label).strip()
    return str(location or "").strip()


def _location_label(location):
    if isinstance(location, LocationCandidate):
        return (location.display_label or location.label or location.query).strip()
    return str(location or "").strip()


def _build_ors_candidate(query, props, coordinates):
    postal_code = str(props.get("postalcode") or props.get("postal_code") or "").strip()
    country_code = _to_iso2_country_code(props.get("country_a") or "")
    locality = str(
        props.get("locality")
        or props.get("borough")
        or props.get("municipality")
        or props.get("localadmin")
        or props.get("county")
        or props.get("name")
        or ""
    ).strip()
    label = _format_address_suggestion(props) or props.get("label") or query
    query_postal_code = extract_german_postal_code(query)
    warning = ""
    match_type = str(props.get("match_type") or "")
    if query_postal_code:
        if postal_code == query_postal_code:
            match_type = "postal_match"
        elif postal_code:
            match_type = "postal_mismatch"
            warning = (
                f"Die eingegebene PLZ {query_postal_code} stimmt nicht mit der von ORS "
                f"gefundenen PLZ {postal_code} überein."
            )
        else:
            match_type = "postal_unconfirmed"
            warning = (
                f"ORS konnte die eingegebene PLZ {query_postal_code} für diesen Treffer "
                "nicht bestätigen."
            )
    confidence = props.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return LocationCandidate(
        label=label,
        display_label=label,
        query=query,
        postal_code=postal_code,
        locality=locality,
        country_code=country_code,
        coordinates=(float(coordinates[0]), float(coordinates[1])),
        source="ors_geocode",
        confidence=confidence,
        match_type=match_type,
        warning=warning,
    )


def _sort_candidates_for_postal_code(candidates, query_postal_code):
    if not query_postal_code:
        return candidates
    priority = {"postal_match": 0, "postal_unconfirmed": 1, "postal_mismatch": 2}
    return sorted(candidates, key=lambda candidate: priority.get(candidate.match_type, 1))


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
def get_location_candidates(query, api_key):
    """Return coordinate-bearing local postal or ORS candidates for one query."""
    if not query or len(query.strip()) < 3:
        return []
    local_candidates = get_de_postal_code_candidates(query)
    if local_candidates is not None:
        return local_candidates
    if not api_key:
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
    candidates = []
    for feature in features:
        props = feature.get("properties", {})
        postal_code = props.get("postalcode") or props.get("postal_code")
        formatted_props = props
        coordinates = feature.get("geometry", {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        if not postal_code:
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
        candidates.append(_build_ors_candidate(query, formatted_props, coordinates))
    seen = set()
    deduped = []
    for candidate in _sort_candidates_for_postal_code(
        candidates,
        extract_german_postal_code(query),
    ):
        key = (candidate.display_label, candidate.coordinates)
        if key not in seen:
            deduped.append(candidate)
            seen.add(key)
    return deduped


@st.cache_data(ttl=300, show_spinner=False)
def get_ors_address_suggestions(query, api_key):
    """Backward-compatible string labels; new UI code uses get_location_candidates."""
    return [candidate.display_label for candidate in get_location_candidates(query, api_key)]


def resolve_location_candidate(location, api_key):
    """Resolve manual input once; preserve already selected coordinates unchanged."""
    if isinstance(location, LocationCandidate) and location.has_coordinates:
        return location
    query = _location_query(location)
    if not query:
        raise LocationResolutionError("Bitte eine Adresse oder einen Ort eingeben.")
    local_candidates = get_de_postal_code_candidates(query)
    if local_candidates is not None:
        return local_candidates[0]
    candidates = geocode_candidates_with_ors(query, api_key)
    if not candidates:
        raise LocationResolutionError(f"Adresse nicht gefunden: {query}")
    return _validated_manual_routing_candidates(query, candidates)[0]


def _validated_manual_routing_candidates(query, candidates):
    query_postal_code = extract_german_postal_code(query)
    if not query_postal_code:
        return candidates
    matching_candidates = [
        candidate for candidate in candidates if candidate.match_type == "postal_match"
    ]
    if matching_candidates:
        return matching_candidates
    warning = candidates[0].warning if candidates else ""
    raise LocationResolutionError(
        warning
        or (
            f"ORS konnte die eingegebene PLZ {query_postal_code} nicht bestätigen. "
            "Bitte vollständige Adresse prüfen."
        )
    )


def _routing_candidates(location, api_key, size=ORS_GEOCODE_CANDIDATE_LIMIT):
    if isinstance(location, LocationCandidate) and location.has_coordinates:
        return [location]
    query = _location_query(location)
    local_candidates = get_de_postal_code_candidates(query)
    if local_candidates is not None:
        return local_candidates
    candidates = geocode_candidates_with_ors(query, api_key, size=size)
    return _validated_manual_routing_candidates(query, candidates)


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
    start_candidates = _routing_candidates(start_address, api_key)
    target_candidates = _routing_candidates(target_address, api_key)
    last_error = None

    for attempt in _build_routing_attempts(start_candidates, target_candidates):
        try:
            return _fetch_ors_route_summary(
                list(attempt["start"].coordinates),
                list(attempt["target"].coordinates),
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
    start = _location_label(start_address)
    target = _location_label(target_address)
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
