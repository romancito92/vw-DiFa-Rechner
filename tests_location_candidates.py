from pathlib import Path

import ors_helpers
from location_candidates import (
    LocationCandidate,
    LocationResolutionError,
    extract_german_postal_code,
    get_de_postal_code_candidates,
    has_concrete_street_address,
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
    assert extract_german_postal_code("50825 Köln") == "50825"
    assert extract_german_postal_code("51105 Köln") == "51105"
    assert extract_german_postal_code("Köln") == ""
    assert has_concrete_street_address("Helmholtzstraße 63, 50825 Köln")
    assert not has_concrete_street_address("50825 Köln")

    west_candidates = get_de_postal_code_candidates("50825 Köln")
    east_candidates = get_de_postal_code_candidates("51105 Köln")
    assert west_candidates[0].display_label == "50825 Köln, DE"
    assert east_candidates[0].display_label == "51105 Köln, DE"
    assert west_candidates[0].coordinates != east_candidates[0].coordinates
    assert west_candidates[0].source == "de_postal_code_centroid"
    assert get_de_postal_code_candidates("50825 Koeln")[0].display_label == "50825 Köln, DE"
    assert get_de_postal_code_candidates("50825 Cologne")[0].display_label == "50825 Köln, DE"
    assert get_de_postal_code_candidates("Helmholtzstraße 63, 50825 Köln") is None

    try:
        get_de_postal_code_candidates("00000 Testort")
        raise AssertionError("Unknown postal code must fail clearly")
    except LocationResolutionError as exc:
        assert "PLZ nicht in lokaler Tabelle gefunden" in str(exc)

    selected = west_candidates[0]
    restored = LocationCandidate.from_dict(selected.to_dict())
    assert restored.postal_code == "50825"
    assert restored.coordinates == selected.coordinates
    assert restored.source == "de_postal_code_centroid"

    original_get = ors_helpers.requests.get
    original_post = ors_helpers.requests.post
    post_payloads = []

    def forbidden_get(*args, **kwargs):
        raise AssertionError("Selected candidates must not be geocoded again")

    def fake_post(url, json, headers, timeout):
        post_payloads.append(json)
        return DummyResponse(
            True,
            {"routes": [{"summary": {"distance": 99000, "duration": 5400}}]},
        )

    try:
        ors_helpers.requests.get = forbidden_get
        ors_helpers.requests.post = fake_post
        distance_km, duration_minutes = ors_helpers.get_ors_distance_and_duration_robust(
            west_candidates[0],
            east_candidates[0],
            "demo-key",
            "driving-car",
        )
    finally:
        ors_helpers.requests.get = original_get
        ors_helpers.requests.post = original_post

    assert distance_km == 99
    assert duration_minutes == 90
    assert post_payloads[0]["coordinates"] == [
        list(west_candidates[0].coordinates),
        list(east_candidates[0].coordinates),
    ]

    mismatch = ors_helpers._build_ors_candidate(
        "Helmholtzstraße 63, 51105 Köln",
        {
            "street": "Helmholtzstraße",
            "housenumber": "63",
            "postalcode": "50825",
            "locality": "Köln",
            "country_a": "DEU",
        },
        [6.903554, 50.955132],
    )
    assert mismatch.display_label == "Helmholtzstraße 63, 50825 Köln, DE"
    assert mismatch.match_type == "postal_mismatch"
    assert "51105" in mismatch.warning and "50825" in mismatch.warning
    try:
        ors_helpers._validated_manual_routing_candidates(
            "Helmholtzstraße 63, 51105 Köln",
            [mismatch],
        )
        raise AssertionError("Manual routing must reject an ORS postal mismatch")
    except LocationResolutionError as exc:
        assert "stimmt nicht" in str(exc)

    app_source = Path("direktfahrt_rechner.py").read_text(encoding="utf-8")
    assert app_source.count("address_input_with_autofill(") == 5
    assert "get_ors_distance_and_duration(" not in app_source
    assert app_source.count("get_ors_distance_and_duration_robust(") >= 3

    print("OK: Lokale PLZ-Kandidaten, Auswahlpersistenz und koordinatenbasiertes Routing funktionieren.")


if __name__ == "__main__":
    run_tests()
