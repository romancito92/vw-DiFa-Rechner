import csv
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import pycountry


DE_POSTAL_CODES_PATH = Path(__file__).with_name("data").joinpath("de_postal_codes.csv")
GERMAN_POSTAL_CODE_PATTERN = re.compile(r"(?<!\d)(\d{5})(?!\d)")
HOUSE_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{1,5}[a-zA-Z]?(?:[-/]\d{1,5}[a-zA-Z]?)?(?!\d)")
EXPLICIT_COUNTRY_PATTERN = re.compile(r"(?:,\s*|\s+)([A-Za-z]{2,3})\s*$")


class LocationResolutionError(ValueError):
    """A user-facing location error that prevents routing with ambiguous coordinates."""


@dataclass(frozen=True)
class LocationCandidate:
    label: str
    display_label: str
    query: str
    postal_code: str = ""
    locality: str = ""
    country_code: str = ""
    coordinates: tuple[float, float] | None = None
    source: str = "manual"
    confidence: float | None = None
    match_type: str = ""
    warning: str = ""

    @property
    def has_coordinates(self):
        return self.coordinates is not None and len(self.coordinates) == 2

    def to_dict(self):
        payload = asdict(self)
        if self.coordinates is not None:
            payload["coordinates"] = list(self.coordinates)
        return payload

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict):
            return None
        values = dict(payload)
        coordinates = values.get("coordinates")
        if coordinates is not None:
            values["coordinates"] = tuple(float(value) for value in coordinates[:2])
        try:
            return cls(**values)
        except (TypeError, ValueError):
            return None

    @classmethod
    def manual(cls, query):
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return None
        return cls(
            label=cleaned_query,
            display_label=cleaned_query,
            query=cleaned_query,
            postal_code=extract_german_postal_code(cleaned_query),
            source="manual",
        )


def extract_german_postal_code(search_text):
    match = GERMAN_POSTAL_CODE_PATTERN.search(str(search_text or ""))
    return match.group(1) if match else ""


def get_location_display_name(location):
    """Return the selected locality, with a conservative fallback for manual inputs."""
    if isinstance(location, LocationCandidate) and location.locality:
        return location.locality.strip()
    if isinstance(location, LocationCandidate):
        raw_value = location.display_label or location.label or location.query
    else:
        raw_value = str(location or "")
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    if not parts:
        return ""
    if len(parts) > 1 and re.fullmatch(r"[A-Za-z]{2,3}", parts[-1]):
        parts.pop()
    place_name = parts[-1] if parts else ""
    return GERMAN_POSTAL_CODE_PATTERN.sub("", place_name).strip()


def build_route_segment_label(start_role, start_location, target_role, target_location):
    start_name = get_location_display_name(start_location)
    target_name = get_location_display_name(target_location)
    start_label = f"{start_role} ({start_name})" if start_name else start_role
    target_label = f"{target_role} ({target_name})" if target_name else target_role
    return f"{start_label} → {target_label}"


def _has_explicit_foreign_country(search_text):
    match = EXPLICIT_COUNTRY_PATTERN.search(str(search_text or "").strip())
    if not match:
        return False
    country_code = match.group(1).upper()
    if country_code in {"DE", "DEU"}:
        return False
    if len(country_code) == 2:
        return pycountry.countries.get(alpha_2=country_code) is not None
    return pycountry.countries.get(alpha_3=country_code) is not None


def has_concrete_street_address(search_text):
    """Treat a query as a concrete address only when it includes a second number."""
    cleaned = str(search_text or "")
    postal_code = extract_german_postal_code(cleaned)
    if postal_code:
        cleaned = cleaned.replace(postal_code, " ", 1)
    return HOUSE_NUMBER_PATTERN.search(cleaned) is not None


@lru_cache(maxsize=4)
def _load_de_postal_code_index(path_string):
    path = Path(path_string)
    if not path.exists():
        raise LocationResolutionError(
            "Lokale PLZ-Tabelle fehlt – bitte vollständige Adresse eingeben."
        )

    index = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"postal_code", "place_name", "lat", "lon"}
        if not required_columns.issubset(reader.fieldnames or ()):
            raise LocationResolutionError("Lokale PLZ-Tabelle hat ein ungültiges Format.")
        for row in reader:
            postal_code = str(row.get("postal_code") or "").strip()
            place_name = str(row.get("place_name") or "").strip()
            try:
                latitude = float(row.get("lat"))
                longitude = float(row.get("lon"))
            except (TypeError, ValueError):
                continue
            if not GERMAN_POSTAL_CODE_PATTERN.fullmatch(postal_code) or not place_name:
                continue
            record = {
                "postal_code": postal_code,
                "place_name": place_name,
                "latitude": latitude,
                "longitude": longitude,
                "state": str(row.get("state") or "").strip(),
                "district": str(row.get("district") or "").strip(),
                "source": str(row.get("source") or "GeoNames").strip(),
                "accuracy": str(row.get("accuracy") or "").strip(),
            }
            index.setdefault(postal_code, []).append(record)
    return index


def load_de_postal_code_index(data_path=DE_POSTAL_CODES_PATH):
    return _load_de_postal_code_index(str(Path(data_path).resolve()))


def clear_de_postal_code_cache():
    _load_de_postal_code_index.cache_clear()


def get_de_postal_code_candidates(search_text, data_path=DE_POSTAL_CODES_PATH):
    """Return local centroid candidates, None for non-local cases, or a clear lookup error."""
    query = str(search_text or "").strip()
    postal_code = extract_german_postal_code(query)
    if not postal_code or _has_explicit_foreign_country(query):
        return None
    if has_concrete_street_address(query):
        return None

    records = load_de_postal_code_index(data_path).get(postal_code, [])
    if not records:
        raise LocationResolutionError(
            "PLZ nicht in lokaler Tabelle gefunden – bitte vollständige Adresse eingeben."
        )

    candidates = []
    seen = set()
    for record in records:
        label = f"{postal_code} {record['place_name']}, DE"
        key = (label.casefold(), record["longitude"], record["latitude"])
        if key in seen:
            continue
        seen.add(key)
        accuracy = record.get("accuracy")
        confidence = float(accuracy) / 6 if accuracy and accuracy.isdigit() else None
        candidates.append(
            LocationCandidate(
                label=label,
                display_label=label,
                query=query,
                postal_code=postal_code,
                locality=record["place_name"],
                country_code="DE",
                coordinates=(record["longitude"], record["latitude"]),
                source="de_postal_code_centroid",
                confidence=confidence,
                match_type="postal_centroid",
            )
        )
    return candidates
