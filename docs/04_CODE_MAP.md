# Code Map

## `direktfahrt_rechner.py`

Rolle:

- Hauptdatei und Streamlit-Einstiegspunkt
- Rendert Header, Login-Gate, Modus-Auswahl und alle vier Modi
- Enthalten sind auch mehrere UI-nahe Sync-/Callback-Funktionen
- Modus D Logik liegt aktuell ebenfalls hier

Typische Aenderungen:

- UI-Texte und Layout der Modi
- neue Eingabefelder
- neue Hinweise/Validierungen
- Modus-Auswahl
- kleine Modus-D-Regeln

Risiken:

- Datei ist gross und vermischt UI, Session-State und teilweise Logik.
- Aenderungen in gemeinsam genutzten Helpern oder Session-State-Keys koennen Modusverhalten brechen.
- Auth-Gate sitzt hier; Aenderungen an `main()` und `render_login_gate()` vorsichtig testen.

## `config.py`

Rolle:

- zentrale Konfiguration
- harte Preis-/Fahrzeugtabellen fuer Modus B
- API-Endpunkte
- Streamlit-/Env-Secret-Aufloesung
- Auth-/OIDC-Konfiguration
- ORS-Profilmapping

Typische Aenderungen:

- Fahrzeugsaetze in `RATE_TABLE`
- API-Secret-Namen/Fallbacks
- erlaubte Default-Domain
- ORS-Profilmapping
- Tankerkoenig-Standort/Radius

Risiken:

- Secret-Aufloesung ist sicherheitsrelevant.
- Falsche Defaults koennen Login oder API-Zugriff brechen.
- `RATE_TABLE` wirkt direkt auf Modus B.

## `logic_direct.py`

Rolle:

- Reine Preislogik fuer Modus A und B
- Distanzklassen
- Rundung auf ungerade ganze Preise

Typische Aenderungen:

- A.1/A.2 Formel
- B-Multiplikatoren
- Distanzklassen
- Rundungsregel fuer A/B

Risiken:

- A und B teilen Rundung und Distanzklassen.
- Tests in `tests_pricing.py` nach jeder Aenderung ausfuehren.

## `logic_parcel.py`

Rolle:

- Reine Paketlogik fuer Modus C
- Laden der JSON-Tarife
- Packstueckmetriken
- Eignungspruefung
- Tarifberechnung
- Zuschlaege und Versicherung

Typische Aenderungen:

- neue Zuschlagsregeln
- Carrier-Validierung
- Abrechnungsgewicht-/Gurtmaßlogik
- Spaetabholungslogik

Risiken:

- Hohe Fehlerwirkung, weil viele Tarifbestandteile additiv zusammenspielen.
- Teilweise Regeln im JSON, teilweise im Code.
- LZ48/EXP-Sonderfaelle sind sensibel.

## `parcel_tariffs_de.json`

Rolle:

- Tarif- und Regelkonfiguration fuer Modus C
- Grundpreise, Gewichtsbaender, Zusatzservices, PLZ-Gebiete, Carrier-Zuschlaege

Typische Aenderungen:

- neuer Tarifstand
- neue Preise
- geaenderte PLZ-/Abholgebiete
- neue Zusatzservices

Risiken:

- JSON-Formatfehler verhindern Laden von Modus C.
- Semantik muss zu `logic_parcel.py` passen.
- Nach Preisupdate unbedingt Regressionstests und manuelle Beispielsendungen pruefen.

## `auth_helpers.py`

Rolle:

- Streamlit-User-Claims auslesen
- E-Mail und Anzeigename bestimmen
- Autorisierung pruefen
- Rolle bestimmen
- Access-Denied-UI

Typische Aenderungen:

- erlaubte Claim-Reihenfolge
- Domain-/Allowlist-Regeln
- Rollenlogik

Risiken:

- Zugriffssicherheit.
- `admin_emails` gibt aktuell nur Rolle `admin`, keine echten Zusatzrechte.

## `ors_helpers.py`

Rolle:

- OpenRouteService Geocoding und Routing
- Adressvorschlaege fuer Autocomplete
- Formatierung deutscher/auslaendischer Adresslabels

Typische Aenderungen:

- ORS-Parameter
- Adressformatierung
- Fehlerbehandlung

Risiken:

- Externe API-Verfuegbarkeit und Rate Limits.
- Falsche Formatierung kann Dispo-Eingaben erschweren.

## `location_candidates.py`

Rolle:

- gemeinsames Kandidatenmodell fuer Modus A und B
- lokale Aufloesung deutscher PLZ-only-/PLZ+Ort-Eingaben
- Session-State-Serialisierung ausgewaehlter Labels und Koordinaten
- Unterscheidung der Quellen `de_postal_code_centroid`, `ors_geocode` und `manual`

Typische Aenderungen:

- PLZ-Erkennung und Lookup-Verhalten
- Kandidatenfelder oder Auswahlpersistenz
- Pfad beziehungsweise Schema der lokalen PLZ-Tabelle

Risiken:

- PLZ-Schwerpunkte sind keine exakten Abhol-/Zustelladressen.
- Aenderungen am Kandidatenformat muessen UI, ORS-Routing und Session-State gemeinsam beruecksichtigen.

## `data/de_postal_codes.csv`

Rolle:

- lokale GeoNames-Schwerpunktkoordinaten deutscher Postleitzahlen
- Datenquelle fuer PLZ-only- und PLZ+Ort-Eingaben in Modus A/B

Quelle, Lizenz und Update-Ablauf stehen in `data/README.md`.

## `tankerkoenig_helpers.py`

Rolle:

- Tankerkoenig API-Abruf
- Dieselpreis extrahieren
- Durchschnitt offener Stationen bilden

Typische Aenderungen:

- Durchschnittslogik
- Fehlerbehandlung
- Stationsfilter

Risiken:

- API kann keine Preise liefern oder Demo-Key begrenzen.
- Durchschnittslogik wirkt auf Modus-A-Spritaufschlag.

## `ui_helpers.py`

Rolle:

- Formatierung von Euro, Dauer, EUR/km
- gemeinsame Karten und Copy-Buttons
- Modus-C-Angebotstexte und Preisbausteine
- CSS der App

Typische Aenderungen:

- visuelles Feintuning
- Copy-Text
- Empfehlungskarten
- Plausibilitaetsboxen

Risiken:

- Komponenten werden in mehreren Modi genutzt.
- CSS-Aenderungen koennen breite Nebenwirkungen haben.

## `.streamlit/config.toml`

Rolle:

- lokale Streamlit-Konfiguration
- aktuell Theme-Primärfarbe

Risiken:

- gering, aber Theme-Aenderungen wirken global.

## `.streamlit/secrets.example.toml`

Rolle:

- Beispielstruktur fuer lokale/Cloud-Secrets
- keine echten Secrets eintragen

Typische Aenderungen:

- neue Secret-Namen dokumentieren
- Beispielstruktur aktuell halten

Risiken:

- niemals echte API-Keys oder Client-Secrets eintragen.

## `.streamlit/secrets.toml`

Rolle:

- lokale echte Secrets
- ist per `.gitignore` ausgeschlossen

Risiken:

- darf nicht committed werden.

## Tests

### `tests_pricing.py`

Deckt Preislogik von A, B, C, D und Tankerkoenig-Durchschnitt ab.

### `tests_config.py`

Deckt Secret-Priorisierung fuer ORS und Tankerkoenig ab.

### `tests_auth.py`

Deckt Domain-/Allowlist-/Admin-Rollenlogik und OIDC-Konfigurationsfehler ab.

### `tests_ors.py`

Deckt ORS-Parameter und Adressformatierung ab.

### `tests_location_candidates.py`

Deckt PLZ-Erkennung, lokale GeoNames-Koordinaten, Kandidatenpersistenz, ORS-PLZ-Mismatch und koordinatenbasiertes Routing ab.

Risiko:

- Tests sind einfache Skripte, kein vollstaendiges Testframework.
- UI-Rendering wird kaum automatisiert getestet.
