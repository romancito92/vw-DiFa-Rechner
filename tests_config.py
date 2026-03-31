import os

import config


class DummySecrets(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def run_tests():
    original_secrets = config.st.secrets
    original_env = os.environ.copy()

    try:
        config.st.secrets = DummySecrets(
            {
                "ORS_API_KEY": "root-ors",
                "TANKERKOENIG_API_KEY": "root-tanker",
                "openrouteservice": {"api_key": "section-ors"},
                "tankerkoenig": {"api_key": "section-tanker"},
            }
        )

        os.environ.pop("ORS_API_KEY", None)
        os.environ.pop("TANKERKOENIG_API_KEY", None)

        ors = config.get_ors_api_key()
        tanker = config.get_tankerkoenig_api_key()
        assert ors.value == "root-ors"
        assert ors.source == "st.secrets[ORS_API_KEY]"
        assert tanker.value == "root-tanker"
        assert tanker.source == "st.secrets[TANKERKOENIG_API_KEY]"

        config.st.secrets = DummySecrets(
            {
                "openrouteservice": {"api_key": "section-ors"},
                "tankerkoenig": {"api_key": "section-tanker"},
            }
        )
        ors = config.get_ors_api_key()
        tanker = config.get_tankerkoenig_api_key()
        assert ors.value == "section-ors"
        assert "openrouteservice.api_key" in ors.source
        assert tanker.value == "section-tanker"
        assert "tankerkoenig.api_key" in tanker.source

        config.st.secrets = DummySecrets({})
        os.environ["ORS_API_KEY"] = "env-ors"
        os.environ["TANKERKOENIG_API_KEY"] = "env-tanker"
        ors = config.get_ors_api_key()
        tanker = config.get_tankerkoenig_api_key()
        assert ors.value == "env-ors"
        assert ors.source == "env[ORS_API_KEY]"
        assert tanker.value == "env-tanker"
        assert tanker.source == "env[TANKERKOENIG_API_KEY]"

        config.st.secrets = DummySecrets({})
        os.environ.pop("ORS_API_KEY", None)
        os.environ.pop("TANKERKOENIG_API_KEY", None)
        ors = config.get_ors_api_key()
        tanker = config.get_tankerkoenig_api_key()
        assert ors.value == ""
        assert ors.source == "missing"
        assert tanker.source == "demo key"

        print("OK: Secret-Zugriff priorisiert Streamlit-Secrets korrekt.")
    finally:
        config.st.secrets = original_secrets
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    run_tests()
