#!/usr/bin/env python3
"""
KI Schulungen - Feedback CLI Tool
Erstellt Schulungen und generiert Feedback-Links + QR-Codes

Version 3.1 - Cloud-kompatibel
"""

import sys
import os
import json
import random
import string
import re
import unicodedata
import tempfile
from datetime import datetime, timedelta
from urllib.parse import quote

# Secrets laden (erst st.secrets versuchen, dann .env)
def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return os.getenv(key, default)

# Lade Umgebungsvariablen aus .env (falls lokal)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/prozess-labor/.env"))
except ImportError:
    pass

# Supabase Konfiguration
SUPABASE_URL = _get_secret("SUPABASE_URL", "https://nzeqfkiaidskutgkpwcv.supabase.co")
SUPABASE_KEY = _get_secret("SUPABASE_KEY", "")

# Feedback-System URL
FEEDBACK_URL = "https://feedback-schulungen.vercel.app"

# Basis-Ordner für Feedbacks (Cloud: temp, Lokal: ~/feedbacks)
_local_feedbacks = os.path.expanduser("~/feedbacks")
IS_CLOUD = not os.path.exists(os.path.dirname(_local_feedbacks)) or os.path.exists("/mount")
FEEDBACKS_BASE_DIR = tempfile.mkdtemp() if IS_CLOUD else _local_feedbacks

# Timeout für Netzwerk-Anfragen (in Sekunden)
NETWORK_TIMEOUT = 10

# Deutsche Monatsnamen
MONATSNAMEN = {
    1: "01-Januar",
    2: "02-Februar",
    3: "03-März",
    4: "04-April",
    5: "05-Mai",
    6: "06-Juni",
    7: "07-Juli",
    8: "08-August",
    9: "09-September",
    10: "10-Oktober",
    11: "11-November",
    12: "12-Dezember"
}

# Umlaut-Ersetzungen für Ordnernamen
UMLAUT_MAP = {
    'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
    'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
}


def generate_id(length=6):
    """Generiert eine zufällige ID für die Schulung"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def replace_umlauts(text):
    """Ersetzt deutsche Umlaute durch ASCII-Äquivalente"""
    for umlaut, replacement in UMLAUT_MAP.items():
        text = text.replace(umlaut, replacement)
    return text


def sanitize_folder_name(name):
    """
    Erstellt einen sicheren Ordnernamen.
    Umlaute werden ersetzt, Sonderzeichen entfernt.
    """
    # Erst Umlaute ersetzen
    safe_name = replace_umlauts(name)
    # Leerzeichen durch Unterstriche
    safe_name = safe_name.replace(' ', '_')
    # Slashes durch Bindestriche
    safe_name = safe_name.replace('/', '-').replace('\\', '-')
    # Nur alphanumerische Zeichen, Unterstriche und Bindestriche behalten
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '_-')
    # Mehrfache Unterstriche/Bindestriche zusammenfassen
    safe_name = re.sub(r'[-_]+', '_', safe_name)
    # Führende/nachfolgende Unterstriche entfernen
    safe_name = safe_name.strip('_-')
    return safe_name


def validate_datum(datum_str):
    """
    Validiert ein Datum im Format YYYY-MM-DD.

    Returns:
        tuple: (ist_gueltig: bool, datum: datetime oder None, warnung: str oder None)
    """
    if not datum_str or not datum_str.strip():
        return False, None, "Datum ist leer"

    datum_str = datum_str.strip()

    # Format prüfen
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', datum_str):
        return False, None, f"Ungültiges Datumsformat: '{datum_str}'. Erwartet: YYYY-MM-DD"

    # Parsen versuchen
    try:
        dt = datetime.strptime(datum_str, '%Y-%m-%d')
    except ValueError as e:
        return False, None, f"Ungültiges Datum: '{datum_str}' ({e})"

    # Warnung bei Vergangenheit
    heute = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if dt < heute:
        tage_vergangen = (heute - dt).days
        warnung = f"Datum liegt {tage_vergangen} Tag(e) in der Vergangenheit"
        return True, dt, warnung

    return True, dt, None


def validate_trainer_name(name):
    """
    Validiert den Trainer-Namen.

    Returns:
        tuple: (ist_gueltig: bool, bereinigter_name: str oder None, fehler: str oder None)
    """
    if not name or not name.strip():
        return False, None, "Trainer-Name ist leer"

    name = name.strip()

    # Mindestlänge
    if len(name) < 2:
        return False, None, "Trainer-Name zu kurz (mindestens 2 Zeichen)"

    # Normalisieren: Führende/nachfolgende Leerzeichen, mehrfache Leerzeichen
    name = ' '.join(name.split())

    return True, name, None


def validate_schulungsname(name):
    """
    Validiert den Schulungsnamen.

    Returns:
        tuple: (ist_gueltig: bool, bereinigter_name: str oder None, fehler: str oder None)
    """
    if not name or not name.strip():
        return False, None, "Schulungsname ist leer"

    name = name.strip()

    # Mindestlänge
    if len(name) < 3:
        return False, None, "Schulungsname zu kurz (mindestens 3 Zeichen)"

    # Normalisieren
    name = ' '.join(name.split())

    return True, name, None


def calculate_expires_at(datum_str):
    """
    Berechnet das Ablaufdatum: Schulungsdatum + 1 Tag, 18:00 Uhr.

    Args:
        datum_str: Datum im Format YYYY-MM-DD

    Returns:
        str: ISO-Format Datetime (YYYY-MM-DDTHH:MM:SS)
    """
    try:
        dt = datetime.strptime(datum_str, '%Y-%m-%d')
        expires = dt + timedelta(days=1)
        expires = expires.replace(hour=18, minute=0, second=0)
        return expires.strftime('%Y-%m-%dT%H:%M:%S')
    except ValueError:
        # Fallback: 7 Tage ab jetzt
        expires = datetime.now() + timedelta(days=7)
        return expires.strftime('%Y-%m-%dT%H:%M:%S')


def get_feedback_folder(datum, schulung_name):
    """
    Erstellt den Ordnerpfad für eine Schulung.
    Format: ~/feedbacks/JAHR/MM-Monatsname/DATUM_Schulungsname/
    """
    # Datum parsen (Format: YYYY-MM-DD)
    try:
        dt = datetime.strptime(datum, '%Y-%m-%d')
    except ValueError:
        dt = datetime.now()

    jahr = str(dt.year)
    monat = MONATSNAMEN.get(dt.month, f"{dt.month:02d}-Unbekannt")

    # Schulungsname für Ordner aufbereiten
    safe_name = sanitize_folder_name(schulung_name)
    ordner_name = f"{datum}_{safe_name}"

    return os.path.join(FEEDBACKS_BASE_DIR, jahr, monat, ordner_name)


def create_info_file(folder_path, schulung_name, kunde, trainer_name, datum, feedback_link, schulung_id, expires_at):
    """Erstellt eine info.txt im Feedback-Ordner"""
    info_path = os.path.join(folder_path, "info.txt")

    erstellt_am = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    content = f"""Schulungsname: {schulung_name}
Kunde/Firma: {kunde}
Trainer: {trainer_name}
Datum: {datum}
Schulung-ID: {schulung_id}
Feedback-Link: {feedback_link}
Erstellt am: {erstellt_am}
Läuft ab: {expires_at}
"""

    with open(info_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return info_path


def check_network_connection():
    """Prüft ob Supabase erreichbar ist"""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/",
            headers={'apikey': SUPABASE_KEY}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return True, None
    except urllib.error.URLError as e:
        return False, f"Netzwerkfehler: {e.reason}"
    except Exception as e:
        return False, f"Verbindungsfehler: {e}"


def check_duplicate_schulung(name, trainer_id, datum):
    """
    Prüft ob bereits eine Schulung mit gleichem Namen, Trainer und Datum existiert.

    Returns:
        tuple: (existiert: bool, schulung_id: str oder None)
    """
    import urllib.request
    import urllib.error

    # URL-encode den Namen für die Query
    encoded_name = quote(name, safe='')

    url = f"{SUPABASE_URL}/rest/v1/schulungen?name=eq.{encoded_name}&trainer_id=eq.{trainer_id}&datum=eq.{datum}&status=eq.aktiv&select=id,name"
    req = urllib.request.Request(url, headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return True, data[0]['id']
    except Exception:
        pass

    return False, None


def get_trainer_id(trainer_name, silent=False):
    """
    Holt die Trainer-ID aus der Datenbank oder erstellt neuen Trainer.

    Args:
        trainer_name: Name des Trainers
        silent: Wenn True, keine Print-Ausgaben

    Returns:
        tuple: (trainer_id, trainer_name) oder (None, None) bei Fehler
    """
    import urllib.request
    import urllib.error

    # URL-encode für Sonderzeichen und Umlaute
    encoded_name = quote(trainer_name, safe='')

    # Trainer suchen (case-insensitive)
    url = f"{SUPABASE_URL}/rest/v1/trainer?name=ilike.*{encoded_name}*&select=id,name"
    req = urllib.request.Request(url, headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return data[0]['id'], data[0]['name']
    except urllib.error.URLError as e:
        if not silent:
            print(f"   Netzwerkfehler bei Trainer-Suche: {e.reason}")
        return None, None
    except urllib.error.HTTPError as e:
        if not silent:
            print(f"   API-Fehler bei Trainer-Suche: {e.code} {e.reason}")
        return None, None
    except Exception as e:
        if not silent:
            print(f"   Fehler bei Trainer-Suche: {e}")
        # Weiter versuchen, neuen Trainer zu erstellen

    # Trainer nicht gefunden - neuen erstellen
    if not silent:
        print(f"   Trainer '{trainer_name}' nicht gefunden. Erstelle neuen Trainer...")

    url = f"{SUPABASE_URL}/rest/v1/trainer"
    payload = json.dumps({'name': trainer_name}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST', headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                if not silent:
                    print(f"   Trainer '{trainer_name}' erstellt (ID: {data[0]['id']})")
                return data[0]['id'], trainer_name
    except urllib.error.URLError as e:
        if not silent:
            print(f"   Netzwerkfehler beim Erstellen des Trainers: {e.reason}")
        return None, None
    except urllib.error.HTTPError as e:
        if not silent:
            print(f"   API-Fehler beim Erstellen des Trainers: {e.code} {e.reason}")
        return None, None
    except Exception as e:
        if not silent:
            print(f"   Fehler beim Erstellen des Trainers: {e}")
        return None, None

    return None, None


def create_schulung(name, kunde, trainer_id, datum, expires_at=None, silent=False):
    """
    Erstellt eine neue Schulung in der Datenbank.

    Args:
        name: Schulungsname
        kunde: Kunde/Firma
        trainer_id: ID des Trainers
        datum: Datum im Format YYYY-MM-DD
        expires_at: Ablaufzeitpunkt (wird lokal gespeichert, nicht in DB)
        silent: Wenn True, keine Print-Ausgaben

    Returns:
        str: Schulungs-ID oder None bei Fehler
    """
    import urllib.request
    import urllib.error

    schulung_id = generate_id()

    url = f"{SUPABASE_URL}/rest/v1/schulungen"
    payload = json.dumps({
        'id': schulung_id,
        'name': name,
        'kunde': kunde,
        'trainer_id': trainer_id,
        'datum': datum,
        'status': 'aktiv'
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, method='POST', headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return schulung_id
    except urllib.error.URLError as e:
        if not silent:
            print(f"   Netzwerkfehler beim Erstellen der Schulung: {e.reason}")
        return None
    except urllib.error.HTTPError as e:
        if not silent:
            print(f"   API-Fehler beim Erstellen der Schulung: {e.code} {e.reason}")
        return None
    except Exception as e:
        if not silent:
            print(f"   Fehler beim Erstellen der Schulung: {e}")
        return None

    return None


def generate_qr_code(url, folder_path):
    """Generiert einen QR-Code für die URL im angegebenen Ordner"""
    try:
        import qrcode

        # QR-Code erstellen
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1388C6", back_color="white")

        # Ordner erstellen falls nicht vorhanden
        os.makedirs(folder_path, exist_ok=True)

        # Speichern als qr-code.png
        filepath = os.path.join(folder_path, "qr-code.png")
        img.save(filepath)

        return filepath

    except ImportError:
        print("   QR-Code Bibliothek nicht installiert.")
        print("   Installiere mit: pip3 install qrcode[pil]")
        return None
    except Exception as e:
        print(f"   Fehler beim Erstellen des QR-Codes: {e}")
        return None


def copy_to_clipboard(text):
    """Kopiert Text in die Zwischenablage (macOS)"""
    try:
        import subprocess
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        return True
    except:
        return False


def validate_kunde(name):
    """
    Validiert den Kunden/Firma-Namen.

    Returns:
        tuple: (ist_gueltig: bool, bereinigter_name: str oder None, fehler: str oder None)
    """
    if not name or not name.strip():
        return False, None, "Kunde/Firma ist leer"

    name = name.strip()

    # Mindestlänge
    if len(name) < 2:
        return False, None, "Kunde/Firma zu kurz (mindestens 2 Zeichen)"

    # Normalisieren
    name = ' '.join(name.split())

    return True, name, None


def cmd_feedback(args, return_result=False):
    """
    Hauptbefehl: Erstellt Schulung und generiert Feedback-Link

    Args:
        args: Liste mit [schulungsname, kunde, trainername, datum (optional)]
        return_result: Wenn True, gibt Dict mit Ergebnis zurück statt zu printen

    Returns:
        Dict mit 'erfolg', 'link', 'qr_path', 'folder_path' wenn return_result=True
    """

    # === EINGABE-VALIDIERUNG ===

    if len(args) < 3:
        if return_result:
            return {'erfolg': False, 'fehler': 'Zu wenige Argumente'}
        print("")
        print("Verwendung: feedback \"Schulungsname\" \"Firma\" \"Trainer\" [\"YYYY-MM-DD\"]")
        print("")
        print("   Beispiel: feedback \"KI Workshop\" \"HAIX\" \"Oumar Langer\" \"2025-01-20\"")
        print("   Beispiel: feedback \"KI Einführung\" \"Bosch\" \"Max Müller\"")
        return

    # Schulungsname validieren
    gueltig, schulung_name, fehler = validate_schulungsname(args[0])
    if not gueltig:
        if return_result:
            return {'erfolg': False, 'fehler': fehler}
        print(f"   Fehler: {fehler}")
        return

    # Kunde validieren
    gueltig, kunde, fehler = validate_kunde(args[1])
    if not gueltig:
        if return_result:
            return {'erfolg': False, 'fehler': fehler}
        print(f"   Fehler: {fehler}")
        return

    # Trainer validieren
    gueltig, trainer_name, fehler = validate_trainer_name(args[2])
    if not gueltig:
        if return_result:
            return {'erfolg': False, 'fehler': fehler}
        print(f"   Fehler: {fehler}")
        return

    # Datum validieren
    datum_input = args[3] if len(args) > 3 else datetime.now().strftime('%Y-%m-%d')
    gueltig, datum_dt, warnung = validate_datum(datum_input)

    if not gueltig:
        if return_result:
            return {'erfolg': False, 'fehler': warnung}
        print(f"   Fehler: {warnung}")
        return

    datum = datum_dt.strftime('%Y-%m-%d')

    if not return_result:
        print("")
        print("Erstelle Feedback-Schulung...")
        print(f"   Schulung: {schulung_name}")
        print(f"   Kunde:    {kunde}")
        print(f"   Trainer:  {trainer_name}")
        print(f"   Datum:    {datum}")

        if warnung:
            print(f"   Warnung: {warnung}")
        print("")

    # === NETZWERK-CHECK ===

    erreichbar, netzwerk_fehler = check_network_connection()
    if not erreichbar:
        if return_result:
            return {'erfolg': False, 'fehler': f'Supabase nicht erreichbar: {netzwerk_fehler}'}
        print(f"   Supabase nicht erreichbar: {netzwerk_fehler}")
        print("   Bitte Internetverbindung prüfen.")
        return

    # === TRAINER HOLEN/ERSTELLEN ===

    trainer_id, trainer_actual_name = get_trainer_id(trainer_name, silent=return_result)
    if not trainer_id:
        if return_result:
            return {'erfolg': False, 'fehler': 'Trainer konnte nicht gefunden oder erstellt werden'}
        print("   Konnte Trainer nicht finden oder erstellen.")
        return

    # === DUPLIKAT-PRÜFUNG ===

    existiert, existierende_id = check_duplicate_schulung(schulung_name, trainer_id, datum)
    if existiert:
        folder_path = get_feedback_folder(datum, schulung_name)
        feedback_link = f"{FEEDBACK_URL}/s/{existierende_id}"

        if return_result:
            return {
                'erfolg': True,
                'schulung_id': existierende_id,
                'link': feedback_link,
                'folder_path': folder_path,
                'kunde': kunde,
                'trainer': trainer_actual_name,
                'warnung': 'Schulung existiert bereits',
                'bereits_vorhanden': True
            }

        print("   Schulung existiert bereits!")
        print(f"   ID: {existierende_id}")
        print(f"   Link: {feedback_link}")
        print("")
        print("   Verwende --list um alle Schulungen anzuzeigen.")
        return

    # === SCHULUNG ERSTELLEN ===

    expires_at = calculate_expires_at(datum)
    schulung_id = create_schulung(schulung_name, kunde, trainer_id, datum, expires_at, silent=return_result)

    if not schulung_id:
        if return_result:
            return {'erfolg': False, 'fehler': 'Schulung konnte nicht erstellt werden'}
        print("   Konnte Schulung nicht erstellen.")
        return

    # === FEEDBACK-LINK & ORDNER ===

    feedback_link = f"{FEEDBACK_URL}/s/{schulung_id}"
    folder_path = get_feedback_folder(datum, schulung_name)
    os.makedirs(folder_path, exist_ok=True)

    # QR-Code generieren
    qr_path = generate_qr_code(feedback_link, folder_path)

    # Info-Datei erstellen
    info_path = create_info_file(
        folder_path, schulung_name, kunde, trainer_actual_name,
        datum, feedback_link, schulung_id, expires_at
    )

    # Link in Zwischenablage
    copied = copy_to_clipboard(feedback_link)

    if return_result:
        return {
            'erfolg': True,
            'schulung_id': schulung_id,
            'link': feedback_link,
            'qr_path': qr_path,
            'folder_path': folder_path,
            'info_path': info_path,
            'kunde': kunde,
            'trainer': trainer_actual_name,
            'expires_at': expires_at
        }

    # === AUSGABE ===

    print("=" * 50)
    print("Schulung erstellt!")
    print("=" * 50)
    print("")
    print(f"   Schulung:   {schulung_name}")
    print(f"   Kunde:      {kunde}")
    print(f"   Trainer:    {trainer_actual_name}")
    print(f"   Datum:      {datum}")
    print(f"   ID:         {schulung_id}")
    print(f"   Läuft ab:   {expires_at}")
    print("")
    print(f"   Link:       {feedback_link}")

    if qr_path:
        print(f"   QR-Code:    {qr_path}")

    print(f"   Ordner:     {folder_path}")

    if copied:
        print("")
        print("   Link wurde in die Zwischenablage kopiert!")

    print("")


def cmd_list(args):
    """Listet alle aktiven Schulungen auf"""
    import urllib.request
    import urllib.error

    url = f"{SUPABASE_URL}/rest/v1/schulungen?status=eq.aktiv&select=id,name,kunde,datum,trainer:trainer_id(name)&order=datum.desc"
    req = urllib.request.Request(url, headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())

            if not data:
                print("")
                print("Keine aktiven Schulungen gefunden.")
                print("")
                return

            print("")
            print("Aktive Schulungen:")
            print("-" * 90)
            print(f"   {'ID':<8} | {'Datum':<12} | {'Kunde':<15} | {'Trainer':<15} | {'Schulung'}")
            print("-" * 90)

            for s in data:
                trainer_name = s['trainer']['name'] if s.get('trainer') else 'Unbekannt'
                kunde = s.get('kunde') or '-'
                print(f"   {s['id']:<8} | {s['datum']:<12} | {kunde:<15} | {trainer_name:<15} | {s['name']}")

            print("")

    except urllib.error.URLError as e:
        print(f"   Netzwerkfehler: {e.reason}")
    except Exception as e:
        print(f"   Fehler: {e}")


def cmd_close(args):
    """Schließt eine Schulung (kein Feedback mehr möglich)"""
    import urllib.request
    import urllib.error

    if len(args) < 1:
        print("")
        print("Verwendung: feedback --close SCHULUNG_ID")
        print("")
        return

    schulung_id = args[0].strip()

    if not schulung_id:
        print("   Fehler: Schulung-ID ist leer")
        return

    url = f"{SUPABASE_URL}/rest/v1/schulungen?id=eq.{schulung_id}"
    payload = json.dumps({'status': 'abgeschlossen'}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='PATCH', headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    })

    try:
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                print(f"   Schulung '{schulung_id}' wurde geschlossen.")
            else:
                print(f"   Fehler: Schulung '{schulung_id}' nicht gefunden oder keine Berechtigung.")
    except urllib.error.URLError as e:
        print(f"   Netzwerkfehler: {e.reason}")
    except Exception as e:
        print(f"   Fehler: {e}")


def main():
    if len(sys.argv) < 2:
        print("")
        print("KI Schulungen - Feedback Tool v3.0")
        print("=" * 45)
        print("")
        print("Verwendung:")
        print("  feedback \"Name\" \"Firma\" \"Trainer\" [\"Datum\"]")
        print("  feedback --list                              - Aktive Schulungen anzeigen")
        print("  feedback --close ID                          - Schulung schließen")
        print("")
        print("Beispiel:")
        print("  feedback \"KI Workshop\" \"HAIX\" \"Oumar Langer\" \"2025-02-15\"")
        print("")
        print("Datum-Format: YYYY-MM-DD (z.B. 2025-01-20)")
        print("")
        print("Ordnerstruktur:")
        print("  ~/feedbacks/JAHR/MM-Monat/DATUM_Name/")
        print("    qr-code.png")
        print("    info.txt")
        print("")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == 'feedback':
        if args and args[0] == '--list':
            cmd_list(args[1:])
        elif args and args[0] == '--close':
            cmd_close(args[1:])
        else:
            cmd_feedback(args)
    elif command == '--list':
        cmd_list(args)
    elif command == '--close':
        cmd_close(args)
    else:
        # Direkter Aufruf mit Schulungsname als erstes Argument
        cmd_feedback([command] + args)


if __name__ == '__main__':
    main()
