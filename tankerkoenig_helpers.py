import requests

from config import TANKERKOENIG_LIST_URL


def _raise_tankerkoenig_error(response):
    """Build a readable Tankerkönig error with HTTP status and payload."""
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    raise ValueError(f"Tankerkönig HTTP {response.status_code}: {payload}")


def _extract_diesel_price(station):
    """Use `price` for diesel list queries, with fallback to `diesel`."""
    for key in ("price", "diesel"):
        value = station.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def format_station_address(station):
    street = (station.get("street") or "").strip()
    house_number = (station.get("houseNumber") or "").strip()
    postcode = station.get("postCode")
    place = (station.get("place") or "").strip()

    street_line = " ".join(part for part in (street, house_number) if part).strip()
    place_line = " ".join(part for part in (str(postcode) if postcode else "", place) if part).strip()
    return ", ".join(part for part in (street_line, place_line) if part)


def build_diesel_price_average(stations):
    """Build a simple average diesel price, preferring open stations."""
    priced_stations = [station for station in stations if _extract_diesel_price(station) is not None]
    if not priced_stations:
        raise ValueError("Keine Dieselpreise im Suchradius gefunden.")

    open_stations = [station for station in priced_stations if station.get("isOpen") is True]
    pool = open_stations if open_stations else priced_stations
    prices = [_extract_diesel_price(station) for station in pool]
    average_price = sum(prices) / len(prices)
    return {
        "price": average_price,
        "station_count": len(pool),
        "open_station_count": len(open_stations),
        "total_station_count": len(priced_stations),
    }


def get_nearby_diesel_price(api_key, lat, lng, radius_km):
    """Fetch a simple average nearby diesel price around the given coordinates."""
    response = requests.get(
        TANKERKOENIG_LIST_URL,
        params={
            "lat": lat,
            "lng": lng,
            "rad": radius_km,
            "sort": "price",
            "type": "diesel",
            "apikey": api_key,
        },
        timeout=20,
    )
    if not response.ok:
        _raise_tankerkoenig_error(response)

    data = response.json()
    if not data.get("ok"):
        raise ValueError(f"Tankerkönig-Fehler: {data.get('message', 'Unbekannter Fehler')}")

    stations = data.get("stations") or []
    if not stations:
        raise ValueError("Keine Tankstellen im Suchradius gefunden.")

    summary = build_diesel_price_average(stations)
    summary["radius_km"] = float(radius_km)
    return summary
