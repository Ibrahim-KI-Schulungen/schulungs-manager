"""
Angebots-Pipeline Modul für Schulungs-Manager
Verwaltet Angebote von Bestätigung bis Rechnungsstellung
"""

import streamlit as st
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
import json
import base64

# Supabase Konfiguration
def get_supabase_config():
    """Holt Supabase-Konfiguration aus secrets oder env"""
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        import os
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
    return url, key


def supabase_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Führt Supabase REST API Request aus"""
    url, key = get_supabase_config()
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    full_url = f"{url}/rest/v1/{endpoint}"

    try:
        if method == "GET":
            r = requests.get(full_url, headers=headers, timeout=10)
        elif method == "POST":
            r = requests.post(full_url, headers=headers, json=data, timeout=10)
        elif method == "PATCH":
            r = requests.patch(full_url, headers=headers, json=data, timeout=10)
        elif method == "DELETE":
            r = requests.delete(full_url, headers=headers, timeout=10)

        if r.status_code in [200, 201, 204]:
            return {"success": True, "data": r.json() if r.text else []}
        else:
            return {"success": False, "error": f"Status {r.status_code}: {r.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_angebote(status_filter: str = None) -> List[dict]:
    """Holt alle Angebote, optional gefiltert nach Status"""
    endpoint = "angebote?select=*&order=created_at.desc"
    if status_filter:
        endpoint += f"&status=eq.{status_filter}"

    result = supabase_request("GET", endpoint)
    return result.get("data", []) if result.get("success") else []


def create_angebot(data: dict) -> dict:
    """Erstellt neues Angebot"""
    return supabase_request("POST", "angebote", data)


def update_angebot(angebot_id: str, data: dict) -> dict:
    """Aktualisiert ein Angebot"""
    return supabase_request("PATCH", f"angebote?id=eq.{angebot_id}", data)


def delete_angebot(angebot_id: str) -> dict:
    """Löscht ein Angebot"""
    return supabase_request("DELETE", f"angebote?id=eq.{angebot_id}")


def auto_update_status():
    """Aktualisiert Status automatisch wenn Schulungsdatum erreicht"""
    heute = date.today().isoformat()
    # Alle mit status='termin_steht' und schulung_datum <= heute
    endpoint = f"angebote?status=eq.termin_steht&schulung_datum=lte.{heute}"
    result = supabase_request("GET", endpoint)

    if result.get("success"):
        for angebot in result.get("data", []):
            update_angebot(angebot["id"], {"status": "rechnung_faellig"})


def extract_pdf_with_claude(pdf_content: bytes) -> dict:
    """Extrahiert Daten aus PDF mit Claude API"""
    try:
        import anthropic
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY", "")

        if not api_key:
            return {"success": False, "error": "ANTHROPIC_API_KEY nicht konfiguriert"}

        client = anthropic.Anthropic(api_key=api_key)

        # PDF als Base64
        pdf_base64 = base64.standard_b64encode(pdf_content).decode("utf-8")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extrahiere aus diesem Angebot/Dokument folgende Informationen:
- Kunde (Firmenname)
- Leistung (Was wird angeboten, z.B. "KI Schulung 2 Tage")
- Betrag (Netto-Betrag in Euro, nur Zahl)

Antworte NUR als JSON in diesem Format:
{"kunde": "...", "leistung": "...", "betrag": 1234.56}

Falls ein Wert nicht gefunden wird, setze null."""
                    }
                ]
            }]
        )

        # Parse JSON aus Antwort
        text = response.content[0].text
        # Finde JSON im Text
        import re
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            return {"success": True, "data": json.loads(json_match.group())}
        else:
            return {"success": False, "error": "Konnte keine Daten extrahieren"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_to_storage(file_content: bytes, filename: str, bucket: str = "angebote") -> dict:
    """Lädt Datei zu Supabase Storage hoch"""
    url, key = get_supabase_config()

    # Eindeutigen Dateinamen erstellen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{filename}"

    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/octet-stream'
    }

    try:
        upload_url = f"{url}/storage/v1/object/{bucket}/{unique_filename}"
        r = requests.post(upload_url, headers=headers, data=file_content, timeout=30)

        if r.status_code in [200, 201]:
            # Öffentliche URL erstellen
            public_url = f"{url}/storage/v1/object/public/{bucket}/{unique_filename}"
            return {"success": True, "url": public_url}
        else:
            return {"success": False, "error": f"Upload fehlgeschlagen: {r.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def render_status_card(angebot: dict, show_actions: bool = True):
    """Rendert eine Angebots-Karte"""
    status_colors = {
        "warte_termin": "#fbbf24",  # Gelb
        "termin_steht": "#34d399",   # Grün
        "rechnung_faellig": "#f87171",  # Rot
        "erledigt": "#9ca3af"  # Grau
    }

    status_labels = {
        "warte_termin": "Warte auf Termin",
        "termin_steht": "Termin steht",
        "rechnung_faellig": "Rechnung fällig",
        "erledigt": "Erledigt"
    }

    color = status_colors.get(angebot.get("status"), "#666")

    # Tage berechnen
    tage_info = ""
    if angebot.get("schulung_datum"):
        try:
            schulung = datetime.strptime(angebot["schulung_datum"], "%Y-%m-%d").date()
            diff = (schulung - date.today()).days
            if diff > 0:
                tage_info = f"Noch {diff} Tage"
            elif diff == 0:
                tage_info = "Heute!"
            else:
                tage_info = f"Vor {abs(diff)} Tagen"
        except (ValueError, TypeError):
            tage_info = ""

    # Rechnungsdaten vorhanden?
    rechnungsdaten_ok = bool(angebot.get("rechnungs_email"))

    st.markdown(f"""
    <div style="background: #1f1f33; border-left: 4px solid {color}; padding: 15px; margin: 10px 0; border-radius: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: #fff; font-size: 1.1em;">{angebot.get('kunde', 'Unbekannt')}</strong>
                <span style="color: {color}; margin-left: 10px; font-size: 0.9em;">{angebot.get('betrag', 0):,.2f} €</span>
            </div>
            <span style="background: {color}; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">
                {status_labels.get(angebot.get('status'), 'Unbekannt')}
            </span>
        </div>
        <div style="color: #9ca3af; margin-top: 8px; font-size: 0.9em;">
            {angebot.get('leistung', '-')}
        </div>
        <div style="display: flex; gap: 20px; margin-top: 8px; color: #6b7280; font-size: 0.85em;">
            <span>📅 {angebot.get('schulung_datum', 'Termin offen')} {tage_info}</span>
            <span>{'✅' if rechnungsdaten_ok else '⚠️'} Rechnungsdaten</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return angebot


def render_angebots_pipeline():
    """Rendert die komplette Angebots-Pipeline Seite"""

    st.markdown("""
    <div class="welcome-header">
        <h2>Angebots-Pipeline</h2>
        <p>Verwalte Angebote von der Bestätigung bis zur Rechnung</p>
    </div>
    """, unsafe_allow_html=True)

    # Auto-Update Status
    auto_update_status()

    # Aktionen
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("➕ Neues Angebot erfassen", use_container_width=True, type="primary"):
            st.session_state.show_angebot_modal = True

    # Alle Angebote laden
    angebote = get_angebote()

    # Nach Status gruppieren
    warte_termin = [a for a in angebote if a.get("status") == "warte_termin"]
    termin_steht = [a for a in angebote if a.get("status") == "termin_steht"]
    rechnung_faellig = [a for a in angebote if a.get("status") == "rechnung_faellig"]
    erledigt = [a for a in angebote if a.get("status") == "erledigt"]

    # Summen berechnen
    def calc_sum(liste):
        return sum(float(a.get("betrag", 0)) for a in liste)

    st.markdown("---")

    # Status-Bereiche
    # 1. WARTE AUF TERMIN
    with st.expander(f"🟡 WARTE AUF TERMIN ({len(warte_termin)}) — {calc_sum(warte_termin):,.2f} €", expanded=True):
        if warte_termin:
            # Sortiert nach erinnerung_datum
            warte_termin.sort(key=lambda x: x.get("erinnerung_datum") or "9999-99-99")
            for angebot in warte_termin:
                col1, col2 = st.columns([4, 1])
                with col1:
                    render_status_card(angebot)
                with col2:
                    if st.button("✏️", key=f"edit_{angebot['id']}", help="Bearbeiten"):
                        st.session_state.edit_angebot = angebot
                        st.session_state.show_angebot_modal = True
                    if st.button("📅", key=f"termin_{angebot['id']}", help="Termin setzen"):
                        st.session_state.set_termin_angebot = angebot
        else:
            st.info("Keine offenen Angebote")

    # 2. TERMIN STEHT
    with st.expander(f"🟢 TERMIN STEHT ({len(termin_steht)}) — {calc_sum(termin_steht):,.2f} €", expanded=True):
        if termin_steht:
            termin_steht.sort(key=lambda x: x.get("schulung_datum") or "9999-99-99")
            for angebot in termin_steht:
                col1, col2 = st.columns([4, 1])
                with col1:
                    render_status_card(angebot)
                with col2:
                    if st.button("✏️", key=f"edit2_{angebot['id']}", help="Bearbeiten"):
                        st.session_state.edit_angebot = angebot
                        st.session_state.show_angebot_modal = True
        else:
            st.info("Keine Termine geplant")

    # 3. RECHNUNG FÄLLIG
    with st.expander(f"🔴 RECHNUNG FÄLLIG ({len(rechnung_faellig)}) — {calc_sum(rechnung_faellig):,.2f} €", expanded=True):
        if rechnung_faellig:
            for angebot in rechnung_faellig:
                col1, col2 = st.columns([4, 1])
                with col1:
                    render_status_card(angebot)
                with col2:
                    if st.button("📧", key=f"mail_{angebot['id']}", help="Mail-Vorlage"):
                        st.session_state.show_mail_modal = angebot
                    if st.button("✅", key=f"done_{angebot['id']}", help="Erledigt"):
                        update_angebot(angebot["id"], {"status": "erledigt"})
                        st.rerun()
        else:
            st.success("Keine fälligen Rechnungen")

    # 4. ERLEDIGT (zugeklappt)
    with st.expander(f"✅ ERLEDIGT ({len(erledigt)}) — {calc_sum(erledigt):,.2f} €", expanded=False):
        if erledigt:
            # Nach Monat gruppieren
            from collections import defaultdict
            by_month = defaultdict(list)
            for a in erledigt:
                month = a.get("created_at", "")[:7]  # YYYY-MM
                by_month[month].append(a)

            for month, items in sorted(by_month.items(), reverse=True):
                st.markdown(f"**{month}** ({len(items)} Angebote)")
                for angebot in items:
                    st.markdown(f"- {angebot.get('kunde')} — {angebot.get('betrag', 0):,.2f} €")
        else:
            st.info("Noch keine erledigten Angebote")

    # Modal: Angebot erfassen/bearbeiten
    if st.session_state.get("show_angebot_modal"):
        render_angebot_modal()

    # Modal: Termin setzen
    if st.session_state.get("set_termin_angebot"):
        render_termin_modal()

    # Modal: Mail-Vorlage
    if st.session_state.get("show_mail_modal"):
        render_mail_modal()


def render_angebot_modal():
    """Modal zum Erfassen/Bearbeiten eines Angebots"""

    edit_mode = st.session_state.get("edit_angebot") is not None
    angebot = st.session_state.get("edit_angebot", {})

    st.markdown("---")
    st.subheader("📑 Angebot bearbeiten" if edit_mode else "📑 Neues Angebot erfassen")

    with st.form("angebot_form"):
        # PDF Upload mit Extraktion
        if not edit_mode:
            st.markdown("**PDF hochladen (optional)**")
            pdf_file = st.file_uploader("Angebot-PDF für automatische Extraktion", type=["pdf"])

            if pdf_file and st.form_submit_button("🔍 Daten aus PDF extrahieren"):
                with st.spinner("Extrahiere Daten mit KI..."):
                    result = extract_pdf_with_claude(pdf_file.read())
                    if result.get("success"):
                        st.session_state.extracted_data = result.get("data", {})
                        st.success("Daten extrahiert!")
                    else:
                        st.error(f"Fehler: {result.get('error')}")

        # Extrahierte Daten als Default
        extracted = st.session_state.get("extracted_data", {})

        st.markdown("---")
        st.markdown("**Pflichtangaben**")

        col1, col2 = st.columns(2)
        with col1:
            kunde = st.text_input("Kunde *", value=angebot.get("kunde", extracted.get("kunde", "")))
            betrag = st.number_input("Betrag (€) *", value=float(angebot.get("betrag", extracted.get("betrag", 0)) or 0), min_value=0.0, step=100.0)
        with col2:
            leistung = st.text_input("Leistung *", value=angebot.get("leistung", extracted.get("leistung", "")))
            bestaetigt_am = st.date_input("Bestätigt am *", value=datetime.strptime(angebot.get("bestaetigt_am"), "%Y-%m-%d").date() if angebot.get("bestaetigt_am") else date.today())

        st.markdown("---")
        st.markdown("**Schulungstermin**")

        termin_bekannt = st.checkbox("Termin bereits bekannt", value=bool(angebot.get("schulung_datum")))

        col1, col2 = st.columns(2)
        with col1:
            if termin_bekannt:
                schulung_datum = st.date_input("Schulungsdatum", value=datetime.strptime(angebot.get("schulung_datum"), "%Y-%m-%d").date() if angebot.get("schulung_datum") else date.today() + timedelta(days=30))
            else:
                schulung_datum = None
                erinnerung_wochen = st.number_input("Erinnerung in X Wochen", value=2, min_value=1, max_value=12)
        with col2:
            schulung_zeitraum = st.text_input("Zeitraum (z.B. 'Q2 2026')", value=angebot.get("schulung_zeitraum", ""))

        st.markdown("---")
        st.markdown("**Rechnungsdaten** ⚠️ *Pflicht vor Rechnungsstellung*")

        col1, col2 = st.columns(2)
        with col1:
            rechnungs_email = st.text_input("Rechnungs-Email", value=angebot.get("rechnungs_email", ""))
            ansprechpartner = st.text_input("Ansprechpartner", value=angebot.get("ansprechpartner", ""))
        with col2:
            rechnungs_firma = st.text_input("Rechnungs-Firma", value=angebot.get("rechnungs_firma", ""))
            po_nummer = st.text_input("PO-Nummer", value=angebot.get("po_nummer", ""))

        st.markdown("---")
        notizen = st.text_area("Notizen", value=angebot.get("notizen", ""))

        col1, col2, col3 = st.columns(3)
        with col1:
            submitted = st.form_submit_button("💾 Speichern", type="primary", use_container_width=True)
        with col2:
            if edit_mode:
                delete = st.form_submit_button("🗑️ Löschen", use_container_width=True)
            else:
                delete = False
        with col3:
            cancel = st.form_submit_button("❌ Abbrechen", use_container_width=True)

        if submitted:
            if not kunde or not leistung or not betrag:
                st.error("Bitte alle Pflichtfelder ausfüllen")
            else:
                data = {
                    "kunde": kunde,
                    "leistung": leistung,
                    "betrag": betrag,
                    "bestaetigt_am": bestaetigt_am.isoformat(),
                    "schulung_datum": schulung_datum.isoformat() if schulung_datum else None,
                    "schulung_zeitraum": schulung_zeitraum or None,
                    "erinnerung_datum": (date.today() + timedelta(weeks=erinnerung_wochen)).isoformat() if not termin_bekannt else None,
                    "rechnungs_email": rechnungs_email or None,
                    "rechnungs_firma": rechnungs_firma or None,
                    "ansprechpartner": ansprechpartner or None,
                    "po_nummer": po_nummer or None,
                    "notizen": notizen or None,
                    "status": "termin_steht" if termin_bekannt else "warte_termin",
                    "updated_at": datetime.now().isoformat()
                }

                if edit_mode:
                    result = update_angebot(angebot["id"], data)
                else:
                    result = create_angebot(data)

                if result.get("success"):
                    st.success("Gespeichert!")
                    st.session_state.show_angebot_modal = False
                    st.session_state.edit_angebot = None
                    st.session_state.extracted_data = None
                    st.rerun()
                else:
                    st.error(f"Fehler: {result.get('error')}")

        if delete:
            result = delete_angebot(angebot["id"])
            if result.get("success"):
                st.session_state.show_angebot_modal = False
                st.session_state.edit_angebot = None
                st.rerun()

        if cancel:
            st.session_state.show_angebot_modal = False
            st.session_state.edit_angebot = None
            st.session_state.extracted_data = None
            st.rerun()


def render_termin_modal():
    """Modal zum schnellen Setzen eines Termins"""
    angebot = st.session_state.get("set_termin_angebot")

    st.markdown("---")
    st.subheader(f"📅 Termin setzen: {angebot.get('kunde')}")

    with st.form("termin_form"):
        schulung_datum = st.date_input("Schulungsdatum", value=date.today() + timedelta(days=30))

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Speichern", type="primary"):
                update_angebot(angebot["id"], {
                    "schulung_datum": schulung_datum.isoformat(),
                    "status": "termin_steht",
                    "erinnerung_datum": None
                })
                st.session_state.set_termin_angebot = None
                st.rerun()
        with col2:
            if st.form_submit_button("❌ Abbrechen"):
                st.session_state.set_termin_angebot = None
                st.rerun()


def render_mail_modal():
    """Modal mit Mail-Vorlage für Rechnung"""
    angebot = st.session_state.get("show_mail_modal")

    st.markdown("---")
    st.subheader(f"📧 Rechnungs-Mail: {angebot.get('kunde')}")

    # Mail-Details
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kunde:** {angebot.get('kunde')}")
        st.markdown(f"**Leistung:** {angebot.get('leistung')}")
        st.markdown(f"**Betrag:** {angebot.get('betrag', 0):,.2f} €")
    with col2:
        st.markdown(f"**Schulungsdatum:** {angebot.get('schulung_datum', '-')}")
        if angebot.get("po_nummer"):
            st.markdown(f"**PO-Nummer:** {angebot.get('po_nummer')}")

    # Rechnungs-Email kopieren
    email = angebot.get("rechnungs_email", "")
    if email:
        st.code(email)
        st.markdown("*Klicke auf den Code um zu kopieren*")
    else:
        st.warning("⚠️ Keine Rechnungs-Email hinterlegt!")

    # Mail-Vorlage
    st.markdown("---")
    st.markdown("**Mail-Vorlage:**")

    po_zeile = f"\nIhre Bestellnummer: {angebot.get('po_nummer')}" if angebot.get("po_nummer") else ""

    mail_text = f"""An: {email}
Betreff: Rechnung AI-Z / KI Schulungen - {angebot.get('leistung')} {angebot.get('schulung_datum', '')}

Sehr geehrte Damen und Herren,

anbei erhalten Sie die Rechnung für die durchgeführte Schulung "{angebot.get('leistung')}" am {angebot.get('schulung_datum', '[Datum]')}.

Rechnungsbetrag: {angebot.get('betrag', 0):,.2f} €{po_zeile}

Bei Rückfragen stehen wir Ihnen gerne zur Verfügung.

Mit freundlichen Grüßen
AI-Z / KI Schulungen Stuttgart"""

    st.code(mail_text, language=None)

    # Aktionen
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Rechnung gestellt", type="primary", use_container_width=True):
            update_angebot(angebot["id"], {"status": "erledigt"})
            st.session_state.show_mail_modal = None
            st.rerun()

    with col2:
        if angebot.get("angebot_pdf_url"):
            st.link_button("📄 Angebot öffnen", angebot.get("angebot_pdf_url"), use_container_width=True)

    with col3:
        if st.button("❌ Schließen", use_container_width=True):
            st.session_state.show_mail_modal = None
            st.rerun()


def get_pipeline_notifications() -> List[dict]:
    """Gibt Benachrichtigungen für Dashboard zurück"""
    notifications = []
    heute = date.today()

    # Fällige Rechnungen
    rechnung_faellig = get_angebote("rechnung_faellig")
    for a in rechnung_faellig:
        notifications.append({
            "type": "error",
            "icon": "🔴",
            "text": f"Rechnung fällig: {a.get('kunde')} — {a.get('betrag', 0):,.2f} €",
            "link": "angebots_pipeline"
        })

    # Erinnerungen
    angebote = get_angebote("warte_termin")
    for a in angebote:
        if a.get("erinnerung_datum"):
            try:
                erinnerung = datetime.strptime(a["erinnerung_datum"], "%Y-%m-%d").date()
                if erinnerung <= heute:
                    notifications.append({
                        "type": "warning",
                        "icon": "🟡",
                        "text": f"Termin nachfragen: {a.get('kunde')}",
                        "link": "angebots_pipeline"
                    })
            except (ValueError, TypeError):
                pass

    return notifications
