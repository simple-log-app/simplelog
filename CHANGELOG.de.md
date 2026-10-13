# Änderungsprotokoll

Alle nennenswerten Änderungen an SimpleLog werden in dieser Datei dokumentiert.

## [Unveröffentlicht]

### Hinzugefügt
- Änderungsprotokoll, verfügbar in 5 Sprachen und in der App (Hilfe → Neuigkeiten).
- Wenn eine neue Version verfügbar ist, zeigt der Update-Dialog die Änderungen seit Ihrer Version an.

### Geändert
- SSH: Beim ersten Verbinden mit einem Host wird der Schlüssel-Fingerabdruck des Servers zur Bestätigung angezeigt; ein geänderter Schlüssel wird abgelehnt.
- Gespeicherte Zugangsdaten und Profile sind jetzt nur noch für Ihr Benutzerkonto lesbar.

### Behoben
- macOS: Das integrierte Update konnte den gesamten Programme-Ordner löschen, statt nur SimpleLog zu ersetzen. Jetzt wird nur noch die SimpleLog-App ersetzt, und die alte bleibt bei Problemen erhalten. Da das Update von der bereits installierten Version ausgeführt wird, können sich 1.0.8 und frühere Versionen unter macOS nicht mehr selbst aktualisieren: Laden Sie die neue Version einmalig von der Website oder mit Homebrew herunter.
- Kubernetes: Logs erscheinen jetzt sofort statt erst nach 200 Zeilen.
- Loki, GCP, Datadog und Fly.io: Dieselben Logzeilen erscheinen beim Verfolgen einer Quelle nicht mehr immer wieder.
- Loki, Datadog und Elasticsearch: Das erste Laden zeigt jetzt die neuesten Logs statt der ältesten des Zeitraums. GCP überspringt bei Lastspitzen keine Einträge mehr.
- Ein kurzes Netzwerkproblem beendet das Verfolgen einer Quelle nicht mehr mit einer Fehlermeldung: SimpleLog versucht es erneut und meldet erst nach mehreren aufeinanderfolgenden Fehlern einen Fehler.
- Die Eingabetaste in einem Textfeld (Suche, Filter, Formulare) fügt keine Trennzeile mehr in das aktuelle Log ein.
- Wird ein Log in einem geteilten Bereich geöffnet, obwohl der Tab bereits 9 Bereiche hat, erscheint jetzt eine Meldung, statt stillschweigend ein nie angezeigtes Log zu starten.
- Das Öffnen vieler gespeicherter Verbindungen verlangsamt die App nicht mehr: Fenster, Timer und SSH-Verbindungen werden beim Schließen freigegeben.
- Lokale Dateien: Das Verfolgen einer Datei funktioniert nach Rotation oder Leeren weiter, in zwei Teilen geschriebene Zeilen werden nicht mehr getrennt, und Umlaute werden nicht mehr verfälscht.

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
