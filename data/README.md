# Deutsche Postleitzahl-Koordinaten

`de_postal_codes.csv` ist ein reduzierter Export des deutschen GeoNames Postal Code Dataset.

- Quelle: https://download.geonames.org/export/zip/DE.zip
- Abrufdatum dieses Exports: 2026-07-05
- Lizenz: Creative Commons Attribution 4.0 (CC BY 4.0)
- Attribution: GeoNames, https://www.geonames.org/
- Quelldokumentation: https://download.geonames.org/export/zip/

Die CSV enthält `postal_code`, `place_name`, `lat`, `lon`, `state`, `district`, `source` und `accuracy`. Die Koordinaten sind Schätz- beziehungsweise Schwerpunktkoordinaten und ersetzen keine konkrete Straßenadresse.

## Aktualisierung

1. Aktuelles `DE.zip` von GeoNames herunterladen.
2. `DE.txt` als UTF-8 und tabulatorgetrennt lesen.
3. Die oben genannten Spalten extrahieren, nach `postal_code` und `place_name` sortieren und als UTF-8-CSV schreiben.
4. Referenztests für `50825`, `51105` und `57072` ausführen.
5. Abrufdatum in dieser Datei aktualisieren.

GeoNames stellt die Daten ohne Gewähr für Richtigkeit, Aktualität oder Vollständigkeit bereit.
