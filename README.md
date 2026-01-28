# Schulungs-Manager Web-App

Streamlit-basiertes Interface für die Schulungsverwaltung.

## Installation

```bash
cd ~/prozess-labor/03_umsetzung/schulungs-app
pip3 install -r requirements.txt
```

## Starten

```bash
streamlit run app.py
```

Oder mit Port-Angabe:
```bash
streamlit run app.py --server.port 8501
```

## Funktionen

| Seite | Funktion |
|-------|----------|
| Email verarbeiten | Email einfügen → Daten extrahieren → Notion/Vertrag/Feedback |
| Notion-Sync | Manuell Schulung in Notion eintragen |
| Vertrag erstellen | Beauftragungsvertrag generieren |
| Feedback-Link | QR-Code + Feedback-Link erstellen |
| Trainer-Datenbank | Übersicht bekannter Trainer |
| Letzte Aktionen | Verlauf dieser Session |
| Einstellungen | Debug-Infos, Pfade, Status |

## Abhängigkeiten

Diese App nutzt die bestehenden Module:
- `~/prozess-labor/03_umsetzung/schulungs-extraktor/extraktor.py`
- `~/prozess-labor/03_umsetzung/schulungs-extraktor/notion_sync.py`
- `~/prozess-labor/03_umsetzung/schulungs-extraktor/vertrag_generator.py`
- `~/prozess-labor/03_umsetzung/feedback-system/feedback_integration.py`

## Konfiguration

Die App nutzt die bestehende `.env` unter `~/prozess-labor/.env`:
```
NOTION_API_KEY=...
NOTION_DATABASE_ID=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

## Fehlerbehebung

**Module nicht geladen:**
- Prüfe ob die Pfade korrekt sind
- Prüfe ob alle Abhängigkeiten installiert sind

**Notion-Fehler:**
- Prüfe die API-Keys in `.env`
- Prüfe die Notion-Datenbank-Berechtigungen

**Vertrag-Fehler:**
- Prüfe ob die Word-Vorlage existiert
- Prüfe ob `python-docx` installiert ist
