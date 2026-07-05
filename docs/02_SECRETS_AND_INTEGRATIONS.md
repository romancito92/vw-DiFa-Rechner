# Secrets und Integrationen

## Grundregel

Keine echten Secret-Werte ins Repo schreiben. Das gilt besonders fuer:

- API-Keys
- Microsoft-Entra-Client-Secret
- Streamlit Auth Cookie Secret
- produktive Redirect-/Tenant-/Client-Konfigurationen, soweit sie vertraulich behandelt werden sollen

`.streamlit/secrets.toml` ist per `.gitignore` ausgeschlossen. `.streamlit/secrets.example.toml` enthaelt nur die erwartete Struktur und Platzhalter.

## Streamlit Secrets

Die App liest Secrets in `config.py`.

Wichtige Helfer:

- `get_secret()`
- `get_ors_api_key()`
- `get_tankerkoenig_api_key()`
- `get_auth_settings()`
- `get_oidc_settings()`

Die Aufloesung priorisiert Streamlit Secrets vor Umgebungsvariablen. Fuer API-Keys werden Root-Level-Secrets bevorzugt, weil Streamlit Community Cloud damit in diesem Projekt kompatibel gehalten wurde.

## OpenRouteService

Zweck:

- Adressvorschlaege / Autocomplete
- Geocoding
- Distanz- und Fahrzeitberechnung fuer Modus A und B

Dateien:

- `config.py`: URLs und Secret-Aufloesung
- `ors_helpers.py`: API-Aufrufe und Adressformatierung
- `direktfahrt_rechner.py`: UI-Integration in Modus A/B

Abgrenzung fuer deutsche Postleitzahlen:

- ORS bleibt die Routing-Engine und geocodiert konkrete Strassenadressen.
- ORS/Pelias liefert fuer deutsche Eingaben nur aus PLZ und Ort nicht immer unterschiedliche oder PLZ-bestaetigte Koordinaten.
- Deutsche PLZ-only- und PLZ+Ort-Eingaben werden deshalb lokal ueber `data/de_postal_codes.csv` aufgeloest.
- Die lokale Schwerpunktkoordinate wird anschliessend direkt an das ORS-Routing uebergeben.
- Liefert ORS bei einer konkreten Adresse eine andere oder keine PLZ, wird die eingegebene PLZ nicht in das Trefferlabel erfunden; die UI zeigt einen Mismatch- beziehungsweise Unbestaetigt-Hinweis.

Erwartete Secret-Namen:

- bevorzugt: `ORS_API_KEY`
- alternativ: `openrouteservice.api_key`
- alternativ: `openrouteservice.apiKey`
- alternativ: `api.ORS_API_KEY`
- env fallback: `ORS_API_KEY` oder `OPENROUTESERVICE_API_KEY`

Kritisch/geheim: ja, API-Key gehoert nicht ins Repo.

## Lokale deutsche PLZ-Daten

Zweck:

- eindeutige Schwerpunktkoordinaten fuer deutsche PLZ-only- und PLZ+Ort-Eingaben
- gemeinsame Verwendung in Modus A und B

Dateien:

- `data/de_postal_codes.csv`: reduzierter deutscher GeoNames-Export
- `data/README.md`: Quelle, Lizenz, Abrufdatum und Aktualisierung
- `location_candidates.py`: Loader, Lookup und `LocationCandidate`

Quelle und Lizenz:

- GeoNames Postal Code Dataset: https://download.geonames.org/export/zip/DE.zip
- Creative Commons Attribution 4.0 (CC BY 4.0)
- Attribution: GeoNames, https://www.geonames.org/

Die Koordinaten sind Schaetz- beziehungsweise Schwerpunktkoordinaten. Sie ersetzen keine konkrete Strassenadresse. Fuer ein Update wird das aktuelle `DE.zip` geladen, `DE.txt` auf die dokumentierten CSV-Spalten reduziert und das Abrufdatum in `data/README.md` aktualisiert.

Keine zusaetzlichen Secrets erforderlich.

## Tankerkoenig

Zweck:

- Dieselpreis im Umkreis des Hauptstandorts abrufen
- Modus A kann daraus eine Spritpreisanpassung berechnen

Dateien:

- `config.py`: API-URL, Default-Standort, Radius und Secret-Aufloesung
- `tankerkoenig_helpers.py`: API-Aufruf und Durchschnittsbildung
- `direktfahrt_rechner.py`: UI-Integration in Modus A

Erwartete Secret-Namen:

- bevorzugt: `TANKERKOENIG_API_KEY`
- alternativ: `tankerkoenig.api_key`
- alternativ: `tankerkoenig.apiKey`
- alternativ: `api.TANKERKOENIG_API_KEY`
- env fallback: `TANKERKOENIG_API_KEY`

Falls kein Key gefunden wird, verwendet `get_tankerkoenig_api_key()` einen Demo-Key aus `config.py`. Dieser ist funktional nicht als produktiver Ersatz zu betrachten.

Kritisch/geheim: ja, produktiver API-Key gehoert nicht ins Repo.

## Microsoft Entra ID / OIDC / Login

Zweck:

- Schutz der internen App
- Login ueber Streamlit Auth und Microsoft Entra ID
- Autorisierung nach erlaubten Domains / erlaubten E-Mail-Adressen
- Rollenanzeige `Admin` vs. `User`

Dateien:

- `direktfahrt_rechner.py`: `render_login_gate()` und `render_user_session_bar()`
- `auth_helpers.py`: Loginstatus, Claims, E-Mail, Rollen, Autorisierung
- `config.py`: Auth-/OIDC-Settings und Secret-Aufloesung

Technischer Ablauf:

1. `main()` ruft `render_login_gate()` auf.
2. Wenn `st.user.is_logged_in` falsch ist, wird nur die Login-Seite angezeigt.
3. Vor dem Login prueft `get_oidc_configuration_error()`, ob OIDC vollstaendig konfiguriert ist.
4. Login erfolgt ueber `st.login(auth_settings.provider_key)`.
5. Nach Login prueft `is_user_authorized()`, ob die E-Mail erlaubt ist.
6. Nicht autorisierte Nutzer sehen `render_access_denied()` und koennen sich abmelden.
7. `render_user_session_bar()` zeigt Displayname, E-Mail und Rolle.

Erwartete Auth-Secrets:

```toml
[auth]
redirect_uri = "..."
cookie_secret = "..."

[auth.microsoft]
tenant_id = "..."
client_id = "..."
client_secret = "..."
server_metadata_url = "..."

[app_auth]
provider_key = "microsoft"
provider_label = "Microsoft Entra ID"
allowed_domains = ["versandwerk.net"]
allowed_emails = []
admin_emails = []
```

Alternative Env-Namen:

- `STREAMLIT_AUTH_REDIRECT_URI`
- `STREAMLIT_AUTH_COOKIE_SECRET`
- `STREAMLIT_AUTH_CLIENT_ID`
- `STREAMLIT_AUTH_CLIENT_SECRET`
- `STREAMLIT_AUTH_TENANT_ID`
- `STREAMLIT_AUTH_SERVER_METADATA_URL`
- `VW_AUTH_PROVIDER_KEY`
- `VW_AUTH_PROVIDER_LABEL`
- `VW_ALLOWED_DOMAINS`
- `VW_ADMIN_EMAILS`

## Autorisierungslogik

Datei: `auth_helpers.py`

Claims fuer E-Mail-Ermittlung in dieser Reihenfolge:

1. `email`
2. `preferred_username`
3. `upn`
4. `unique_name`

Regeln:

- Explizite `allowed_emails` erlauben einzelne Adressen.
- Danach greift der Domain-Check ueber `allowed_domains`.
- Wenn weder Allowlist noch Domain passt, ist der Zugriff verweigert.
- `admin_emails` steuert nur die Rolle `admin`; daraus entstehen aktuell keine zusaetzlichen Rechte im UI.

Default:

- `DEFAULT_ALLOWED_EMAIL_DOMAINS = ("versandwerk.net",)` in `config.py`

Risiko:

- Wenn `allowed_domains` unabsichtlich leer ist und keine `allowed_emails` gesetzt sind, ist deny-by-default aktiv.
- Rollenlogik ist aktuell Anzeige/Grundlage, aber kein vollstaendiges Rechtekonzept.

## Weitere Integrationen

Aktuell aus der Codebasis ableitbar:

- GitHub fuer Source/Deployment
- Streamlit Cloud fuer Hosting
- keine Datenbank
- keine persistente Speicherung von Kalkulationen
- keine CRM-/ERP-Anbindung
