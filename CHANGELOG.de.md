# Änderungsprotokoll

Alle nennenswerten Änderungen an SimpleLog werden in dieser Datei dokumentiert.

## [Unveröffentlicht]

### Hinzugefügt
- Änderungsprotokoll, verfügbar in 5 Sprachen und in der App (Hilfe → Neuigkeiten).
- Wenn eine neue Version verfügbar ist, zeigt der Update-Dialog die Änderungen seit Ihrer Version an.

### Geändert
- SSH: Beim ersten Verbinden mit einem Host wird der Schlüssel-Fingerabdruck des Servers zur Bestätigung angezeigt; ein geänderter Schlüssel wird abgelehnt.
- Gespeicherte Zugangsdaten und Profile sind jetzt nur noch für Ihr Benutzerkonto lesbar.

## [1.0.8] - 2026-09-30

### Hinzugefügt
- Beim erneuten Öffnen einer gespeicherten Verbindung wird automatisch verbunden und das ausgewählte Ziel (Log-Gruppe, Projekt, Dienst, Pod, Worker…) samt Optionen wiederhergestellt – für alle Anbieter. Ein Klick auf Öffnen genügt.

### Behoben
- AWS CloudWatch: Gespeicherte Zugangsdaten werden beim erneuten Öffnen einer Verbindung jetzt vorausgefüllt.

## [1.0.7] - 2026-08-19

### Behoben
- macOS: Release-Builds funktionieren wieder (sie schlugen seit 1.0.4 fehl).
- Links und Update-Prüfung verweisen jetzt auf die neue GitHub-Organisation simple-log-app.

## [1.0.6] - 2026-07-29

### Behoben
- Das Mausrad ändert beim Scrollen nicht mehr versehentlich Werte in Auswahllisten.

## [1.0.5] - 2026-07-29

### Hinzugefügt
- Rechtsklick-Menü zum Kopieren der ausgewählten Logzeilen.

## [1.0.4] - 2026-07-29

### Behoben
- Im Log-Viewer können jetzt mehrere Logzeilen gleichzeitig ausgewählt werden.

## [1.0.3] - 2026-05-25

### Behoben
- macOS: Absturz beim Start behoben.

## [1.0.2] - 2026-05-25

### Behoben
- macOS: Absturz beim Start behoben.

## [1.0.1] - 2026-05-21

### Geändert
- Interne Aufräumarbeiten und bessere Testabdeckung.

## [1.0.0] - 2026-05-20

### Hinzugefügt
- Erste Version: Log-Viewer für lokale Dateien, stdin, AWS CloudWatch, SSH, Docker, Kubernetes, Vercel, Google Cloud, Azure, Loki, Datadog, Elasticsearch, Railway, Fly.io und Cloudflare Workers.
