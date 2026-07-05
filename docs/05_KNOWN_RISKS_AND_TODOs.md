# Known Risks und TODOs

## Technische Schwachstellen

### Grosse Hauptdatei

`direktfahrt_rechner.py` enthaelt sehr viel UI, Session-State-Handling, Callback-Logik und inzwischen auch Modus-D-Preislogik. Das ist fuer schnelle MVP-Arbeit praktisch, aber langfristig schwer wartbar.

Empfehlung:

- Modus-D-Logik in eigenes Modul auslagern, falls sie weiter waechst.
- UI und reine Berechnung staerker trennen.

### Modus C: Regeln verteilt auf JSON und Code

Ein Teil der Paketlogik ist in `parcel_tariffs_de.json`, ein Teil fest in `logic_parcel.py` und `direktfahrt_rechner.py`.

Beispiele:

- UPS/LZ48 Maßzuschlag-Konstanten im Code
- DeKu-Hinweise in der UI
- LZ48/EXP-Empfehlungslogik in `show_case_c()`

Risiko:

- Tarifupdate im JSON kann unvollstaendig sein, wenn die passende Code-Regel nicht angepasst wird.

### Encoding / Umlautartefakte

In einigen Dateien/Outputs sind historische Encoding-Artefakte sichtbar. Das kann beim Bearbeiten oder Anzeigen von deutschen Labels stoeren.

Empfehlung:

- konsequent UTF-8 verwenden
- bei groesseren Text-/Tarifbearbeitungen Diffs aufmerksam pruefen

### Auth-Rollen noch nicht als Rechtekonzept ausgebaut

`admin_emails` erzeugt aktuell Rolle `admin`, aber daraus entstehen keine klar getrennten Berechtigungen in der App.

Risiko:

- Der Name `admin` kann mehr Sicherheit suggerieren, als technisch umgesetzt ist.

Empfehlung:

- entweder Rolle nur als Anzeige verstehen und so dokumentieren
- oder spaeter echte Admin-Funktionen sauber absichern

### Keine persistente Kalkulationshistorie

Die App speichert keine Angebote, Nutzeraktionen oder Kalkulationen dauerhaft.

Das ist datensparsam, bedeutet aber:

- keine Nachvollziehbarkeit einzelner Angebotspreise
- keine Audit-Historie fuer hohe EKs
- keine zentrale Auswertung

### Kein automatisierter UI-Test

Tests pruefen Logik, aber kaum Streamlit-Rendering.

Risiko:

- Layout- oder Copy-Button-Probleme koennen trotz gruenem Test unbemerkt bleiben.

## Aktuelle Uebergangsloesungen

- Modus D ist bewusst als EK+-Schnellkalkulator direkt in `direktfahrt_rechner.py` implementiert.
- Tankerkoenig hat einen Demo-Key-Fallback, wenn kein Key gesetzt ist.
- Streamlit Cloud Deploy-Branch und App-URL sind nicht im Repo dokumentiert.
- Tarifpflege fuer Modus C erfolgt manuell ueber JSON plus Codewissen.

## Vorsicht bei kuenftigen Aenderungen

### Auth / Secrets

Immer pruefen:

- Login mit erlaubtem Konto
- Zugriff verweigert fuer nicht erlaubtes Konto
- keine echten Secrets im Diff
- Streamlit Cloud Secrets passend gepflegt

### Modus C Tarifupdates

Immer pruefen:

- JSON gueltig
- Beispielsendungen fuer EXP und LZ48
- Packstueckgrenzen
- Ueberlaenge/Gurtmaß
- Spaetanmeldung/Spaetabholung
- Hoeherversicherung
- PLZ-Gebiete

### Rundungslogiken

Nicht vereinheitlichen, ohne fachliche Entscheidung:

- A/B nutzen Abrundung auf ungerade ganze Zahl.
- D nutzt Abrundung auf den naechstniedrigeren Preis mit Endziffer 9.
- C nutzt Tarifsumme direkt aus Bausteinen.

### Externe APIs

ORS und Tankerkoenig koennen durch Rate Limits, Ausfaelle oder Key-Probleme fehlschlagen. Die App sollte fuer Kernkalkulationen weiterhin manuelle Eingaben erlauben.

### Deutsche PLZ-Schwerpunktkoordinaten

`data/de_postal_codes.csv` basiert auf dem GeoNames Postal Code Dataset. Die Koordinaten sind Naeherungen und koennen je nach GeoNames-Genauigkeitsstufe aus Ortsdaten, benachbarten PLZ oder anderen Schaetzverfahren stammen.

Risiken:

- Ein PLZ-Schwerpunkt ersetzt keine konkrete Strassenadresse.
- Neue oder geaenderte PLZ werden erst mit einem Datenupdate wirksam.
- Mehrere Ortsnamen koennen dieselbe PLZ besitzen und werden als getrennte Kandidaten angeboten.
- Die GeoNames-Attribution und CC-BY-4.0-Dokumentation muessen bei Datenupdates erhalten bleiben.

Empfehlung:

- GeoNames-Export regelmaessig aktualisieren und die Referenzfaelle `50825`, `51105` und `57072` testen.
- Bei zeitkritischen Fahrten nach Moeglichkeit eine vollstaendige Strassenadresse verwenden.

## Sinnvolle naechste Evolutionsschritte

1. Deploy-Daten dokumentieren:
   - Streamlit-App-URL
   - beobachteter Branch
   - verantwortliches Streamlit-Konto

2. Parameter aus Code in Konfiguration ziehen:
   - Modus A Saetze
   - Modus B Multiplikatoren und Distanzklassen
   - Modus D EK+-Matrix
   - Freigabeschwellen

3. Modus C Tarifpflege absichern:
   - JSON-Schema oder Validierungstest
   - Beispielsendungen als Testfaelle
   - Changelog je Tarifversion

4. Teststruktur verbessern:
   - pytest einfuehren oder bestehende Skripte vereinheitlichen
   - Tests in CI/GitHub Actions laufen lassen
   - UI-Smoke-Test fuer Streamlit Start

5. Auth/Rollen klar entscheiden:
   - nur Login und Anzeige
   - oder echte Admin-/Settings-Funktionen mit Rollenpruefung

6. Dokumentation aktuell halten:
   - bei jeder neuen Integration `02_SECRETS_AND_INTEGRATIONS.md` aktualisieren
   - bei jeder Preisregel `03_PRICING_LOGIC.md` aktualisieren
   - bei jeder neuen Datei `04_CODE_MAP.md` aktualisieren
