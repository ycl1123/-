"""Modern dark theme stylesheet for Brooks Signals."""

# Color palette
BG_DARK = "#0d1117"
BG_CARD = "#161b22"
BG_CARD_HOVER = "#1c2333"
BORDER = "#30363d"
BORDER_ACCENT = "#58a6ff"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#6e7681"
ACCENT_GREEN = "#3fb950"
ACCENT_RED = "#f85149"
ACCENT_BLUE = "#58a6ff"
ACCENT_YELLOW = "#d2991d"
ACCENT_ORANGE = "#f0883e"
ACCENT_TEAL = "#39d353"
BULL = "#26a69a"
BEAR = "#ef5350"

CARD_STYLE = f"""
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px;
"""

GLOBAL_STYLESHEET = f"""
/* === Global === */
QMainWindow {{
    background-color: {BG_DARK};
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}

/* === Scrollbars === */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* === Splitter === */
QSplitter::handle {{
    background: {BORDER};
    margin: 2px;
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

/* === Scroll Area === */
QScrollArea {{
    background: transparent;
    border: none;
}}

/* === Labels === */
QLabel {{
    background: transparent;
    border: none;
}}

/* === Status Bar === */
QStatusBar {{
    background: {BG_CARD};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 12px;
    padding: 4px 12px;
}}

/* === Push Buttons === */
QPushButton {{
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: #2ea043;
}}
QPushButton:pressed {{
    background-color: #196c2e;
}}
QPushButton:disabled {{
    background-color: #1a1a2e;
    color: #555;
    border-color: #333;
}}
QPushButton#danger {{
    background-color: #da3633;
    border-color: #f85149;
}}
QPushButton#danger:hover {{
    background-color: #f85149;
}}
QPushButton#primary {{
    background-color: #1f6feb;
    border-color: #388bfd;
}}
QPushButton#primary:hover {{
    background-color: #388bfd;
}}

/* === Card Frame === */
QFrame#card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px;
}}

/* === Title Label === */
QLabel#cardTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    padding-bottom: 8px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 8px;
}}

/* === Value Labels === */
QLabel#value {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
QLabel#valueBull {{
    font-size: 15px;
    font-weight: 700;
    color: {BULL};
}}
QLabel#valueBear {{
    font-size: 15px;
    font-weight: 700;
    color: {BEAR};
}}
QLabel#metric {{
    font-size: 12px;
    color: {TEXT_SECONDARY};
}}
QLabel#metricValue {{
    font-size: 12px;
    color: {TEXT_PRIMARY};
    font-weight: 500;
}}
QLabel#sectionHeader {{
    font-size: 14px;
    font-weight: 700;
    color: {ACCENT_BLUE};
    padding: 4px 0;
}}
QLabel#header {{
    font-size: 16px;
    font-weight: 800;
    color: {TEXT_PRIMARY};
}}

/* === Alert/Trade signal rows === */
QFrame#signalRow {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
}}
QFrame#signalRow:hover {{
    border-color: {ACCENT_BLUE};
}}
QFrame#alertInfo {{
    border-left: 3px solid {ACCENT_BLUE};
}}
QFrame#alertSignal {{
    border-left: 3px solid {ACCENT_GREEN};
}}
QFrame#alertWarning {{
    border-left: 3px solid {ACCENT_ORANGE};
}}
QFrame#alertDanger {{
    border-left: 3px solid {ACCENT_RED};
}}

/* === Line separator === */
QFrame#separator {{
    background-color: {BORDER};
    max-height: 1px;
}}
"""

def card_title_style(accent_color: str = ACCENT_BLUE) -> str:
    return f"""
        font-size: 13px; font-weight: 700; color: {accent_color};
        padding-bottom: 8px; border-bottom: 1px solid {BORDER};
        margin-bottom: 8px;
    """
