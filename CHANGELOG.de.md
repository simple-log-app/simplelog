# Änderungsprotokoll

Alle nennenswerten Änderungen an SimpleLog werden in dieser Datei dokumentiert.

## [Unveröffentlicht]

### Behoben
- Die Schaltflächen Schließen/OK/Abbrechen/Ja/Nein in Dialogen folgen jetzt der App-Sprache.

## [2.2.1] - 2026-10-15

### Behoben
- Auch die Meldungsfenster („Über“, Update, Fehler, Bestätigungen) haben jetzt keine System-Titelleiste mehr, wie die übrigen Dialoge.

## [2.2.0] - 2026-10-15

### Geändert
- Dialoge haben keine System-Titelleiste mehr: keine Schaltflächen zum Minimieren / Maximieren und sie lassen sich nicht mehr verschieben; schließen Sie sie mit ✕ oder Esc.

## [2.1.3] - 2026-10-15

### Behoben
- Linux: „Hinzufügen“ und gespeicherte Verbindungen funktionieren in der installierten App wieder (in 2.1.2 passierte nichts).
- Das Menü Automatisch / Tag / Nacht ist im Tag-Modus nicht mehr dunkel.

## [2.1.2] - 2026-10-15

### Geändert
- Interne Neuorganisation der Anwendung; am Aussehen und Verhalten von SimpleLog ändert sich nichts.

## [2.1.1] - 2026-10-15

### Behoben
- Der Mauszeiger „Laden“ bleibt nicht mehr mehrere Sekunden sichtbar, wenn Sie auf „Hinzufügen“ klicken oder eine gespeicherte Verbindung öffnen (Linux/GNOME).

## [2.1.0] - 2026-10-14

### Hinzugefügt
- Das Design kann jetzt der Hell-/Dunkel-Einstellung Ihres Systems folgen: Wählen Sie „Automatisch“ über den Pfeil neben der Tag-/Nacht-Schaltfläche.
- Filter nach Stufe: Zeilen der Stufen ERROR, WARN, INFO, DEBUG und TRACE lassen sich mit den Chips im Tab „Filter“ ein- oder ausblenden.
- Suche und Filter: neue Optionen „Groß-/Kleinschreibung beachten“ und „Regulärer Ausdruck“; zuletzt verwendete Begriffe werden beim Tippen vorgeschlagen (↓ in einem leeren Feld zeigt sie an).
- Hervorhebungsregeln (Menü Bearbeiten): Färben Sie wichtige Wörter in jedem Log ein, optional mit Groß-/Kleinschreibung und regulären Ausdrücken.
- Lesezeichen: Markieren Sie Zeilen mit Strg+B (oder dem Rechtsklickmenü) und springen Sie mit F2 / Umschalt+F2 zwischen ihnen oder entfernen Sie alle auf einmal (Strg+Umschalt+B).
- Export: Speichern Sie die aktuell angezeigten Zeilen (nach Ihren Filtern) oder nur die Auswahl in einer Datei – über das Menü Datei (Strg+Umschalt+E) oder das Rechtsklickmenü.
- Zusammengeführte Ansicht (Menü Bearbeiten oder Rechtsklickmenü): Zeigen Sie mehrere geöffnete Logs in einem Tab in zeitlicher Reihenfolge an, jede Zeile mit ihrer Quelle.
- Remote-Tabs zeigen ihren Verbindungsstatus (farbiger Punkt am Logo) und verbinden sich bei Abbruch von selbst neu, ohne Zeilen zu duplizieren; im Menü Datei abschaltbar.
- Neue Log-Quellen: das lokale systemd-Journal, Heroku, Render, Splunk, Better Stack und Sentry (Fehlerereignisse).

### Geändert
- Verbindung hinzufügen: Die „Split“-Optionen von „Öffnen als“ sind ausgegraut, solange kein Log geöffnet ist, da es noch nichts zu teilen gibt.

### Behoben
- Der Mauszeiger „Laden“ bleibt beim Start von SimpleLog nicht mehr etwa 12 Sekunden lang sichtbar (Linux/GNOME).

## [2.0.0] - 2026-10-14

### Hinzugefügt
- Suche: F3 springt zum nächsten Treffer und Umschalt+F3 zum vorherigen; die Tastenkürzel stehen in den Tooltips der Schaltflächen.
- Tag-/Nachtmodus: Wechseln Sie das Design mit der Schaltfläche rechts in der Menüleiste (oder mit Strg+Umschalt+L); Ihre Wahl wird gespeichert.

### Geändert
- Neues Erscheinungsbild: überarbeitete dunkle Farbpalette mit limettengrünem Akzent für bessere Lesbarkeit.
- Remote-Quellen: Die Liste zeigt nur noch Dienste, für die Sie gespeicherte Verbindungen haben, mit einem Link „+ Neue Verbindung“ und zweistufigem Löschen.
- Verbindung hinzufügen: eine filterbare Auswahl in 4 Spalten mit dem offiziellen Logo jedes Dienstes und ein übersichtlicheres Verbindungsformular.
- Dienst-Logos erscheinen jetzt auf den Tabs, und die Auswahl „Öffnen als“ passt in eine Zeile.

### Behoben
- Die UND-/ODER-Schaltfläche zwischen Such- und Filterbegriffen wird jetzt in Ihrer Sprache angezeigt.

## [1.0.9] - 2026-10-13

### Hinzugefügt
- Änderungsprotokoll, verfügbar in 5 Sprachen und in der App (Hilfe → Neuigkeiten).
- Wenn eine neue Version verfügbar ist, zeigt der Update-Dialog die Änderungen seit Ihrer Version an.
- Neue Option „Umbruch“ in der Log-Leiste: Ausgeschaltet wird jedes Log in einer Zeile angezeigt (lange Zeilen lassen sich seitlich scrollen), was bei sehr großen Logs schneller ist.

### Geändert
- SSH: Beim ersten Verbinden mit einem Host wird der Schlüssel-Fingerabdruck des Servers zur Bestätigung angezeigt; ein geänderter Schlüssel wird abgelehnt.
- Gespeicherte Zugangsdaten und Profile sind jetzt nur noch für Ihr Benutzerkonto lesbar.
- Deutlich schneller bei Log-Strömen mit viel Verkehr (SSH, Docker, Kubernetes, stdin, Dateien): Zeilen werden gruppenweise hinzugefügt, und lange Logs bleiben beim Verfolgen, Skalieren und Tab-Wechsel flüssig.
- Strg+W schließt jetzt den aktuellen Tab; alle Logs schließen Sie mit Strg+Umschalt+W.
- Zeitstempel in der Log-Ansicht werden jetzt in Ihrer Ortszeit statt in UTC angezeigt.
- Schnellerer Start, und das Öffnen einer großen Datei mit sehr vielen angeforderten Zeilen geht jetzt fast sofort.
- Die Anbieter-Karten in „Verbindung hinzufügen“ zeigen beim Darüberfahren jetzt eine kurze Beschreibung der jeweiligen Quelle.
- Statusmeldungen, Verbindungsfehler und Tooltips, die bisher immer englisch waren, folgen jetzt der gewählten Sprache.
- Updates werden jetzt mit der zur Version veröffentlichten Prüfsumme geprüft; ein beschädigter Download wird verworfen.

### Behoben
- CloudWatch: Eine Verbindung auf Basis eines AWS-Profils verwendet jetzt die für dieses Profil in `~/.aws/config` festgelegte Region.
- Die Anwendung stürzt nicht mehr ab, wenn eine Verbindung direkt nach dem Schließen ihres Tabs fehlschlägt oder wenn Ihre AWS-Konfigurationsdatei ein doppeltes Profil enthält.
- Datei → Öffnen (Strg+O) öffnet die Datei nicht mehr doppelt.
- Docker-, Kubernetes-, SSH- und Pipe-Logs brechen bei einer Zeile mit ungültigen Zeichen nicht mehr stillschweigend ab.
- Das Laden eines sehr großen Zeilenblocks (z. B. `cat big.log | simplelog`) hinterlässt keine Geisterzeilen mehr in der Ansicht.
- Fly.io: Ein ungültiges Token oder eine unbekannte App zeigt jetzt einen Fehler statt eines endlos leeren Logs.
- Azure: Die zusätzlichen Bedingungen Ihrer Abfrage (z. B. zur Schwere) bleiben beim Verfolgen erhalten, und verspätet eingespielte Zeilen gehen nicht mehr verloren.
- Kubernetes: Ein Pod mit vielen Warnungen blockiert den Log-Strom nicht mehr.
- Die automatische Aktualisierung unter Linux (AppImage) funktioniert jetzt auch, wenn der Installationspfad ein Anführungszeichen enthält.
- Aktualisierungen werden abgelehnt, wenn die veröffentlichten Prüfsummen die heruntergeladene Datei nicht auflisten.
- Der Titel „Fehler“ sowie die Schaltflächen „Zurück/Weiter“ und „+ Schlüssel=Wert“ folgen jetzt der gewählten Sprache.
- Schlüssel=Wert-Filter sind bei JSON-Logs etwa doppelt so schnell.
- macOS: Das integrierte Update konnte den gesamten Programme-Ordner löschen, statt nur SimpleLog zu ersetzen. Jetzt wird nur noch die SimpleLog-App ersetzt, und die alte bleibt bei Problemen erhalten. Da das Update von der bereits installierten Version ausgeführt wird, können sich 1.0.8 und frühere Versionen unter macOS nicht mehr selbst aktualisieren: Laden Sie die neue Version einmalig von der Website oder mit Homebrew herunter.
- Kubernetes: Logs erscheinen jetzt sofort statt erst nach 200 Zeilen.
- Loki, GCP, Datadog und Fly.io: Dieselben Logzeilen erscheinen beim Verfolgen einer Quelle nicht mehr immer wieder.
- Loki, Datadog und Elasticsearch: Das erste Laden zeigt jetzt die neuesten Logs statt der ältesten des Zeitraums. GCP überspringt bei Lastspitzen keine Einträge mehr.
- Ein kurzes Netzwerkproblem beendet das Verfolgen einer Quelle nicht mehr mit einer Fehlermeldung: SimpleLog versucht es erneut und meldet erst nach mehreren aufeinanderfolgenden Fehlern einen Fehler.
- Die Eingabetaste in einem Textfeld (Suche, Filter, Formulare) fügt keine Trennzeile mehr in das aktuelle Log ein.
- Wird ein Log in einem geteilten Bereich geöffnet, obwohl der Tab bereits 9 Bereiche hat, erscheint jetzt eine Meldung, statt stillschweigend ein nie angezeigtes Log zu starten.
- Das Öffnen vieler gespeicherter Verbindungen verlangsamt die App nicht mehr: Fenster, Timer und SSH-Verbindungen werden beim Schließen freigegeben.
- Lokale Dateien: Das Verfolgen einer Datei funktioniert nach Rotation oder Leeren weiter, in zwei Teilen geschriebene Zeilen werden nicht mehr getrennt, und Umlaute werden nicht mehr verfälscht.
- Suche: Treffer werden transparent gelb und bei umgebrochenen Zeilen an der richtigen Stelle hervorgehoben; AND / OR zwischen Suchbegriffen wird beachtet; JSON-Zeilen mit Treffer werden hervorgehoben; und die Ansicht springt beim Verfolgen eines Logs nicht mehr zum ersten Treffer zurück.
- Ein Rechtsklick oder eine Auswahl mit der Maus auf einer JSON-Zeile klappt sie nicht mehr auf oder zu; nur ein einfacher Klick tut das.
- Eine Datei mit `simplelog datei.log` aus einem anderen Ordner zu öffnen, während SimpleLog läuft, funktioniert jetzt.
- Das Schließen eines Tabs oder Beenden friert die App nicht mehr für mehrere Sekunden ein.
- Das Ein- oder Ausschalten der Zeitstempel passt umgebrochene Zeilen jetzt korrekt an.
- Gespeicherte Verbindungen und Zugangsdaten gehen nicht mehr verloren, wenn die App beim Speichern abstürzt.
- Elasticsearch 8 und neuer: Das Verfolgen von Logs funktioniert wieder (es nutzte eine Sortierung, die neuere Versionen ablehnen).
- Updates: Ein unvollständiger Download wird erkannt, und die Installation eines .deb-Updates friert das Fenster nicht mehr ein.
- CloudWatch, Docker und SSH: Das Auflisten von Log-Gruppen, Streams und Containern sowie das Öffnen eines SSH-Logs friert die App beim Warten auf das Netzwerk nicht mehr ein.
- Der SFTP-Dateibrowser, wiederhergestellte SSH- / GCP- / Azure-Sitzungen und die Kubernetes-Clusterliste frieren die App beim Warten auf das Netzwerk nicht mehr ein.
- Das Quellen-Badge in der Log-Leiste zeigte eine interne Bezeichnung wie „src_ssh“; jetzt wird der Name der Quelle angezeigt.
- Gespeicherte Google-Cloud-Verbindungen zeigen jetzt ihr Projekt neben dem Namen.
- Azure: Das Live-Verfolgen funktioniert jetzt auch mit einzeiligen Abfragen oder mit einer Zeilenbegrenzung (`take`/`limit`) vor dem Filter.
- CloudWatch: Ereignisse, die einige Sekunden verspätet eintreffen, gehen beim Verfolgen nicht mehr verloren.
- Railway: Das Verfolgen eines Dienstes behält nicht mehr alle Zeilen im Speicher, und die mehrfache Auswahl von Diensten öffnet keine zusätzlichen Verbindungen mehr.
- Azure: Das erste Laden einer Tabelle oder einer Abfrage mit begrenzter Zeilenzahl zeigt jetzt die neuesten statt der ältesten Zeilen.
- Railway: Das Verfolgen eines Dienstes lädt nur noch neue Zeilen, statt bei jeder Aktualisierung alle Logs erneut herunterzuladen.

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
