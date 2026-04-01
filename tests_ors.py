from ors_helpers import (
    _build_geocode_params,
    _format_address_suggestion,
)


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
    assert _format_address_suggestion(german_props) == "Helmholtzstraße 63, 50825 Köln"

    foreign_props = {
        "street": "Bahnhofstrasse",
        "housenumber": "1",
        "postalcode": "8001",
        "locality": "Zürich",
        "country": "Switzerland",
        "country_a": "CH",
    }
    assert _format_address_suggestion(foreign_props) == "Bahnhofstrasse 1, 8001 Zürich, Schweiz"

    print("OK: ORS-Vorschläge werden deutsch und mit PLZ formatiert.")


if __name__ == "__main__":
    run_tests()
