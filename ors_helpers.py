import streamlit as st
import requests
from config import ORS_GEOCODE_URL, ORS_DIRECTIONS_URL_TEMPLATE


def _raise_ors_error(response):
    """Build a readable ORS error with HTTP status and payload."""
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    raise ValueError(f"ORS HTTP {response.status_code}: {payload}")


def geocode_with_ors(address, api_key):
    """Liefert [lon, lat] für eine Adresse via ORS Geocoder."""
    response = requests.get(
        ORS_GEOCODE_URL,
        params={"api_key": api_key, "text": address, "size": 1},
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Adresse nicht gefunden: {address}")
    return features[0]["geometry"]["coordinates"]


@st.cache_data(ttl=300, show_spinner=False)
def get_ors_address_suggestions(query, api_key):
    """Liefert bis zu 5 Adressvorschläge für Autocomplete."""
    if not query or len(query.strip()) < 3:
        return []
    response = requests.get(
        ORS_GEOCODE_URL,
        params={"api_key": api_key, "text": query.strip(), "size": 5},
        timeout=20,
    )
    if not response.ok:
        _raise_ors_error(response)
    data = response.json()
    features = data.get("features", [])
    suggestions = []
    for feature in features:
        props = feature.get("properties", {})
        label = props.get("label")
        if label:
            suggestions.append(label)
    # Reihenfolge behalten, Duplikate entfernen
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


