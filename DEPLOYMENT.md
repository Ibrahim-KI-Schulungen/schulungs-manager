# Deployment Anleitung - Schulungs-Manager

## Lokaler Test

```bash
cd ~/prozess-labor/03_umsetzung/schulungs-app
streamlit run app.py
```

Login: Passwort `aiz2026`

---

## Streamlit Cloud Deployment

### 1. GitHub Repository

Das Repository ist bereits erstellt unter:
**https://github.com/Ibrahim-KI-Schulungen/schulungs-manager**

### 2. Streamlit Cloud Setup

1. Gehe zu **https://share.streamlit.io**
2. Login mit GitHub Account
3. Klicke **"New app"**
4. Wähle:
   - **Repository:** schulungs-manager
   - **Branch:** main
   - **Main file path:** app.py
5. Klicke **"Advanced settings"**
6. Im **Secrets** Feld, füge ein:

```toml
APP_PASSWORD = "your-password-here"

NOTION_API_KEY = "your-notion-api-key"
NOTION_DATABASE_ID = "your-notion-database-id"

SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-anon-key"

ANTHROPIC_API_KEY = "your-anthropic-api-key"
```

**WICHTIG:** Die echten Keys findest du in `~/.streamlit/secrets.toml` (lokal) oder frag Ibrahim.

7. Klicke **"Deploy!"**

### 3. Nach dem Deployment

Die App ist erreichbar unter:
**https://[APP-NAME].streamlit.app**

---

## Updates deployen

```bash
cd ~/prozess-labor/03_umsetzung/schulungs-app
git add .
git commit -m "Update: [Beschreibung]"
git push
```

Streamlit Cloud deployed automatisch bei jedem Push.

---

## Troubleshooting

**App startet nicht:**
- Prüfe ob alle Secrets korrekt eingetragen sind
- Prüfe die Logs unter "Manage app" > "Logs"

**Module fehlen:**
- Prüfe requirements.txt
- Alle Module sollten in modules/ liegen

**Verträge funktionieren nicht:**
- Prüfe ob vorlagen/ mit .docx Dateien hochgeladen wurde

---

## Dateien im Repository

```
schulungs-app/
├── app.py              # Hauptanwendung
├── requirements.txt    # Python Dependencies
├── .gitignore          # Git Ignore Rules
├── DEPLOYMENT.md       # Diese Anleitung
├── modules/            # Python Module
│   ├── extraktor.py
│   ├── notion_sync.py
│   ├── vertrag_generator.py
│   ├── feedback_cli.py
│   ├── feedback_integration.py
│   └── config.json
└── vorlagen/           # Word-Vorlagen
    ├── Beauftragungsvertrag_Vorlage.docx
    └── Rahmenvertrag_Vorlage.docx
```

## Security

**NIEMALS echte API-Keys in Git committen!**

- Keys gehören nur in `.env` (lokal) und Streamlit Cloud Secrets (online)
- `.env` und `secrets.toml` sind in `.gitignore`
- Bei versehentlichem Commit: Keys sofort rotieren!
