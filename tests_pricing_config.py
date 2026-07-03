import base64
import json
import os
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pricing_config as pricing
from logic_direct import build_case_a_preview, calculate_case_a


class DummySecrets(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def default_config():
    return {
        "version": 1,
        "modes": {
            "A": {
                "label": "Selber fahren",
                "vehicles": {
                    "transporter": {
                        "label": "Transporter",
                        "base_price_eur": 29.0,
                        "km_price_eur": 1.3,
                    },
                    "transporter_liftgate": {
                        "label": "Transporter mit Hebebühne",
                        "base_price_eur": 39.0,
                        "km_price_eur": 1.45,
                    },
                },
            }
        },
        "audit": {
            "updated_at": None,
            "updated_by": None,
            "change_comment": None,
        },
    }


def assert_raises(expected_exception, function, *args):
    try:
        function(*args)
    except expected_exception as exc:
        return exc
    raise AssertionError(f"{expected_exception.__name__} wurde nicht ausgelöst")


def run_tests():
    config = default_config()
    pricing.validate_pricing_config(config)

    # Defaultwerte liefern exakt die bisherigen Ergebnisse.
    standard = calculate_case_a(92, 72, 0.0, False, config)
    liftgate = calculate_case_a(92, 72, 0.0, True, config)
    assert round(standard[4], 2) == 148.60
    assert round(liftgate[4], 2) == 172.40

    # Eine explizit ungültige Config darf nicht durch die Datei ersetzt werden.
    assert_raises(pricing.PricingConfigError, calculate_case_a, 92, 72, 0.0, False, {})

    # Die Admin-Vorschau verwendet dieselbe Berechnung und Rundung wie Modus A.
    standard_preview = build_case_a_preview(config, liftgate_required=False)
    liftgate_preview = build_case_a_preview(config, liftgate_required=True)
    assert round(standard_preview["price_a1_raw"], 2) == 148.60
    assert standard_preview["price_a1_rounded"] == 147
    assert standard_preview["price_a2_rounded"] == 173
    assert standard_preview["lower_rounded"] == 147
    assert standard_preview["mid_rounded"] == 161
    assert standard_preview["upper_rounded"] == 173
    assert round(liftgate_preview["price_a1_raw"], 2) == 172.40
    assert liftgate_preview["price_a1_rounded"] == 171

    # Geänderte Werte werden verwendet, ohne die Formel zu verändern.
    changed = deepcopy(config)
    changed["modes"]["A"]["vehicles"]["transporter"]["base_price_eur"] = 31.5
    changed["modes"]["A"]["vehicles"]["transporter"]["km_price_eur"] = 1.42
    changed_result = calculate_case_a(92, 72, 0.0, False, changed)
    assert round(changed_result[4], 2) == round(31.5 + 1.42 * 92, 2)

    # Negative und nichtnumerische Preise werden abgewiesen.
    negative = deepcopy(config)
    negative["modes"]["A"]["vehicles"]["transporter"]["base_price_eur"] = -0.01
    assert_raises(pricing.PricingConfigError, pricing.validate_pricing_config, negative)
    non_numeric = deepcopy(config)
    non_numeric["modes"]["A"]["vehicles"]["transporter"]["km_price_eur"] = "1.30"
    assert_raises(pricing.PricingConfigError, pricing.validate_pricing_config, non_numeric)

    original_path = pricing.PRICING_CONFIG_PATH
    original_role_check = pricing.get_role_for_email
    original_secrets = pricing.st.secrets
    original_env = os.environ.copy()
    original_get = pricing.requests.get
    original_put = pricing.requests.put
    try:
        pricing.st.secrets = DummySecrets({})
        for env_name in (
            "PRICING_CONFIG_BACKEND",
            "GITHUB_TOKEN",
            "GITHUB_REPO",
            "GITHUB_BRANCH",
            "GITHUB_PRICING_CONFIG_PATH",
        ):
            os.environ.pop(env_name, None)

        # Ohne Konfiguration ist das lokale Backend aktiv; die Env-Variable kann umschalten.
        assert pricing.get_pricing_config_backend() == "local"
        os.environ["PRICING_CONFIG_BACKEND"] = "github"
        assert pricing.get_pricing_config_backend() == "github"
        os.environ["PRICING_CONFIG_BACKEND"] = "local"

        with TemporaryDirectory() as temporary_directory:
            pricing.PRICING_CONFIG_PATH = Path(temporary_directory).joinpath("pricing_config.json")
            pricing.get_role_for_email = lambda email: "admin" if email == "admin@example.com" else "user"

            # Nicht-Admins können selbst bei direktem Funktionsaufruf nicht speichern.
            assert_raises(
                PermissionError,
                pricing.save_pricing_config,
                config,
                "user@example.com",
                "nicht erlaubt",
            )

            # Admin-Speichern setzt Auditdaten; ein Reload liest dieselben Preise.
            saved = pricing.save_pricing_config(config, "ADMIN@example.com", "Teständerung")
            reloaded = pricing.load_pricing_config()
            assert reloaded == saved
            assert reloaded["audit"]["updated_by"] == "admin@example.com"
            assert reloaded["audit"]["updated_at"]
            assert reloaded["audit"]["change_comment"] == "Teständerung"

            # pricing_config=None lädt weiterhin regulär aus dem gewählten Backend.
            loaded_result = calculate_case_a(92, 72, 0.0, False, None)
            assert round(loaded_result[4], 2) == 148.60

        # Fehlende GitHub-Zugangsdaten werden vor jedem HTTP-Aufruf klar gemeldet.
        os.environ["PRICING_CONFIG_BACKEND"] = "github"
        missing_error = assert_raises(
            pricing.PricingConfigError,
            pricing.load_pricing_config,
        )
        assert "GITHUB_TOKEN" in str(missing_error)
        assert "GITHUB_REPO" in str(missing_error)

        # GitHub Contents API wird vollständig gemockt; es findet kein Netzwerkzugriff statt.
        pricing.st.secrets = DummySecrets(
            {
                "pricing_config_backend": "github",
                "github_pricing_config": {
                    "token": "test-token",
                    "repo": "owner/repo",
                    "branch": "main",
                    "path": "config/pricing_config.json",
                },
            }
        )
        encoded_config = base64.b64encode(
            (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        ).decode("ascii")
        calls = {"get": 0, "put": 0}

        def fake_get(url, headers, params, timeout):
            calls["get"] += 1
            assert url.endswith("/repos/owner/repo/contents/config/pricing_config.json")
            assert headers["Authorization"] == "Bearer test-token"
            assert params == {"ref": "main"}
            return DummyResponse(
                200,
                {"encoding": "base64", "content": encoded_config, "sha": "sha-before"},
            )

        def fake_put(url, headers, json, timeout):
            calls["put"] += 1
            assert json["sha"] == "sha-before"
            assert json["branch"] == "main"
            assert json["message"] == "Update pricing config by admin@example.com"
            uploaded = __import__("json").loads(
                base64.b64decode(json["content"]).decode("utf-8")
            )
            assert uploaded["audit"]["updated_by"] == "admin@example.com"
            return DummyResponse(200, {"content": {"sha": "sha-after"}})

        pricing.requests.get = fake_get
        pricing.requests.put = fake_put
        pricing._github_config_sha = None
        pricing._github_config_location = None
        github_loaded = pricing.load_pricing_config()
        assert github_loaded == config
        pricing.save_pricing_config(github_loaded, "admin@example.com", "GitHub-Test")
        assert calls == {"get": 1, "put": 1}
        assert pricing._github_config_sha == "sha-after"

        # Ein SHA/API-Konflikt wird als verständlicher Konfigurationsfehler gemeldet.
        pricing.requests.put = lambda *args, **kwargs: DummyResponse(
            409, {"message": "sha does not match"}
        )
        conflict_error = assert_raises(
            pricing.PricingConfigError,
            pricing.save_pricing_config,
            github_loaded,
            "admin@example.com",
            "Konflikttest",
        )
        assert "Konflikt" in str(conflict_error)
    finally:
        pricing.PRICING_CONFIG_PATH = original_path
        pricing.get_role_for_email = original_role_check
        pricing.st.secrets = original_secrets
        pricing.requests.get = original_get
        pricing.requests.put = original_put
        pricing._github_config_sha = None
        pricing._github_config_location = None
        os.environ.clear()
        os.environ.update(original_env)

    print("OK: Preiskonfiguration, Persistenz und Admin-Schutz funktionieren.")


if __name__ == "__main__":
    run_tests()
