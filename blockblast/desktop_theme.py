"""Complete semantic palettes shared by Qt styles and custom-painted controls."""
from PySide6.QtGui import QPalette,QColor,QFont,QFontDatabase
from pathlib import Path

PALETTES={
'dark':dict(bg='#141820',card='#1D232D',raised='#252D3A',field='#181E28',border='#343E4E',text='#E7ECF5',muted='#9AA8BC',accent='#7C8CFF',accent_hi='#98A4FF',tint='#303A60',danger='#F0808C',danger_bg='#422932',green='#56D8AD',yellow='#EDC566',empty='#252E3C',shadow='#080C14'),
'light':dict(bg='#F4F6F9',card='#FFFFFF',raised='#F0F3FA',field='#F8FAFC',border='#E2E8F0',text='#202C40',muted='#63748C',accent='#5468DC',accent_hi='#687BE8',tint='#E9EDFF',danger='#CA4058',danger_bg='#FFF0F2',green='#148264',yellow='#A57412',empty='#EAF0F7',shadow='#C8D2E1'),
}

def colors(theme='dark'):return PALETTES[theme]

def apply(app,theme='dark'):
    if not app.property('bundledFontsLoaded'):
        for path in sorted((Path(__file__).parent/'assets/fonts').glob('*.ttf')):
            if QFontDatabase.addApplicationFontFromData(path.read_bytes())<0:
                raise RuntimeError('Cannot load interface font: '+path.name)
        app.setFont(QFont('DejaVu Sans'))
        app.setProperty('bundledFontsLoaded',True)
    c=colors(theme);palette=QPalette()
    roles={'Window':'bg','WindowText':'text','Base':'field','AlternateBase':'empty','Text':'text','Button':'card','ButtonText':'text','Highlight':'accent','HighlightedText':None,'Mid':'border','Link':'accent','ToolTipBase':'card','ToolTipText':'text','PlaceholderText':'muted','Light':'card','Dark':'border'}
    for role,key in roles.items():palette.setColor(getattr(QPalette.ColorRole,role),QColor(c[key] if key else '#FFFFFF'))
    for role in (QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText,QPalette.ColorRole.WindowText):palette.setColor(QPalette.ColorGroup.Disabled,role,QColor(c['muted']))
    app.setPalette(palette)
    style='''
QWidget { font-family:"Noto Sans","DejaVu Sans",sans-serif; font-size:12px; color:$text; }
QMainWindow, QWidget#surface, QTabWidget::pane { background:$bg; }
QFrame#header { background:$card; border-bottom:1px solid $border; }
QLabel#brand { font-size:15px; font-weight:700; }
QLabel#sectionTitle { font-size:21px; font-weight:700; }
QLabel#muted { color:$muted; font-size:11px; }
QLabel#sessionStatus { color:$muted; padding:6px 9px; border-radius:6px; }
QLabel#sessionStatus[state="running"] { color:$green; background:$field; }
QLabel#sessionStatus[state="paused"] { color:$yellow; background:$field; }
QLabel#sessionStatus[state="error"] { color:$danger; background:$danger_bg; }
QTextBrowser#eventsView { font-size:13px; }
QLabel#statusBadge { background:$tint; color:$accent; padding:6px 9px; border-radius:6px; }
QLabel#statusBadge[severity="error"] { background:$danger_bg; color:$danger; }
QLabel#metric { font-family:"DejaVu Sans Mono",monospace; font-size:23px; font-weight:700; }
QFrame#statCard { background:$raised; border:1px solid $border; border-radius:10px; }
QFrame#settingsFooter { background:$card; border:1px solid $border; border-radius:10px; }
QLabel#settingsBanner { color:$muted; padding:0 0 4px; }
QWidget#settingRow { background:$raised; border-radius:9px; }
QPushButton, QToolButton { background:$card; border:1px solid $border; border-radius:8px; padding:8px 13px; }
QPushButton:hover, QToolButton:hover { background:$raised; border-color:$accent; }
QPushButton:pressed { background:$tint; }
QPushButton:disabled { color:$muted; background:$field; border-color:$border; }
QPushButton#primary { background:$accent; border-color:$accent; color:#FFFFFF; font-weight:600; }
QPushButton#primary:hover { background:$accent_hi; }
QPushButton#primary:disabled { background:$tint; color:$muted; border-color:$border; }
QPushButton#danger { color:$danger; }
QPushButton#danger:disabled { color:$muted; }
QPushButton#danger:hover, QPushButton#danger:pressed { background:$danger_bg; border-color:$danger; }
QPushButton#navigation { border:0; background:transparent; color:$muted; padding:9px 13px; }
QPushButton#navigation:checked { background:$tint; color:$accent; }
QPushButton#themeButton { padding:8px; }
QPushButton#link:disabled { color:$muted; }
QLineEdit[invalid="true"] { border-color:$danger; }
QLabel#profileInvalid { color:$danger; font-size:11px; }
QLabel#profileValid { color:$green; font-size:11px; }
QPushButton#link { border:0; background:transparent; color:$accent; padding:5px; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background:$field; border:1px solid $border; border-radius:8px; padding:7px 9px; min-height:20px; selection-background-color:$accent; }
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:$accent; }
QComboBox::drop-down { border:0; width:26px; }
QComboBox::down-arrow { image:url("$down_icon"); width:10px; height:9px; }
QSpinBox, QDoubleSpinBox { padding-right:28px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:25px; border:0; margin:3px 3px 0 0; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:25px; border:0; margin:0 3px 3px 0; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image:url("$up_icon"); width:10px; height:9px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image:url("$down_icon"); width:10px; height:9px; }
QComboBox QAbstractItemView { background:$card; color:$text; selection-background-color:$tint; selection-color:$accent; outline:0; }
QGroupBox { background:$card; border:1px solid $border; border-radius:12px; margin:0; padding:38px 14px 12px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left; left:16px; top:13px; }
QLabel { background:transparent; }
QTextBrowser, QPlainTextEdit, QListWidget { background:$card; border:1px solid $border; border-radius:10px; padding:8px; color:$text; selection-background-color:$tint; }
QListWidget { outline:0; }
QListWidget::item { background:$raised; margin:3px 0; padding:13px 12px; border:1px solid transparent; border-radius:8px; }
QListWidget::item:selected { background:$tint; border-color:$accent; color:$accent; }
QListWidget#settingsCategories { background:$card; padding:7px; }
QListWidget#settingsCategories::item { background:transparent; padding:12px 10px; }
QListWidget#settingsCategories::item:selected { background:$tint; }
QTabWidget::pane { border:0; }
QScrollArea { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:transparent; }
QScrollBar:vertical { background:transparent; width:7px; margin:2px; }
QScrollBar::handle:vertical { background:$border; border-radius:3px; min-height:28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QStatusBar { background:$card; border-top:1px solid $border; color:$muted; padding:5px 14px; }
QStatusBar::item { border:0; }
QSplitter::handle { background:transparent; width:12px; }
QToolTip { color:$text; background:$card; border:1px solid $border; padding:7px; }
'''
    for direction in ('up','down'):
        style=style.replace('$'+direction+'_icon',str(Path(__file__).parent/'assets'/f'{direction}-{theme}.svg'))
    for key in sorted(c,key=len,reverse=True):style=style.replace('$'+key,c[key])
    app.setStyleSheet(style)
