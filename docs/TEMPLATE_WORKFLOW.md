# Workflow für neue Map-Templates

Ziel: Viele **unterschiedliche, spielbare** Kartenlayouts entwickeln, mit wenig wiederholter
Handarbeit. Ein kopiertes Template ist zunächst ein Prototyp. Eine neue Farbe oder andere
Standardwerte allein ergeben noch kein neues Layout.

Die technischen Regeln stehen in [TEMPLATE_GUIDE.md](TEMPLATE_GUIDE.md). Dieser Workflow ergänzt
sie um Gerüste, Prüfungen, Sichtkontrolle und Integration. Alles, was Spieler sehen, bleibt Englisch.
Keine neuen Python-Abhängigkeiten nötig.

## Der Ablauf

**Bestand prüfen → Idee festlegen → Gerüst erzeugen → entwickeln → voll prüfen → Bilder ansehen →
integrieren → Export und Regression prüfen → im Spiel testen.**

Die Befehle laufen aus dem Projektverzeichnis mit dem Projekt-Python. In dieser Windows-Umgebung:

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow catalog
.\.venv\Scripts\python.exe -m tools.template_workflow new three_lanes --title "Three Lanes" --base chokepoint
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes --level quick
```

Auf anderen Systemen/bei aktivierter Python-Umgebung kann `python` anstelle von
`.\.venv\Scripts\python.exe` verwendet werden.

### 1. Eine Idee mit eigenem Gameplay festlegen

Vor dem Programmieren `catalog` ansehen und ähnliche Templates vergleichen. Dann das erzeugte
Briefing `docs/template_briefs/<id>.json` ausfüllen:

- **concept:** Was erleben die Spieler auf dieser Karte?
- **difference_from_base:** Worin unterscheiden sich Geometrie und Entscheidungen vom Vorbild?
- **intended_players:** 1v1, Teams, FFA oder Koop; Anzahl und Startverteilung.
- **routes:** Hauptwege, Flanken, Engstellen, Landungszonen; Rolle der Bewegungsklassen.
- **economy:** Sichere Startressourcen, Expansionen und umkämpfte Wirtschaft.
- **mode:** `competitive`, `coop` oder `naval`; bestimmt Symmetrie- und Capability-Prüfungen.

Eine Familie darf mehrere Templates haben, wenn die Spielentscheidungen verschieden sind.
Eine Seenplatte mit Landwegen, offene See und Inselketten brauchen beispielsweise andere
Routen- und Ressourcenregeln. Reine Varianten derselben Karte gehören meist in deren Parameter.

### 2. Ein funktionierendes Gerüst erzeugen

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow new three_lanes --title "Three Lanes" --base chokepoint
```

Das erzeugt vier Dateien, ohne vorhandene Dateien zu überschreiben:

| Datei | Zweck |
|---|---|
| `atlasforge/templates/three_lanes.py` | Kopie eines funktionierenden Vorbilds mit eigenem Klassennamen, id und Titel |
| `tests/test_template_three_lanes.py` | Wiederverwendbare Vertragsprüfungen, Seeds 1–10 und Parametergrenzen |
| `docs/template_briefs/three_lanes.json` | Design-Briefing und Review-Status |
| `docs/template_briefs/three_lanes_TASK.md` | Fertiger Arbeitsauftrag für einen Entwickler oder KI-Assistenten |

Kommentare und Terrain-Code des Vorbilds bleiben erhalten. Registrierung und App-Galerie bleiben
bis zur Integration unverändert. So können mehrere Entwürfe nebeneinander entstehen, ohne die
normalen Nutzer mit unfertigen Einträgen zu belasten. Die Prüfwerkzeuge laden einen Prototyp nur
für ihren eigenen Prozess.

Geeignete Ausgangspunkte:

| Vorbild | Verwenden für |
|---|---|
| `skirmish` | Offene Karten und prozedurale Geländeformen |
| `chokepoint` | Mauern, Pässe, Lanes und Bewegungsklassen |
| `river` | Wasser/Lava mit Landquerungen und zeitweisen Sperren |
| `arena` | Mehrere geschützte Basen und vierfache Symmetrie |
| `volcano` | Inselverbindungen und zeitgesteuerte Ereignisse |
| `chicken` | Koop-Verteidigung ohne erforderliche Wettbewerbssymmetrie |
| Lokale Naval-Dateien | Erst nach vorhandener Naval-Core-Unterstützung als Seekarten freigeben |

`--mode coop` erlaubt bewusst asymmetrisches Gelände. Es schaltet die normalen Erreichbarkeitschecks
nicht aus. `naval` setzt echte Schiffsprüfungen voraus; der Workflow ersetzt sie niemals durch
abgeschwächte Landprüfungen.

### 3. In kurzen Schleifen entwickeln

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes --level quick
```

Der schnelle Check erzeugt Seed 1 mit Standardwerten, prüft Erreichbarkeit, endliche Höhendaten,
gültige Koordinaten, deklarierte Symmetrie und spiegelgleiche Ressourcen. Er prüft außerdem
Determinismus und schreibt Vorschau, Galerie-Miniatur und Bericht.

Danach eine konkrete Sache ändern und erneut prüfen: zuerst die Routen, dann Basen und Ressourcen,
dann Parameter, schließlich die Optik. Template-spezifische Aussagen gehören in eigene Tests:
zum Beispiel, dass der Mitteldurchgang bei Flut gesperrt wird oder eine Flanke wirklich erreichbar ist.
Die erzeugten Vertragstests ersetzen diese Gameplay-Tests nicht.

Bei dieser Arbeit nur Template und zugehörige Tests ändern. Neue Core-Wünsche ins Briefing schreiben.
Ein Fehler in gemeinsamem Terrain-Code wird gesondert korrigiert und mit Regressionstests geprüft.

### 4. Gründlich prüfen

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes --level full
```

Der Vollcheck enthält:

- Standardwerte mit Seeds 1–10.
- Sichere Grenzen aller Template-Parameter und jede Auswahloption.
- Erweiterte Grenzen, sämtliche erweiterten Auswahlwerte, beide booleschen Werte.
- Zwei kombinierte Fälle mit kleinster erweiterter Kartengröße und minimalen/maximalen Zahlenwerten.
- Vorschau und Checkbarkeit auch bei unspielbaren erweiterten Einstellungen.
- Rohzeiten von `Template.make()` an den regulären Größenrändern und bei Größe 20, falls angeboten.
- Einen Fehler, wenn die Erzeugung bei Größe 20 mindestens fünf Sekunden braucht.

Sichere Einstellungen müssen die Gameplay-Checks bestehen. Im erweiterten Modus darf ein
Gameplay-Check scheitern; Abstürze, ungültige Daten und nicht mehr erzeugbare Vorschauen bleiben
Fehler. Der Bericht zeigt diesen Unterschied ausdrücklich. Alle Parameterkombinationen und Seeds
vollständig abzudecken ist nicht möglich; auffällige Kombinationen bekommen zusätzliche Tests.

### 5. Die Bilder tatsächlich ansehen

Ausgaben liegen unter `out/template_workflow/<id>/<quick|full|release>/`:

- `<id>_preview.png`: große Vorschau von Seed 1.
- `contact_sheet.png`: Übersicht der Standard-Seeds.
- `<id>.jpg`: vorbereitete App-Miniatur.
- `report.json`: Ergebnisse, Laufzeiten, konkrete Einstellungen und Fehler.
- `HANDOFF_<id>.md`: automatisch erstellter Bericht mit Parametern und Check-Protokollen.

Kontrollieren: Sind Basen und Wege verständlich? Gibt es harte Übergänge, sichtbare Symmetrienähte,
ungewollte Plateaus oder zu enge Durchgänge? Liegen Ressourcen vernünftig? Mindestens eine Vorschau
vergrößert ansehen. Danach im Briefing `visual_review` auf `true` setzen. Dieses Review-Flag allein
macht einen geometrischen Testbericht nicht veraltet; Änderungen am Code oder am Design-Briefing
erfordern einen neuen Vollcheck. Reine Registrierung und Wasserzeichen-Zuordnung sind davon
ausgenommen: Die Integration eines geprüften Templates macht die Berichte der übrigen Templates
eines Batches nicht automatisch veraltet. Diese Zuordnungen prüft zusätzlich die Release-Stufe.

Automatische Prüfungen bestätigen weder gutes Balancing noch ein optisch gelungenes Layout.

### 6. Kontrolliert integrieren

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow integrate three_lanes
```

Der Befehl verlangt ein ausgefülltes Design-Briefing, Sichtfreigabe und einen aktuellen vollständigen
PASS-Bericht am Standard-Ausgabeort. Er ergänzt Import und Registrierung, vergibt den nächsten
freien stabilen Wasserzeichen-Code und übernimmt die Galerie-Miniatur. Bestehende Codes werden
nicht umnummeriert. Unvollständige, fehlgeschlagene oder nach Codeänderungen veraltete Berichte
werden zurückgewiesen. Änderungen anschließend als normalen Code-Diff prüfen.

### 7. Export und Regression als letzte technische Schranke

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes --level release
```

Diese Stufe wiederholt den Vollcheck, verlangt Briefing und Sichtfreigabe, prüft die dauerhafte
Registrierung und den Wasserzeichen-Code, baut eine echte Karte in der kleinsten regulären Größe
und kontrolliert deren Wasserzeichen. Außerdem läuft die **gesamte pytest-Suite**; deren Ausgabe
steht in `pytest.log`. Ein nicht erfolgreiches Ergebnis liefert einen Fehlercode und bleibt FAIL.

Diese technische Prüfung lädt keine Karte automatisch in eine laufende Zero-K-Partie. Vor einer
öffentlichen Empfehlung die Karte im Spiel ansehen und mindestens einen passenden Spieltest
durchführen. Ergebnis und Schwächen im Briefing dokumentieren; `in_game_tested` nur nach einem
tatsächlichen Test setzen. Ohne Spieltest wird das im Handoff ausdrücklich als nicht getestet ausgewiesen.

Ein neuer Template-Eintrag ist noch keine Veröffentlichung einer neuen App-Version. Release-Build,
Veröffentlichung und Ankündigung bleiben separate Schritte.

## Mehrere Templates effizient bearbeiten

```powershell
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes fortress dunes --level quick
.\.venv\Scripts\python.exe -m tools.template_workflow check three_lanes fortress dunes --level full
```

Der Batch läuft bewusst nacheinander und beendet sich mit Fehler, sobald mindestens ein Ergebnis
fehlgeschlagen ist; die übrigen angegebenen Templates werden trotzdem geprüft. Pro Template gibt
es eigene Dateien und Berichte. Keine gemeinsamen Registry-Änderungen während des Entwurfs.

Praktisch: Erst zwei bis drei unterschiedliche Konzepte in einer Familie erproben. Einen guten
Entwurf fertigstellen, danach seine wiederverwendbaren Erfahrungen in die nächste Runde übernehmen.
Das vermeidet eine große Sammlung ähnlicher, ungeprüfter Karten.

## Abnahmekriterien

- Ein unterscheidbares Gameplay und verständliche englische Beschreibung.
- Standard-Seeds und sichere Parametergrenzen erfolgreich.
- Erweiterte Einstellungen ohne Absturz, Fehlerfälle nachvollziehbar dokumentiert.
- Symmetrie und Wirtschaft passend zum Spielmodus.
- Vorschauen geprüft, Handoff und Miniatur vorhanden.
- Registrierung und stabiles Wasserzeichen korrekt.
- Vollständiger Kartenexport und gesamte Testsuite erfolgreich.
- Ergebnis eines tatsächlichen Spieltests oder ausdrücklich benannte Einschränkung.

## Baseline und Capability-Prüfungen

Der Baseline-Testlauf vom 22. Oktober 2026 scheiterte bereits vor diesen Änderungen an
`tests/test_naval_checks.py::test_ship_depth_uses_heavy_ship_limit`: Im aktuellen Core fehlt
`unit_masks(...)["ships"]`. Zu diesem Zeitpunkt fehlten auch die Naval-Felder in `Design`, obwohl
Naval-Dateien und frühere Tests vorhanden waren. Während der Arbeit wurde der Core-Stand außerhalb
der Workflow-Änderungen aktualisiert: Die Naval-Unterstützung und Registrierung sind wieder vorhanden,
und der Archipelago-Quickcheck besteht. Die Capability-Prüfung bleibt erhalten, damit fehlende
Unterstützung künftig als Blocker auffällt. Ein fehlgeschlagener Gesamtlauf wird nicht durch
Auslassen von Tests grün gemacht.
