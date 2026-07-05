from urllib.parse import parse_qs, urlparse

import ors_helpers
from ors_helpers import (
    ORS_FALLBACK_USER_MESSAGE,
    ORSError,
    _build_geocode_params,
    _extract_german_postal_code,
    _format_address_suggestion,
    _reverse_lookup_postal_code,
    _to_iso2_country_code,
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
    assert _format_address_suggestion(german_props) == "Helmholtzstraße 63, 50825 Köln, DE"

    german_city_props = {
        "name": "Freudenberg",
        "postalcode": "57258",
        "locality": "Freudenberg",
        "country": "Germany",
        "country_a": "DE",
    }
    assert _format_address_suggestion(german_city_props) == "57258 Freudenberg, DE"

    german_city_without_postcode = {
        "name": "Freudenberg",
        "locality": "Freudenberg",
        "country": "Germany",
        "country_a": "DE",
    }
    assert _format_address_suggestion(german_city_without_postcode) == "Freudenberg, DE"
    assert _format_address_suggestion(
        german_city_without_postcode,
        fallback_postal_code="57258",
    ) == "57258 Freudenberg, DE"
    assert _extract_german_postal_code("57072 Siegen") == "57072"
    assert _extract_german_postal_code("Siegen") == ""

    foreign_props = {
        "street": "Bahnhofstrasse",
        "housenumber": "1",
        "postalcode": "8001",
        "locality": "Zürich",
        "country": "Switzerland",
        "country_a": "CH",
    }
    assert _format_address_suggestion(foreign_props) == "Bahnhofstrasse 1, 8001 Zürich, CH"
    assert _format_address_suggestion(
        foreign_props,
        fallback_postal_code="57072",
    ) == "Bahnhofstrasse 1, 8001 Zürich, CH"

    german_three_letter_code = {
        "name": "Siegen",
        "locality": "Siegen",
        "country": "Germany",
        "country_a": "DEU",
    }
    assert _format_address_suggestion(
        german_three_letter_code,
        fallback_postal_code="57072",
    ) == "57072 Siegen, DE"
    assert _to_iso2_country_code("DEU") == "DE"
    assert _to_iso2_country_code("AUT") == "AT"
    assert _to_iso2_country_code("AUS") == "AU"
    assert _to_iso2_country_code("USA") == "US"
    assert _to_iso2_country_code("CH") == "CH"

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

    def fake_suggestion_get(url, params, timeout):
        return DummyResponse(
            True,
            {
                "features": [
                    {
                        "properties": {
                            "name": "Siegen",
                            "locality": "Siegen",
                            "country": "Germany",
                            "country_a": "DEU",
                        }
                    },
                    {
                        "properties": {
                            "name": "Siegen",
                            "locality": "Siegen",
                            "country": "United States",
                            "country_a": "USA",
                        }
                    },
                    {
                        "properties": {
                            "name": "Freudenberg",
                            "postalcode": "57258",
                            "locality": "Freudenberg",
                            "country": "Germany",
                            "country_a": "DEU",
                        }
                    },
                ]
            },
        )

    try:
        ors_helpers.requests.get = fake_suggestion_get
        ors_helpers.get_ors_address_suggestions.clear()
        suggestions = ors_helpers.get_ors_address_suggestions("57072 Siegen", "demo-key")
    finally:
        ors_helpers.requests.get = original_get
        ors_helpers.get_ors_address_suggestions.clear()

    assert suggestions == [
        "57072 Siegen, DE",
        "Siegen, US",
        "57258 Freudenberg, DE",
    ]

    def fake_reverse_get(url, params, timeout):
        assert url == ors_helpers.ORS_REVERSE_GEOCODE_URL
        assert params["layers"] == "address"
        return DummyResponse(
            True,
            {
                "features": [
                    {
                        "properties": {
                            "postalcode": "56179",
                            "country_a": "DEU",
                        }
                    }
                ]
            },
        )

    try:
        ors_helpers.requests.get = fake_reverse_get
        _reverse_lookup_postal_code.clear()
        assert _reverse_lookup_postal_code(7.60713, 50.394447, "demo-key", "DEU") == "56179"
    finally:
        ors_helpers.requests.get = original_get
        _reverse_lookup_postal_code.clear()

    enrichment_calls = []

    def fake_enriched_suggestion_get(url, params, timeout):
        enrichment_calls.append(url)
        if url == ors_helpers.ORS_GEOCODE_URL:
            return DummyResponse(
                True,
                {
                    "features": [
                        {
                            "geometry": {"coordinates": [7.60713, 50.394447]},
                            "properties": {
                                "name": "Niederwerth",
                                "locality": "Niederwerth",
                                "country": "Deutschland",
                                "country_a": "DEU",
                            },
                        }
                    ]
                },
            )
        return DummyResponse(
            True,
            {
                "features": [
                    {
                        "properties": {
                            "postalcode": "56179",
                            "country_a": "DEU",
                        }
                    }
                ]
            },
        )

    try:
        ors_helpers.requests.get = fake_enriched_suggestion_get
        ors_helpers.get_ors_address_suggestions.clear()
        _reverse_lookup_postal_code.clear()
        assert ors_helpers.get_ors_address_suggestions("Niederwerth", "demo-key") == [
            "56179 Niederwerth, DE"
        ]
    finally:
        ors_helpers.requests.get = original_get
        ors_helpers.get_ors_address_suggestions.clear()
        _reverse_lookup_postal_code.clear()

    assert enrichment_calls == [
        ors_helpers.ORS_GEOCODE_URL,
        ors_helpers.ORS_REVERSE_GEOCODE_URL,
    ]

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
