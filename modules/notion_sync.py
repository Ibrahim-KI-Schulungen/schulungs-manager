#!/usr/bin/env python3
"""
Notion-Sync für Schulungs-Extraktor
Synchronisiert extrahierte Schulungsdaten mit Notion-Datenbank.
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv


class NotionSync:
    """Synchronisiert Schulungsdaten mit Notion."""

    # Feld-Mapping: Extraktor → Notion (echte Feldnamen aus Datenbank)
    # ACHTUNG: Manche Felder haben trailing spaces im Namen!
    # Felder MIT trailing space: "Status ", "Ansprechpartner Kunde "
    # Felder OHNE trailing space: "Held by", "Schulungsthema", "Akquiriert durch"
    FIELD_MAPPING = {
        "schulungsname": ("Name", "title"),
        "datum_start": ("Event time", "date"),
        "kunde": ("Firmenname", "text"),
        "firma_ort": ("Firmenname", "text"),  # Fallback wenn kunde nicht gesetzt
        "ansprechpartner_extern": ("Ansprechpartner Kunde ", "text"),  # trailing space!
        "tagessatz": ("Preis - Netto", "number"),
        "trainer_kosten": ("Kosten Trainer", "number"),
        "uhrzeit": ("Uhrzeit", "text"),
        "teilnehmeranzahl": ("Teilnehmeranzahl", "number"),
        "format": ("Remote/vor Ort", "select"),
        "auftraggeber": ("Akquiriert durch", "select"),
        "trainer": ("Held by", "select"),
        "reisekosten": ("Reisekosten", "multi_select"),
    }

    # Zusätzliche Felder die aus demselben Extraktor-Feld befüllt werden
    EXTRA_MAPPINGS = {
        "schulungsname": ("Schulungsthema", "select"),  # Zusätzlich zum Titel
    }

    # Select-Wert-Mapping: Extraktor-Wert → Notion-Option
    SELECT_MAPPINGS = {
        "format": {
            "Vor Ort": "vor Ort",
            "Remote": "Remote",
        },
        "auftraggeber": {
            "GFU Cyrus AG": "GFU",
            "NobleProg": "Nobleprog",
        },
        "trainer": {
            "Oumar Langer": "Oumar",
            # Alle anderen Trainer werden mit ihrem Namen neu angelegt
        },
        "reisekosten": {
            "inkl. im Tagessatz": "Im Angebot inkludiert",
        },
    }

    # Flexibel = neue Optionen können erstellt werden
    FLEXIBLE_SELECTS = ["auftraggeber", "trainer", "schulungsthema"]

    # Strikt = nur existierende Optionen, sonst Fallback
    STRICT_SELECTS = {
        "format": "vor Ort",
        "reisekosten": "Gemäß Trainer RK",
    }

    def __init__(self):
        self.api_key = None
        self.database_id = None
        self.base_url = "https://api.notion.com/v1"
        self.headers = {}
        self._lade_config()

    def _lade_config(self):
        """Lädt API-Konfiguration aus .env Datei."""
        env_path = os.path.expanduser("~/prozess-labor/.env")

        if not os.path.exists(env_path):
            raise FileNotFoundError(
                f"⚠ Konfigurationsfehler: .env Datei nicht gefunden!\n"
                f"  Erwartet unter: {env_path}\n"
                f"  Bitte erstelle die Datei mit:\n"
                f"    NOTION_API_KEY=dein_key\n"
                f"    NOTION_DATABASE_ID=deine_db_id"
            )

        load_dotenv(env_path)

        self.api_key = os.getenv("NOTION_API_KEY")
        self.database_id = os.getenv("NOTION_DATABASE_ID")

        if not self.api_key:
            raise ValueError("⚠ NOTION_API_KEY fehlt in .env Datei!")
        if not self.database_id:
            raise ValueError("⚠ NOTION_DATABASE_ID fehlt in .env Datei!")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def _konvertiere_datum(self, datum_str: str) -> Optional[str]:
        """Konvertiert deutsches Datum DD.MM.YYYY zu ISO-Format YYYY-MM-DD."""
        if not datum_str:
            return None
        try:
            parts = datum_str.split('.')
            if len(parts) == 3:
                tag = parts[0].zfill(2)
                monat = parts[1].zfill(2)
                jahr = parts[2]
                return f"{jahr}-{monat}-{tag}"
            return None
        except:
            return None

    def _hole_select_wert(self, feld: str, wert: Any) -> Optional[str]:
        """Ermittelt den korrekten Select-Wert für Notion."""
        if wert is None:
            return None

        wert_str = str(wert)
        mapping = self.SELECT_MAPPINGS.get(feld, {})

        # Direktes Mapping vorhanden?
        if wert_str in mapping:
            return mapping[wert_str]

        # Flexibles Feld: Wert direkt verwenden
        if feld in self.FLEXIBLE_SELECTS:
            return wert_str

        # Striktes Feld: Fallback verwenden
        if feld in self.STRICT_SELECTS:
            fallback = self.STRICT_SELECTS[feld]
            print(f"  ⚠ '{wert_str}' nicht in Notion-Optionen für '{feld}', nutze Fallback: '{fallback}'")
            return fallback

        return wert_str

    def _baue_properties(self, daten: Dict[str, Any]) -> Dict[str, Any]:
        """Baut Notion Properties aus extrahierten Daten."""
        properties = {}

        # Status immer auf "Angefragt" für neue Einträge
        # ACHTUNG: Feldname hat trailing space!
        properties["Status "] = {
            "status": {"name": "Angefragt"}
        }

        # Firmenname: Priorität kunde > firma_ort
        firmenname = daten.get("kunde") or daten.get("firma_ort")
        if firmenname:
            properties["Firmenname"] = {
                "rich_text": [{"text": {"content": str(firmenname)}}]
            }

        for extraktor_feld, (notion_feld, typ) in self.FIELD_MAPPING.items():
            # Firmenname bereits behandelt
            if notion_feld == "Firmenname":
                continue

            wert = daten.get(extraktor_feld)
            if wert is None:
                continue

            if typ == "title":
                properties[notion_feld] = {
                    "title": [{"text": {"content": str(wert)}}]
                }
            elif typ == "text":
                properties[notion_feld] = {
                    "rich_text": [{"text": {"content": str(wert)}}]
                }
            elif typ == "number":
                try:
                    properties[notion_feld] = {"number": float(wert)}
                except (ValueError, TypeError):
                    pass
            elif typ == "date":
                iso_datum_start = self._konvertiere_datum(wert)
                if iso_datum_start:
                    # Prüfe ob datum_ende vorhanden für Date-Range
                    datum_ende = daten.get("datum_ende")
                    iso_datum_ende = self._konvertiere_datum(datum_ende) if datum_ende else None

                    if iso_datum_ende and iso_datum_ende != iso_datum_start:
                        properties[notion_feld] = {
                            "date": {
                                "start": iso_datum_start,
                                "end": iso_datum_ende
                            }
                        }
                    else:
                        properties[notion_feld] = {
                            "date": {"start": iso_datum_start}
                        }
            elif typ == "select":
                select_wert = self._hole_select_wert(extraktor_feld, wert)
                if select_wert:
                    properties[notion_feld] = {
                        "select": {"name": select_wert}
                    }
            elif typ == "multi_select":
                select_wert = self._hole_select_wert(extraktor_feld, wert)
                if select_wert:
                    properties[notion_feld] = {
                        "multi_select": [{"name": select_wert}]
                    }

        # EXTRA_MAPPINGS verarbeiten (z.B. schulungsname → Schulungsthema)
        for extraktor_feld, (notion_feld, typ) in self.EXTRA_MAPPINGS.items():
            wert = daten.get(extraktor_feld)
            if wert is None:
                continue

            if typ == "select":
                # Für schulungsthema: Wert direkt als Option verwenden
                select_wert = self._hole_select_wert("schulungsthema", wert)
                if select_wert:
                    properties[notion_feld] = {
                        "select": {"name": select_wert}
                    }

        return properties

    def erstelle_eintrag(self, daten: Dict[str, Any]) -> Dict[str, Any]:
        """Erstellt einen neuen Eintrag in der Notion-Datenbank."""
        properties = self._baue_properties(daten)

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        try:
            response = requests.post(
                f"{self.base_url}/pages",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "erfolg": True,
                    "id": result.get("id"),
                    "url": result.get("url"),
                }
            else:
                error_data = response.json()
                error_msg = error_data.get("message", "Unbekannter Fehler")
                error_code = error_data.get("code", "unknown")

                # Verständliche deutsche Fehlermeldungen
                if error_code == "validation_error":
                    if "select" in error_msg.lower():
                        return {
                            "erfolg": False,
                            "fehler": f"Select-Feld Fehler: Eine Option existiert nicht in Notion.\n  Details: {error_msg}"
                        }
                    return {
                        "erfolg": False,
                        "fehler": f"Validierungsfehler: {error_msg}"
                    }
                elif error_code == "unauthorized":
                    return {
                        "erfolg": False,
                        "fehler": "API-Key ungültig oder keine Berechtigung für diese Datenbank."
                    }
                elif error_code == "object_not_found":
                    return {
                        "erfolg": False,
                        "fehler": "Datenbank nicht gefunden. Prüfe die NOTION_DATABASE_ID."
                    }
                else:
                    return {
                        "erfolg": False,
                        "fehler": f"Notion API Fehler ({error_code}): {error_msg}"
                    }

        except requests.exceptions.Timeout:
            return {
                "erfolg": False,
                "fehler": "Zeitüberschreitung bei Notion-Anfrage. Bitte später erneut versuchen."
            }
        except requests.exceptions.ConnectionError:
            return {
                "erfolg": False,
                "fehler": "Keine Verbindung zu Notion. Prüfe deine Internetverbindung."
            }
        except Exception as e:
            return {
                "erfolg": False,
                "fehler": f"Unerwarteter Fehler: {str(e)}"
            }

    def zeige_vorschau(self, daten: Dict[str, Any]):
        """Zeigt Vorschau der Notion-Felder."""
        print("\n" + "-" * 60)
        print("NOTION VORSCHAU")
        print("-" * 60)

        properties = self._baue_properties(daten)

        for notion_feld, prop in properties.items():
            if "title" in prop:
                wert = prop["title"][0]["text"]["content"]
            elif "rich_text" in prop:
                wert = prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else ""
            elif "number" in prop:
                wert = prop["number"]
            elif "date" in prop:
                wert = prop["date"]["start"]
            elif "select" in prop:
                wert = prop["select"]["name"]
            elif "status" in prop:
                wert = prop["status"]["name"]
            else:
                wert = str(prop)

            print(f"  {notion_feld}: {wert}")


def teste_verbindung():
    """Testet die Notion-Verbindung."""
    try:
        sync = NotionSync()
        print("✓ .env geladen")
        print(f"✓ API-Key: {sync.api_key[:20]}...")
        print(f"✓ Database-ID: {sync.database_id}")

        # Test-Anfrage
        response = requests.get(
            f"{sync.base_url}/databases/{sync.database_id}",
            headers=sync.headers,
            timeout=10
        )

        if response.status_code == 200:
            db_info = response.json()
            print(f"✓ Verbindung erfolgreich!")
            print(f"  Datenbank: {db_info.get('title', [{}])[0].get('plain_text', 'Unbekannt')}")
            return True
        else:
            print(f"✗ Fehler: {response.status_code}")
            print(f"  {response.json().get('message', 'Unbekannt')}")
            return False

    except Exception as e:
        print(f"✗ Fehler: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("NOTION SYNC - Verbindungstest")
    print("=" * 60)
    teste_verbindung()
