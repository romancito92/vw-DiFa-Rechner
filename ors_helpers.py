import requests
import streamlit as st

from config import ORS_DIRECTIONS_URL_TEMPLATE, ORS_GEOCODE_URL


ORS_GEOCODE_LANGUAGE = "de"

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


def _raise_ors_error(response):
    """Build a readable ORS error with HTTP status and payload."""
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    raise ValueError(f"ORS HTTP {response.status_code}: {payload}")


def _build_geocode_params(search_text, api_key, size):
    return {
        "api_key": api_key,
        "text": search_text,
        "size": size,
        "lang": ORS_GEOCODE_LANGUAGE,
    }


def geocode_with_ors(address, api_key):
    """Liefert [lon, lat] für eine Adresse via ORS Geocoder."""
    response = requests.get(
        ORS_GEOCODE_URL,
        params=_build_geocode_params(address, api_key, 1),
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Adresse nicht gefunden: {address}")
    return features[0]["geometry"]["coordinates"]


def _join_non_empty(parts, separator=", "):
    return separator.join(str(part).strip() for part in parts if str(part).strip())


def _translate_locality_name(locality, country_code):
    cleaned_locality = (locality or "").strip()
    if not cleaned_locality:
        return ""
    if country_code == "DE":
        return GERMAN_CITY_TRANSLATIONS.get(cleaned_locality, cleaned_locality)
    return cleaned_locality


def _translate_country_name(country, country_code):
    cleaned_country = (country or "").strip()
    if not cleaned_country:
        return ""
    if country_code == "DE":
        return "Deutschland"
    return COUNTRY_TRANSLATIONS.get(cleaned_country, cleaned_country)


def _format_address_suggestion(props):
    street = props.get("street") or props.get("name") or ""
    house_number = props.get("housenumber") or ""
    postal_code = props.get("postalcode") or ""
    country_code = (props.get("country_a") or "").upper()
    locality = (
        props.get("locality")
        or props.get("borough")
        or props.get("municipality")
        or props.get("county")
        or ""
    )
    locality = _translate_locality_name(locality, country_code)
    country = _translate_country_name(props.get("country"), country_code)

    street_line = _join_non_empty([street, house_number], separator=" ")
    city_line = _join_non_empty([postal_code, locality], separator=" ")

    if country_code == "DE":
        return _join_non_empty([street_line, city_line])

    return _join_non_empty([street_line, city_line, country])


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
    for feature in features:
        props = feature.get("properties", {})
        label = _format_address_suggestion(props) or props.get("label")
        if label:
            suggestions.append(label)
    seen = set()
    deduped = []
    for item in suggestions:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def get_ors_distance_and_duration(start_address, target_address, api_key, profile):
    """Berechnet Distanz (km) und Dauer (Minuten) via ORS Directions."""
    start_coords = geocode_with_ors(start_address, api_key)
    target_coords = geocode_with_ors(target_address, api_key)

    response = requests.post(
        ORS_DIRECTIONS_URL_TEMPLATE.format(profile=profile),
        json={"coordinates": [start_coords, target_coords]},
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
