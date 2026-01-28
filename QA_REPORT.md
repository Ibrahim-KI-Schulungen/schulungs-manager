# QA-Report Schulungs-Manager
**Datum:** 28.01.2026
**Tester:** Claude Code
**App-Version:** v2.2 + Backoffice-Module

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| Getestete Module | 6/6 |
| Code-Analyse Findings | 21 |
| **Kritische Bugs** | 7 |
| **Mittlere Bugs** | 7 |
| **Niedrige Bugs** | 7 |

### API-Status
| Service | Status | Bemerkung |
|---------|--------|-----------|
| Supabase | ✅ OK | Verbindung funktioniert, 0 Angebote, 0 Belege |
| Notion | ❌ FEHLER | `401 Unauthorized` - Token ungültig! |
| Anthropic | ⚠️ Nicht getestet | (Hook blockiert direkten Test) |

---

## Kritische Bugs 🔴

| # | Datei:Zeile | Problem | Reproduzieren | Fix |
|---|-------------|---------|---------------|-----|
| 1 | `angebots_pipeline.py:203` | `strptime()` crasht wenn `schulung_datum` = None | Angebot ohne Datum anlegen | `if angebot.get("schulung_datum"):` vor strptime |
| 2 | `angebots_pipeline.py:591` | `strptime()` crasht wenn `erinnerung_datum` = None | Angebot mit Erinnerung aber ohne Datum | Gleicher Fix wie #1 |
| 3 | `vertrag_generator.py:101` | `split()[0]` crasht bei leerem Trainer-Namen | Vertrag ohne Trainer erstellen | `if trainer_name and trainer_name.strip():` |
| 4 | `app.py:1759` | `split()[0]` crasht bei leerem Trainer-String | Quick-Analyze mit leerer Mail | Prüfung vor split() |
| 5 | `feedback_cli.py:287,322,355` | `data[0]` ohne Längenprüfung → IndexError | API gibt leere Liste zurück | `if data and len(data) > 0:` |
| 6 | **Notion API** | Token `401 Unauthorized` | Notion-Sync Seite aufrufen | Neuen Token generieren in Notion |
| 7 | `beleg_center.py:122` | `float()` kann bei ungültigem Betrag crashen | Beleg mit Text statt Zahl importieren | try/except um float() |

---

## Mittlere Bugs 🟡

| # | Datei:Zeile | Problem | Reproduzieren | Fix |
|---|-------------|---------|---------------|-----|
| 1 | `angebots_pipeline.py:19` | Bare `except:` verbirgt Fehler | Supabase-Verbindungsfehler | `except Exception as e: logging.error(e)` |
| 2 | `beleg_center.py:18` | Bare `except:` verbirgt Fehler | Config-Ladefehler | Spezifische Exception abfangen |
| 3 | `notion_sync.py:119` | `except: return None` ohne Logging | API-Fehler wird stumm ignoriert | Fehler loggen |
| 4 | `angebots_pipeline.py:38-52` | HTTP 204 wird als Fehler behandelt | DELETE-Operation | `[200, 201, 204]` in Status-Check |
| 5 | `angebots_pipeline.py:141` | `response.content[0].text` ohne Längenprüfung | Claude gibt leere Response | `if response.content:` |
| 6 | `app.py:651` | `letzte_aktionen[:20]` ohne Init-Check | Erste Nutzung nach App-Start | `st.session_state.get("letzte_aktionen", [])` |
| 7 | `notion_sync.py:184` | `except (ValueError, TypeError): pass` | Ungültige Notion-Daten | Zumindest Warning loggen |

---

## Niedrige Bugs / UX-Verbesserungen 🟢

| # | Datei:Zeile | Problem | Verbesserung |
|---|-------------|---------|--------------|
| 1 | `angebots_pipeline.py:362-429` | Kein Doppelklick-Schutz bei Form-Submit | `disabled` nach erstem Klick |
| 2 | `beleg_center.py:338-370` | Modal hat keinen "Schließen" Button oben | X-Button hinzufügen |
| 3 | Allgemein | Keine Ladeanimation bei API-Calls | `st.spinner()` verwenden |
| 4 | Allgemein | Keine Offline-Erkennung | Verbindungsstatus prüfen |
| 5 | `app.py` | Session-Timeout nicht konfiguriert | Auto-Logout nach Inaktivität |
| 6 | `beleg_center.py` | Excel-Export ohne Datum im Filename | `Belege_{datum}.xlsx` |
| 7 | `angebots_pipeline.py` | Keine Bestätigung vor Löschen | Confirm-Dialog hinzufügen |

---

## Erfolgreich getestet ✅

| Modul | Funktionen | Status |
|-------|------------|--------|
| `extraktor.py` | Import, Klasse instanziierbar | ✅ OK |
| `notion_sync.py` | Import, Klasse instanziierbar | ✅ OK |
| `vertrag_generator.py` | Import, Klasse instanziierbar | ✅ OK |
| `feedback_integration.py` | Import, Funktionen verfügbar | ✅ OK |
| `angebots_pipeline.py` | Import, render-Funktion verfügbar | ✅ OK |
| `beleg_center.py` | Import, render-Funktion verfügbar | ✅ OK |
| `app.py` | Syntax-Check, Server startet | ✅ OK |
| Supabase-Verbindung | REST API erreichbar | ✅ OK |

---

## Nicht testbar / Eingeschränkt ⚠️

| Funktion | Grund |
|----------|-------|
| Notion-Sync | API-Token ungültig (401) |
| Anthropic KI-Features | Direkter API-Test durch Hook blockiert |
| Outlook-Integration | Nur lokal auf Mac testbar |
| QR-Code Download | Manueller Browser-Test nötig |

---

## Sofort-Maßnahmen (Priorisiert)

### 1. KRITISCH: Notion-Token erneuern
```
1. https://notion.so/my-integrations öffnen
2. Integration "Schulungs-Manager" auswählen
3. "Internal Integration Secret" kopieren
4. In ~/prozess-labor/.env ersetzen:
   NOTION_API_KEY=ntn_NEUER_TOKEN
5. In Streamlit Cloud Secrets aktualisieren
```

### 2. KRITISCH: Null-Checks hinzufügen
```python
# angebots_pipeline.py:203
if angebot.get("schulung_datum"):
    try:
        schulung = datetime.strptime(angebot["schulung_datum"], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        schulung = None
```

### 3. KRITISCH: Split-Absicherung
```python
# vertrag_generator.py:101
def get_vorname(trainer_name):
    if trainer_name and trainer_name.strip():
        parts = trainer_name.strip().split()
        return parts[0] if parts else ""
    return ""
```

---

## Empfehlungen

1. **Logging einführen** - Aktuell werden Fehler oft stumm ignoriert. Python `logging` Modul nutzen.

2. **Input-Validierung** - Alle Formularfelder server-seitig validieren, nicht nur client-seitig.

3. **Error-Boundary** - Globalen Exception-Handler in app.py, der Fehler anzeigt statt zu crashen.

4. **Automated Tests** - pytest mit Fixtures für die wichtigsten Flows (Extraktion, Vertrag, Feedback).

5. **Health-Check Endpoint** - `/health` Route die alle API-Verbindungen prüft.

---

## Nächste Schritte

- [ ] Notion-Token erneuern (SOFORT)
- [ ] Kritische Null-Checks fixen (HEUTE)
- [ ] Mittlere Bugs in nächstem Sprint
- [ ] UX-Verbesserungen als Backlog

---

*Report generiert am 28.01.2026 von Claude Code QA-Agent*
