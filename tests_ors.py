from urllib.parse import parse_qs, urlparse

import ors_helpers
from ors_helpers import (
    ORS_FALLBACK_USER_MESSAGE,
    ORSError,
    _build_geocode_params,
    _format_address_suggestion,
    build_google_maps_directions_url,
    build_ors_failure_feedback,
)


class DummyResponse:
    def __init__(self, ok, payload, status_code=200):
        self.ok = ok
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


def run_tests():
    params = _build_geocode_params("Helmholtzstraße 63 Köln", "demo-key", 5)
    assert params["lang"] == "de"
    assert params["size"] == 5

    german_props = {
        "street": "Helmholtzstraße",
        "housenumber": "63",
        "postalcode": "50825",
        "locality": "Cologne",
        "country": "Germany",
        "country_a": "DE",
    }
    assert _format_address_suggestion(german_props) == "Helmholtzstraße 63, 50825 Köln, Deutschland"

    german_city_props = {
        "name": "Freudenberg",
        "postalcode": "57258",
        "locality": "Freudenberg",
        "country": "Germany",
        "country_a": "DE",
    }
    assert _format_address_suggestion(german_city_props) == "57258 Freudenberg, Deutschland"

    german_city_without_postcode = {
        "name": "Freudenberg",
        "locality": "Freudenberg",
        "country": "Germany",
        "country_a": "DE",
    }
    assert _format_address_suggestion(german_city_without_postcode) == "Freudenberg, Deutschland"

    foreign_props = {
        "street": "Bahnhofstrasse",
        "housenumber": "1",
        "postalcode": "8001",
        "locality": "Zürich",
        "country": "Switzerland",
        "country_a": "CH",
    }
    assert _format_address_suggestion(foreign_props) == "Bahnhofstrasse 1, 8001 Zürich, Schweiz"

    maps_url = build_google_maps_directions_url(
        "Heeserstraße 5, 57072 Siegen",
        "Niederkassel, Deutschland",
    )
    parsed = urlparse(maps_url)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "www.google.com"
    assert parsed.path == "/maps/dir/"
    assert params["api"] == ["1"]
    assert params["origin"] == ["Heeserstraße 5, 57072 Siegen"]
    assert params["destination"] == ["Niederkassel, Deutschland"]
    assert params["travelmode"] == ["driving"]
    assert build_google_maps_directions_url("", "Niederkassel") is None
    assert build_google_maps_directions_url("Freudenberg", "") is None

    ors_error = ORSError(
        404,
        {
            "error": {
                "code": 2010,
                "message": "Could not find routable point within a radius of 350.0 meters",
            }
        },
    )
    feedback = build_ors_failure_feedback(
        ors_error,
        "Freudenberg, Deutschland",
        "Niederkassel, Deutschland",
    )
    assert feedback["message"] == ORS_FALLBACK_USER_MESSAGE
    assert feedback["maps_url"]
    assert "ORS HTTP 404" in feedback["details"]
    assert "2010" in feedback["details"]

    sanitized_feedback = build_ors_failure_feedback(
        "Connection failed: https://api.openrouteservice.org/geocode/search?api_key=secret-token&text=Freudenberg"
    )
    assert "secret-token" not in sanitized_feedback["details"]
    assert "api_key=<redacted>" in sanitized_feedback["details"]

    original_get = ors_helpers.requests.get
    original_post = ors_helpers.requests.post
    post_payloads = []

    def fake_get(url, params, timeout):
        return DummyResponse(
            True,
            {
                "features": [
                    {
                        "geometry": {"coordinates": [7.0, 50.0]},
                        "properties": {
                            "name": params["text"],
                            "locality": params["text"],
                            "country": "Germany",
                            "country_a": "DE",
                        },
                    }
                ]
            },
        )

    def fake_post(url, json, headers, timeout):
        post_payloads.append(json)
        if len(post_payloads) == 1:
            return DummyResponse(
                False,
                {
                    "error": {
                        "code": 2010,
                        "message": "Could not find routable point within a radius of 350.0 meters",
                    }
                },
                status_code=404,
            )
        return DummyResponse(
            True,
            {"routes": [{"summary": {"distance": 1234, "duration": 600}}]},
        )

    try:
        ors_helpers.requests.get = fake_get
        ors_helpers.requests.post = fake_post
        distance_km, duration_minutes = ors_helpers.get_ors_distance_and_duration_robust(
            "Freudenberg",
            "Niederkassel",
            "demo-key",
            "driving-car",
        )
    finally:
        ors_helpers.requests.get = original_get
        ors_helpers.requests.post = original_post

    assert distance_km == 1.234
    assert duration_minutes == 10
    assert "radiuses" not in post_payloads[0]
    assert post_payloads[1]["radiuses"] == [
        ors_helpers.ORS_RETRY_SNAP_RADIUS_METERS,
        ors_helpers.ORS_RETRY_SNAP_RADIUS_METERS,
    ]

    print("OK: ORS-Vorschläge, Maps-Fallback und Fehlerfeedback funktionieren.")


if __name__ == "__main__":
    run_tests()
