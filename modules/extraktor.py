#!/usr/bin/env python3
"""
Schulungs-Extraktor
Extrahiert strukturierte Daten aus E-Mail-Text für Trainer-Beauftragung.
Mit Konfiguration für interne/externe Unterscheidung.
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Aktuelles Jahr für Datumslogik (dynamisch)
AKTUELLES_JAHR = datetime.now().year


class SchulungsExtraktor:
    """Extrahiert Schulungsdaten aus E-Mail-Text."""

    def __init__(self, config_path: str = None):
        self.gefunden = {}
        self.nicht_gefunden = []
        self.config = self._lade_config(config_path)

    def _lade_config(self, config_path: str = None) -> Dict:
        """Lädt die Konfigurationsdatei."""
        if config_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'config.json')

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠ Warnung: config.json nicht gefunden unter {config_path}")
            return {
                "firma": {"namen": [], "domains": [], "adresse": ""},
                "interne_personen": [],
                "bekannte_trainer": [],
                "bekannte_auftraggeber": []
            }

    def _ist_interne_email(self, email: str) -> bool:
        """Prüft ob eine E-Mail-Adresse intern ist."""
        email_lower = email.lower()
        for domain in self.config.get("firma", {}).get("domains", []):
            if domain.lower() in email_lower:
                return True
        for person in self.config.get("interne_personen", []):
            for intern_email in person.get("emails", []):
                if intern_email.lower() == email_lower:
                    return True
        return False

    def _finde_interne_person(self, email: str) -> Optional[Dict]:
        """Findet interne Person anhand E-Mail."""
        email_lower = email.lower()
        for person in self.config.get("interne_personen", []):
            for intern_email in person.get("emails", []):
                if intern_email.lower() == email_lower:
                    return person
        return None

    def _ist_bekannter_trainer(self, name: str) -> Optional[Dict]:
        """Prüft ob ein Name ein bekannter Trainer ist und gibt den Eintrag zurück."""
        name_lower = name.lower().strip()
        for trainer in self.config.get("bekannte_trainer", []):
            if isinstance(trainer, str):
                if trainer.lower() == name_lower:
                    return {"name": trainer, "kurznamen": []}
            else:
                trainer_name = trainer.get("name", "")
                if trainer_name.lower() == name_lower:
                    return trainer
                for kurzname in trainer.get("kurznamen", []):
                    if kurzname.lower() == name_lower:
                        return trainer
        return None

    def _ist_interne_firma(self, name: str) -> bool:
        """Prüft ob ein Firmenname intern ist."""
        name_lower = name.lower()
        for firma_name in self.config.get("firma", {}).get("namen", []):
            if firma_name.lower() in name_lower or name_lower in firma_name.lower():
                return True
        return False

    def _finde_bekannten_auftraggeber(self, text: str) -> Optional[Dict]:
        """Findet bekannten Auftraggeber aus config."""
        text_lower = text.lower()
        for auftraggeber in self.config.get("bekannte_auftraggeber", []):
            for kurzname in auftraggeber.get("kurznamen", []):
                if kurzname.lower() in text_lower:
                    return auftraggeber
            for domain in auftraggeber.get("domains", []):
                if f"@{domain.lower()}" in text_lower:
                    return auftraggeber
        return None

    def extrahiere(self, text: str) -> Dict[str, Any]:
        """Hauptmethode: Extrahiert alle Felder aus dem Text."""
        self.gefunden = {}
        self.nicht_gefunden = []

        self._extrahiere_schulungsname(text)
        self._extrahiere_datum(text)
        self._extrahiere_uhrzeit(text)
        self._extrahiere_ort_und_adresse(text)
        self._extrahiere_format(text)
        self._extrahiere_alle_kontakte(text)
        self._extrahiere_teilnehmeranzahl(text)
        self._extrahiere_trainer(text)
        self._extrahiere_trainer_adresse(text)
        self._extrahiere_tagessatz(text)
        self._extrahiere_trainer_kosten(text)
        self._extrahiere_vorbereitungspauschale(text)
        self._extrahiere_reisekosten(text)
        self._extrahiere_auftraggeber_und_kunde(text)
        self._berechne_briefing_datum()

        return self.gefunden

    def _setze(self, feld: str, wert: Any):
        """Setzt ein Feld wenn Wert vorhanden."""
        if wert:
            self.gefunden[feld] = wert
        else:
            self.nicht_gefunden.append(feld)

    def _extrahiere_schulungsname(self, text: str):
        """Extrahiert Schulungsname aus Anführungszeichen oder 'Seminar' Kontext."""
        patterns = [
            r'[„""]([^„""]+)[„""]',
            r'Seminar\s+"([^"]+)"',
            r'Schulung\s+"([^"]+)"',
            r'Kurs\s+"([^"]+)"',
            r'Workshop\s+"([^"]+)"',
            r'Thema\s+"([^"]+)"',
            r'zum\s+Thema\s+"([^"]+)"',
            r'Betreff:.*?:\s*(.+?)(?:\n|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if len(name) > 5 and name.lower() not in ['re', 'aw', 'fwd']:
                    self._setze("schulungsname", name)
                    return
        self._setze("schulungsname", None)

    def _extrahiere_datum(self, text: str):
        """Extrahiert Datum mit intelligenter Jahreszahl-Logik."""
        patterns = [
            (r'vom\s+(\d{1,2}\.\d{1,2}\.?)(?:\d{0,4})?\s*(?:bis\s+(?:zum\s+)?)?(\d{1,2}\.\d{1,2}\.\d{2,4})', 'bereich'),
            (r'(\d{1,2}\.\d{1,2}\.?)\s*(?:bis|–|-)\s*(\d{1,2}\.\d{1,2}\.\d{2,4})', 'bereich'),
            (r'am\s+(\d{1,2}\.\d{1,2}\.\d{2,4})\s+und\s+(\d{1,2}\.\d{1,2}\.\d{2,4})', 'mehrere'),
            (r'am\s+(\d{1,2})\.(\d{1,2})\.\d{0,2}\s+und\s+(\d{1,2})\.(\d{1,2})\.(\d{2,4})', 'tage_separate'),
            (r'(\d{1,2})\.\s*und\s+(\d{1,2})\.\s*(Dezember|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November)\s*(\d{2,4})?', 'tage_monat'),
            (r'am\s+(\d{1,2}\.\d{1,2}\.\d{2,4})', 'einzel'),
            (r'(\d{1,2}\.\d{1,2}\.\d{4})', 'einzel'),
            (r'(\d{1,2}\.\d{1,2}\.\d{2})(?!\d)', 'einzel'),
        ]

        for pattern, typ in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if typ == 'bereich':
                    start = match.group(1).rstrip('.')
                    ende = match.group(2)
                    jahr = self._extrahiere_jahr(ende)
                    if jahr:
                        start_normalisiert = self._normalisiere_datum_mit_jahr(start, jahr)
                        ende_normalisiert = self._normalisiere_datum_mit_jahr(ende, jahr)
                        self._setze("datum_start", start_normalisiert)
                        self._setze("datum_ende", ende_normalisiert)
                        return
                elif typ == 'mehrere':
                    self._setze("datum_start", self._normalisiere_datum(match.group(1)))
                    self._setze("datum_ende", self._normalisiere_datum(match.group(2)))
                    return
                elif typ == 'tage_separate':
                    tag1, monat1 = match.group(1), match.group(2)
                    tag2, monat2, jahr = match.group(3), match.group(4), match.group(5)
                    jahr = self._normalisiere_jahr(jahr)
                    self._setze("datum_start", f"{int(tag1):02d}.{int(monat1):02d}.{jahr}")
                    self._setze("datum_ende", f"{int(tag2):02d}.{int(monat2):02d}.{jahr}")
                    return
                elif typ == 'tage_monat':
                    tag1 = match.group(1)
                    tag2 = match.group(2)
                    monat = match.group(3)
                    jahr = match.group(4) if match.group(4) else str(AKTUELLES_JAHR)
                    jahr = self._normalisiere_jahr(jahr)
                    monat_num = self._monat_zu_nummer(monat)
                    self._setze("datum_start", f"{int(tag1):02d}.{monat_num}.{jahr}")
                    self._setze("datum_ende", f"{int(tag2):02d}.{monat_num}.{jahr}")
                    return
                elif typ == 'einzel':
                    datum = self._normalisiere_datum(match.group(1))
                    self._setze("datum_start", datum)
                    self._setze("datum_ende", datum)
                    return

        self._setze("datum_start", None)
        self._setze("datum_ende", None)

    def _extrahiere_jahr(self, datum_str: str) -> Optional[str]:
        """Extrahiert Jahr aus Datumsstring."""
        match = re.search(r'\.(\d{2,4})$', datum_str)
        if match:
            return self._normalisiere_jahr(match.group(1))
        return None

    def _normalisiere_jahr(self, jahr: str) -> str:
        """Normalisiert 2-stelliges Jahr zu 4-stelligem."""
        if len(jahr) == 2:
            return '20' + jahr
        return jahr

    def _normalisiere_datum_mit_jahr(self, datum: str, jahr: str) -> str:
        """Normalisiert Datum und setzt Jahr wenn nicht vorhanden."""
        datum = datum.rstrip('.')
        parts = datum.split('.')
        if len(parts) >= 2:
            tag = int(parts[0])
            monat = int(parts[1])
            if len(parts) == 3 and parts[2]:
                jahr = self._normalisiere_jahr(parts[2])
            return f"{tag:02d}.{monat:02d}.{jahr}"
        return datum

    def _normalisiere_datum(self, datum: str) -> str:
        """Normalisiert Datum zu dd.mm.yyyy Format mit Plausibilitätsprüfung."""
        datum = datum.rstrip('.')
        parts = datum.split('.')

        if len(parts) >= 2:
            tag = int(parts[0])
            monat = int(parts[1])

            if len(parts) == 3 and parts[2]:
                jahr = self._normalisiere_jahr(parts[2])
            else:
                jahr = self._berechne_sinnvolles_jahr(tag, monat)

            jahr_int = int(jahr)
            if jahr_int < AKTUELLES_JAHR - 2:
                jahr = str(AKTUELLES_JAHR)

            return f"{tag:02d}.{monat:02d}.{jahr}"

        return datum

    def _berechne_sinnvolles_jahr(self, tag: int, monat: int) -> str:
        """Berechnet sinnvolles Jahr wenn keines angegeben."""
        heute = datetime(AKTUELLES_JAHR, 1, 16)
        try:
            datum_dieses_jahr = datetime(AKTUELLES_JAHR, monat, tag)
            if datum_dieses_jahr < heute - timedelta(days=30):
                return str(AKTUELLES_JAHR + 1)
            return str(AKTUELLES_JAHR)
        except ValueError:
            return str(AKTUELLES_JAHR)

    def _monat_zu_nummer(self, monat: str) -> str:
        """Konvertiert Monatsname zu Nummer."""
        monate = {
            'januar': '01', 'februar': '02', 'märz': '03', 'april': '04',
            'mai': '05', 'juni': '06', 'juli': '07', 'august': '08',
            'september': '09', 'oktober': '10', 'november': '11', 'dezember': '12'
        }
        return monate.get(monat.lower(), '01')

    def _extrahiere_uhrzeit(self, text: str):
        """Extrahiert Uhrzeiten."""
        patterns = [
            r'(\d{1,2}:\d{2})\s*(?:–|-|bis)\s*(\d{1,2}:\d{2})\s*Uhr',
            r'(\d{1,2}:\d{2})\s*Uhr\s*(?:–|-|bis)\s*(\d{1,2}:\d{2})\s*Uhr',
            r'(\d{1,2}\.\d{2})\s*(?:–|-|bis)\s*(\d{1,2}\.\d{2})\s*Uhr',
            r'(\d{1,2})\s*(?:–|-|bis)\s*(\d{1,2})\s*Uhr',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                start = match.group(1).replace('.', ':')
                ende = match.group(2).replace('.', ':')
                if ':' not in start:
                    start = f"{start}:00"
                if ':' not in ende:
                    ende = f"{ende}:00"
                self._setze("uhrzeit", f"{start} – {ende} Uhr")
                return
        self._setze("uhrzeit", None)

    def _extrahiere_ort_und_adresse(self, text: str):
        """Extrahiert Seminarort und Adresse."""
        ort_match = re.search(
            r'Seminarort:?\s*\n(.+?)(?=\n\s*\n|\nAnsprechpartner|\nTeilnehmer|\nTrainer|$)',
            text, re.DOTALL | re.IGNORECASE
        )
        if ort_match:
            adresse_block = ort_match.group(1).strip()
            zeilen = [z.strip() for z in adresse_block.split('\n') if z.strip()]
            if zeilen:
                self._setze("firma_ort", zeilen[0] if zeilen else None)
                if len(zeilen) > 1:
                    self._setze("adresse", '\n'.join(zeilen[1:]))
                return

        findet_match = re.search(
            r'findet\s+in\s+der\s+([^,]+),\s*(\d{4,5})\s+(\w+)\s+statt',
            text, re.IGNORECASE
        )
        if findet_match:
            strasse = findet_match.group(1).strip()
            plz = findet_match.group(2)
            ort = findet_match.group(3)
            self._setze("adresse", f"{strasse}, {plz} {ort}")
            self._setze("firma_ort", ort)
            return

        plz_match = re.search(r'(\d{4,5})\s+(\w+)', text)
        if plz_match:
            self._setze("adresse", f"{plz_match.group(1)} {plz_match.group(2)}")
        else:
            self._setze("firma_ort", None)
            self._setze("adresse", None)

    def _extrahiere_format(self, text: str):
        """Erkennt ob Remote oder Vor Ort. Seminarort überschreibt alles."""
        text_lower = text.lower()

        if re.search(r'seminarort:?\s*\n', text_lower):
            self._setze("format", "Vor Ort")
            return

        remote_keywords = ['online-seminar', 'online seminar', 'virtuell', 'remote training',
                          'remote', 'webinar', 'microsoft teams', 'zoom meeting']
        for keyword in remote_keywords:
            if keyword in text_lower:
                self._setze("format", "Remote")
                return

        vor_ort_keywords = ['vor ort', 'vor-ort', 'präsenz', 'findet in', 'stattfinden']
        for keyword in vor_ort_keywords:
            if keyword in text_lower:
                self._setze("format", "Vor Ort")
                return

        if self.gefunden.get("adresse") or self.gefunden.get("firma_ort"):
            self._setze("format", "Vor Ort")
        else:
            self._setze("format", None)

    def _extrahiere_alle_kontakte(self, text: str):
        """Extrahiert und kategorisiert alle Kontakte (intern/extern)."""
        alle_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)

        interne_emails = []
        externe_emails = []

        for email in alle_emails:
            if self._ist_interne_email(email):
                interne_emails.append(email)
            else:
                externe_emails.append(email)

        for email in interne_emails:
            person = self._finde_interne_person(email)
            if person:
                self._setze("absender_intern", f"{person['name']} ({person['rolle']})")
                self._setze("absender_email", email)
                break

        ansprechpartner_email = self._finde_ansprechpartner_email(text)
        if ansprechpartner_email and not self._ist_interne_email(ansprechpartner_email):
            self._setze("email_extern", ansprechpartner_email)
        elif externe_emails:
            for email in externe_emails:
                if not self._ist_auftraggeber_email(email):
                    self._setze("email_extern", email)
                    break
            else:
                self._setze("email_extern", externe_emails[0] if externe_emails else None)
        else:
            self._setze("email_extern", None)

        self._extrahiere_ansprechpartner_extern(text)
        self._extrahiere_telefon(text)

    def _ist_auftraggeber_email(self, email: str) -> bool:
        """Prüft ob E-Mail zu einem bekannten Auftraggeber gehört."""
        email_lower = email.lower()
        for auftraggeber in self.config.get("bekannte_auftraggeber", []):
            for domain in auftraggeber.get("domains", []):
                if f"@{domain.lower()}" in email_lower:
                    return True
        return False

    def _finde_ansprechpartner_email(self, text: str) -> Optional[str]:
        """Findet E-Mail-Adresse im Ansprechpartner-Block (höchste Priorität)."""
        ansprechpartner_match = re.search(
            r'Ansprechpartner:?\s*\n(.*?)(?=\n\s*\n|\nDie\s+GFU|\nSeminar|\nTeilnehmer|\nBitte|$)',
            text, re.DOTALL | re.IGNORECASE
        )
        if ansprechpartner_match:
            block = ansprechpartner_match.group(1)
            email_match = re.search(r'E-?Mail:?\s*([\w\.-]+@[\w\.-]+\.\w+)', block, re.IGNORECASE)
            if email_match:
                return email_match.group(1)
            email_fallback = re.search(r'([\w\.-]+@[\w\.-]+\.\w+)', block)
            if email_fallback:
                return email_fallback.group(1)
        return None

    def _extrahiere_ansprechpartner_extern(self, text: str):
        """Extrahiert externen Ansprechpartner mit vollem Namen."""
        patterns = [
            r'([A-Z][a-zäöü]+\s+[A-Z][a-zäöü]+)\s*\|\s*Team',
            r'Ansprechpartner:?\s*\n(?:.*?\n)*((?:Herr|Frau)\s+[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)',
            r'Ansprechpartner:?\s*((?:Herr|Frau)\s+[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)',
            r'Ansprechpartner:?\s*\n(?:.*?\n)*((?:Herr|Frau)\s+[A-ZÄÖÜ][a-zäöüß]+)',
            r'Ansprechpartner:?\s*((?:Herr|Frau)\s+[A-ZÄÖÜ][a-zäöüß]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                ist_intern = False
                for person in self.config.get("interne_personen", []):
                    if person["name"].lower() in name.lower():
                        ist_intern = True
                        break

                if not ist_intern:
                    self._setze("ansprechpartner_extern", name)
                    return

        self._setze("ansprechpartner_extern", None)

    def _extrahiere_telefon(self, text: str):
        """Extrahiert Telefonnummern."""
        patterns = [
            r'Telefon:?\s*([\d\s\-\/\+]+)',
            r'Tel\.?:?\s*([\d\s\-\/\+]+)',
            r'(\+\d{2}\s*\d{2,3}\s*\d{3,4}\s*\d{2,4}\s*\d{0,4})',
            r'(01\d{2,3}\s+\d{3,4}\s+\d{3,4})',
            r'(\+?\d{2,4}[\s\-]?\d{3,}[\s\-]?\d{3,})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                telefon = re.sub(r'\s+', ' ', match.group(1).strip())
                if len(telefon) >= 8:
                    self._setze("telefon", telefon)
                    return
        self._setze("telefon", None)

    def _extrahiere_teilnehmeranzahl(self, text: str):
        """Extrahiert Teilnehmeranzahl."""
        patterns = [
            r'(?:max\.?|maximal)\s*(\d+)\s*(?:Teilnehmer)?',
            r'Teilnehmeranzahl[:\s]+(?:max\.?\s*)?(\d+)',
            r'(\d+)\s*Teilnehmer',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self._setze("teilnehmeranzahl", int(match.group(1)))
                return
        self._setze("teilnehmeranzahl", None)

    def _extrahiere_trainer(self, text: str):
        """Extrahiert Trainer-Name mit Kurzname-Matching."""
        # Wichtig: Spezifischere Patterns zuerst!
        patterns = [
            # "für Lukas als Trainer kosten" → Lukas
            r'(?:für|mit)\s+([A-ZÄÖÜ][a-zäöüß]+)\s+als\s+Trainer',
            # "Lukas als Trainer"
            r'([A-ZÄÖÜ][a-zäöüß]+)\s+als\s+Trainer\s+kosten',
            # "Trainer Svend:" oder "Trainer: Max Mustermann"
            r'Trainer[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)',
            # Andere Patterns
            r'mit\s+([A-ZÄÖÜ][a-zäöüß]+)\s+gesprochen',
            r'Beauftragung\s+(?:an\s+)?(?:Trainer\s+)?([A-ZÄÖÜ][a-zäöüß]+)',
        ]

        stopwords = ['der', 'die', 'das', 'für', 'und', 'kosten', 'euro', 'trainer', 'herr', 'frau']

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                trainer = match.group(1).strip()
                if trainer.lower() not in stopwords:
                    bekannter_trainer = self._ist_bekannter_trainer(trainer)
                    if bekannter_trainer:
                        self._setze("trainer", bekannter_trainer["name"])
                        self._setze("trainer_bekannt", True)
                    else:
                        self._setze("trainer", trainer)
                        self._setze("trainer_bekannt", False)
                    return

        self._setze("trainer", None)
        self._setze("trainer_bekannt", None)

    def _extrahiere_trainer_adresse(self, text: str):
        """Extrahiert Trainer-Adresse (falls neuer Trainer)."""
        match = re.search(
            r'Trainer:?\s*\w+\s+\w+\s*\n\s*Adresse:?\s*(.+?\d{4,5}\s+\w+)',
            text, re.DOTALL | re.IGNORECASE
        )
        if match:
            adresse = match.group(1).replace('\n', ', ').strip()
            self._setze("trainer_adresse", adresse)
        else:
            self._setze("trainer_adresse", None)

    def _extrahiere_tagessatz(self, text: str):
        """Extrahiert Tagessatz (Einnahme/Gesamthonorar)."""
        patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:€|Euro)\s*inkl',
            r'Tagessatz\s*:?\s*(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?',
            r'(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?\s*(?:pro\s+Tag|\/\s*Tag|Tagessatz)',
            r'Satz\s+(?:von\s+)?(\d+(?:[.,]\d+)?)\s*(?:€|Euro)',
            r'(\d{3,})\s*(?:€|Euro)\s*gehen',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                betrag = match.group(1).replace(',', '.')
                self._setze("tagessatz", float(betrag))
                return
        self._setze("tagessatz", None)

    def _extrahiere_trainer_kosten(self, text: str):
        """Extrahiert Trainer-Kosten."""
        patterns = [
            r'Kosten\s+Trainer\s+(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?',
            r'(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?\s*(?:für\s+\w+\s+)?als\s+Trainer\s*kosten',
            r'(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?\s*(?:für|an)\s+(?:den\s+)?Trainer',
            r'Vergütung\s*:?\s*(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?(?:\s*pro\s+Tag)?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                betrag = match.group(1).replace(',', '.')
                self._setze("trainer_kosten", float(betrag))
                return
        self._setze("trainer_kosten", None)

    def _extrahiere_vorbereitungspauschale(self, text: str):
        """Extrahiert Vorbereitungspauschale."""
        patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?\s*(?:für\s+)?Vorbereitung',
            r'Vorbereitung(?:spauschale)?[:\s]+(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?',
            r'\+\s*(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?\s*(?:für\s+)?Vorbereitung',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                betrag = match.group(1).replace(',', '.')
                self._setze("vorbereitungspauschale", float(betrag))
                return
        self._setze("vorbereitungspauschale", None)

    def _extrahiere_reisekosten(self, text: str):
        """Extrahiert Reisekosten-Information."""
        patterns = [
            r'inkl\.?\s*Reisekosten',
            r'Reisekosten[:\s]+(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?',
            r'Fahrtkosten[:\s]+(\d+(?:[.,]\d+)?)\s*(?:€|Euro)?',
            r'(Fahrtkosten\s*\+?\s*Hotel\s*werden\s*erstattet)',
            r'(Reisekosten\s*werden\s*erstattet)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if 'inkl' in match.group(0).lower():
                    self._setze("reisekosten", "inkl. im Tagessatz")
                    return
                wert = match.group(1) if match.lastindex else match.group(0)
                if re.match(r'\d', wert):
                    self._setze("reisekosten", float(wert.replace(',', '.')))
                else:
                    self._setze("reisekosten", wert.strip())
                return
        self._setze("reisekosten", None)

    def _extrahiere_auftraggeber_und_kunde(self, text: str):
        """Extrahiert Auftraggeber (wer beauftragt) und Kunde (wo Schulung stattfindet)."""
        bekannter = self._finde_bekannten_auftraggeber(text)
        if bekannter:
            self._setze("auftraggeber", bekannter["name"])
        else:
            von_match = re.search(r'Von:\s*[^<]*<([^>]+)>', text)
            if von_match:
                absender_email = von_match.group(1)
                domain = absender_email.split('@')[-1].split('.')[0]
                if not self._ist_interne_email(absender_email):
                    self._setze("auftraggeber", domain.upper())
            else:
                self._setze("auftraggeber", None)

        firma_ort = self.gefunden.get("firma_ort")
        if firma_ort:
            self._setze("kunde", firma_ort)
        else:
            self._setze("kunde", None)

    def _berechne_briefing_datum(self):
        """Berechnet Briefing-Datum (3 Tage vor Schulung)."""
        datum_start = self.gefunden.get("datum_start")
        if not datum_start:
            self._setze("briefing_datum", None)
            return

        formate = ['%d.%m.%Y', '%d.%m.%y']
        for fmt in formate:
            try:
                dt = datetime.strptime(datum_start, fmt)
                briefing = dt - timedelta(days=3)
                self._setze("briefing_datum", briefing.strftime('%d.%m.%Y'))
                return
            except ValueError:
                continue

        self._setze("briefing_datum", None)

    def zeige_ergebnis(self):
        """Zeigt formatiertes Ergebnis."""
        print("\n" + "=" * 60)
        print("EXTRAHIERTE DATEN")
        print("=" * 60)

        kategorien = {
            "Schulung": ["schulungsname", "datum_start", "datum_ende", "uhrzeit", "format"],
            "Ort": ["firma_ort", "adresse"],
            "Intern (wir)": ["absender_intern", "absender_email"],
            "Extern (Ansprechpartner)": ["ansprechpartner_extern", "email_extern", "telefon"],
            "Auftraggeber/Kunde": ["auftraggeber", "kunde"],
            "Teilnehmer": ["teilnehmeranzahl"],
            "Trainer": ["trainer", "trainer_bekannt", "trainer_adresse"],
            "Finanzen": ["tagessatz", "trainer_kosten", "vorbereitungspauschale", "reisekosten"],
            "Termine": ["briefing_datum"],
        }

        for kategorie, felder in kategorien.items():
            gefundene = [(f, self.gefunden[f]) for f in felder if f in self.gefunden]
            if gefundene:
                print(f"\n{kategorie}:")
                for feld, wert in gefundene:
                    if feld == "trainer_bekannt":
                        symbol = "⭐" if wert else "🆕"
                        print(f"  {symbol} trainer_bekannt: {'Ja (in config.json)' if wert else 'Nein (neuer Trainer)'}")
                    else:
                        print(f"  ✓ {feld}: {wert}")

        if self.nicht_gefunden:
            print("\n" + "-" * 60)
            print("NICHT GEFUNDEN:")
            for feld in self.nicht_gefunden:
                print(f"  ✗ {feld}")

        print("\n" + "=" * 60)

    def als_json(self) -> str:
        """Gibt Ergebnis als JSON zurück."""
        return json.dumps(self.gefunden, indent=2, ensure_ascii=False)


def main():
    """Hauptprogramm mit interaktiver Eingabe."""
    print("=" * 60)
    print("SCHULUNGS-EXTRAKTOR")
    print("Extrahiert Daten aus E-Mail-Text")
    print("=" * 60)
    print("\nFüge den E-Mail-Text ein (beende mit einer Leerzeile + Enter):\n")

    zeilen = []
    while True:
        try:
            zeile = input()
            if zeile == "" and zeilen and zeilen[-1] == "":
                break
            zeilen.append(zeile)
        except EOFError:
            break

    text = "\n".join(zeilen)

    if not text.strip():
        print("Kein Text eingegeben.")
        return

    extraktor = SchulungsExtraktor()
    extraktor.extrahiere(text)
    extraktor.zeige_ergebnis()

    # Notion-Sync anbieten
    print("\n" + "-" * 60)
    notion_sync = input("In Notion eintragen? (ja/nein): ").strip().lower()

    if notion_sync in ('ja', 'j', 'yes', 'y'):
        try:
            from notion_sync import NotionSync

            sync = NotionSync()
            sync.zeige_vorschau(extraktor.gefunden)

            print("\n" + "-" * 60)
            bestaetigen = input("Eintrag erstellen? (ja/nein): ").strip().lower()

            if bestaetigen in ('ja', 'j', 'yes', 'y'):
                print("\nErstelle Notion-Eintrag...")
                ergebnis = sync.erstelle_eintrag(extraktor.gefunden)

                if ergebnis["erfolg"]:
                    print("\n" + "=" * 60)
                    print("✓ NOTION-EINTRAG ERSTELLT!")
                    print("=" * 60)
                    print(f"  URL: {ergebnis['url']}")
                    print("=" * 60)
                else:
                    print("\n" + "=" * 60)
                    print("✗ FEHLER BEIM ERSTELLEN")
                    print("=" * 60)
                    print(f"  {ergebnis['fehler']}")
                    print("=" * 60)
            else:
                print("Abgebrochen.")

        except FileNotFoundError as e:
            print(f"\n{e}")
        except ImportError:
            print("\n⚠ notion_sync.py nicht gefunden!")
            print("  Stelle sicher, dass die Datei im selben Ordner liegt.")
        except Exception as e:
            print(f"\n⚠ Fehler bei Notion-Sync: {e}")

    # Vertrag-Generierung anbieten
    print("\n" + "-" * 60)
    vertrag_erstellen = input("Beauftragungsvertrag erstellen? (ja/nein): ").strip().lower()

    if vertrag_erstellen in ('ja', 'j', 'yes', 'y'):
        try:
            from vertrag_generator import VertragGenerator

            generator = VertragGenerator()
            print("\nGeneriere Vertrag...")
            ergebnis = generator.generiere(extraktor.gefunden)

            if ergebnis["erfolg"]:
                print("\n" + "=" * 60)
                print("✓ VERTRAG ERSTELLT!")
                print("=" * 60)
                print(f"  Datei: {ergebnis['pfad']}")

                if ergebnis.get("warnungen"):
                    print("\n  Warnungen:")
                    for warnung in ergebnis["warnungen"]:
                        print(f"    ⚠ {warnung}")

                print("=" * 60)

                # Datei öffnen anbieten
                oeffnen = input("\nVertrag jetzt öffnen? (ja/nein): ").strip().lower()
                if oeffnen in ('ja', 'j', 'yes', 'y'):
                    import subprocess
                    subprocess.run(["open", ergebnis["pfad"]])
            else:
                print("\n" + "=" * 60)
                print("✗ FEHLER BEIM ERSTELLEN")
                print("=" * 60)
                print(f"  {ergebnis['fehler']}")
                print("=" * 60)

        except ImportError:
            print("\n⚠ vertrag_generator.py nicht gefunden!")
            print("  Stelle sicher, dass die Datei im selben Ordner liegt.")
        except Exception as e:
            print(f"\n⚠ Fehler bei Vertrag-Generierung: {e}")

    # Optional: JSON speichern
    print("\n" + "-" * 60)
    speichern = input("Als JSON-Datei speichern? (ja/nein): ").strip().lower()
    if speichern in ('ja', 'j', 'yes', 'y'):
        dateiname = input("Dateiname (ohne .json): ").strip() or "extraktion"
        with open(f"{dateiname}.json", 'w', encoding='utf-8') as f:
            f.write(extraktor.als_json())
        print(f"Gespeichert als {dateiname}.json")


if __name__ == "__main__":
    main()
