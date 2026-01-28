#!/usr/bin/env python3
"""
Feedback Integration Wrapper
Stellt eine einfache API für die Streamlit-App bereit.
Nutzt intern feedback_cli.py.
"""

import os
import sys

# Feedback CLI importieren
FEEDBACK_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FEEDBACK_PATH)

from feedback_cli import cmd_feedback, check_duplicate_schulung, get_trainer_id


def create_feedback(schulungsname: str, trainer: str, datum_iso: str, kunde: str = None) -> dict:
    """
    Erstellt einen Feedback-Link für eine Schulung.

    Args:
        schulungsname: Name der Schulung
        trainer: Name des Trainers
        datum_iso: Datum im Format YYYY-MM-DD
        kunde: Optional - Kunde/Firma (default: wird aus Schulungsname extrahiert oder leer)

    Returns:
        dict mit:
        - erfolg: bool
        - link: Feedback-URL
        - qr_pfad: Pfad zum QR-Code PNG
        - fehler: Fehlermeldung (wenn erfolg=False)
    """
    # Kunde ermitteln (falls nicht angegeben)
    if not kunde:
        kunde = schulungsname.split(" bei ")[-1] if " bei " in schulungsname else ""
        if not kunde:
            kunde = "Unbekannt"

    # feedback_cli aufrufen
    args = [schulungsname, kunde, trainer, datum_iso]
    result = cmd_feedback(args, return_result=True)

    if not result:
        return {"erfolg": False, "fehler": "Unbekannter Fehler"}

    if result.get("erfolg"):
        return {
            "erfolg": True,
            "link": result.get("link", ""),
            "qr_pfad": result.get("qr_path", ""),
            "schulung_id": result.get("schulung_id", ""),
            "folder_path": result.get("folder_path", ""),
            "trainer": result.get("trainer", trainer),
            "kunde": result.get("kunde", kunde),
            "warnung": result.get("warnung"),
            "bereits_vorhanden": result.get("bereits_vorhanden", False)
        }
    else:
        return {
            "erfolg": False,
            "fehler": result.get("fehler", "Unbekannter Fehler")
        }


def feedback_exists(datum_iso: str, schulungsname: str, trainer: str = None) -> bool:
    """
    Prüft ob bereits ein Feedback-Link für diese Schulung existiert.

    Args:
        datum_iso: Datum im Format YYYY-MM-DD
        schulungsname: Name der Schulung
        trainer: Optional - Trainer-Name für genauere Prüfung

    Returns:
        True wenn Feedback-Link bereits existiert
    """
    if not trainer:
        # Ohne Trainer können wir nicht genau prüfen
        return False

    try:
        # Trainer-ID holen
        trainer_id, _ = get_trainer_id(trainer, silent=True)
        if not trainer_id:
            return False

        # Duplikat prüfen
        existiert, _ = check_duplicate_schulung(schulungsname, trainer_id, datum_iso)
        return existiert
    except Exception:
        return False


# Für CLI-Kompatibilität
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        result = create_feedback(sys.argv[1], sys.argv[2], sys.argv[3])
        print(result)
    else:
        print("Verwendung: python feedback_integration.py \"Schulungsname\" \"Trainer\" \"YYYY-MM-DD\"")
