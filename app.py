#!/usr/bin/env python3
"""
Schulungs-Manager Web-App v2.2
Game-Menu Style Dashboard mit AI-Z Dark Mode + KI-Features.
Deployable auf Streamlit Cloud.
"""

import streamlit as st
import sys
import os
import json
import tempfile
from datetime import datetime, date

# ============================================================
# UMGEBUNGS-ERKENNUNG
# ============================================================
# Erkennt ob lokal oder in Streamlit Cloud
APP_DIR = os.path.dirname(os.path.abspath(__file__))
IS_CLOUD = os.path.exists("/mount") or not os.path.exists(os.path.expanduser("~/prozess-labor"))

# Secrets laden (Cloud: st.secrets, Lokal: .env)
def get_secret(key: str, default: str = "") -> str:
    """Holt Secret aus st.secrets (Cloud) oder Umgebungsvariablen (Lokal)."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.getenv(key, default)

# Bei lokalem Betrieb: .env laden
if not IS_CLOUD:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.expanduser("~/prozess-labor/.env"))
    except ImportError:
        pass

# ============================================================
# PASSWORD-SCHUTZ
# ============================================================
def check_password() -> bool:
    """Zeigt Login-Formular und prüft Passwort."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Login-Seite
    st.markdown("""
    <style>
        .stApp { background-color: #0a0a0f !important; }
        .login-container {
            max-width: 400px; margin: 100px auto; padding: 2rem;
            background: linear-gradient(145deg, #111118 0%, #1a1a24 100%);
            border-radius: 16px; border: 1px solid rgba(139,92,246,0.2);
            text-align: center;
        }
        .login-title { color: #fff; font-size: 1.8rem; margin-bottom: 0.5rem; }
        .login-subtitle { color: #8b8fa3; font-size: 0.9rem; margin-bottom: 2rem; }
    </style>
    <div class="login-container">
        <div class="login-title">⚡ AI-Z Portal</div>
        <div class="login-subtitle">Schulungs-Manager</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Passwort", type="password", key="login_password")
        if st.button("Anmelden", type="primary", use_container_width=True):
            correct_password = get_secret("APP_PASSWORD", "aiz2026")
            if password == correct_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Falsches Passwort")
    return False

# ============================================================
# PFADE KONFIGURIEREN
# ============================================================
if IS_CLOUD:
    # Cloud: Module aus lokalem modules/ Verzeichnis
    MODULES_PATH = os.path.join(APP_DIR, "modules")
    VORLAGEN_PATH = os.path.join(APP_DIR, "vorlagen")
    CONFIG_PATH = os.path.join(MODULES_PATH, "config.json")
    # Temp-Verzeichnis für generierte Dateien
    TEMP_DIR = tempfile.mkdtemp()
else:
    # Lokal: Module aus prozess-labor
    MODULES_PATH = os.path.join(APP_DIR, "modules")
    VORLAGEN_PATH = os.path.join(APP_DIR, "vorlagen")
    CONFIG_PATH = os.path.join(MODULES_PATH, "config.json")
    # Fallback auf alte Pfade wenn modules/ nicht existiert
    if not os.path.exists(MODULES_PATH):
        MODULES_PATH = os.path.expanduser("~/prozess-labor/03_umsetzung/schulungs-extraktor")
        CONFIG_PATH = os.path.join(MODULES_PATH, "config.json")
    if not os.path.exists(VORLAGEN_PATH):
        VORLAGEN_PATH = os.path.expanduser("~/prozess-labor/03_umsetzung/schulungs-extraktor/vorlagen")
    TEMP_DIR = None  # Lokal: Normale Pfade verwenden

# Zusätzliche Pfade für Einstellungen-Seite
EXTRAKTOR_PATH = MODULES_PATH
FEEDBACK_PATH = os.path.join(APP_DIR, "modules") if IS_CLOUD else os.path.expanduser("~/prozess-labor/03_umsetzung/feedback-system")

sys.path.insert(0, MODULES_PATH)

# Module importieren
try:
    from extraktor import SchulungsExtraktor
    from notion_sync import NotionSync
    from vertrag_generator import VertragGenerator
    from feedback_integration import create_feedback, feedback_exists
    MODULES_LOADED = True
    IMPORT_ERROR = None
except ImportError as e:
    MODULES_LOADED = False
    IMPORT_ERROR = str(e)

# Anthropic SDK für KI-Features
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# KI-Konfiguration
ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY", "")
KI_AVAILABLE = ANTHROPIC_AVAILABLE and bool(ANTHROPIC_API_KEY)


def ki_call(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> dict:
    """
    Führt einen Claude API Call aus.

    Returns:
        dict mit 'erfolg', 'text' oder 'fehler'
    """
    if not KI_AVAILABLE:
        if not ANTHROPIC_AVAILABLE:
            return {"erfolg": False, "fehler": "Anthropic SDK nicht installiert. Installiere mit: pip install anthropic"}
        else:
            return {"erfolg": False, "fehler": "ANTHROPIC_API_KEY fehlt in ~/prozess-labor/.env"}

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return {"erfolg": True, "text": response.content[0].text}
    except anthropic.APIConnectionError:
        return {"erfolg": False, "fehler": "Keine Verbindung zur Claude API"}
    except anthropic.RateLimitError:
        return {"erfolg": False, "fehler": "Rate Limit erreicht. Bitte kurz warten."}
    except anthropic.APIStatusError as e:
        return {"erfolg": False, "fehler": f"API Fehler: {e.message}"}
    except Exception as e:
        return {"erfolg": False, "fehler": f"Fehler: {str(e)}"}

# Seiten-Konfiguration
st.set_page_config(
    page_title="AI-Z Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - AI-Z Dark Mode + Game Menu
st.markdown("""
<style>
    /* ===== GLOBAL DARK THEME ===== */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0a0a0f !important;
        color: #e2e8f0 !important;
    }
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 1200px;
    }
    header[data-testid="stHeader"] {
        background-color: #0a0a0f !important;
    }

    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d14 0%, #111118 50%, #0d0d14 100%) !important;
        border-right: 1px solid rgba(139, 92, 246, 0.15);
    }
    [data-testid="stSidebar"] * {
        color: #c4b5fd !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #c4b5fd !important;
        padding: 0.5rem 0.75rem !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(139, 92, 246, 0.15) !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
        font-size: 0.95rem !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(139, 92, 246, 0.2) !important;
    }
    [data-testid="stSidebar"] .stAlert {
        background: rgba(139, 92, 246, 0.1) !important;
        border: 1px solid rgba(139, 92, 246, 0.3) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] small, [data-testid="stSidebar"] .stCaption {
        color: #7c6faa !important;
    }

    /* ===== TYPOGRAPHY ===== */
    h1 {
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }
    h2 {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    h3 {
        color: #c4b5fd !important;
        font-weight: 600 !important;
    }
    p, span, label, .stMarkdown {
        color: #b8c0cc !important;
    }
    a {
        color: #a78bfa !important;
    }
    hr {
        border-color: rgba(139, 92, 246, 0.15) !important;
    }

    /* ===== CARDS / CONTAINER ===== */
    [data-testid="stExpander"] {
        background: #1a1a24 !important;
        border: 1px solid rgba(139, 92, 246, 0.15) !important;
        border-radius: 12px !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        color: #e2e8f0 !important;
        font-weight: 500 !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background: #1a1a24 !important;
    }
    .stMetric {
        background: linear-gradient(135deg, #1a1a24 0%, #1e1e2a 100%) !important;
        border: 1px solid rgba(139, 92, 246, 0.2) !important;
        padding: 1rem !important;
        border-radius: 12px !important;
    }
    .stMetric label {
        color: #8b8fa3 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #a78bfa !important;
    }

    /* ===== FORM / INPUT FIELDS ===== */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background-color: #111118 !important;
        border: 1px solid rgba(139, 92, 246, 0.25) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        padding: 0.6rem 0.8rem !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2) !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #4a4a5a !important;
    }
    .stSelectbox [data-testid="stSelectbox"], .stSelectbox > div > div {
        background-color: #111118 !important;
        border-color: rgba(139, 92, 246, 0.25) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }
    .stDateInput > div > div > input {
        background-color: #111118 !important;
        border-color: rgba(139, 92, 246, 0.25) !important;
        color: #e2e8f0 !important;
    }
    .stCheckbox label span {
        color: #b8c0cc !important;
    }
    .stNumberInput button {
        background-color: #1a1a24 !important;
        border-color: rgba(139, 92, 246, 0.25) !important;
        color: #a78bfa !important;
    }

    /* ===== BUTTONS ===== */
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    .stFormSubmitButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 50%, #a78bfa 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3) !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    .stFormSubmitButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #6d28d9 0%, #7c3aed 50%, #8b5cf6 100%) !important;
        box-shadow: 0 4px 16px rgba(139, 92, 246, 0.4) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"], .stButton > button:not([kind="primary"]),
    .stFormSubmitButton > button:not([kind="primary"]) {
        background: #1a1a24 !important;
        color: #c4b5fd !important;
        border: 1px solid rgba(139, 92, 246, 0.3) !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="secondary"]:hover, .stButton > button:not([kind="primary"]):hover {
        background: rgba(139, 92, 246, 0.15) !important;
        border-color: #8b5cf6 !important;
    }

    /* ===== ALERTS ===== */
    .stAlert {
        border-radius: 10px !important;
        border: none !important;
    }
    [data-testid="stAlert"][data-baseweb*="positive"],
    div[data-testid="stNotification"][data-type="success"],
    .element-container .stSuccess {
        background: rgba(16, 185, 129, 0.1) !important;
        border-left: 4px solid #10b981 !important;
    }
    [data-testid="stAlert"][data-baseweb*="negative"],
    div[data-testid="stNotification"][data-type="error"],
    .element-container .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border-left: 4px solid #ef4444 !important;
    }
    [data-testid="stAlert"][data-baseweb*="warning"],
    div[data-testid="stNotification"][data-type="warning"],
    .element-container .stWarning {
        background: rgba(245, 158, 11, 0.1) !important;
        border-left: 4px solid #f59e0b !important;
    }
    [data-testid="stAlert"][data-baseweb*="info"],
    div[data-testid="stNotification"][data-type="info"],
    .element-container .stInfo {
        background: rgba(139, 92, 246, 0.1) !important;
        border-left: 4px solid #8b5cf6 !important;
    }

    /* ===== INFO-BOX (Custom HTML) ===== */
    .info-box {
        background: rgba(139, 92, 246, 0.08);
        border-left: 4px solid #8b5cf6;
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: #b8c0cc;
    }
    .info-box strong {
        color: #c4b5fd;
    }
    .success-box {
        background: rgba(16, 185, 129, 0.08);
        border-left: 4px solid #10b981;
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: #b8c0cc;
    }
    .error-box {
        background: rgba(239, 68, 68, 0.08);
        border-left: 4px solid #ef4444;
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: #b8c0cc;
    }

    /* ===== CODE BLOCK ===== */
    .stCodeBlock, code, .stCode {
        background-color: #111118 !important;
        border: 1px solid rgba(139, 92, 246, 0.15) !important;
        border-radius: 8px !important;
        color: #c4b5fd !important;
    }

    /* ===== FORM CONTAINER ===== */
    [data-testid="stForm"] {
        background: #12121a !important;
        border: 1px solid rgba(139, 92, 246, 0.12) !important;
        border-radius: 14px !important;
        padding: 1.5rem !important;
    }

    /* ===== TIMELINE / AKTIONEN ===== */
    .timeline-item {
        background: #1a1a24;
        border-left: 3px solid #8b5cf6;
        padding: 0.8rem 1.2rem;
        border-radius: 0 10px 10px 0;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }
    .timeline-item:hover {
        background: #1e1e2a;
        border-left-color: #a78bfa;
    }
    .timeline-item.error {
        border-left-color: #ef4444;
    }
    .timeline-time {
        color: #6b6b80;
        font-size: 0.8rem;
        font-family: monospace;
    }
    .timeline-type {
        color: #c4b5fd;
        font-weight: 600;
    }
    .timeline-desc {
        color: #8b8fa3;
        font-size: 0.9rem;
    }

    /* ===== WELCOME HEADER ===== */
    .welcome-header {
        background: linear-gradient(135deg, #1a1a24 0%, #1e1028 100%);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
    }
    .welcome-header h2 {
        color: #ffffff !important;
        margin: 0 0 0.3rem 0;
        font-size: 1.4rem;
    }
    .welcome-header p {
        color: #8b8fa3 !important;
        margin: 0;
        font-size: 0.95rem;
    }

    /* ===== DARK CARD ===== */
    .dark-card {
        background: #1a1a24;
        border: 1px solid rgba(139, 92, 246, 0.12);
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
    }
    .dark-card h4 {
        color: #c4b5fd !important;
        margin: 0 0 0.5rem 0;
    }

    /* ===== STATUS DOT ===== */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .status-dot.green { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
    .status-dot.red { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }
    .status-dot.yellow { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }

    /* ===== MENU CARDS (Game-Menu Style) ===== */
    .menu-card {
        background: linear-gradient(135deg, #1a1a24 0%, #1e1028 100%);
        border: 1px solid rgba(139, 92, 246, 0.15);
        border-radius: 16px;
        padding: 2rem 1rem;
        text-align: center;
        transition: all 0.3s ease;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .menu-card:hover {
        border-color: #8b5cf6;
        background: linear-gradient(135deg, #1e1e2a 0%, #251838 100%);
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(139, 92, 246, 0.15);
    }
    .menu-card-icon {
        font-size: 2.5rem;
        margin-bottom: 0.75rem;
        line-height: 1;
    }
    .menu-card-title {
        color: #e2e8f0;
        font-weight: 600;
        font-size: 1.05rem;
    }

    /* ===== PREFILL HINT ===== */
    .prefill-hint {
        background: rgba(139, 92, 246, 0.08);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        margin-bottom: 1rem;
        color: #a78bfa;
        font-size: 0.85rem;
    }

    /* ===== QUICK ANALYZE ===== */
    .quick-section {
        background: #12121a;
        border: 1px solid rgba(139, 92, 246, 0.12);
        border-radius: 14px;
        padding: 1.5rem;
        margin-top: 1.5rem;
    }
    .quick-section h3 {
        color: #c4b5fd !important;
        margin-top: 0;
    }

    /* ===== EXTRACTED DATA CARD ===== */
    .data-card {
        background: #1a1a24;
        border: 1px solid rgba(139, 92, 246, 0.15);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }
    .data-card .data-label {
        color: #8b8fa3;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .data-card .data-value {
        color: #e2e8f0;
        font-size: 1rem;
        font-weight: 500;
    }

    /* ===== NEXT ACTION BAR ===== */
    .next-action {
        background: rgba(16, 185, 129, 0.06);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-top: 1rem;
    }
    .next-action strong {
        color: #10b981 !important;
    }

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0a0a0f;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(139, 92, 246, 0.3);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(139, 92, 246, 0.5);
    }

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab"] {
        color: #8b8fa3 !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #a78bfa !important;
        border-bottom-color: #8b5cf6 !important;
    }

    /* ===== SELECTBOX DROPDOWN ===== */
    [data-baseweb="popover"] {
        background: #1a1a24 !important;
        border: 1px solid rgba(139, 92, 246, 0.3) !important;
    }
    [data-baseweb="menu"] {
        background: #1a1a24 !important;
    }
    [data-baseweb="menu"] li {
        color: #e2e8f0 !important;
    }
    [data-baseweb="menu"] li:hover {
        background: rgba(139, 92, 246, 0.15) !important;
    }

    /* ===== RADIO as PILLS ===== */
    .stRadio > div[role="radiogroup"] {
        gap: 2px !important;
    }

    /* ===== TOOLTIP / CAPTION ===== */
    .stCaption, small {
        color: #6b6b80 !important;
    }
</style>
""", unsafe_allow_html=True)

# ============== PASSWORD CHECK ==============
if not check_password():
    st.stop()

# ============== SESSION STATE ==============
if "aktuelle_daten" not in st.session_state:
    st.session_state.aktuelle_daten = None
if "extrahierte_daten" not in st.session_state:
    st.session_state.extrahierte_daten = None
if "letzte_aktionen" not in st.session_state:
    st.session_state.letzte_aktionen = []
if "last_success" not in st.session_state:
    st.session_state.last_success = None

def log_aktion(typ: str, beschreibung: str, erfolg: bool = True, details: dict = None, ergebnis: dict = None):
    """Loggt eine Aktion in die Historie mit optionalen Details."""
    st.session_state.letzte_aktionen.insert(0, {
        "zeit": datetime.now().strftime("%H:%M:%S"),
        "typ": typ,
        "beschreibung": beschreibung,
        "erfolg": erfolg,
        "details": details or {},
        "ergebnis": ergebnis or {},
    })
    st.session_state.letzte_aktionen = st.session_state.letzte_aktionen[:20]

def nav_zu(seite):
    """Navigiert zu einer Seite."""
    st.session_state.nav_seite = seite
    st.rerun()

def get_ad(key, default=""):
    """Holt Wert aus aktuelle_daten oder gibt Default zurueck."""
    ad = st.session_state.get("aktuelle_daten")
    if ad and isinstance(ad, dict):
        val = ad.get(key, default)
        return str(val) if val else default
    return default

def hat_daten():
    """Prueft ob aktuelle Daten vorhanden sind."""
    ad = st.session_state.get("aktuelle_daten")
    return ad is not None and isinstance(ad, dict) and len(ad) > 0

def zeige_prefill_hint():
    """Zeigt Hinweis wenn Daten vorausgefuellt sind."""
    if hat_daten():
        st.markdown('<div class="prefill-hint">📋 Vorausgefüllt aus letzter Analyse — du kannst alles überschreiben.</div>', unsafe_allow_html=True)

def zeige_naechste_aktion(ausser=None):
    """Zeigt Navigation zu naechster Aktion nach Erfolg."""
    st.markdown('<div class="next-action"><strong>✓ Erledigt!</strong> Nächste Aktion?</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    aktionen = [
        ("🏠 Start", "🏠 Start"),
        ("📋 Notion", "📋 Notion-Sync"),
        ("📄 Vertrag", "📄 Vertrag erstellen"),
        ("🔗 Feedback", "🔗 Feedback-Link"),
        ("📧 Briefing", "📧 Briefing erstellen"),
    ]
    for i, (label, ziel) in enumerate(aktionen):
        if ausser and ziel == ausser:
            continue
        with cols[i]:
            if st.button(label, key=f"next_{ziel}"):
                nav_zu(ziel)

# ============== SIDEBAR ==============
PAGES = [
    "🏠 Start",
    "📋 Notion-Sync",
    "📄 Vertrag erstellen",
    "🔗 Feedback-Link",
    "📧 Briefing erstellen",
    "👥 Trainer-Datenbank",
    "📊 Letzte Aktionen",
    "⚙️ Einstellungen"
]

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 0.5rem 0 1rem 0;">
        <div style="font-size: 1.8rem; font-weight: 700; color: #ffffff; letter-spacing: -0.03em;">
            AI-Z <span style="color: #8b5cf6;">Portal</span>
        </div>
        <div style="font-size: 0.75rem; color: #6b6b80; letter-spacing: 0.05em; text-transform: uppercase;">
            Schulungs-Manager
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    seite = st.radio(
        "Navigation",
        PAGES,
        key="nav_seite",
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Status-Anzeige
    if MODULES_LOADED:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:8px; padding:0.5rem 0.75rem;
            background:rgba(16,185,129,0.08); border-radius:8px; border:1px solid rgba(16,185,129,0.2);">
            <span class="status-dot green"></span>
            <span style="color:#10b981; font-size:0.85rem; font-weight:500;">Module geladen</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; padding:0.5rem 0.75rem;
            background:rgba(239,68,68,0.08); border-radius:8px; border:1px solid rgba(239,68,68,0.2);">
            <span class="status-dot red"></span>
            <span style="color:#ef4444; font-size:0.85rem; font-weight:500;">Import-Fehler</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(IMPORT_ERROR if not MODULES_LOADED else "")

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; padding:0.25rem 0;">
        <span style="color:#4a4a5a; font-size:0.75rem;">v2.0 &middot; AI-Z / KI Schulungen Stuttgart</span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# STARTSEITE: GAME-MENU
# ============================================================
if seite == "🏠 Start":
    st.markdown("""
    <div class="welcome-header">
        <h2>Was willst du tun?</h2>
        <p>Wähle eine Aktion oder analysiere unten eine Email.</p>
    </div>
    """, unsafe_allow_html=True)

    # --- 2x3 Menu Grid ---
    menu_items = [
        ("📋", "Notion Eintragen", "📋 Notion-Sync"),
        ("📄", "Vertrag Erstellen", "📄 Vertrag erstellen"),
        ("🔗", "Feedback-Link", "🔗 Feedback-Link"),
        ("📧", "Briefing Erstellen", "📧 Briefing erstellen"),
        ("👥", "Trainer Verwalten", "👥 Trainer-Datenbank"),
        ("📊", "Letzte Aktionen", "📊 Letzte Aktionen"),
    ]

    # Row 1
    col1, col2, col3 = st.columns(3, gap="medium")
    for col, (icon, title, target) in zip([col1, col2, col3], menu_items[:3]):
        with col:
            st.markdown(f"""
            <div class="menu-card">
                <div class="menu-card-icon">{icon}</div>
                <div class="menu-card-title">{title}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"→ {title}", key=f"mc_{target}", use_container_width=True):
                nav_zu(target)

    # Row 2
    col4, col5, col6 = st.columns(3, gap="medium")
    for col, (icon, title, target) in zip([col4, col5, col6], menu_items[3:]):
        with col:
            st.markdown(f"""
            <div class="menu-card">
                <div class="menu-card-icon">{icon}</div>
                <div class="menu-card-title">{title}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"→ {title}", key=f"mc_{target}", use_container_width=True):
                nav_zu(target)

    # --- Quick-Analyze Bereich ---
    st.markdown("---")
    st.markdown("""
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:0.5rem;">
        <span style="font-size:1.3rem;">⚡</span>
        <span style="color:#e2e8f0; font-weight:600; font-size:1.1rem;">Quick-Analyze</span>
        """ + ("""<span style="background:rgba(139,92,246,0.15); color:#a78bfa; padding:2px 8px;
            border-radius:4px; font-size:0.75rem; margin-left:8px;">+ KI</span>""" if KI_AVAILABLE else "") + """
    </div>
    """, unsafe_allow_html=True)

    # Session state für KI-Chat
    if "ki_chat_history" not in st.session_state:
        st.session_state.ki_chat_history = []
    if "last_analyzed_text" not in st.session_state:
        st.session_state.last_analyzed_text = ""
    if "ki_suggestions" not in st.session_state:
        st.session_state.ki_suggestions = []

    email_text = st.text_area(
        "Email oder Text hier pasten...",
        height=200,
        placeholder="Buchungsbestätigung, Schulungsanfrage oder andere Mail hier einfügen...",
        label_visibility="collapsed",
        key="qa_input"
    )

    # Zwei Analyse-Buttons
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        regex_btn = st.button("🔍 Regex-Analyse", use_container_width=True, key="quick_analyze")
    with col_btn2:
        ki_btn = st.button("🤖 KI-Analyse", type="primary", use_container_width=True, key="ki_analyze",
                           disabled=not KI_AVAILABLE)

    # Regex-Analyse
    if regex_btn:
        if email_text.strip():
            if MODULES_LOADED:
                try:
                    extraktor = SchulungsExtraktor()
                    daten = extraktor.extrahiere(email_text)
                    st.session_state.aktuelle_daten = daten
                    st.session_state.extrahierte_daten = daten
                    st.session_state.last_analyzed_text = email_text
                    st.session_state.ki_suggestions = []

                    # Felder zählen
                    gefundene_felder = len([k for k, v in daten.items() if v])
                    log_aktion("Extraktion", f"Regex: {daten.get('schulungsname', 'Unbekannt')}",
                        details=dict(daten),
                        ergebnis={"felder_gefunden": gefundene_felder, "methode": "regex"})

                    # Vorschläge generieren
                    suggestions = []
                    if gefundene_felder < 4:
                        suggestions.append(("🤖", "Wenig erkannt – KI-Analyse probieren?", "ki"))
                    if daten.get("auftraggeber", "").lower() in ["gfu", "gfu cyrus"]:
                        suggestions.append(("📄", "GFU-Schulung → Beauftragungsvertrag?", "vertrag"))
                    if daten.get("trainer") and daten.get("schulungsname"):
                        suggestions.append(("📧", "Daten komplett → Briefing erstellen?", "briefing"))
                    if not daten.get("datum_start"):
                        suggestions.append(("⚠️", "Kein Datum gefunden", "info"))
                    st.session_state.ki_suggestions = suggestions

                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler bei Extraktion: {e}")
                    log_aktion("Extraktion", f"Fehler: {e}", erfolg=False)
            else:
                st.error("Module nicht geladen.")
        else:
            st.warning("Bitte Text eingeben.")

    # KI-Analyse
    if ki_btn:
        if email_text.strip():
            with st.spinner("🤖 KI analysiert Text..."):
                system_prompt = """Du analysierst Texte (Emails, Notizen) und extrahierst Schulungsinformationen.

Antworte IMMER als JSON mit diesem Format:
{
    "schulungsname": "...",
    "datum_start": "TT.MM.JJJJ",
    "datum_ende": "TT.MM.JJJJ oder null",
    "uhrzeit": "...",
    "trainer": "...",
    "kunde": "...",
    "auftraggeber": "GFU/NobleProg/Direkt/...",
    "format": "Vor Ort/Remote",
    "ort": "...",
    "teilnehmeranzahl": Zahl oder null,
    "tagessatz": Zahl oder null,
    "hinweise": "...",
    "confidence": {
        "schulungsname": "high/medium/low",
        "datum_start": "high/medium/low",
        "trainer": "high/medium/low",
        "kunde": "high/medium/low"
    },
    "vorschlaege": ["Vorschlag 1", "Vorschlag 2"]
}

Regeln:
- Nur Daten aus dem Text, NICHTS erfinden
- Bei Unsicherheit: confidence = "low"
- Vorschläge: Was könnte als nächstes sinnvoll sein?"""

                user_prompt = f"Analysiere diesen Text:\n\n{email_text}"

                result = ki_call(system_prompt, user_prompt)

                if result.get("erfolg"):
                    try:
                        # JSON aus Antwort extrahieren
                        text = result["text"]
                        # Finde JSON in der Antwort
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', text)
                        if json_match:
                            ki_daten = json.loads(json_match.group())

                            # In aktuelle_daten übernehmen
                            daten = {
                                "schulungsname": ki_daten.get("schulungsname", ""),
                                "datum_start": ki_daten.get("datum_start", ""),
                                "datum_ende": ki_daten.get("datum_ende", ""),
                                "uhrzeit": ki_daten.get("uhrzeit", ""),
                                "trainer": ki_daten.get("trainer", ""),
                                "kunde": ki_daten.get("kunde", ""),
                                "auftraggeber": ki_daten.get("auftraggeber", ""),
                                "format": ki_daten.get("format", ""),
                                "ort": ki_daten.get("ort", ""),
                                "teilnehmeranzahl": ki_daten.get("teilnehmeranzahl"),
                                "tagessatz": ki_daten.get("tagessatz"),
                                "hinweise": ki_daten.get("hinweise", ""),
                                "_ki_confidence": ki_daten.get("confidence", {}),
                                "_ki_vorschlaege": ki_daten.get("vorschlaege", [])
                            }

                            st.session_state.aktuelle_daten = daten
                            st.session_state.extrahierte_daten = daten
                            st.session_state.last_analyzed_text = email_text

                            # Vorschläge aus KI-Antwort
                            suggestions = []
                            for v in ki_daten.get("vorschlaege", []):
                                suggestions.append(("💡", v, "info"))
                            st.session_state.ki_suggestions = suggestions

                            log_aktion("Extraktion", f"KI: {daten.get('schulungsname', 'Unbekannt')}",
                                details=dict(daten),
                                ergebnis={"methode": "ki", "confidence": ki_daten.get("confidence", {})})

                            st.rerun()
                        else:
                            st.error("KI-Antwort konnte nicht geparst werden.")
                    except json.JSONDecodeError as e:
                        st.error(f"JSON-Fehler: {e}")
                        st.code(result["text"])
                else:
                    st.error(f"KI-Fehler: {result.get('fehler')}")
        else:
            st.warning("Bitte Text eingeben.")

    # Extrahierte Daten anzeigen
    if hat_daten():
        daten = st.session_state.aktuelle_daten
        confidence = daten.get("_ki_confidence", {})

        st.markdown("---")

        # Header mit Methode
        methode_badge = ""
        if confidence:
            methode_badge = '<span style="background:rgba(139,92,246,0.15); color:#a78bfa; padding:2px 8px; border-radius:4px; font-size:0.75rem; margin-left:8px;">KI</span>'
        st.markdown(f"""
        <div style="color:#10b981; font-weight:600; font-size:1rem; margin-bottom:0.5rem;">
            ✓ Daten erkannt {methode_badge}
        </div>
        """, unsafe_allow_html=True)

        # Confidence-Indikator Funktion
        def conf_badge(field):
            if not confidence:
                return ""
            level = confidence.get(field, "")
            if level == "high":
                return '<span style="color:#10b981; font-size:0.7rem; margin-left:4px;">●</span>'
            elif level == "medium":
                return '<span style="color:#f59e0b; font-size:0.7rem; margin-left:4px;">●</span>'
            elif level == "low":
                return '<span style="color:#ef4444; font-size:0.7rem; margin-left:4px;">●</span>'
            return ""

        # Daten als kompakte Karten mit Confidence
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.markdown(f"""
            <div class="data-card">
                <div class="data-label">Schulung {conf_badge('schulungsname')}</div>
                <div class="data-value">{daten.get('schulungsname', '-')}</div>
            </div>
            <div class="data-card">
                <div class="data-label">Datum {conf_badge('datum_start')}</div>
                <div class="data-value">{daten.get('datum_start', '-')}{(' – ' + daten.get('datum_ende')) if daten.get('datum_ende') else ''}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_d2:
            st.markdown(f"""
            <div class="data-card">
                <div class="data-label">Trainer {conf_badge('trainer')}</div>
                <div class="data-value">{daten.get('trainer', '-')}</div>
            </div>
            <div class="data-card">
                <div class="data-label">Kunde {conf_badge('kunde')}</div>
                <div class="data-value">{daten.get('kunde', '-') or daten.get('firma_ort', '-')}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_d3:
            st.markdown(f"""
            <div class="data-card">
                <div class="data-label">Format</div>
                <div class="data-value">{daten.get('format', '-')}</div>
            </div>
            <div class="data-card">
                <div class="data-label">Tagessatz</div>
                <div class="data-value">{daten.get('tagessatz', '-')}</div>
            </div>
            """, unsafe_allow_html=True)

        # Smart Suggestions
        if st.session_state.ki_suggestions:
            st.markdown("")
            st.markdown('<div style="color:#8b8fa3; font-size:0.85rem; margin-bottom:0.5rem;">💡 Vorschläge</div>', unsafe_allow_html=True)
            for icon, text, action in st.session_state.ki_suggestions:
                col_sug1, col_sug2 = st.columns([4, 1])
                with col_sug1:
                    st.markdown(f"""
                    <div style="background:rgba(139,92,246,0.08); border:1px solid rgba(139,92,246,0.15);
                        border-radius:8px; padding:0.5rem 0.8rem; margin:0.25rem 0; display:flex; align-items:center; gap:8px;">
                        <span>{icon}</span>
                        <span style="color:#b8c0cc; font-size:0.9rem;">{text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col_sug2:
                    if action == "ki":
                        if st.button("→", key=f"sug_ki", use_container_width=True):
                            st.session_state.ki_analyze = True
                            st.rerun()
                    elif action == "vertrag":
                        if st.button("→", key=f"sug_vertrag", use_container_width=True):
                            nav_zu("📄 Vertrag erstellen")
                    elif action == "briefing":
                        if st.button("→", key=f"sug_briefing", use_container_width=True):
                            nav_zu("📧 Briefing erstellen")

        # Action-Buttons
        st.markdown("")
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        with col_a1:
            if st.button("📋 → Notion", key="qa_notion", use_container_width=True):
                nav_zu("📋 Notion-Sync")
        with col_a2:
            if st.button("📄 → Vertrag", key="qa_vertrag", use_container_width=True):
                nav_zu("📄 Vertrag erstellen")
        with col_a3:
            if st.button("🔗 → Feedback", key="qa_feedback", use_container_width=True):
                nav_zu("🔗 Feedback-Link")
        with col_a4:
            if st.button("📧 → Briefing", key="qa_briefing", use_container_width=True):
                nav_zu("📧 Briefing erstellen")

    # --- KI-Assistent Chat ---
    if KI_AVAILABLE:
        st.markdown("---")
        st.markdown("""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:0.5rem;">
            <span style="font-size:1rem;">💬</span>
            <span style="color:#a78bfa; font-weight:500; font-size:0.95rem;">KI-Assistent</span>
        </div>
        """, unsafe_allow_html=True)

        ki_frage = st.text_input(
            "Frag mich was...",
            placeholder="z.B. 'Was muss ich bei diesem Kunden beachten?' oder 'Fass die Mail zusammen'",
            key="ki_chat_input",
            label_visibility="collapsed"
        )

        if st.button("Fragen", key="ki_chat_send", use_container_width=True):
            if ki_frage.strip():
                with st.spinner("🤖 Denke nach..."):
                    # Kontext aufbauen
                    kontext = ""
                    if st.session_state.last_analyzed_text:
                        kontext += f"\n\nAnalysierter Text:\n{st.session_state.last_analyzed_text[:1000]}"
                    if hat_daten():
                        kontext += f"\n\nExtrahierte Daten:\n{json.dumps(st.session_state.aktuelle_daten, indent=2, ensure_ascii=False, default=str)}"

                    system_prompt = f"""Du bist ein hilfreicher Assistent für AI-Z / KI Schulungen Stuttgart.
Du hilfst bei der Schulungsverwaltung und beantwortest Fragen kurz und präzise.

Aktueller Kontext:{kontext}"""

                    result = ki_call(system_prompt, ki_frage, max_tokens=500)

                    if result.get("erfolg"):
                        st.session_state.ki_chat_history.append({
                            "frage": ki_frage,
                            "antwort": result["text"]
                        })
                        st.rerun()
                    else:
                        st.error(f"Fehler: {result.get('fehler')}")

        # Chat-Historie anzeigen
        if st.session_state.ki_chat_history:
            for chat in reversed(st.session_state.ki_chat_history[-3:]):
                st.markdown(f"""
                <div style="background:#1a1a24; border-radius:8px; padding:0.8rem; margin:0.5rem 0;">
                    <div style="color:#a78bfa; font-size:0.85rem; margin-bottom:0.3rem;">Du: {chat['frage']}</div>
                    <div style="color:#e2e8f0; font-size:0.9rem;">{chat['antwort']}</div>
                </div>
                """, unsafe_allow_html=True)

            if st.button("🗑️ Chat löschen", key="clear_chat"):
                st.session_state.ki_chat_history = []
                st.rerun()


# ============================================================
# NOTION-SYNC
# ============================================================
elif seite == "📋 Notion-Sync":
    st.markdown("""
    <div class="welcome-header">
        <h2>Notion-Sync</h2>
        <p>Schulungsdaten in Notion eintragen. Nur ausgefüllte Felder werden gesendet.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_notion"):
        nav_zu("🏠 Start")

    zeige_prefill_hint()

    if not MODULES_LOADED:
        st.error("Module nicht geladen.")
    else:
        with st.form("notion_manual"):
            st.subheader("Schulung eintragen")

            schulungsname = st.text_input("Schulungsname *", value=get_ad("schulungsname"))

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Termin & Ort**")
                datum_str = get_ad("datum_start")
                try:
                    if datum_str and "." in datum_str:
                        parts = datum_str.split(".")
                        datum_val = date(int(parts[2]), int(parts[1]), int(parts[0]))
                    else:
                        datum_val = date.today()
                except (ValueError, IndexError):
                    datum_val = date.today()
                datum = st.date_input("Datum", value=datum_val)

                datum_ende_str = get_ad("datum_ende")
                try:
                    if datum_ende_str and "." in datum_ende_str:
                        parts = datum_ende_str.split(".")
                        datum_ende_val = date(int(parts[2]), int(parts[1]), int(parts[0]))
                    else:
                        datum_ende_val = None
                except (ValueError, IndexError):
                    datum_ende_val = None
                datum_ende = st.date_input("Datum Ende (bei mehrtägig)", value=datum_ende_val)

                uhrzeit = st.text_input("Uhrzeit", value=get_ad("uhrzeit"), placeholder="z.B. 09:00 - 17:00")

                format_opts = ["", "Vor Ort", "Remote"]
                format_prefill = get_ad("format")
                format_idx = 0
                if format_prefill:
                    for fi, fo in enumerate(format_opts):
                        if fo.lower() == format_prefill.lower():
                            format_idx = fi
                            break
                format_val = st.selectbox("Format", format_opts, index=format_idx)
                ort = st.text_input("Ort / Plattform", value=get_ad("ort"), placeholder="z.B. Stuttgart oder Teams")

            with col2:
                st.markdown("**Organisation**")
                kunde = st.text_input("Kunde / Firma", value=get_ad("kunde") or get_ad("firma_ort"))

                ag_opts = ["", "GFU Cyrus AG", "NobleProg", "Direkt"]
                ag_prefill = get_ad("auftraggeber")
                ag_idx = 0
                for ai, ao in enumerate(ag_opts):
                    if ao.lower() == ag_prefill.lower():
                        ag_idx = ai
                        break
                auftraggeber = st.selectbox("Auftraggeber", ag_opts, index=ag_idx)

                trainer = st.text_input("Trainer", value=get_ad("trainer"))
                ansprechpartner = st.text_input("Ansprechpartner Kunde", value=get_ad("ansprechpartner_extern"))

                tn_str = get_ad("teilnehmeranzahl", "0")
                try:
                    tn_val = int(tn_str) if tn_str else 0
                except ValueError:
                    tn_val = 0
                teilnehmer = st.number_input("Teilnehmeranzahl", min_value=0, step=1, value=tn_val)

            st.markdown("---")
            st.markdown("**Finanzen & Extras**")
            col3, col4 = st.columns(2)

            with col3:
                ts_str = get_ad("tagessatz", "0")
                try:
                    ts_val = int(float(ts_str)) if ts_str else 0
                except ValueError:
                    ts_val = 0
                tagessatz = st.number_input("Tagessatz / Honorar (€)", min_value=0, step=100, value=ts_val)
                trainer_kosten = st.number_input("Kosten Trainer (€)", min_value=0, step=100, value=0)

                vp_str = get_ad("vorbereitungspauschale", "0")
                try:
                    vp_val = int(float(vp_str)) if vp_str else 0
                except ValueError:
                    vp_val = 0
                vorbereitung = st.number_input("Vorbereitungspauschale (€)", min_value=0, step=50, value=vp_val)

            with col4:
                reisekosten = st.selectbox("Reisekosten", ["", "inkl. im Tagessatz", "nach Aufwand", "keine"], index=0)
                status = st.selectbox("Status", ["Angefragt", "Gebucht", "Durchgeführt", "Storniert"], index=0)
                hinweise = st.text_area("Hinweise / Notizen", height=100)

            if st.form_submit_button("📋 In Notion eintragen", type="primary", use_container_width=True):
                if not schulungsname.strip():
                    st.error("Schulungsname ist Pflichtfeld!")
                else:
                    try:
                        notion = NotionSync()
                        daten = {"schulungsname": schulungsname}
                        if datum:
                            daten["datum_start"] = datum.strftime("%d.%m.%Y")
                        if datum_ende:
                            daten["datum_ende"] = datum_ende.strftime("%d.%m.%Y")
                        if uhrzeit.strip():
                            daten["uhrzeit"] = uhrzeit
                        if format_val:
                            daten["format"] = format_val
                        if kunde.strip():
                            daten["kunde"] = kunde
                        if auftraggeber:
                            daten["auftraggeber"] = auftraggeber
                        if trainer.strip():
                            daten["trainer"] = trainer
                        if ansprechpartner.strip():
                            daten["ansprechpartner_extern"] = ansprechpartner
                        if teilnehmer > 0:
                            daten["teilnehmeranzahl"] = teilnehmer
                        if tagessatz > 0:
                            daten["tagessatz"] = tagessatz
                        if trainer_kosten > 0:
                            daten["trainer_kosten"] = trainer_kosten
                        if reisekosten:
                            daten["reisekosten"] = reisekosten

                        result = notion.erstelle_eintrag(daten)
                        st.success(f"✅ Eintrag erstellt: {schulungsname}")
                        log_aktion("Notion", f"Eintrag: {schulungsname}",
                            details=dict(daten),
                            ergebnis={"notion_url": result.get("url", "") if isinstance(result, dict) else ""})
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                        log_aktion("Notion", str(e), erfolg=False)

        # Nächste Aktion (außerhalb Form)
        if st.session_state.letzte_aktionen and st.session_state.letzte_aktionen[0].get("typ") == "Notion" and st.session_state.letzte_aktionen[0].get("erfolg"):
            zeige_naechste_aktion(ausser="📋 Notion-Sync")


# ============================================================
# VERTRAG ERSTELLEN
# ============================================================
elif seite == "📄 Vertrag erstellen":
    st.markdown("""
    <div class="welcome-header">
        <h2>Vertrag erstellen</h2>
        <p>Beauftragungsvertrag oder Rahmenvertrag aus Vorlage generieren.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_vertrag"):
        nav_zu("🏠 Start")

    zeige_prefill_hint()

    if not MODULES_LOADED:
        st.error("Module nicht geladen.")
    else:
        # Vertragstyp-Auswahl
        vertragstyp = st.radio(
            "Vertragstyp",
            ["Beauftragungsvertrag", "Rahmenvertrag"],
            horizontal=True,
            help="Beauftragungsvertrag = einzelner Schulungsauftrag, Rahmenvertrag = neue Trainer-Kooperation"
        )

        # Generator mit korrekten Pfaden initialisieren
        vertraege_output = TEMP_DIR if IS_CLOUD else os.path.join(APP_DIR, "vertraege")
        os.makedirs(vertraege_output, exist_ok=True)
        generator = VertragGenerator(
            config_path=CONFIG_PATH,
            vorlagen_dir=VORLAGEN_PATH,
            vertraege_dir=vertraege_output
        )

        if vertragstyp == "Beauftragungsvertrag":
            trainer_liste = generator.get_trainer_liste()

            with st.form("vertrag_form"):
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Schulungsdaten")
                    schulungsname = st.text_input("Schulungsname*", value=get_ad("schulungsname"))
                    kunde = st.text_input("Kunde/Firma*", value=get_ad("kunde") or get_ad("firma_ort"))

                    datum_str = get_ad("datum_start")
                    try:
                        if datum_str and "." in datum_str:
                            parts = datum_str.split(".")
                            ds_val = date(int(parts[2]), int(parts[1]), int(parts[0]))
                        else:
                            ds_val = date.today()
                    except (ValueError, IndexError):
                        ds_val = date.today()
                    datum_start = st.date_input("Datum Start*", value=ds_val)

                    datum_ende_str = get_ad("datum_ende")
                    try:
                        if datum_ende_str and "." in datum_ende_str:
                            parts = datum_ende_str.split(".")
                            de_val = date(int(parts[2]), int(parts[1]), int(parts[0]))
                        else:
                            de_val = None
                    except (ValueError, IndexError):
                        de_val = None
                    datum_ende = st.date_input("Datum Ende", value=de_val)

                with col2:
                    st.subheader("Trainer & Kosten")
                    trainer_namen = [t.get("name", t) if isinstance(t, dict) else t for t in trainer_liste]
                    # Prefill Trainer-Auswahl
                    trainer_prefill = get_ad("trainer")
                    trainer_idx = 0
                    if trainer_prefill:
                        for ti, tn in enumerate(trainer_namen):
                            if tn.lower() == trainer_prefill.lower():
                                trainer_idx = ti
                                break
                    trainer = st.selectbox("Trainer*", trainer_namen, index=trainer_idx)

                    ts_str = get_ad("tagessatz", "1500")
                    try:
                        ts_val = int(float(ts_str)) if ts_str and ts_str != "0" else 1500
                    except ValueError:
                        ts_val = 1500
                    tagessatz = st.number_input("Tagessatz (€)*", min_value=0, step=100, value=ts_val)

                    vp_str = get_ad("vorbereitungspauschale", "250")
                    try:
                        vp_val = int(float(vp_str)) if vp_str and vp_str != "0" else 250
                    except ValueError:
                        vp_val = 250
                    vorbereitung = st.number_input("Vorbereitung (€)", min_value=0, step=50, value=vp_val)
                    reisekosten = st.selectbox("Reisekosten", ["inkl. im Tagessatz", "nach Aufwand", "keine"])

                if st.form_submit_button("📄 Vertrag generieren", type="primary", use_container_width=True):
                    try:
                        daten = {
                            "schulungsname": schulungsname,
                            "kunde": kunde,
                            "datum_start": datum_start.strftime("%d.%m.%Y"),
                            "datum_ende": datum_ende.strftime("%d.%m.%Y") if datum_ende else "",
                            "trainer": trainer,
                            "tagessatz": tagessatz,
                            "vorbereitungspauschale": vorbereitung,
                            "reisekosten": reisekosten
                        }
                        result = generator.generiere(daten)

                        if result.get("erfolg"):
                            st.success(f"✅ Vertrag erstellt: {result.get('datei')}")
                            datei_pfad = result.get("pfad")
                            # Download-Button
                            if datei_pfad and os.path.exists(datei_pfad):
                                with open(datei_pfad, "rb") as f:
                                    st.download_button(
                                        "⬇️ Vertrag herunterladen",
                                        data=f.read(),
                                        file_name=result.get("datei"),
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True
                                    )
                            if not IS_CLOUD:
                                st.info(f"📁 Gespeichert in: {datei_pfad}")
                            log_aktion("Vertrag", f"Beauftragung: {result.get('datei')}",
                                details=dict(daten),
                                ergebnis={"datei_pfad": datei_pfad, "datei": result.get("datei")})
                        else:
                            st.error(f"Fehler: {result.get('fehler')}")
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                        log_aktion("Vertrag", str(e), erfolg=False)

        else:
            # Rahmenvertrag
            st.markdown("""
            <div class="info-box">
                <strong>Rahmenvertrag</strong> — Für neue Trainer-Kooperationen.
                Gib die Trainer-Daten direkt ein.
            </div>
            """, unsafe_allow_html=True)

            with st.form("rahmenvertrag_form"):
                col_r1, col_r2 = st.columns(2)

                with col_r1:
                    rv_name = st.text_input("Name*", value=get_ad("trainer"))
                    rv_strasse = st.text_input("Straße + Hausnummer*")
                    rv_email = st.text_input("E-Mail (optional)")

                with col_r2:
                    rv_plz = st.text_input("PLZ*")
                    rv_ort = st.text_input("Ort*")
                    rv_telefon = st.text_input("Telefon (optional)")

                save_to_db = st.checkbox("Trainer nach Erstellung in Datenbank speichern", value=True)

                if st.form_submit_button("📄 Rahmenvertrag generieren", type="primary", use_container_width=True):
                    if not rv_name.strip() or not rv_strasse.strip() or not rv_plz.strip() or not rv_ort.strip():
                        st.error("Name, Straße, PLZ und Ort sind Pflichtfelder!")
                    else:
                        try:
                            # Trainer temporär in Generator-Config einfügen
                            temp_trainer = {
                                "name": rv_name.strip(),
                                "kurznamen": [],
                                "strasse": rv_strasse.strip(),
                                "plz": rv_plz.strip(),
                                "ort": rv_ort.strip(),
                                "email": rv_email.strip(),
                                "telefon": rv_telefon.strip()
                            }
                            generator.config["bekannte_trainer"].append(temp_trainer)

                            result = generator.generiere_rahmenvertrag(rv_name.strip())

                            if result.get("erfolg"):
                                st.success(f"✅ Rahmenvertrag erstellt: {result.get('dateiname')}")
                                datei_pfad = result.get("pfad")
                                # Download-Button
                                if datei_pfad and os.path.exists(datei_pfad):
                                    with open(datei_pfad, "rb") as f:
                                        st.download_button(
                                            "⬇️ Rahmenvertrag herunterladen",
                                            data=f.read(),
                                            file_name=result.get("dateiname"),
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            use_container_width=True
                                        )
                                if not IS_CLOUD:
                                    st.info(f"📁 Gespeichert in: {datei_pfad}")
                                log_aktion("Vertrag", f"Rahmenvertrag: {result.get('dateiname')}",
                                    details={"trainer": rv_name.strip(), "ort": f"{rv_plz} {rv_ort}"},
                                    ergebnis={"datei_pfad": datei_pfad, "datei": result.get("dateiname")})

                                if result.get("warnungen"):
                                    for w in result["warnungen"]:
                                        st.warning(w)

                                # In config.json speichern
                                if save_to_db:
                                    cfg_path = os.path.join(EXTRAKTOR_PATH, "config.json")
                                    with open(cfg_path, "r", encoding="utf-8") as f:
                                        cfg = json.load(f)
                                    # Prüfe ob schon vorhanden
                                    existing = [t for t in cfg.get("bekannte_trainer", [])
                                                 if isinstance(t, dict) and t.get("name", "").lower() == rv_name.strip().lower()]
                                    if not existing:
                                        cfg["bekannte_trainer"].append(temp_trainer)
                                        with open(cfg_path, "w", encoding="utf-8") as f:
                                            json.dump(cfg, f, indent=2, ensure_ascii=False)
                                        st.success(f"✅ {rv_name} in Trainer-Datenbank gespeichert!")
                                        log_aktion("Trainer", f"Neu aus Rahmenvertrag: {rv_name}")
                                    else:
                                        st.info(f"ℹ️ {rv_name} ist bereits in der Datenbank.")
                            else:
                                st.error(f"Fehler: {result.get('fehler')}")
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                            log_aktion("Vertrag", str(e), erfolg=False)

        # Nächste Aktion
        if st.session_state.letzte_aktionen and st.session_state.letzte_aktionen[0].get("typ") == "Vertrag" and st.session_state.letzte_aktionen[0].get("erfolg"):
            zeige_naechste_aktion(ausser="📄 Vertrag erstellen")


# ============================================================
# FEEDBACK-LINK
# ============================================================
elif seite == "🔗 Feedback-Link":
    st.markdown("""
    <div class="welcome-header">
        <h2>Feedback-Link erstellen</h2>
        <p>QR-Code und Feedback-Link für eine Schulung generieren.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_feedback"):
        nav_zu("🏠 Start")

    zeige_prefill_hint()

    # Session state für Feedback-Ergebnis
    if "feedback_result" not in st.session_state:
        st.session_state.feedback_result = None

    if not MODULES_LOADED:
        st.error("Module nicht geladen.")
    else:
        with st.form("feedback_form"):
            col1, col2 = st.columns(2)

            with col1:
                schulungsname = st.text_input("Schulungsname*", value=get_ad("schulungsname"))
                trainer = st.text_input("Trainer*", value=get_ad("trainer"))
                kunde = st.text_input("Kunde/Firma*", value=get_ad("kunde") or get_ad("firma_ort"))

            with col2:
                datum_str = get_ad("datum_start")
                try:
                    if datum_str and "." in datum_str:
                        parts = datum_str.split(".")
                        d_val = date(int(parts[2]), int(parts[1]), int(parts[0]))
                    else:
                        d_val = date.today()
                except (ValueError, IndexError):
                    d_val = date.today()
                datum = st.date_input("Schulungsdatum*", value=d_val)

            if st.form_submit_button("🔗 Link erstellen", type="primary", use_container_width=True):
                if not schulungsname.strip() or not trainer.strip() or not kunde.strip():
                    st.error("Schulungsname, Trainer und Kunde sind Pflichtfelder!")
                    st.session_state.feedback_result = None
                else:
                    try:
                        datum_iso = datum.strftime("%Y-%m-%d")

                        if feedback_exists(datum_iso, schulungsname, trainer):
                            st.warning("⚠️ Feedback-Link existiert bereits für diese Schulung!")

                        result = create_feedback(schulungsname, trainer, datum_iso, kunde)

                        if result.get("erfolg"):
                            st.session_state.feedback_result = result
                            log_aktion("Feedback", f"Link: {result.get('link', '')}",
                                details={"schulungsname": schulungsname, "trainer": trainer, "kunde": kunde, "datum": datum_iso},
                                ergebnis={"link": result.get("link", ""), "qr_pfad": result.get("qr_pfad", "")})
                        else:
                            st.error(f"Fehler: {result.get('fehler')}")
                            st.session_state.feedback_result = None
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                        log_aktion("Feedback", str(e), erfolg=False)
                        st.session_state.feedback_result = None

        # QR-Code Anzeige AUSSERHALB des Formulars
        if st.session_state.feedback_result:
            result = st.session_state.feedback_result
            st.success("✅ Feedback-Link erstellt!")
            link = result.get("link", "")
            st.code(link)

            qr_pfad = result.get("qr_pfad", "")
            if qr_pfad and os.path.exists(qr_pfad):
                st.markdown("---")
                st.markdown("**📱 QR-Code:**")
                col_qr1, col_qr2 = st.columns([1, 2])
                with col_qr1:
                    st.image(qr_pfad, width=250)
                with col_qr2:
                    st.markdown(f"""
                    <div class="data-card">
                        <div class="data-label">Gespeichert unter</div>
                        <div class="data-value" style="font-size:0.85rem; word-break:break-all;">{qr_pfad}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    # Download-Button (jetzt AUSSERHALB des Formulars)
                    with open(qr_pfad, "rb") as qr_file:
                        st.download_button(
                            "⬇️ QR-Code herunterladen",
                            data=qr_file.read(),
                            file_name=os.path.basename(qr_pfad),
                            mime="image/png",
                            use_container_width=True
                        )
            elif qr_pfad:
                st.info(f"📱 QR-Code: {qr_pfad}")

            # Reset-Button
            if st.button("🔄 Neuen Link erstellen"):
                st.session_state.feedback_result = None
                st.rerun()

        if st.session_state.letzte_aktionen and st.session_state.letzte_aktionen[0].get("typ") == "Feedback" and st.session_state.letzte_aktionen[0].get("erfolg"):
            zeige_naechste_aktion(ausser="🔗 Feedback-Link")


# ============================================================
# BRIEFING ERSTELLEN (mit KI-Option)
# ============================================================
elif seite == "📧 Briefing erstellen":
    st.markdown("""
    <div class="welcome-header">
        <h2>Briefing erstellen</h2>
        <p>Trainer-Briefing für eine bevorstehende Schulung generieren.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_briefing"):
        nav_zu("🏠 Start")

    zeige_prefill_hint()

    # Session state für generiertes Briefing
    if "briefing_result" not in st.session_state:
        st.session_state.briefing_result = None

    # KI-Status anzeigen
    if KI_AVAILABLE:
        st.markdown("""
        <div style="display:inline-flex; align-items:center; gap:6px; background:rgba(139,92,246,0.1);
            padding:4px 10px; border-radius:6px; margin-bottom:1rem;">
            <span style="color:#a78bfa;">🤖</span>
            <span style="color:#a78bfa; font-size:0.85rem;">KI-Briefing verfügbar</span>
        </div>
        """, unsafe_allow_html=True)

    with st.form("briefing_form"):
        col1, col2 = st.columns(2)

        with col1:
            trainer = st.text_input("Trainer (Vorname)*", value=get_ad("trainer").split()[0] if get_ad("trainer") else "")
            schulungsname = st.text_input("Schulungsname*", value=get_ad("schulungsname"))
            kunde = st.text_input("Kunde/Firma", value=get_ad("kunde") or get_ad("firma_ort"))

        with col2:
            datum_str = get_ad("datum_start")
            datum_display = datum_str if datum_str else date.today().strftime("%d.%m.%Y")
            datum = st.text_input("Datum", value=datum_display)
            uhrzeit = st.text_input("Uhrzeit", value=get_ad("uhrzeit", "09:00 - 17:00"))

            format_opts = ["Vor Ort", "Remote"]
            format_prefill = get_ad("format", "Vor Ort")
            format_idx = 0
            for fi, fo in enumerate(format_opts):
                if fo.lower() == format_prefill.lower():
                    format_idx = fi
                    break
            format_val = st.selectbox("Format", format_opts, index=format_idx)

        ort = st.text_input("Ort / Plattform", value=get_ad("ort", ""))

        # Größeres Hinweise-Feld für KI
        hinweise = st.text_area(
            "Zusätzliche Hinweise / Notizen",
            height=120,
            placeholder="Stichpunkte, Notizen, Besonderheiten...\n\nBeispiel: Kunde erwartet Praxisbeispiele aus Automotive, Trainer soll 15 min früher da sein, Parkplatz knapp"
        )

        # Zwei Buttons: Template oder KI
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            template_btn = st.form_submit_button("📧 Template-Briefing", use_container_width=True)
        with col_btn2:
            ki_btn = st.form_submit_button("🤖 KI-Briefing", type="primary", use_container_width=True)

    # Briefing generieren (außerhalb Form)
    if template_btn or ki_btn:
        if not trainer.strip() or not schulungsname.strip():
            st.error("Trainer und Schulungsname sind Pflichtfelder!")
        else:
            vorname = trainer.strip().split()[0]

            # Ort-Info je nach Format
            if format_val == "Remote":
                ort_info = f"Remote / Online ({ort})" if ort.strip() else "Remote / Online"
            else:
                ort_info = ort.strip() if ort.strip() else "wird noch bekannt gegeben"

            # Betreff
            briefing_betreff = f"Briefing: {schulungsname} am {datum}"
            if kunde.strip():
                briefing_betreff += f" bei {kunde}"

            if ki_btn and KI_AVAILABLE:
                # KI-Briefing generieren
                with st.spinner("🤖 KI generiert Briefing..."):
                    system_prompt = """Du bist ein Assistent für AI-Z / KI Schulungen Stuttgart.
Erstelle professionelle, freundliche Trainer-Briefings auf Deutsch.

Regeln:
- Duze den Trainer
- Schreibe warm aber professionell
- Füge IMMER "[FEEDBACK-LINK]" als Platzhalter ein
- Erwähne den QR-Code für Feedback
- Unterschreibe mit "Ibrahim"
- Erfinde KEINE Informationen - nutze nur die gegebenen Daten
- Baue die zusätzlichen Hinweise elegant ein (nicht als Aufzählung, sondern in den Fließtext)"""

                    user_prompt = f"""Erstelle ein Trainer-Briefing mit diesen Daten:

Trainer: {vorname}
Schulung: {schulungsname}
Datum: {datum}
Uhrzeit: {uhrzeit}
Format: {format_val}
Ort: {ort_info}
Kunde: {kunde if kunde.strip() else "nicht angegeben"}

Zusätzliche Hinweise/Notizen:
{hinweise if hinweise.strip() else "Keine besonderen Hinweise"}

Wichtig: Gib NUR den Briefing-Text aus, keine Erklärungen davor oder danach."""

                    result = ki_call(system_prompt, user_prompt)

                    if result.get("erfolg"):
                        briefing_text = result["text"]
                        st.session_state.briefing_result = {
                            "betreff": briefing_betreff,
                            "text": briefing_text,
                            "vorname": vorname,
                            "schulungsname": schulungsname,
                            "kunde": kunde,
                            "ki_generiert": True
                        }
                    else:
                        st.error(f"KI-Fehler: {result.get('fehler')}")
                        st.info("Verwende stattdessen das Template-Briefing.")
                        ki_btn = False
                        template_btn = True

            if template_btn or (ki_btn and not KI_AVAILABLE):
                # Template-Briefing (wie vorher)
                if ki_btn and not KI_AVAILABLE:
                    st.warning("⚠️ KI nicht verfügbar. ANTHROPIC_API_KEY in .env prüfen.")

                briefing_text = f"""Hallo {vorname},

kurze Info zu deiner bevorstehenden Schulung:

Schulung: {schulungsname}
Datum: {datum}
Uhrzeit: {uhrzeit}
Format: {format_val}
Ort: {ort_info}"""

                if kunde.strip():
                    briefing_text += f"\nKunde: {kunde}"

                if hinweise.strip():
                    briefing_text += f"\n\nHinweise:\n{hinweise}"

                briefing_text += """

Am Ende der Schulung bitte den Teilnehmenden den Feedback-Link teilen:
[FEEDBACK-LINK]

Du bekommst auch einen QR-Code, den du ausdrucken oder auf dem Beamer zeigen kannst.

Bei Fragen melde dich jederzeit.

Beste Grüße
Ibrahim"""

                st.session_state.briefing_result = {
                    "betreff": briefing_betreff,
                    "text": briefing_text,
                    "vorname": vorname,
                    "schulungsname": schulungsname,
                    "kunde": kunde,
                    "ki_generiert": False
                }

    # Briefing anzeigen (außerhalb Form)
    if st.session_state.briefing_result:
        res = st.session_state.briefing_result
        briefing_betreff = res["betreff"]
        vorname = res["vorname"]

        st.markdown("---")

        # KI-Badge wenn KI-generiert
        if res.get("ki_generiert"):
            st.markdown("""
            <div style="display:inline-flex; align-items:center; gap:6px; background:rgba(16,185,129,0.1);
                padding:4px 10px; border-radius:6px; margin-bottom:0.5rem;">
                <span style="color:#10b981;">🤖</span>
                <span style="color:#10b981; font-size:0.85rem;">KI-generiert</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="dark-card">
            <h4>BETREFF</h4>
            <div style="color:#e2e8f0;">{briefing_betreff}</div>
        </div>
        """, unsafe_allow_html=True)

        # Editierbares Textfeld für Briefing
        briefing_text = st.text_area(
            "Briefing-Text (editierbar)",
            value=res["text"],
            height=350,
            key="briefing_edit"
        )

        log_aktion("Briefing", f"Erstellt für {vorname}: {res['schulungsname']}",
            details={"trainer": vorname, "schulungsname": res["schulungsname"], "kunde": res.get("kunde", ""),
                     "ki_generiert": res.get("ki_generiert", False)},
            ergebnis={"betreff": briefing_betreff})

        # Action Buttons
        col_act1, col_act2, col_act3 = st.columns(3)

        with col_act1:
            if st.button("📋 Kopieren", use_container_width=True, key="copy_briefing"):
                st.code(briefing_text)
                st.success("Text oben markieren und kopieren (Cmd+C)")

        with col_act2:
            if st.button("📮 Ab in Outlook", type="primary", use_container_width=True, key="outlook_briefing"):
                try:
                    html_body = briefing_text.replace("\n", "<br>")
                    html_body = html_body.replace("[FEEDBACK-LINK]", "<b>[FEEDBACK-LINK]</b>")
                    html_body = html_body.replace('"', '\\"')

                    applescript = f'''
                    tell application "Microsoft Outlook"
                        set newMsg to make new outgoing message with properties {{subject:"{briefing_betreff}", content:"{html_body}"}}
                        tell newMsg
                            set sender to account "ibrahim@kischulungen.com"
                        end tell
                        open newMsg
                    end tell
                    '''
                    os.system(f"osascript -e '{applescript}'")
                    st.success("✅ Outlook-Entwurf erstellt!")
                    log_aktion("Outlook", f"Briefing-Entwurf für {vorname}",
                        details={"trainer": vorname, "schulungsname": res["schulungsname"]},
                        ergebnis={"betreff": briefing_betreff})
                except Exception as e:
                    st.error(f"Outlook-Fehler: {e}")

        with col_act3:
            if st.button("🔄 Neues Briefing", use_container_width=True, key="reset_briefing"):
                st.session_state.briefing_result = None
                st.rerun()

        # Nächste Aktion
        zeige_naechste_aktion(ausser="📧 Briefing erstellen")


# ============================================================
# TRAINER-DATENBANK
# ============================================================
elif seite == "👥 Trainer-Datenbank":
    st.markdown("""
    <div class="welcome-header">
        <h2>Trainer-Datenbank</h2>
        <p>Trainer aus config.json verwalten.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_trainer"):
        nav_zu("🏠 Start")

    if "edit_trainer_idx" not in st.session_state:
        st.session_state.edit_trainer_idx = None
    if "show_new_trainer" not in st.session_state:
        st.session_state.show_new_trainer = False

    CONFIG_PATH = os.path.join(EXTRAKTOR_PATH, "config.json")

    def lade_config():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def speichere_config(config):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    if not MODULES_LOADED:
        st.error("Module nicht geladen.")
    else:
        try:
            config = lade_config()
            trainer_liste = config.get("bekannte_trainer", [])

            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.subheader(f"📊 {len(trainer_liste)} Trainer")
            with col_h2:
                if st.button("➕ Neuer Trainer", type="primary", use_container_width=True):
                    st.session_state.show_new_trainer = True
                    st.session_state.edit_trainer_idx = None

            # Neuer Trainer
            if st.session_state.show_new_trainer:
                st.markdown("---")
                st.subheader("➕ Neuer Trainer")
                with st.form("new_trainer_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("Name *")
                        new_kurznamen = st.text_input("Kurznamen (kommagetrennt)")
                        new_email = st.text_input("E-Mail")
                        new_telefon = st.text_input("Telefon")
                    with col2:
                        new_strasse = st.text_input("Straße")
                        new_plz = st.text_input("PLZ")
                        new_ort = st.text_input("Ort")

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        save_new = st.form_submit_button("💾 Speichern", type="primary", use_container_width=True)
                    with col_btn2:
                        cancel_new = st.form_submit_button("Abbrechen", use_container_width=True)

                    if save_new and new_name.strip():
                        neuer_trainer = {
                            "name": new_name.strip(),
                            "kurznamen": [k.strip() for k in new_kurznamen.split(",") if k.strip()],
                            "strasse": new_strasse.strip(),
                            "plz": new_plz.strip(),
                            "ort": new_ort.strip(),
                            "email": new_email.strip(),
                            "telefon": new_telefon.strip()
                        }
                        config["bekannte_trainer"].append(neuer_trainer)
                        speichere_config(config)
                        st.session_state.show_new_trainer = False
                        log_aktion("Trainer", f"Neu: {new_name}")
                        st.rerun()
                    elif cancel_new:
                        st.session_state.show_new_trainer = False
                        st.rerun()

            st.markdown("---")

            for i, t in enumerate(trainer_liste):
                if not isinstance(t, dict):
                    continue

                is_editing = st.session_state.edit_trainer_idx == i

                if is_editing:
                    with st.expander(f"✏️ {t.get('name', 'Unbekannt')} — Bearbeiten", expanded=True):
                        with st.form(f"edit_trainer_{i}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                ed_name = st.text_input("Name", value=t.get("name", ""), key=f"ed_name_{i}")
                                ed_kurz = st.text_input("Kurznamen",
                                    value=", ".join(t.get("kurznamen", [])), key=f"ed_kurz_{i}")
                                ed_email = st.text_input("E-Mail", value=t.get("email", ""), key=f"ed_email_{i}")
                                ed_telefon = st.text_input("Telefon", value=t.get("telefon", ""), key=f"ed_tel_{i}")
                            with col2:
                                ed_strasse = st.text_input("Straße", value=t.get("strasse", ""), key=f"ed_str_{i}")
                                ed_plz = st.text_input("PLZ", value=t.get("plz", ""), key=f"ed_plz_{i}")
                                ed_ort = st.text_input("Ort", value=t.get("ort", ""), key=f"ed_ort_{i}")

                            col_b1, col_b2 = st.columns(2)
                            with col_b1:
                                save = st.form_submit_button("💾 Speichern", type="primary", use_container_width=True)
                            with col_b2:
                                cancel = st.form_submit_button("Abbrechen", use_container_width=True)

                            if save:
                                config["bekannte_trainer"][i] = {
                                    "name": ed_name.strip(),
                                    "kurznamen": [k.strip() for k in ed_kurz.split(",") if k.strip()],
                                    "strasse": ed_strasse.strip(),
                                    "plz": ed_plz.strip(),
                                    "ort": ed_ort.strip(),
                                    "email": ed_email.strip(),
                                    "telefon": ed_telefon.strip()
                                }
                                speichere_config(config)
                                st.session_state.edit_trainer_idx = None
                                log_aktion("Trainer", f"Bearbeitet: {ed_name}")
                                st.rerun()
                            elif cancel:
                                st.session_state.edit_trainer_idx = None
                                st.rerun()
                else:
                    with st.expander(f"👤 {t.get('name', 'Unbekannt')}"):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.markdown(f"**Name:** {t.get('name', '-')}")
                            st.markdown(f"**Ort:** {t.get('ort', '-')}")
                            st.markdown(f"**E-Mail:** {t.get('email', '-') or '-'}")
                        with col2:
                            st.markdown(f"**Telefon:** {t.get('telefon', '-') or '-'}")
                            st.markdown(f"**Adresse:** {t.get('strasse', '-')}, {t.get('plz', '')} {t.get('ort', '')}")
                            kurz = ", ".join(t.get("kurznamen", []))
                            st.markdown(f"**Kurznamen:** {kurz or '-'}")
                        with col3:
                            if st.button("✏️ Bearbeiten", key=f"btn_edit_{i}", use_container_width=True):
                                st.session_state.edit_trainer_idx = i
                                st.session_state.show_new_trainer = False
                                st.rerun()

        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")


# ============================================================
# LETZTE AKTIONEN
# ============================================================
elif seite == "📊 Letzte Aktionen":
    st.markdown("""
    <div class="welcome-header">
        <h2>Letzte Aktionen</h2>
        <p>Verlauf der durchgeführten Aktionen in dieser Session.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_aktionen"):
        nav_zu("🏠 Start")

    if st.session_state.letzte_aktionen:
        for idx, aktion in enumerate(st.session_state.letzte_aktionen):
            icon = "✅" if aktion["erfolg"] else "❌"
            typ = aktion.get("typ", "Aktion")
            zeit = aktion.get("zeit", "")
            beschreibung = aktion.get("beschreibung", "")
            details = aktion.get("details", {})
            ergebnis = aktion.get("ergebnis", {})

            # Expander-Titel
            expander_titel = f"{icon} {zeit} — {typ}: {beschreibung[:50]}{'...' if len(beschreibung) > 50 else ''}"

            with st.expander(expander_titel, expanded=(idx == 0)):
                # Details anzeigen (was wurde eingegeben)
                if details:
                    st.markdown("**Verwendete Daten:**")
                    cols_detail = st.columns(2)
                    detail_items = list(details.items())
                    half = (len(detail_items) + 1) // 2
                    for i, (k, v) in enumerate(detail_items):
                        col = cols_detail[0] if i < half else cols_detail[1]
                        with col:
                            if v:
                                st.markdown(f"""
                                <div class="data-card" style="padding:0.5rem 0.8rem; margin:0.2rem 0;">
                                    <div class="data-label" style="font-size:0.7rem;">{k.replace('_', ' ').title()}</div>
                                    <div class="data-value" style="font-size:0.85rem;">{v}</div>
                                </div>
                                """, unsafe_allow_html=True)

                # Ergebnis anzeigen (was wurde erstellt)
                if ergebnis:
                    st.markdown("---")
                    st.markdown("**Ergebnis:**")

                    # Datei-Pfad (Verträge)
                    if ergebnis.get("datei_pfad"):
                        pfad = ergebnis["datei_pfad"]
                        datei = ergebnis.get("datei", os.path.basename(pfad))
                        st.markdown(f"""
                        <div class="data-card" style="padding:0.5rem 0.8rem;">
                            <div class="data-label" style="font-size:0.7rem;">Datei</div>
                            <div class="data-value" style="font-size:0.85rem; word-break:break-all;">{datei}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if os.path.exists(pfad):
                            if st.button(f"📂 Datei öffnen", key=f"open_file_{idx}", use_container_width=True):
                                os.system(f'open "{pfad}"')
                                st.success("Datei wird geöffnet...")

                    # Notion-URL
                    if ergebnis.get("notion_url"):
                        url = ergebnis["notion_url"]
                        st.markdown(f"""
                        <div class="data-card" style="padding:0.5rem 0.8rem;">
                            <div class="data-label" style="font-size:0.7rem;">Notion</div>
                            <div class="data-value" style="font-size:0.85rem;">Eintrag erstellt</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if url:
                            if st.button("🔗 In Notion öffnen", key=f"open_notion_{idx}", use_container_width=True):
                                os.system(f'open "{url}"')

                    # Feedback-Link
                    if ergebnis.get("link"):
                        link = ergebnis["link"]
                        qr_pfad = ergebnis.get("qr_pfad", "")
                        st.markdown(f"""
                        <div class="data-card" style="padding:0.5rem 0.8rem;">
                            <div class="data-label" style="font-size:0.7rem;">Feedback-Link</div>
                            <div class="data-value" style="font-size:0.85rem; word-break:break-all;">{link}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        col_fb1, col_fb2 = st.columns(2)
                        with col_fb1:
                            if st.button("🔗 Link öffnen", key=f"open_link_{idx}", use_container_width=True):
                                os.system(f'open "{link}"')
                        with col_fb2:
                            if qr_pfad and os.path.exists(qr_pfad):
                                if st.button("📱 QR-Code öffnen", key=f"open_qr_{idx}", use_container_width=True):
                                    os.system(f'open "{qr_pfad}"')

                    # Betreff (Briefing/Outlook)
                    if ergebnis.get("betreff") and not ergebnis.get("datei_pfad"):
                        st.markdown(f"""
                        <div class="data-card" style="padding:0.5rem 0.8rem;">
                            <div class="data-label" style="font-size:0.7rem;">Betreff</div>
                            <div class="data-value" style="font-size:0.85rem;">{ergebnis['betreff']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Daten erneut verwenden Button
                if details:
                    st.markdown("---")
                    if st.button("🔄 Daten erneut verwenden", key=f"reuse_{idx}", use_container_width=True):
                        st.session_state.aktuelle_daten = dict(details)
                        st.success("Daten geladen! Du kannst sie jetzt auf anderen Seiten verwenden.")
                        st.rerun()

        st.markdown("---")
        if st.button("🗑️ Verlauf löschen", use_container_width=True):
            st.session_state.letzte_aktionen = []
            st.rerun()
    else:
        st.info("Noch keine Aktionen durchgeführt.")


# ============================================================
# EINSTELLUNGEN
# ============================================================
elif seite == "⚙️ Einstellungen":
    st.markdown("""
    <div class="welcome-header">
        <h2>Einstellungen</h2>
        <p>API-Verbindungen, Pfade, Module und Standard-Werte konfigurieren.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Start", key="back_settings"):
        nav_zu("🏠 Start")

    # --- API-Verbindungen ---
    st.subheader("API-Verbindungen")

    env_path = os.path.expanduser("~/prozess-labor/.env")
    env_vars = {}
    if IS_CLOUD:
        # Cloud: Secrets aus st.secrets lesen
        try:
            env_vars = dict(st.secrets)
        except Exception:
            env_vars = {}
    elif os.path.exists(env_path):
        from dotenv import dotenv_values
        env_vars = dotenv_values(env_path)

    col1, col2 = st.columns(2)

    with col1:
        notion_key = env_vars.get("NOTION_API_KEY", "")
        notion_db = env_vars.get("NOTION_DATABASE_ID", "")
        if notion_key:
            dot_class = "green"
            status_text = f"Verbunden &middot; ...{notion_key[-8:]}"
            db_line = f'<div style="color:#6b6b80; font-size:0.75rem; margin-top:4px;">DB: ...{notion_db[-8:]}</div>' if notion_db else ""
        else:
            dot_class = "red"
            status_text = "NOTION_API_KEY fehlt"
            db_line = ""
        st.markdown(f"""
        <div class="dark-card">
            <h4>Notion API</h4>
            <span class="status-dot {dot_class}"></span>
            <span style="color:#b8c0cc; font-size:0.9rem;">{status_text}</span>
            {db_line}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        supa_url = env_vars.get("SUPABASE_URL", "")
        supa_key = env_vars.get("SUPABASE_KEY", "")
        if supa_url and supa_key:
            dot_class = "green"
            status_text = f"Verbunden &middot; {supa_url.split('//')[1][:20]}..."
        elif supa_url:
            dot_class = "yellow"
            status_text = "URL vorhanden, Key fehlt"
        else:
            dot_class = "red"
            status_text = "SUPABASE_URL fehlt"
        st.markdown(f"""
        <div class="dark-card">
            <h4>Supabase</h4>
            <span class="status-dot {dot_class}"></span>
            <span style="color:#b8c0cc; font-size:0.9rem;">{status_text}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # --- Pfade ---
    st.subheader("Pfade")

    pfade = {
        "Extraktor-Module": EXTRAKTOR_PATH,
        "Feedback-System": FEEDBACK_PATH,
        "config.json": os.path.join(EXTRAKTOR_PATH, "config.json"),
        "Beauftragungsvertrag": os.path.join(EXTRAKTOR_PATH, "vorlagen", "Beauftragungsvertrag_Vorlage.docx"),
        "Rahmenvertrag": os.path.join(EXTRAKTOR_PATH, "vorlagen", "Rahmenvertrag_Vorlage.docx"),
        "Generierte Verträge": os.path.join(EXTRAKTOR_PATH, "vertraege"),
        "QR-Codes & Feedbacks": os.path.expanduser("~/feedbacks"),
        "Environment (.env)": env_path,
    }

    pfad_html = ""
    for label, pfad in pfade.items():
        exists = os.path.exists(pfad)
        dot = "green" if exists else "red"
        pfad_html += f'<div style="padding:0.3rem 0;"><span class="status-dot {dot}"></span> <strong style="color:#c4b5fd;">{label}:</strong> <code style="color:#8b8fa3; background:#111118; padding:2px 6px; border-radius:4px; font-size:0.8rem;">{pfad}</code></div>'

    st.markdown(f'<div class="dark-card">{pfad_html}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- Module-Status ---
    st.subheader("Module-Status")
    if MODULES_LOADED:
        module_info = {
            "SchulungsExtraktor": "Email-Parsing (extraktor.py)",
            "NotionSync": "Notion-Integration (notion_sync.py)",
            "VertragGenerator": "Word-Verträge (vertrag_generator.py)",
            "create_feedback": "Feedback-Links (feedback_integration.py)",
        }
        mod_html = ""
        for modul, beschreibung in module_info.items():
            mod_html += f'<div style="padding:0.25rem 0;"><span class="status-dot green"></span> <code style="color:#c4b5fd; background:#111118; padding:2px 6px; border-radius:4px;">{modul}</code> <span style="color:#8b8fa3;">&mdash; {beschreibung}</span></div>'
        st.markdown(f'<div class="dark-card">{mod_html}</div>', unsafe_allow_html=True)
    else:
        st.error(f"Import-Fehler: {IMPORT_ERROR}")

    st.markdown("---")

    # --- Default-Werte ---
    st.subheader("Standard-Werte")
    st.caption("Diese Werte werden als Vorauswahl in Formularen verwendet.")

    if "defaults" not in st.session_state:
        st.session_state.defaults = {
            "auftraggeber": "GFU Cyrus AG",
            "format": "Vor Ort",
            "reisekosten": "inkl. im Tagessatz",
            "tagessatz": 1500,
            "vorbereitung": 250,
        }

    defaults = st.session_state.defaults

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        defaults["auftraggeber"] = st.selectbox("Standard-Auftraggeber",
            ["GFU Cyrus AG", "NobleProg", "Direkt"],
            index=["GFU Cyrus AG", "NobleProg", "Direkt"].index(defaults.get("auftraggeber", "GFU Cyrus AG")))
        defaults["format"] = st.selectbox("Standard-Format",
            ["Vor Ort", "Remote"],
            index=["Vor Ort", "Remote"].index(defaults.get("format", "Vor Ort")))
    with col_d2:
        defaults["tagessatz"] = st.number_input("Standard-Tagessatz (€)",
            min_value=0, step=100, value=defaults.get("tagessatz", 1500))
        defaults["vorbereitung"] = st.number_input("Standard-Vorbereitung (€)",
            min_value=0, step=50, value=defaults.get("vorbereitung", 250))

    st.session_state.defaults = defaults

    st.markdown("---")

    # --- Debug ---
    st.subheader("Debug")
    if st.checkbox("Session State anzeigen"):
        st.json({
            "aktuelle_daten": st.session_state.aktuelle_daten,
            "letzte_aktionen_count": len(st.session_state.letzte_aktionen),
            "edit_trainer_idx": st.session_state.get("edit_trainer_idx"),
            "defaults": st.session_state.get("defaults", {}),
            "hat_daten": hat_daten()
        })

    if st.button("🗑️ Aktuelle Daten löschen"):
        st.session_state.aktuelle_daten = None
        st.session_state.extrahierte_daten = None
        st.rerun()
