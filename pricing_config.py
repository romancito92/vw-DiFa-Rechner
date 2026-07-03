"""Load, validate, and persist the centrally managed pricing configuration."""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st

from auth_helpers import get_role_for_email


PRICING_CONFIG_PATH = Path(__file__).with_name("config").joinpath("pricing_config.json")
MODE_A_VEHICLES = ("transporter", "transporter_liftgate")
PRICE_FIELDS = ("base_price_eur", "km_price_eur")
GITHUB_API_ROOT = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT_SECONDS = 15

_github_config_sha = None
_github_config_location = None


class PricingConfigError(ValueError):
    """Raised when the pricing configuration is missing or invalid."""


def _require_mapping(value, path):
    if not isinstance(value, dict):
        raise PricingConfigError(f"'{path}' muss ein Objekt sein.")
    return value


def validate_pricing_config(config):
    """Validate required Mode A fields and return the config unchanged."""
    root = _require_mapping(config, "config")
    if "version" not in root:
        raise PricingConfigError("Pflichtfeld 'version' fehlt.")
    if not isinstance(root["version"], int) or isinstance(root["version"], bool):
        raise PricingConfigError("'version' muss eine ganze Zahl sein.")

    modes = _require_mapping(root.get("modes"), "modes")
    mode_a = _require_mapping(modes.get("A"), "modes.A")
    if not isinstance(mode_a.get("label"), str) or not mode_a["label"].strip():
        raise PricingConfigError("Pflichtfeld 'modes.A.label' fehlt oder ist leer.")
    vehicles = _require_mapping(mode_a.get("vehicles"), "modes.A.vehicles")

    for vehicle_key in MODE_A_VEHICLES:
        path = f"modes.A.vehicles.{vehicle_key}"
        vehicle = _require_mapping(vehicles.get(vehicle_key), path)
        if not isinstance(vehicle.get("label"), str) or not vehicle["label"].strip():
            raise PricingConfigError(f"Pflichtfeld '{path}.label' fehlt oder ist leer.")
        for price_field in PRICE_FIELDS:
            price_path = f"{path}.{price_field}"
            value = vehicle.get(price_field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PricingConfigError(f"'{price_path}' muss numerisch sein.")
            if not math.isfinite(float(value)):
                raise PricingConfigError(f"'{price_path}' muss eine endliche Zahl sein.")
            if value < 0:
                raise PricingConfigError(f"'{price_path}' darf nicht negativ sein.")

    audit = _require_mapping(root.get("audit"), "audit")
    for audit_field in ("updated_at", "updated_by", "change_comment"):
        if audit_field not in audit:
            raise PricingConfigError(f"Pflichtfeld 'audit.{audit_field}' fehlt.")
        if audit[audit_field] is not None and not isinstance(audit[audit_field], str):
            raise PricingConfigError(f"'audit.{audit_field}' muss Text oder null sein.")

    return config


def _read_secret(path, default=None):
    try:
        node = st.secrets
        for key in path:
            if hasattr(node, "get"):
                node = node.get(key)
            else:
                node = node[key]
            if node is None:
                return default
        return node
    except Exception:
        return default


def get_pricing_config_backend():
    """Resolve the configured persistence backend with secrets taking precedence."""
    secret_backend = str(_read_secret(("pricing_config_backend",), "") or "").strip()
    env_backend = str(os.getenv("PRICING_CONFIG_BACKEND", "") or "").strip()
    backend = (secret_backend or env_backend or "local").lower()
    if backend not in ("local", "github"):
        raise PricingConfigError(
            "Ungültiges Preisconfig-Backend. Erlaubt sind 'local' und 'github'."
        )
    return backend


def _get_github_setting(secret_name, section_name, env_name, default=""):
    root_value = _read_secret((secret_name,), None)
    if root_value is not None and str(root_value).strip():
        return str(root_value).strip()

    section_value = _read_secret(("github_pricing_config", section_name), None)
    if section_value is None:
        section_value = _read_secret(("github_pricing_config", secret_name), None)
    if section_value is not None and str(section_value).strip():
        return str(section_value).strip()

    env_value = os.getenv(env_name, "")
    if env_value and env_value.strip():
        return env_value.strip()
    return default


def _get_github_settings():
    settings = {
        "token": _get_github_setting("GITHUB_TOKEN", "token", "GITHUB_TOKEN"),
        "repo": _get_github_setting("GITHUB_REPO", "repo", "GITHUB_REPO"),
        "branch": _get_github_setting(
            "GITHUB_BRANCH", "branch", "GITHUB_BRANCH", default="main"
        ),
        "path": _get_github_setting(
            "GITHUB_PRICING_CONFIG_PATH",
            "path",
            "GITHUB_PRICING_CONFIG_PATH",
            default="config/pricing_config.json",
        ).lstrip("/"),
    }
    missing = [name for name in ("token", "repo") if not settings[name]]
    if missing:
        labels = {"token": "GITHUB_TOKEN", "repo": "GITHUB_REPO"}
        raise PricingConfigError(
            "GitHub-Preisconfig ist unvollständig. Es fehlen: "
            + ", ".join(labels[name] for name in missing)
            + "."
        )
    if settings["repo"].count("/") != 1 or settings["repo"].startswith("/"):
        raise PricingConfigError("GITHUB_REPO muss im Format 'owner/repo' angegeben werden.")
    if not settings["branch"] or not settings["path"]:
        raise PricingConfigError("GitHub-Branch und Preisconfig-Pfad dürfen nicht leer sein.")
    return settings


def _github_contents_url(settings):
    encoded_path = quote(settings["path"], safe="/")
    return f"{GITHUB_API_ROOT}/repos/{settings['repo']}/contents/{encoded_path}"


def _github_headers(settings):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings['token']}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_github_response_json(response, action):
    try:
        return response.json()
    except ValueError as exc:
        raise PricingConfigError(
            f"GitHub-Antwort beim {action} der Preisconfig war kein gültiges JSON."
        ) from exc


def _raise_github_api_error(response, action):
    if action == "Speichern" and response.status_code in (409, 422):
        raise PricingConfigError(
            "GitHub-Konflikt beim Speichern der Preisconfig. "
            "Bitte die Seite neu laden und die Änderung erneut prüfen."
        )
    try:
        message = response.json().get("message", "")
    except (ValueError, AttributeError):
        message = ""
    detail = f": {message}" if message else ""
    raise PricingConfigError(
        f"GitHub API-Fehler beim {action} der Preisconfig "
        f"(HTTP {response.status_code}){detail}"
    )


def _load_pricing_config_local():
    try:
        with PRICING_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise PricingConfigError(
            f"Preiskonfiguration nicht gefunden: {PRICING_CONFIG_PATH}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PricingConfigError(
            f"Preiskonfiguration enthält ungültiges JSON (Zeile {exc.lineno})."
        ) from exc
    except OSError as exc:
        raise PricingConfigError(f"Preiskonfiguration konnte nicht gelesen werden: {exc}") from exc

    return validate_pricing_config(config)


def _load_pricing_config_github():
    global _github_config_location, _github_config_sha

    settings = _get_github_settings()
    try:
        response = requests.get(
            _github_contents_url(settings),
            headers=_github_headers(settings),
            params={"ref": settings["branch"]},
            timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PricingConfigError(
            f"GitHub-Preisconfig konnte nicht geladen werden: {exc}"
        ) from exc
    if response.status_code != 200:
        _raise_github_api_error(response, "Laden")

    payload = _parse_github_response_json(response, "Laden")
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise PricingConfigError("GitHub-Preisconfig hat ein unerwartetes Dateiformat.")
    if not payload.get("sha") or not payload.get("content"):
        raise PricingConfigError("GitHub-Antwort enthält weder Dateiinhalt noch SHA.")
    try:
        decoded_content = base64.b64decode(payload["content"]).decode("utf-8")
        config = json.loads(decoded_content)
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise PricingConfigError(
            "GitHub-Preisconfig konnte nicht als Base64/UTF-8-JSON gelesen werden."
        ) from exc

    validate_pricing_config(config)
    _github_config_sha = payload["sha"]
    _github_config_location = (
        settings["repo"],
        settings["branch"],
        settings["path"],
    )
    return config


def load_pricing_config():
    """Read and validate pricing configuration from the selected backend."""
    if get_pricing_config_backend() == "github":
        return _load_pricing_config_github()
    return _load_pricing_config_local()


def _write_pricing_config_local(config):
    """Local storage adapter; replace this function for a future remote backend."""
    PRICING_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = PRICING_CONFIG_PATH.with_suffix(".json.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=2)
            config_file.write("\n")
        temporary_path.replace(PRICING_CONFIG_PATH)
    except OSError as exc:
        raise PricingConfigError(f"Preiskonfiguration konnte nicht gespeichert werden: {exc}") from exc


def _write_pricing_config_github(config, current_user_email):
    global _github_config_location, _github_config_sha

    settings = _get_github_settings()
    location = (settings["repo"], settings["branch"], settings["path"])
    if not _github_config_sha or _github_config_location != location:
        _load_pricing_config_github()

    serialized = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    request_payload = {
        "message": f"Update pricing config by {current_user_email}",
        "content": base64.b64encode(serialized.encode("utf-8")).decode("ascii"),
        "branch": settings["branch"],
        "sha": _github_config_sha,
    }
    try:
        response = requests.put(
            _github_contents_url(settings),
            headers=_github_headers(settings),
            json=request_payload,
            timeout=GITHUB_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PricingConfigError(
            f"GitHub-Preisconfig konnte nicht gespeichert werden: {exc}"
        ) from exc
    if response.status_code not in (200, 201):
        _raise_github_api_error(response, "Speichern")

    payload = _parse_github_response_json(response, "Speichern")
    saved_sha = payload.get("content", {}).get("sha") if isinstance(payload, dict) else None
    if saved_sha:
        _github_config_sha = saved_sha
        _github_config_location = location


def save_pricing_config(config, current_user_email, change_comment=None):
    """Validate and save configuration after enforcing admin authorization."""
    normalized_email = str(current_user_email or "").strip().lower()
    if get_role_for_email(normalized_email) != "admin":
        raise PermissionError("Nur Administratoren dürfen Preiseinstellungen speichern.")

    config_to_save = deepcopy(config)
    audit = config_to_save.setdefault("audit", {})
    audit["updated_at"] = datetime.now(timezone.utc).isoformat()
    audit["updated_by"] = normalized_email
    normalized_comment = str(change_comment or "").strip()
    audit["change_comment"] = normalized_comment or None

    validate_pricing_config(config_to_save)
    if get_pricing_config_backend() == "github":
        _write_pricing_config_github(config_to_save, normalized_email)
    else:
        _write_pricing_config_local(config_to_save)
    return config_to_save
